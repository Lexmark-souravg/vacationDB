from lxkintranet.vacationdb.models import VacationAllotment, Holiday, TimeAwayFromWork, VacationSchedule
from decimal import Decimal
from lxkintranet.accounts.models import Profile
from django.core.urlresolvers import reverse
from django.utils.http import urlquote

import json

class UserVacationAggregated:
    """
    A convenient name to represent aggregated vacation schedule for user.
    
    Fields:
    
    days_total      - total vacation days
    days_used       - days used as well as future days that are already approved
    days_pending    - vacation days pending approval
    days_available  - vacation days available
    
    """
    def __init__(self, user, schedule):
        self.user = user
        self.schedule = schedule
        self.days_total = Decimal("0.0")
        self.days_used = Decimal("0.0")
        self.days_pending = Decimal("0.0")
        self.memos = []
        self._pie_data = None
        va = VacationAllotment.objects.filter(user=user, schedule=schedule )
        vr = TimeAwayFromWork.objects.filter(user=user, status__in=['approved','requested'], absence__absence_type__is_vacation=True, schedule=schedule)
        for v in va:
            self.days_total += v.days
            if v.memo:
                self.memos.append(v.memo)
        for v in vr:
            if v.status == "requested":
                self.days_pending += v.days_requested
            else:
                self.days_used += v.days_approved
        #assert False
    @property
    def days_available(self):
        return self.days_total - self.days_used - self.days_pending

    def _int_or_float(self, v):
        iv = int(v)
        if iv == v:
            return iv
        return v

    def _make_data(self):
        fields = ["days_available","days_pending","days_used"]
        colormap = {
            "days_available" : "#32CD32",
            "days_pending" : "#CFCFC4",
            "days_used" : "#4166F5",
        }
        labelmap = {
            "days_available" : "%s\navailable",
            "days_pending" : "%s\npending",
            "days_used" : "%s used",            
        }
        
        slices = []
        
        for field in fields:
            value = getattr(self, field, None)
            if value:
                value = self._int_or_float(value)
                slices.append({
                    "label": labelmap[field] % value,
                    "data": float(value),
                    "color": colormap[field]
                })
        return slices
    
    @property
    def title(self):
        return "Vacation entitlement: %s days" % self._int_or_float(self.days_total)
    @property
    def pie_chart_data(self):
        if not self._pie_data:
            self._pie_data = self._make_data();
        pd = self._pie_data
        return self._pie_data

    @property
    def json_pie_chart_data(self):
        return json.dumps(self.pie_chart_data)
    

def user_vacation_schedules(user, schedule_queryset):
    """
    Returns a list of vacation schedules (UserVacationAggregated) sorted by schedule start date.
    
    Arguments:
    user                - Current user
    schedule_queryset   - Schedule queryset
    """    
    result = []
    for s in schedule_queryset:
        uv = UserVacationAggregated(user, s)
        if uv.days_total:
            result.append(uv)
    return result

def get_my_staff_vacation_schedules(user, **kwargs):
    """
    kwargs the list of keywords that can be applied to TimeAwayFromWork filtering
    """
    my_staff = Profile.filter(manager=user).order_by('user__first_name','user__last_name')

def get_my_staff_vacation_requests(user, **kwargs):
    """
    kwargs the list of keywords that can be applied to TimeAwayFromWork filtering
    """
    return TimeAwayFromWork.objects.select_related('user').filter(
        status='requested',
        user__in = [ p.user.id for p in Profile.objects.filter(manager=user) ]
        )

def get_access(viewed_user_profile, viewing_user_profile):
    """
    Returnes a tuple of Booleans: (view_access, modify_access)
    modify_access refers primarily to vacation requests
    """
    can_view = False
    can_modify = False
    
    if viewed_user_profile.is_under(viewing_user_profile.user):
        can_view = True
        can_modify = True
    elif viewing_user_profile.user.has_perm("vacationdb.change_absence"): # HR can change absences
        can_view = True
        can_modify = True # will be able approve own requests
    elif viewed_user_profile == viewing_user_profile:
        can_view = True
    return (can_view, can_modify)
