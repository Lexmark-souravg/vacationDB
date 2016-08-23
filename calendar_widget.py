from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.contrib.auth.models import SiteProfileNotAvailable
from datetime import date, timedelta
import calendar
#from copy import deepcopy
from lxkintranet.vacationdb.models import Holiday, TimeAwayFromWork

class Day(object):
    def __init__(self, date_obj, is_weekend):
        self.date = date_obj
        self.is_weekend = is_weekend
    def __str__(self):
        return str(self.date_obj)

class UserDay(object):
    def __init__(self, day, timeoff_request = None, holiday = None):
        self.day = day
        self.timeoff_request = timeoff_request
        self.holiday = holiday


class TeamCalendar(object):
    def __init__(self, year, month, weekends=[calendar.SUNDAY, calendar.SATURDAY]):
        # , first_weekday=calendar.SUNDAY, 
        """
        Arguments:
        """
        self.year = year
        self.month = month
        #self.first_weekday = first_weekday
        self.weekends = weekends
        self.last_month_day = calendar.monthrange(self.year, self.month)[1]
        
        # initialize calendar
        self.calendar = [  ]
        for day in range(1, self.last_month_day+1):
            date_obj = date(year, month, day)
            is_weekend = date_obj.weekday() in self.weekends
            self.calendar.append( Day(date_obj, is_weekend) )
        
    def load_users(self, users=[], all_absence_types=False):
        start_date = date(self.year, self.month, 1)
        end_date = date(self.year, self.month, self.last_month_day)
        holidays = Holiday.objects.filter(date__gte=start_date, date__lte=end_date).order_by('date')
        filters = {
            'from_date__lte': end_date,
            'to_date__gte'  : start_date,
            'user__in'      : users,
            'status__in'    : ['requested', 'approved']
        }
        if not all_absence_types:
            filters['absence__absence_type__is_private'] = False
        vacation_requests = TimeAwayFromWork.objects.select_related('absence', 'absence__absence_type').filter(**filters)
        user_calendars = {}
        
        for u in users:
            user_calendars[u.username] = []
            for day in self.calendar:
                user_calendars[u.username].append( UserDay(day) )
        
        # load holidays
        for u in users:
            try:
                profile = u.get_profile()
            except SiteProfileNotAvailable:
                continue
            for holiday in holidays:
                if holiday.country == profile.office_country:
                    if not holiday.region or (holiday.region == profile.office_region):
                        user_calendars[u.username][holiday.date.day-1].holiday = holiday
        
        # load timeoff requests
        delta = timedelta(days=1)
        for vr in vacation_requests:
            # FIXME: there could be 2 half day requests
            the_date = vr.from_date
            # request dates could be outside of this month boundaries
            # if this is the case set it to month boundaries
            if the_date < start_date:
                the_date = start_date
            while the_date <= end_date and the_date <= vr.to_date:
                user_calendars[vr.user.username][the_date.day-1].timeoff_request = vr
                the_date += delta        
        self._user_calendars = user_calendars
        self.users = users
        
    def user_calendars(self):
        class UserCalendar:
            def __init__(self, user, calendar):
                self.user = user
                self.calendar = calendar
        
        class UserCalendarIterator:
            def __init__(self, users, user_calendars):
                self.user_calendars = user_calendars
                self.users = users
                self.index = -1
            def __iter__(self):
                return self
            def next(self):
                self.index = self.index + 1
                if self.index >= len(self.users):
                    raise StopIteration
                return UserCalendar( self.users[self.index], self.user_calendars[self.users[self.index].username] )
        
        return UserCalendarIterator(self.users, self._user_calendars)


