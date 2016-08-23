from decimal import Decimal
from django import forms
from django.db.models import Q
from lxkintranet.vacationdb.models import TimeAwayFromWork, Holiday, Absence
from lxkintranet.jquery.json_utils import JSObject
from lxkintranet.jquery.widgets import jQueryDatePicker
from lxkintranet.widgets import SelectOrHidden
from dateutils import BusinessDelta

class UserVacationBaseForm(forms.ModelForm):
    """
    Required arguments:
        * instance - Caller must pass an instance of TimeAwayFromWork with user and schedule fields
          properly initialized.
        * user_vacation - (keyword argument). An instance of UserVacationAggregated
        * absense_type - (keyword argument). An instance of AbsenceType
    """
    
    def __init__(self, *args, **kwargs):
        assert 'user_vacation' in kwargs
        assert 'absense_type' in kwargs
        #assert self.instance.schedule
        
        self.user_vacation = kwargs['user_vacation']
        self.absense_type = kwargs['absense_type']
        del(kwargs['user_vacation'])
        del(kwargs['absense_type'])
        
        super(UserVacationBaseForm, self).__init__(*args, **kwargs)
        
        self.fields['absence'] = forms.ModelChoiceField (
            label = self.absense_type.name,
            required = True,
            queryset = Absence.objects.filter(absence_type=self.absense_type, is_active=True, absence_type__is_active=True),
            widget = SelectOrHidden()
        )
        if self.absense_type.memo_option == "avoid":
            del(self.fields['memo'])
        else:
            required = self.absense_type.memo_option == "required"
            self.fields['memo'].required = required

class TimeAwayFromWorkForm(UserVacationBaseForm):
    class Meta:
        model = TimeAwayFromWork
        fields = ('from_date','to_date','absence','memo')
        
    def __init__(self, *args, **kwargs):
        super(TimeAwayFromWorkForm, self).__init__(*args, **kwargs)
        self.fields['from_date'].widget = jQueryDatePicker(
            attrs={'size':'10'},
            minDate=self.instance.schedule.from_date,
            maxDate=self.instance.schedule.to_date,
            beforeShowDay=JSObject('$.datepicker.noWeekends'),
        )
        self.fields['to_date'].widget = jQueryDatePicker(
            attrs={'size':'10'},
            minDate=self.instance.schedule.from_date,
            maxDate=self.instance.schedule.to_date,
            beforeShowDay=JSObject('$.datepicker.noWeekends'),
        )
        
    def clean(self):
        if 'from_date' in self.cleaned_data and 'to_date' in self.cleaned_data:
            # start date should not be greater then end date
            if self.cleaned_data['from_date'] > self.cleaned_data['to_date']:
                raise forms.ValidationError("End date must be greater then start date")
            
            # dates must be within schedule range
            if not (self.cleaned_data['from_date']>=self.instance.schedule.from_date and self.cleaned_data['to_date'] <= self.instance.schedule.to_date):
                raise forms.ValidationError("Requested dates are outside of allowed range (%s)"%(unicode(self.instance.schedule)))
            
            # are there other requests in this date range?
            reqs = TimeAwayFromWork.objects.filter(
                user=self.instance.user,
                status__in = ["approved","requested"],
                from_date__lte = self.cleaned_data['to_date'],
                to_date__gte = self.cleaned_data['from_date']
            )
            for r in reqs:
                raise forms.ValidationError("You already have a time away from work request in the interval of %s to %s" % (unicode(self.cleaned_data['from_date']), unicode(self.cleaned_data['to_date'])))
            
            # do we have the right number of days?
            profile = self.instance.user.get_profile()
            holiday_queryset = Holiday.objects.filter(
                Q(date__gte=self.cleaned_data['from_date']),
                Q(date__lte=self.cleaned_data['to_date']),
                Q(country=profile.office_country),
                Q(region=None) | Q(region=profile.office_region)
                )
            holidays = [h.date for h in holiday_queryset ]
            biz_delta = BusinessDelta(self.cleaned_data['from_date'], self.cleaned_data['to_date'], holidays=holidays)
            days_requested = biz_delta.getdays() + 1 # add one because vacation days include boundaries
            if not days_requested:
                raise forms.ValidationError("Your time away from work request spans entirerly over weekends and holidays. Please select a different date range.")
            if self.absense_type == 'vacation':
                if days_requested > self.user_vacation.days_available:
                    raise forms.ValidationError("Vacation days requested (%s) exceed the number of available days (%s)"%(days_requested, self.user_vacation.days_available))
            self.vacation_days_requested = days_requested
            
        return self.cleaned_data
    
    def save(self, *args, **kwargs):
        instance = forms.ModelForm.save(self, commit=False)
        instance.days_requested = self.vacation_days_requested
        instance.days_approved = 0
        instance.status = "requested"
        instance.half_day = ""
        instance.save(*args, **kwargs)
        return instance
    
class HalfDayTimeAwayFromWorkForm(UserVacationBaseForm):
    
    class Meta:
        model = TimeAwayFromWork
        fields = ('from_date','half_day','absence','memo')
    
    def __init__(self, *args, **kwargs):
        super(HalfDayTimeAwayFromWorkForm, self).__init__(*args, **kwargs)
        self.fields['from_date'] = forms.DateField(
            widget = jQueryDatePicker(
                attrs={'size':'10'},
                minDate=self.instance.schedule.from_date,
                maxDate=self.instance.schedule.to_date,
                beforeShowDay=JSObject('$.datepicker.noWeekends'),
            ),
            required=True,
            label="Date", 
        )
        self.fields['half_day'].required = True
        
    def save(self, *args, **kwargs):
        instance = forms.ModelForm.save(self, commit=False)
        instance.to_date = instance.from_date
        instance.days_requested = Decimal('0.5')
        instance.days_approved = 0
        instance.status = "requested"
        instance.save(*args, **kwargs)
        return instance

    def clean(self):
        if 'from_date' in self.cleaned_data and 'half_day' in self.cleaned_data:
            # dates must be within schedule range
            if not (self.cleaned_data['from_date']>=self.instance.schedule.from_date and self.cleaned_data['from_date'] <= self.instance.schedule.to_date):
                raise forms.ValidationError("Requested date is outside of allowed range (%s)"%(unicode(self.instance.schedule)))
            
            # are there other requests in this date range?
            reqs = TimeAwayFromWork.objects.filter(
                user=self.instance.user,
                status__in = ["approved","requested"],
                from_date__lte = self.cleaned_data['from_date'],
                to_date__gte = self.cleaned_data['from_date']
            )
            for r in reqs:
                if not r.half_day or r.half_day == self.cleaned_data['half_day']:
                    raise forms.ValidationError("You already have a time away from work request on %s" % (unicode(self.cleaned_data['from_date'])))
            
            profile = self.instance.user.get_profile()
            holidays = Holiday.objects.filter(
                Q(date=self.cleaned_data['from_date']),
                Q(country=profile.office_country),
                Q(region=None) | Q(region=profile.office_region)
                )
            for h in holidays:
                raise forms.ValidationError("%s is a holiday: %s" % (unicode(self.cleaned_data['from_date']), unicode(h)) )
            
            # do we have the right number of days?
            if self.absense_type == 'vacation' and not self.user_vacation.days_available:
                raise forms.ValidationError("There are no vacation days left")
        return self.cleaned_data
