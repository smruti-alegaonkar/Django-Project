from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def send_html_email(subject, template_name, context, recipient_list):
    """
    Send HTML email with text fallback
    """
    # Render HTML email
    html_content = render_to_string(f'leaves/emails/{template_name}.html', context)
    text_content = render_to_string(f'leaves/emails/{template_name}.txt', context)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
        to=recipient_list
    )
    
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)