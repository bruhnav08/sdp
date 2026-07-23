"""
booking/tasks.py
-----------------
Celery tasks for the booking module.

In dev/demo mode (CELERY_TASK_ALWAYS_EAGER=True), tasks execute
synchronously inline — no worker or Redis needed.  To switch to real
async execution, set CELERY_TASK_ALWAYS_EAGER=False and start a worker:

    celery -A config worker -l info
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation_email(self, booking_pk: int) -> str:
    """
    Send a booking confirmation email to the requestor (and CC the
    faculty in-charge if they are a different person).

    Args:
        booking_pk: Primary key of the BookingRequest to notify about.

    Returns:
        A status string describing what was sent.
    """
    try:
        # Import inside task to avoid circular imports at module load time
        from booking.models import BookingRequest

        booking = BookingRequest.objects.select_related("requestor").get(pk=booking_pk)
        requestor = booking.requestor

        subject = f"[HSRS] Booking Request Submitted — {booking.booking_id}"
        message = (
            f"Dear {requestor.get_full_name() or requestor.username},\n\n"
            f"Your guest room booking request has been successfully submitted.\n\n"
            f"Booking ID  : {booking.booking_id}\n"
            f"Status      : {booking.get_status_display()}\n"
            f"Purpose     : {booking.purpose_of_booking}\n"
            f"Guests      : {booking.total_guests} "
            f"({booking.num_guests_male}M / {booking.num_guests_female}F)\n"
            f"Rooms needed: {booking.num_rooms_required}\n\n"
            f"Your request is now with the HOD / Director for initial approval.\n"
            f"You will receive further updates as the booking progresses.\n\n"
            f"--- HSRS Guest Room Booking System ---\n"
        )

        recipients = [requestor.email]

        # CC the faculty in-charge if they are a different person
        if not booking.is_faculty_incharge and booking.incharge_email:
            recipients.append(booking.incharge_email)

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )

        return f"Confirmation email sent for booking {booking.booking_id} to {recipients}"

    except Exception as exc:
        # Retry on failure (e.g. SMTP hiccup) up to max_retries times
        raise self.retry(exc=exc)


@shared_task(bind=True)
def send_status_update_email(self, booking_pk: int, new_status: str) -> str:
    """
    Notify the requestor when their booking status changes.
    Called by approval/rejection workflow views (built in future sprints).
    """
    try:
        from booking.models import BookingRequest

        booking = BookingRequest.objects.select_related("requestor").get(pk=booking_pk)
        requestor = booking.requestor

        subject = f"[HSRS] Booking {booking.booking_id} — Status Update"
        message = (
            f"Dear {requestor.get_full_name() or requestor.username},\n\n"
            f"Your booking request status has been updated.\n\n"
            f"Booking ID : {booking.booking_id}\n"
            f"New Status : {booking.get_status_display()}\n\n"
        )

        if booking.status == BookingRequest.Status.REJECTED:
            message += f"Reason for rejection: {booking.rejection_reason or 'Not specified'}\n\n"
        elif booking.status == BookingRequest.Status.CONFIRMED:
            message += "Congratulations! Your booking has been fully approved and confirmed.\n\n"

        message += "--- HSRS Guest Room Booking System ---\n"

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[requestor.email],
            fail_silently=False,
        )

        return f"Status update email sent for {booking.booking_id}"

    except Exception as exc:
        raise self.retry(exc=exc)
