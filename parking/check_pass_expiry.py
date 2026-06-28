from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from parking.models import MonthlyPass
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check for expiring/expired monthly passes and send notifications'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        # ✅ 1. Mark expired passes
        expired_count = MonthlyPass.objects.filter(
            status='active',
            end_date__lt=today
        ).update(status='expired')
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Marked {expired_count} passes as expired')
        )
        
        # ✅ 2. Send 7-day expiry warning
        expiring_soon = MonthlyPass.objects.filter(
            status='active',
            end_date__gte=today,
            end_date__lte=today + timezone.timedelta(days=7)
        ).select_related('user', 'vehicle')
        
        warning_count = 0
        for monthly_pass in expiring_soon:
            days_left = (monthly_pass.end_date - today).days
            
            try:
                send_mail(
                    subject=f'⏰ Monthly Pass Expiring in {days_left} Days',
                    message=f'''
Dear {monthly_pass.user.get_full_name() or monthly_pass.user.username},

Your Monthly Pass is expiring soon!

Pass Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pass Number: {monthly_pass.pass_number}
Vehicle: {monthly_pass.vehicle.license_plate}
Expiry Date: {monthly_pass.end_date.strftime('%d %b %Y')}
Days Remaining: {days_left} days

⚠️ After expiry, regular parking charges will apply.

Renew Now: http://yourwebsite.com/monthly-pass/

Best regards,
Parkease Team
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[monthly_pass.user.email],
                    fail_silently=False,
                )
                warning_count += 1
            except Exception as e:
                logger.error(f"Error sending expiry warning: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Sent {warning_count} expiry warnings')
        )