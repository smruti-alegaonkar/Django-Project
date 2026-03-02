from django.core.management.base import BaseCommand
from django.core.mail import send_mail

class Command(BaseCommand):
    help = 'Send a test email'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Recipient email address')

    def handle(self, *args, **options):
        recipient = options['email']
        
        send_mail(
            subject='Test Email from Leave Management System',
            message='This is a test email. If you receive this, email configuration is working!',
            from_email='noreply@example.com',
            recipient_list=[recipient],
            fail_silently=False,
        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully sent test email to {recipient}'))