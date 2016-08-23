from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from Lexmark.django.geo.models import Country, Region
from django.utils.translation import ungettext
#from lxkintranet.validators import ascii_alphanumeric

_ = lambda x:x

REQUEST_STATUSES = (
    ('requested',_("Pending Approval")),
    ('approved',_("Approved")),
    ('rejected',_("Rejected")),
    ('cancelled',_("Cancelled by User")),
)

class Holiday(models.Model):
    date = models.DateField(verbose_name=_("holiday date"))
    name = models.CharField(max_length=60, verbose_name=_("holiday name"))
    country = models.ForeignKey(Country, verbose_name=_("contry"))
    region = models.ForeignKey(Region, verbose_name=_("region"), null=True, blank=True, help_text=_("Leave empty if the holiday applies to the whole country"))
 
    def __unicode__(self):
        if self.region:
            return "%s (%s, %s)" % (self.name, self.region.name, self.country.name)
        else:
            return "%s (%s)" % (self.name, self.country.name)

class VacationSchedule(models.Model):
    created_on  = models.DateTimeField(verbose_name=_("created on"), auto_now_add=True, editable=False)
    modified_on = models.DateTimeField(verbose_name=_("modified on"), auto_now=True, editable=False)
    #created_by  = models.ForeignKey(User, verbose_name=_("created by"), related_name="schedule_creators")
    #modified_by = models.ForeignKey(User, verbose_name=_("modified by"), related_name="schedule_modifiers")
    from_date   = models.DateField(verbose_name=_("start date"))
    to_date     = models.DateField(verbose_name=_("end date"))
    memo        = models.TextField(verbose_name=_("memo"), blank=True)
    
    def __unicode__(self):
        return unicode(self.from_date.strftime("%B %d, %Y") + " - " + self.to_date.strftime("%B %d, %Y"))
    

class VacationAllotment(models.Model):
    created_on  = models.DateTimeField(verbose_name=_("created on"), auto_now_add=True, editable=False)
    modified_on = models.DateTimeField(verbose_name=_("modified on"), auto_now=True, editable=False)
    #created_by  = models.ForeignKey(User, verbose_name=_("created by"), related_name="allotment_creators")
    #modified_by = models.ForeignKey(User, verbose_name=_("modified by"), related_name="allotment_modifiers")
    user        = models.ForeignKey(User, verbose_name=_("user"), limit_choices_to={'is_active':True})
    schedule    = models.ForeignKey(VacationSchedule, verbose_name=_("vacation schedule"), limit_choices_to = {'to_date__gte': datetime.now})
    days        = models.DecimalField(max_digits=4, decimal_places=1, verbose_name=_("vacation days"), help_text=_("Only full or half days allowed"))
    memo        = models.TextField(verbose_name=_("memo"), blank=True)

    def get_full_user_name(self):
        return self.user.get_full_name()

class AbsenceType(models.Model):
    NEED_MEMO_VALUES = (
        ('avoid',    _('Not Needed')),
        ('optional', _('Optional')),
        ('required', _('Required')),
    )
    
    key         = models.CharField(
        max_length=20,
        verbose_name=_("keyword"),
        unique=True,
        help_text=_("""Unique key to be used in user-friendly URLs, e.g. "vacation" or "absense". Please use lower case letters and digits only."""),
        #validators=[ascii_alphanumeric]
        )
    name        = models.CharField(max_length=40, verbose_name=_("description"))
    is_active   = models.BooleanField(default=True, verbose_name=_("is active"), help_text=_("Consider deactivating instead of deleting."))
    is_vacation = models.BooleanField(default=False, verbose_name=_("is vacation"), help_text=_("If checked day will be deduced from the vacation schedule."))
    is_private  = models.BooleanField(default=False, verbose_name=_("is private"), help_text=_("If checked absenses of this type will only be visible to authorized staff only (HR and appropriate managers)"))
    memo_option = models.CharField(max_length=20, verbose_name=_("request description"), choices=NEED_MEMO_VALUES, help_text=_("Indicates whether additional description is required when requesting this type of absence"))
    approver    = models.ForeignKey(
        User,
        null=True,
        blank=True,
        verbose_name=_("Copy to"),
        help_text=_("A copy of request will go to the person selected here. Leave empty if absense requests should go only to direct manager."),
        limit_choices_to={'is_active':True},
        )
    icon        = models.ImageField(upload_to="contrib", verbose_name=_("image icon"), help_text=_("Small image (up to 20px x 20px) to represent this absence type."))
    class Meta:
        ordering = ['name']
    
    def __unicode__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.key = self.key.lower()
        super(AbsenceType, self).save(*args, **kwargs)

class Absence(models.Model):
    name        = models.CharField(max_length=40, verbose_name=_("description"))
    is_active   = models.BooleanField(default=True, verbose_name=_("is active"), help_text=_("Consider deactivating instead of deleting."))
    absence_type= models.ForeignKey(AbsenceType, verbose_name=_("absence type"))

    class Meta:
        ordering = ['name']
    
    def __unicode__(self):
        return self.name

class TimeAwayFromWork(models.Model):
    HALF_DAYS = (
        ('am','Morning'),
        ('pm','Afternoon'),
    )
    user            = models.ForeignKey(User, verbose_name=_("user"), related_name="users")
    requestor       = models.ForeignKey(User, verbose_name=_("user"), related_name="requestors")
    backup          = models.ForeignKey(User, verbose_name=_("user"), related_name="backups", null=True)
    absence         = models.ForeignKey(Absence, verbose_name=_("absence type"))
    created_on      = models.DateTimeField(verbose_name=_("created on"), auto_now_add=True, editable=False)
    modified_on     = models.DateTimeField(verbose_name=_("modified on"), auto_now=True, editable=False)
    aproved_by      = models.ForeignKey(User, verbose_name=_("user"), related_name="approvers", null=True)
    schedule        = models.ForeignKey(VacationSchedule, verbose_name=_("vacation schedule"), null=True, blank=True, limit_choices_to = {'to_date__gte': datetime.now})
    from_date       = models.DateField(verbose_name=_("first day away"))
    to_date         = models.DateField(verbose_name=_("last day away"), help_text=_("For single day requests it is the same as first day."))
    days_requested  = models.DecimalField(max_digits=4, decimal_places=1, verbose_name=_("days requested"))
    days_approved   = models.DecimalField(max_digits=4, decimal_places=1, verbose_name=_("days approved"))
    status          = models.CharField(max_length=20, verbose_name=_("status"), choices=REQUEST_STATUSES)
    memo            = models.TextField(verbose_name=_("memo"), blank=True)
    half_day        = models.CharField(max_length=20, verbose_name="Half-day vacation time", blank=True, choices=HALF_DAYS)
    
    def __unicode__(self):
        if self.half_day:
            return _("Half day (%s) on %s") % (self.half_day, self.from_date)
        return ungettext(
            "%(from)s - %(to)s (%(days)d day)",
            "%(from)s - %(to)s (%(days)d days)",
            self.days_requested
            ) % {
                'from':unicode(self.from_date),
                'to'  :unicode(self.to_date),
                'days':self.days_requested
            }
    
    class Meta:
        permissions = (
            ("can_view_all", _("Can view all time away from work requests")),
        )

class TimeAwayFromWorkApprovalLog(models.Model):
    timeoff_request = models.ForeignKey(TimeAwayFromWork, verbose_name=_("time off request"))
    user            = models.ForeignKey(User, verbose_name=_("approver"))
    status          = models.CharField(max_length=20, verbose_name=_("status"), choices=REQUEST_STATUSES, blank=True)
    when_date       = models.DateTimeField(auto_now=True, verbose_name=_("date"), editable=False)
    comment         = models.CharField(max_length=256, verbose_name=_("comment"))
    
    class Meta:
        ordering = ['-id']
    
    def __unicode__(self):
        return self.timeoff_request + u" :: " + self.status
    
