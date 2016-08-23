from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse, HttpResponseForbidden
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import permission_required
from django.template import RequestContext #, Template
from django.db.models import Count
from django.contrib.auth.models import SiteProfileNotAvailable
from django.contrib.auth.models import User
from django.db.models import Q

from lxkintranet.accounts.models import Profile
from lxkintranet.vacationdb.models import VacationAllotment, Holiday, TimeAwayFromWork, VacationSchedule, Absence, AbsenceType, TimeAwayFromWorkApprovalLog
from lxkintranet.vacationdb.utils import user_vacation_schedules, UserVacationAggregated, get_my_staff_vacation_requests, get_access
from lxkintranet.vacationdb.forms import HalfDayTimeAwayFromWorkForm, TimeAwayFromWorkForm
from lxkintranet.vacationdb.notifications import notify_approver, notify_requestor, notify_backup
from lxkintranet.shortcuts import get_paginated_queryset
from lxkintranet.vacationdb.calendar_widget import TeamCalendar
from datetime import date, datetime, timedelta

# shortcuts
def message2response(request, title, message, is_error=True):
    return render_to_response('vacationdb/message.html', {'title':title,'is_error':is_error,'message':message}, context_instance=RequestContext(request))



# homepage
def index(request):
    "Vacation tracker home page."
    schedules = VacationSchedule.objects.filter(to_date__gte = datetime.now())
    my_vacations = user_vacation_schedules(request.user, schedules)
    absense_types = AbsenceType.objects.filter(is_active=True).order_by('-is_vacation','name')
    staff_requests = []
    # staff vacations:
    try:
        profile = request.user.get_profile()
    except SiteProfileNotAvailable:
        return message2response(request, 'Error', 'Your profile does not exist in the system. Please contact HR.')
    if profile.is_manager:
        staff_requests = get_my_staff_vacation_requests(request.user)
    return render_to_response('vacationdb/index.html', { 'my_vacations':my_vacations,'staff_vacation_requests':staff_requests, 'absense_types':absense_types}, context_instance=RequestContext(request))


# holidays
def this_year_holiday_listing(request):
    return holiday_listing(request, date.today().year)
    
def holiday_listing(request, year):
    year = int(year)
    jan1 = date(year, 1, 1) #.strftime("%Y-%m-%d")
    dec31 = date(year, 12, 31)
    holidays = Holiday.objects.filter(date__gte=jan1, date__lte=dec31).select_related().order_by('country__name', 'region__name','date')
    return render_to_response('vacationdb/holiday-listing.html', {'holidays':holidays,'year':year,'prev_year':year-1, 'next_year':year+1}, context_instance=RequestContext(request))






# time off requests
def new_time_off_request(request, type, schedule_id, halfday=False, username=None):
    notify = True
    if halfday:
        form_class = HalfDayTimeAwayFromWorkForm
    else:
        form_class = TimeAwayFromWorkForm
    if username and username != request.user.username:
        user = get_object_or_404(User, username=username)
        try:
            (can_read, can_modify) = get_access(user.get_profile(), request.user.get_profile())
        except SiteProfileNotAvailable:
            return message2response(request, 'Error', 'Profile for user %s does not exist. Please contact HR regarding this problem.'%user)
        if not can_modify:
            return HttpResponseForbidden("You cannot create time away from work requests for user " + username)
        notify = False # do not e-mail for requests placed on behalf of others
    else:
        user = request.user
        
    absence_type = get_object_or_404(AbsenceType, key=type)
    schedule = get_object_or_404(VacationSchedule, id=schedule_id)
    if absence_type.approver:
        manager = absence_type.approver
    else:
        manager = user.get_profile().manager

    vr = TimeAwayFromWork()
    vr.user = user
    vr.requestor = request.user
    vr.schedule = schedule
    
    user_vacation = UserVacationAggregated(request.user, schedule)
    all_resources = User.objects.filter(is_active=True)
    
    if request.method == 'POST':
        backup_person_id = request.POST.get('backup')
        form = form_class(request.POST, instance=vr, user_vacation=user_vacation, absense_type=absence_type)
        if form.is_valid():
            vr = form.save()
            if backup_person_id:
                vr.backup_id = backup_person_id
                vr.save()
            if notify:
                emails = [user.get_profile().manager.email]
                if vr.absence.absence_type.approver:
                    emails.append(vr.absence.absence_type.approver.email)
                notify_approver(emails, vr)
                if backup_person_id:
    		    backup_email = [vr.backup.email]
                    notify_backup(backup_email, vr)
            return HttpResponseRedirect(reverse(vacation_request, args=[vr.id]))
    else:
        form = form_class(instance=vr, user_vacation=user_vacation, absense_type=absence_type)
    return render_to_response('vacationdb/new-vacation-request.html', {
        'form':form,
        'user_vacation':user_vacation,
        'approving_manager':manager,
        'absence_type':absence_type,
        'employee' : user,
        'backups':all_resources,
        }, context_instance=RequestContext(request))


def prepare_for_timeoff_request_by_user(request, username):
    user = get_object_or_404(User, username=username)
    a_date = date.today() - timedelta(days=100) # 100 days ago
    schedules = VacationSchedule.objects.filter(to_date__gte=a_date, vacationallotment__user=user)
    absence_types = AbsenceType.objects.filter(is_active=True)
    return render_to_response('vacationdb/prepare-for-timeoff-request.html', {
        'current_user':user,
        'schedules':schedules,
        'absence_types':absence_types,
        }, context_instance=RequestContext(request))

# undeviewed
def vacation_request(request, vr_id):
    vr = get_object_or_404(TimeAwayFromWork, id=int(vr_id))
    
    can_modify = False
    current_user_profile = request.user.get_profile()
    request_user_profile = vr.user.get_profile()    
    
    (can_view,can_modify) = get_access(request_user_profile, current_user_profile)
    can_cancel = request.user == vr.user and vr.status == "requested"
    
    if vr.status == "cancelled":
        # rationale: to prevent manager from approving by accident a cancelled request
        can_modify = False 
    
    if not can_view:
        return HttpResponseForbidden("You are not authorized to view this vacation request")

    user_vacation = UserVacationAggregated(vr.user, vr.schedule)
    
    if (can_modify or can_cancel) and request.method == "POST":
        # status = request.POST.get('status','')
        # IE 6 cannot handle muptiple <button type="submit"> elements
        # Using input is less convenient since display value is the same as submit value
        # Because of this we need to perform this circus:
        status = ''
        for v in ("approved", "rejected", "cancelled"):
            if v in request.POST:
                status = v
                break
        if status == "approved" and can_modify:
            vr.aproved_by = request.user
            vr.days_approved = vr.days_requested
            vr.status = status
        elif (status == "rejected" and can_modify) or (status == "cancelled" and can_cancel):
            vr.aproved_by = request.user
            vr.days_approved = 0
            vr.status = status
        elif status == "cancelled" and not can_cancel:
            # FIXME: do a nice error message
            return HttpResponseForbidden("This request cannot be cancelled.It must have already been approved or rejected by your manager.")
        else:
            return HttpResponseForbidden("Cannot modify vacation request.")
        vr.save()
        log_rec = TimeAwayFromWorkApprovalLog()
        log_rec.comment = request.POST.get('comment','')
        log_rec.status = vr.status
        log_rec.timeoff_request = vr
        log_rec.user = request.user
        log_rec.save()
        notify_requestor(vr)
        return HttpResponseRedirect(reverse(vacation_request, args=[vr_id]))
    request_log = TimeAwayFromWorkApprovalLog.objects.filter(timeoff_request=vr)
    return render_to_response('vacationdb/vacation-request.html', {'vacation_request':vr,'user_vacation':user_vacation,'can_modify':can_modify, 'can_cancel':can_cancel, 'request_log':request_log}, context_instance=RequestContext(request))
    
def vacation_requests(request, user_name=None):
    if user_name:
        user = get_object_or_404(User, username=user_name)
    else:
        user = request.user
    (can_view, can_modify) = get_access(user.get_profile(), request.user.get_profile())
    if not can_view:
        return HttpResponseForbidden("You are not authorized to view this vacation request")
    reqs = TimeAwayFromWork.objects.select_related('absence','absence__absence_type').filter(user=user).order_by('-id')
    req_page = get_paginated_queryset(reqs, request.GET.get('page', '1'))

    return render_to_response('vacationdb/vacation-requests.html', {'viewed_user':user,'paginated_objects':req_page}, context_instance=RequestContext(request))

def my_staff(request, user_name=None):
    manager = None
    if user_name:
        manager = get_object_or_404(User, username=user_name)
        (can_view, can_modify) = get_access(manager.get_profile(), request.user.get_profile())
        if not can_view:
            return HttpResponseForbidden()
        profiles = Profile.objects.select_related('user').filter(manager=manager,user__is_active=True).order_by('user__first_name', 'user__last_name')
    else:
        profiles = Profile.objects.select_related('user').filter(manager=request.user, user__is_active=True).order_by('user__first_name', 'user__last_name')
    return render_to_response('vacationdb/my-staff.html', {'profiles':profiles, 'manager':manager}, context_instance=RequestContext(request))

def my_approved_leaves(request, user_name=None):
    manager = None
    name = None
    from_date = 'Start Date'
    to_date = 'End Date'
    exclude_absence_type_id = 15
    if user_name:
        manager = get_object_or_404(User, username=user_name)
        (can_view, can_modify) = get_access(manager.get_profile(), request.user.get_profile())
        if not can_view:
            return HttpResponseForbidden()
        #profiles = Profile.objects.select_related('user').filter(manager=manager,user__is_active=True).order_by('user__first_name', 'user__last_name')
        leaves = TimeAwayFromWork.objects.filter(status='approved').filter(aproved_by_id=request.user.id)
    else:
        name = request.user.first_name
        #profiles = Profile.objects.select_related('user').filter(manager=request.user, user__is_active=True).order_by('user__first_name', 'user__last_name')
        leaves = TimeAwayFromWork.objects.filter(status='approved').filter(aproved_by_id=request.user.id).exclude(absence__id=exclude_absence_type_id).order_by('-from_date')
    profiles = []
#    for leave in leaves:
#        prof = Profile.objects.get(user_id=leave.requestor_id)
#        profiles.append(prof)    
    if request.method == 'POST':
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        leaves = leaves.filter(from_date__gte=from_date, to_date__lte=to_date)
    for leave in leaves:
        prof = Profile.objects.get(user_id=leave.requestor_id)
        profiles.append(prof)
    emp_n_page = get_paginated_queryset(profiles, request.GET.get('page', '1'))
    req_page = get_paginated_queryset(leaves, request.GET.get('page', '1'))
    return render_to_response('vacationdb/approved-leaves.html', {'paginated_profiles':emp_n_page, 'fdate':from_date, 'tdate':to_date, 'manager':manager, 'paginated_objects':req_page, 'fname':name}, context_instance=RequestContext(request))

def staff_sickdays(request):
    profiles = []
    from_date = 'Start Date'
    to_date = 'End Date'
    sickdays = TimeAwayFromWork.objects.filter(status='approved').filter(Q(absence__id=1) | Q(absence__id=20)).order_by('-from_date')
    if request.method == 'POST':
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        sickdays = sickdays.filter(from_date__gte=from_date, to_date__lte=to_date)
    for sickday in sickdays:
        profile = Profile.objects.get(user_id=sickday.requestor_id)
        profiles.append(profile)
    req_profiles = get_paginated_queryset(profiles, request.GET.get('page', '1'))
    req_page = get_paginated_queryset(sickdays, request.GET.get('page', '1')) 
    return render_to_response('vacationdb/staff-sickdays.html', {'paginated_profiles': req_profiles, 'paginated_objects':req_page, 'fdate':from_date, 'tdate':to_date}, context_instance=RequestContext(request))

def employee_search(request):
    query_string = request.GET.get('q','')
    users = None
    if query_string:
        terms = query_string.split()
        users = User.objects.all()
        for term in terms:
            users = users.filter(Q(username__istartswith=term) | Q(first_name__istartswith=term) | Q(last_name__istartswith=term))
    return render_to_response('vacationdb/employee-search.html', {'users_found':users, 'search_string':query_string}, context_instance=RequestContext(request))        

def employee_calendar(request, user_profiles, html_title, view_name, year=None, month=None, extra_arg=None, all_absence_types=False):
    """
    show_all - enables viewing all absense requests
    """
    if year and month:
        year = int(year)
        month = int(month)
        curr_month = date(year, month, 1)
    else:
        curr_month = date.today()
        year = curr_month.year
        month = curr_month.month
    if month == 12:
        next_month = date(year+1, 1, 1)
    else:
        next_month = date(year, month+1, 1)
    if month == 1:
        prev_month = date(year-1, 12, 1)
    else:
        prev_month = date(year, month-1, 1)
    users = []
    user_profiles = user_profiles.order_by('user__first_name','user__last_name')
    for p in user_profiles:
        users.append(p.user)
    if not all_absence_types and request.user.has_perm("vacationdb.change_vacationrequest"):
        all_absence_types = True # upgrade access for HR admins
    tc = TeamCalendar(year, month)
    tc.load_users(users, all_absence_types=all_absence_types)
    if extra_arg:
        prev_url = reverse(view_name, args=[extra_arg, prev_month.year, prev_month.month] )
        next_url = reverse(view_name, args=[extra_arg, next_month.year, next_month.month] )
    else:
        prev_url = reverse(view_name, args=[prev_month.year, prev_month.month] )
        next_url = reverse(view_name, args=[next_month.year, next_month.month] )
    return render_to_response('vacationdb/calendar.html', {'vacation_calendar':tc, 'title':html_title, 'curr_month':curr_month, 'next_month':next_month, 'prev_url':prev_url, 'prev_month':prev_month, 'next_url':next_url, 'view_name':view_name}, context_instance=RequestContext(request))
    
def team_calendar(request, year=None, month=None):
    """ Team is all people who have the same manager as current user. """
    manager = request.user.get_profile().manager
    if not manager:
        return message2response(request, 'Error', 'Cannot determine your team')
    user_profiles = Profile.objects.filter( Q(manager=manager) | Q(user=manager), Q(user__is_active=True))
    return employee_calendar(request, user_profiles, "Team Calendar", 'lxkintranet.vacationdb.views.team_calendar', year, month)

def my_staff_calendar(request, year=None, month=None):
    """ Staff is all people reporting to current user. """
    user_profiles = Profile.objects.filter( Q(manager=request.user)|Q(user=request.user), Q(user__is_active=True) )
    return employee_calendar(request, user_profiles, "Staff Calendar", 'lxkintranet.vacationdb.views.my_staff_calendar', year, month, all_absence_types=True)

@permission_required("vacationdb.can_view_all")
def list_locations(request):
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT c.id, c.name, p.location FROM accounts_profile p, geo_country c WHERE c.id=p.office_country_id AND p.location <> '' ORDER BY c.name, p.location")
    rows = cursor.fetchall()
    return render_to_response('vacationdb/list-locations.html', {'locations':rows}, context_instance=RequestContext(request))
    
# @permission_required(?)
def location_calendar(request, location, year=None, month=None):
    """ Calendar by Location """
    user_profiles = Profile.objects.filter( location=location, user__is_active=True )
    return employee_calendar(request, user_profiles, "Calendar for %s"%location, 'lxkintranet.vacationdb.views.location_calendar', year, month, location, all_absence_types=True)

    
def staff_calendar(request, username, year=None, month=None):
    """ Staff is all people reporting to user identified by username. """
    user = get_object_or_404(User, username=username)
    profile = user.get_profile()
    (can_view, can_modify) = get_access(profile, request.user.get_profile())
    if not can_view:
        return HttpResponseForbidden("You cannot view the team of %s" % user.get_full_name())
    user_profiles = Profile.objects.filter( Q(manager=user) | Q(user=user), Q(user__is_active=True) )
    return employee_calendar(request, user_profiles, "Staff Calendar for %s"%user.get_full_name(), 'lxkintranet.vacationdb.views.staff_calendar', year, month, username, all_absence_types=can_modify)


def user_vacation_summary(request, username=None):
    if username:
        user = get_object_or_404(User, username=username)
        (can_view, can_modify) = get_access(user.get_profile(), request.user.get_profile())
        if not can_view:
            return HttpResponseForbidden()
    else:
        user = request.user
    vas = VacationAllotment.objects.filter(user=user).order_by('-schedule__from_date')
    vacations = []
    seen = set()
    for va in vas:
        if not (va.schedule.id in seen): # can have multiple entitlements in the same allotment
            seen.add( va.schedule.id )
            vacations.append( UserVacationAggregated(user, va.schedule) )
    return render_to_response('vacationdb/user-vacations.html', {'vacations':vacations, 'current_user':user }, context_instance=RequestContext(request))




@permission_required('vacationdb.add_holiday') # only hr admins can add holidays
def vacation_usage(request, schedule_id=None):
    import csv
    import re
    
    if not schedule_id:
        schedules = VacationSchedule.objects.all().order_by('-id')
        return render_to_response("vacationdb/usage-by-schedule.html",
                                  {'schedules':schedules},
                                  context_instance=RequestContext(request))
    
    schedule = get_object_or_404(VacationSchedule, id=int(schedule_id))
    
    allotments = VacationAllotment.objects.select_related('user').filter(schedule=schedule)
    
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=' + re.sub('\W+','-', unicode(schedule)) + ".csv"
    
    writer = csv.writer(response)
    writer.writerow(["Employee name", "Is active", "Email", "Total days",
                     "Used days", "Pending days", "Available days"])
    
    for allotment in allotments:
        summary = UserVacationAggregated(allotment.user, schedule)
        writer.writerow(
            [unicode(x) for x in [allotment.user.get_full_name(), allotment.user.is_active,
                                  allotment.user.email, summary.days_total,
                                  summary.days_used, summary.days_pending,
                                  summary.days_available]
            ]
        )
    
    return response
