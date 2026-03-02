from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import LeaveRequest

@receiver(post_save, sender=LeaveRequest)
def leave_request_notification(sender, instance, created, **kwargs):
    """
    Send email notifications for leave requests
    """
    if created:
        # New leave request - notify admin
        send_leave_application_email(instance)
    else:
        # Leave request updated - check if status changed
        if instance.status in ['approved', 'rejected']:
            send_leave_decision_email(instance)


def send_leave_application_email(leave_request):
    """
    Notify admin when new leave request is submitted
    """
    subject = f'New Leave Request from {leave_request.faculty.user.get_full_name()}'
    
    message = f"""
    A new leave request has been submitted:
    
    Faculty: {leave_request.faculty.user.get_full_name()}
    Employee ID: {leave_request.faculty.employee_id}
    Department: {leave_request.faculty.department}
    
    Leave Type: {leave_request.leave_type.name}
    Period: {leave_request.start_date} to {leave_request.end_date}
    Number of Days: {leave_request.number_of_days}
    
    Reason: {leave_request.reason}
    
    Please review this request at your earliest convenience.
    """
    
    # Get admin emails
    from django.contrib.auth.models import User
    admin_emails = list(User.objects.filter(is_staff=True).values_list('email', flat=True))
    admin_emails = [email for email in admin_emails if email]  # Remove empty emails
    
    if admin_emails:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
            recipient_list=admin_emails,
            fail_silently=True,
        )


def send_leave_decision_email(leave_request):
    """
    Notify faculty when their leave request is approved/rejected
    """
    faculty_email = leave_request.faculty.user.email
    
    if not faculty_email:
        return
    
    status_text = 'APPROVED' if leave_request.status == 'approved' else 'REJECTED'
    
    subject = f'Leave Request {status_text}'
    
    message = f"""
    Dear {leave_request.faculty.user.get_full_name()},
    
    Your leave request has been {status_text.lower()}.
    
    Leave Details:
    - Leave Type: {leave_request.leave_type.name}
    - Period: {leave_request.start_date} to {leave_request.end_date}
    - Number of Days: {leave_request.number_of_days}
    
    Reviewed By: {leave_request.reviewed_by.get_full_name() if leave_request.reviewed_by else 'Admin'}
    Reviewed On: {leave_request.reviewed_on}
    """
    
    if leave_request.admin_remarks:
        message += f"\nRemarks: {leave_request.admin_remarks}"
    
    message += "\n\nThank you,\nLeave Management System"
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
        recipient_list=[faculty_email],
        fail_silently=True,
    )