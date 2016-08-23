from lxkintranet.vacationdb.models import Holiday, VacationAllotment, VacationSchedule, AbsenceType, Absence
from django.contrib import admin

class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name','date','country','region')
    date_hierarchy = 'date'

class VacationAllotmentAdmin(admin.ModelAdmin):
    list_display = ('user','schedule','days','memo')
    search_fields = ('^user__first_name','^user__last_name','^user__username')

class VacationScheduleAdmin(admin.ModelAdmin):
    list_display = ('__unicode__',) # ('from_date','to_date',)

class AbsenceTypeAdmin(admin.ModelAdmin):
    list_display = ('key','name','is_active', 'is_vacation', 'is_private', 'memo_option', 'approver')

class AbsenceAdmin(admin.ModelAdmin):
    list_display = ('name','is_active','absence_type',)

admin.site.register(Holiday, HolidayAdmin)
admin.site.register(VacationSchedule, VacationScheduleAdmin)
admin.site.register(VacationAllotment, VacationAllotmentAdmin)
admin.site.register(AbsenceType, AbsenceTypeAdmin)
admin.site.register(Absence, AbsenceAdmin)





