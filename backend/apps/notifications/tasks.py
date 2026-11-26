import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage, send_mail

from .models import EmailLog

logger = logging.getLogger(__name__)


@shared_task(name="notifications.send_booking_confirmation_email")
def send_booking_confirmation_email(
    booking_id: str,
    generated_password: str | None = None,
    invoice_number: str | None = None,
) -> dict:
    from apps.bookings.models import Booking
    from apps.bookings.pdf import generate_boarding_pass_pdf, generate_invoice_pdf

    booking = (
        Booking.objects.select_related("user", "discount")
        .prefetch_related(
            "tickets__flight__origin",
            "tickets__flight__destination",
            "tickets__passenger",
            "tickets__seat_type",
            "tickets__ticket_options__option",
            "payments",
        )
        .get(pk=booking_id)
    )

    lines = [
        f"Hello {booking.user.full_name},",
        "",
        f"Your DjangoAir booking {booking.booking_reference} is confirmed!",
        "",
        "=== TICKETS ===",
    ]

    for ticket in booking.tickets.all():
        flight = ticket.flight
        opts = ", ".join(
            f"{to.option.name} (${to.unit_price})" for to in ticket.ticket_options.all()
        ) or "None"
        lines.append(
            f"- Ticket {ticket.ticket_code} | Passenger: {ticket.passenger.full_name} "
            f"| Flight: {flight.flight_number} ({flight.origin.code} -> {flight.destination.code}) "
            f"| Departure: {flight.departure_time.strftime('%Y-%m-%d %H:%M UTC')} "
            f"| Seat: {ticket.seat_number} ({ticket.seat_type.name}) "
            f"| Options: {opts}"
        )

    lines.extend(
        [
            "",
            "=== INVOICE / BILL ===",
            f"Invoice Number: {invoice_number or 'N/A'}",
            f"Subtotal: ${booking.subtotal_amount}",
            f"Discount: -${booking.discount_amount}",
            f"Total Paid: ${booking.total_amount}",
            "",
            "=== PERSONAL CABINET ===",
            f"Email: {booking.contact_email}",
        ]
    )

    if generated_password:
        lines.append(f"Temporary Password: {generated_password}")
    else:
        lines.append("Password: Use your existing Personal Cabinet password.")

    lines.append(
        "Your QR Boarding Pass(es) and itemized Invoice PDF are attached to this email."
    )
    body = "\n".join(lines)
    subject = f"DjangoAir Tickets & Bill — Booking {booking.booking_reference}"

    try:
        email_msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.contact_email],
        )
        for ticket in booking.tickets.all():
            pdf_bytes = generate_boarding_pass_pdf(ticket)
            email_msg.attach(
                f"boarding-pass-{ticket.ticket_code}.pdf", pdf_bytes, "application/pdf"
            )
        payment = booking.payments.filter(invoice_number=invoice_number).first() or booking.payments.first()
        if payment:
            inv_bytes = generate_invoice_pdf(payment)
            email_msg.attach(
                f"invoice-{payment.invoice_number}.pdf", inv_bytes, "application/pdf"
            )

        email_msg.send(fail_silently=False)
        EmailLog.objects.create(
            recipient=booking.contact_email,
            subject=subject,
            template_type="BOOKING_CONFIRMATION",
            body_preview=body[:1000],
            status=EmailLog.Status.SENT,
        )
        return {"status": "sent", "recipient": booking.contact_email}
    except Exception as exc:
        logger.exception("Failed sending booking confirmation email for %s", booking_id)
        EmailLog.objects.create(
            recipient=booking.contact_email,
            subject=subject,
            template_type="BOOKING_CONFIRMATION",
            body_preview=body[:1000],
            status=EmailLog.Status.FAILED,
            error_message=str(exc),
        )
        return {"status": "failed", "error": str(exc)}


@shared_task(name="notifications.send_flight_cancellation_email")
def send_flight_cancellation_email(
    recipient: str,
    flight_number: str,
    booking_reference: str,
    refund_amount: str,
) -> dict:
    subject = f"DjangoAir Notice — Flight {flight_number} Cancelled"
    body = (
        f"Hello,\n\n"
        f"We regret to inform you that flight {flight_number} (Booking {booking_reference}) "
        f"has been cancelled by airline operations.\n"
        f"An automatic refund of ${refund_amount} has been credited to your Personal Cabinet balance.\n\n"
        f"DjangoAir Operations"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        EmailLog.objects.create(
            recipient=recipient,
            subject=subject,
            template_type="FLIGHT_CANCELLATION",
            body_preview=body[:1000],
            status=EmailLog.Status.SENT,
        )
        return {"status": "sent", "recipient": recipient}
    except Exception as exc:
        logger.exception("Failed sending flight cancellation email to %s", recipient)
        EmailLog.objects.create(
            recipient=recipient,
            subject=subject,
            template_type="FLIGHT_CANCELLATION",
            body_preview=body[:1000],
            status=EmailLog.Status.FAILED,
            error_message=str(exc),
        )
        return {"status": "failed", "error": str(exc)}
