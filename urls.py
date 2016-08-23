#from lxkintranet.vacationdb.forms import HolidayForm
from lxkintranet.vacationdb.forms import TimeAwayFromWorkForm
from django.conf.urls.defaults import *

#from django.contrib import admin
#admin.autodiscover()

urlpatterns = patterns('',
    (r'^$', 'lxkintranet.vacationdb.views.index'),
    
    (r'^holidays/$', 'lxkintranet.vacationdb.views.this_year_holiday_listing'),
    (r'^holidays/(\d\d\d\d)/$', 'lxkintranet.vacationdb.views.holiday_listing'),
    
    url(r'^new-time-away-request/(?P<type>\w+)/schedule-(?P<schedule_id>\d+)/$', 'lxkintranet.vacationdb.views.new_time_off_request', name='fullday_time_off'),
    url(r'^new-time-away-request/(?P<type>\w+)/schedule-(?P<schedule_id>\d+)/(?P<username>\w+)/$', 'lxkintranet.vacationdb.views.new_time_off_request', name='fullday_time_off'),

    (r'^new-halfday-time-away-request/(?P<type>\w+)/schedule-(?P<schedule_id>\d+)/$', 'lxkintranet.vacationdb.views.new_time_off_request', {'halfday':True}, 'halfday_time_off'),
    (r'^new-halfday-time-away-request/(?P<type>\w+)/schedule-(?P<schedule_id>\d+)/(?P<username>\w+)/$', 'lxkintranet.vacationdb.views.new_time_off_request', {'halfday':True}, 'halfday_time_off'),
    
    (r'^new-time-away-request/(?P<username>\w+)/$', 'lxkintranet.vacationdb.views.prepare_for_timeoff_request_by_user'),
    
    (r'^vacation-request/(\d+)/$', 'lxkintranet.vacationdb.views.vacation_request'),
    
    (r'^my-vacation-requests/$', 'lxkintranet.vacationdb.views.vacation_requests'),
    (r'^vacation-requests/(\w+)/$', 'lxkintranet.vacationdb.views.vacation_requests'),
    (r'^vacation-summary/(\w+)/$', 'lxkintranet.vacationdb.views.user_vacation_summary'),
    (r'^vacation-summary/$', 'lxkintranet.vacationdb.views.user_vacation_summary'),
    (r'^vacation-usage/$', 'lxkintranet.vacationdb.views.vacation_usage'),
    (r'^vacation-usage/(\d+)/$', 'lxkintranet.vacationdb.views.vacation_usage'),
    (r'^staff-sick-days/$', 'lxkintranet.vacationdb.views.staff_sickdays'),
    
    (r'^my-staff/$', 'lxkintranet.vacationdb.views.my_staff'),
    (r'^my-approved-leaves/$', 'lxkintranet.vacationdb.views.my_approved_leaves'),
    (r'^staff/(\w+)/$', 'lxkintranet.vacationdb.views.my_staff'),
    
    (r'^my-team-calendar/$', 'lxkintranet.vacationdb.views.team_calendar'),
    (r'^my-team-calendar/(\d\d\d\d)/(\d\d?)/$', 'lxkintranet.vacationdb.views.team_calendar'),
    (r'^my-staff-calendar/$', 'lxkintranet.vacationdb.views.my_staff_calendar'),
    (r'^my-staff-calendar/(\d\d\d\d)/(\d\d?)/$', 'lxkintranet.vacationdb.views.my_staff_calendar'),
    (r'^staff-calendar/(\w+)/$', 'lxkintranet.vacationdb.views.staff_calendar'),
    (r'^staff-calendar/(\w+)/(\d\d\d\d)/(\d\d?)/$', 'lxkintranet.vacationdb.views.staff_calendar'),
    
    (r'^search/$', 'lxkintranet.vacationdb.views.employee_search'),
    
    (r'^location-calendar/$', 'lxkintranet.vacationdb.views.list_locations'),
    (r'^location-calendar/([^/]+)/$', 'lxkintranet.vacationdb.views.location_calendar'),
    (r'^location-calendar/([^/]+)/(\d\d\d\d)/(\d\d?)/$', 'lxkintranet.vacationdb.views.location_calendar'),
    
)
