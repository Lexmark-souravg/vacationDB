from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from datetime import date, timedelta
import calendar
from copy import deepcopy
from lxkintranet.vacationdb.models import Holiday, TimeAwayFromWork

class DayInfo(object):
    def __init__(self, daytype="", extra="", html=''):
        #assert daytype in ("","holiday","weekend","vacation approved","vacation pending")
        self.daytype = daytype
        self.extra = extra
        self.html = html
    def __str__(self):
        return self.daytype

class VacationCalendar(object):
    def __init__(self, year, month, users=[], all_absence_types=False, first_weekday=calendar.SUNDAY, weekends=[calendar.SUNDAY, calendar.SATURDAY]):
        """
        Arguments:
        start_date
        end_date   - start/end dates (day value will be reset to the first/last months respectively)
        users      - an iterable consisting of instances of User objects for which we display vacation schedules
        """
        #self.start_date = start_date.replace(day=1)
        #self.end_date = end_date.replace( day=calendar.monthrange(end_date.year, end_date.month)[1] )
        self.year = year
        self.month = month
        self.users = users
        self.first_weekday = first_weekday
        self.weekends = weekends
        self.all_absence_types = all_absence_types
        
    def _load(self):
        month_start_date = date( self.year, self.month, 1 )
        month_end_date = date( self.year, self.month, calendar.monthrange(self.year, self.month)[1] )
        
        holidays = Holiday.objects.filter(date__gte=month_start_date, date__lte=month_end_date).order_by('date')
        filters = {
            'from_date__lte': month_end_date,                                                         
            'to_date__gte'  : month_start_date,
            'user__in'      : self.users,
            'status__in'    : ['requested', 'approved']
        }
        if not self.all_absence_types:
            filters['absence__absence_type__is_private'] = False
        vacation_requests = TimeAwayFromWork.objects.select_related('absence', 'absence__absence_type').filter(**filters)
        user_calendars = {}
        calendar.setfirstweekday(self.first_weekday)
        week = [0,1,2,3,4,5,6]
        self.week_ordered = week[self.first_weekday:] + week[:self.first_weekday]
        moncal = calendar.monthcalendar(self.year, self.month)
        week_offset = 0;
        for d in moncal[0]:
            if d ==0:
                week_offset += 1
            else:
                break
        offsets = make_offset_calculator(week_offset)
        profiles = {}
        
        default_week = []
        for day in self.week_ordered:
            if day in self.weekends:
                di = DayInfo("weekend")
            else:
                di = DayInfo()
            default_week.append(di)
        #assert False
        for u in self.users:
            user_calendars[u.username] = []
            profiles[u.username] = u.get_profile()
            for week in moncal:
                user_calendars[u.username].append( deepcopy(default_week) )
        
        # fixme: it is better to to hashing for user holidays and vacations
        for holiday in holidays:
            for u in self.users:
                if holiday.country == profiles[u.username].office_country:
                    if not holiday.region or (holiday.region == profiles[u.username].office_region):
                        (w,d) = offsets(holiday.date.day)
                        user_calendars[u.username][w][d] = DayInfo("holiday", unicode(holiday))
        for vr in vacation_requests:
            key = vr.user.username
            (w,d) = offsets(vr.from_date.day)
            description = unicode(vr)
            delta = timedelta(days=1)
            if vr.half_day:
                if user_calendars[key][w][d].extra: # there is already another vacation
                    user_calendars[key][w][d].extra += ", " + description
                    user_calendars[key][w][d].daytype += " " + vr.half_day # fixme: need something like "approved_am" "pending_pm"
                else:
                    user_calendars[key][w][d] = DayInfo("vacation " + vr.status + " " + vr.half_day, description)
                user_calendars[key][w][d].html = '<img src="%s" alt="%s" />' % (vr.absence.absence_type.icon.url, vr.absence.absence_type.name)
            else:
                the_date = vr.from_date
                while the_date <= month_end_date and the_date <= vr.to_date:
                    (w,d) = offsets(the_date.day)
                    if user_calendars[key][w][d].daytype == "":
                        user_calendars[key][w][d] = DayInfo("vacation " + vr.status, description)
                    the_date += delta
        
        self.monthcalendar = moncal
        self.user_calendars = user_calendars
        self.profiles = profiles
        
    def render(self):
        """ Renders calendar as HTML. """
        self._load()
        weekday_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        header = '<tr><th></th>'
        user_rows = {}
        for key in self.user_calendars.keys():
            if self.profiles[key].is_manager:
                user_rows[key] = '<tr><th class="person"><a href="%s" title="View staff calendar">%s</a></th>' % (
                    reverse('lxkintranet.vacationdb.views.staff_calendar', args=[self.profiles[key].user.username]),
                    self.profiles[key].user.get_full_name()
                )
            else:
                user_rows[key] = '<tr><th class="person">%s</th>' % self.profiles[key].user.get_full_name()
        w = 0
        for week in self.monthcalendar:
            d = 0
            for day in week:
                if day == 0:
                    d += 1
                    continue
                    #html_class = "inactive"
                    #header += '<th class="%s"><span class="day"></span><span class="weekday">%s</span></th>' % (html_class, weekday_names[ self.week_ordered[d] ])
                html_class = ""
                if self.week_ordered[d] in self.weekends:
                    html_class = "weekend"
                header += '<th class="day %s"><span class="day">%d</span><span class="weekday">%s</span></th>' % (html_class, day, weekday_names[ self.week_ordered[d] ])
                for key in self.user_calendars.keys():
                    user_html_class = html_class
                    if user_html_class == "":
                        user_html_class = self.user_calendars[key][w][d].daytype
                    user_rows[key] += '<td class="day %s" title="%s">%s</td>' % (user_html_class, self.user_calendars[key][w][d].extra, self.user_calendars[key][w][d].html)
                d += 1
            w += 1
        buffer = '<table class="calendar"><thead>' + header + '</tr></thead><tbody>'
        for key in user_rows.keys():
            buffer += user_rows[key] + '</tr>'
        buffer += '</tbody></table>'
        #assert False
        return mark_safe(buffer)
        
def make_offset_calculator(week_offset):
    """ Utility function returning a tuple of (week index and day index) to find day position in
    the list of lists returned by monthcalendar
    """
    def _inner(day):
        weeki = (week_offset + day) / 7
        dayi = (week_offset + day - 1) % 7 # days start from one but index starts from zero
        return (weeki, dayi)
    return _inner
