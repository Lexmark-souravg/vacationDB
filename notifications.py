from django.template.loader import get_template
from django.template import Context
from django.core.mail import EmailMessage
from lxkintranet.vacationdb import appsettings

def notify_approver(to_emails, vacation_request):
    t = get_template("vacationdb/mail-vacation-request.html")
    content = t.render(Context({'vacation_request':vacation_request}))
    subject = vacation_request.absence.absence_type.name + u" Request for %s" % vacation_request.user.get_full_name()
    msg = EmailMessage(subject, content, appsettings.return_email_addres, to_emails)
    msg.content_subtype = "html"  # Main content is now text/html
    msg.send()

def notify_backup(to_emails, vacation_request):
    t = get_template("vacationdb/mail-vacation-request-backup.html")
    content = t.render(Context({'vacation_request':vacation_request}))
    subject = "You're assigned as Backup Resource for %s" % vacation_request.user.get_full_name()
    msg = EmailMessage(subject, content, appsettings.return_email_addres, to_emails)
    msg.content_subtype = "html"  # Main content is now text/html
    msg.send()

def notify_requestor(vacation_request):
    exclude_absence_id = [15, 16]
    additional_emails = ['kweaver@lexmark.com']
    t = get_template("vacationdb/mail-vacation-request-modified.html")
    content = t.render(Context({'vacation_request':vacation_request}))
    subject = vacation_request.absence.absence_type.name + " Request " + vacation_request.status
    emails = [vacation_request.user.email,vacation_request.aproved_by.email]
    if vacation_request.absence_id not in exclude_absence_id:
        emails.extend(additional_emails)
    msg = EmailMessage(subject, content, appsettings.return_email_addres, emails)
    msg.content_subtype = "html"  # Main content is now text/html
    msg.send()
