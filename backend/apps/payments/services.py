import secrets
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import CustomerProfile, User
from apps.bookings.models import Booking, BookingStatus, TicketStatus
from apps.integrations.events import publish_domain_event
from apps.integrations.metrics import PAYMENTS_TOTAL
from apps.notifications.tasks import send_booking_confirmation_email

from .gateway import PaymentProvider, get_payment_provider
from .models import Payment, PaymentStatus


class PaymentProcessingError(Exception):
    """Domain error raised when a payment charge cannot be completed."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        payment: Payment | None = None,
    ):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.payment = payment


@dataclass
class PaymentChargeResult:
    booking: Booking
    payment: Payment
    generated_password: str | None = None
    success: bool = True
    error_detail: str = ""
    status_code: int = status.HTTP_200_OK


@dataclass
class BalanceTopUpResult:
    transaction_id: str
    credited_amount: Decimal
    balance: Decimal


def _finalize_paid_booking(booking: Booking, payment: Payment) -> tuple[Booking, str | None]:
    """Transition booking & tickets to PAID, provision guest cabinet password, and emit events."""
    booking.status = BookingStatus.PAID
    booking.save(update_fields=["status"])
    booking.tickets.filter(status=TicketStatus.RESERVED).update(status=TicketStatus.PAID)

    generated_password = None
    if not booking.user.has_usable_password():
        generated_password = f"Air-{secrets.token_hex(4)}"
        booking.user.set_password(generated_password)
        booking.user.save(update_fields=["password"])

    send_booking_confirmation_email.delay(
        booking_id=str(booking.id),
        generated_password=generated_password,
        invoice_number=payment.invoice_number,
    )

    reloaded = (
        Booking.objects.select_related("discount")
        .prefetch_related(
            "tickets__flight__origin",
            "tickets__flight__destination",
            "tickets__passenger",
            "tickets__seat_type",
            "tickets__ticket_options__option",
        )
        .get(pk=booking.pk)
    )
    first_ticket = reloaded.tickets.first()
    flight_number = first_ticket.flight.flight_number if first_ticket else ""

    publish_domain_event(
        "booking.confirmed",
        {
            "booking_reference": reloaded.booking_reference,
            "flight_number": flight_number,
            "total_amount": str(reloaded.total_amount),
            "invoice_number": payment.invoice_number,
            "ticket_codes": [t.ticket_code for t in reloaded.tickets.all()],
        },
    )
    publish_domain_event(
        "payment.succeeded",
        {
            "booking_reference": reloaded.booking_reference,
            "transaction_id": payment.transaction_id,
            "invoice_number": payment.invoice_number,
            "amount": str(payment.amount),
            "provider": payment.provider,
        },
    )
    return reloaded, generated_password


@transaction.atomic
def charge_booking_payment(
    *,
    booking_reference: str,
    payment_method: str,
    card_number: str = "",
    exp_month: int = 12,
    exp_year: int = 2030,
    cvv: str = "",
    cardholder_name: str = "",
    idempotency_key: str | None = None,
    provider: PaymentProvider | None = None,
) -> PaymentChargeResult:
    """Atomically charge a RESERVED booking via cabinet balance or the active PaymentProvider."""
    booking = get_object_or_404(
        Booking.objects.select_for_update().select_related("user"),
        booking_reference__iexact=booking_reference.strip(),
    )
    if booking.status == BookingStatus.PAID:
        raise PaymentProcessingError(
            "Booking is already paid.", status_code=status.HTTP_400_BAD_REQUEST
        )
    if booking.status == BookingStatus.CANCELLED:
        raise PaymentProcessingError(
            "Cannot pay for a cancelled booking.", status_code=status.HTTP_400_BAD_REQUEST
        )

    if payment_method == "BALANCE":
        profile, _ = CustomerProfile.objects.get_or_create(user=booking.user)
        try:
            profile.debit(booking.total_amount)
        except ValueError as exc:
            PAYMENTS_TOTAL.labels(provider="cabinet_balance", status="FAILED").inc()
            raise PaymentProcessingError(
                str(exc), status_code=status.HTTP_402_PAYMENT_REQUIRED
            ) from exc

        payment = Payment.objects.create(
            booking=booking,
            transaction_id=f"BAL-{secrets.token_hex(6).upper()}",
            provider="cabinet_balance",
            amount=booking.total_amount,
            status=PaymentStatus.SUCCEEDED,
            card_last4="BAL",
            paid_at=timezone.now(),
        )
        PAYMENTS_TOTAL.labels(provider="cabinet_balance", status="SUCCEEDED").inc()
    else:
        gateway = provider or get_payment_provider()
        result = gateway.charge(
            amount=booking.total_amount,
            card_number=card_number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvv=cvv,
            cardholder_name=cardholder_name,
            idempotency_key=idempotency_key,
        )
        payment = Payment.objects.create(
            booking=booking,
            transaction_id=result.transaction_id,
            provider=result.provider,
            amount=booking.total_amount,
            status=PaymentStatus.SUCCEEDED if result.success else PaymentStatus.FAILED,
            card_last4=result.card_last4,
            failure_reason=result.failure_reason,
            paid_at=timezone.now() if result.success else None,
        )
        PAYMENTS_TOTAL.labels(provider=result.provider, status=payment.status).inc()
        if not result.success:
            return PaymentChargeResult(
                booking=booking,
                payment=payment,
                success=False,
                error_detail=result.failure_reason,
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
            )

    reloaded_booking, generated_password = _finalize_paid_booking(booking, payment)
    return PaymentChargeResult(
        booking=reloaded_booking,
        payment=payment,
        generated_password=generated_password,
    )


def top_up_customer_balance(
    *,
    user: User,
    amount: Decimal,
    card_number: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    provider: PaymentProvider | None = None,
) -> BalanceTopUpResult:
    """Charge card via configured PaymentProvider and credit the customer's Personal Cabinet."""
    gateway = provider or get_payment_provider()
    result = gateway.charge(
        amount=amount,
        card_number=card_number,
        exp_month=exp_month,
        exp_year=exp_year,
        cvv=cvv,
    )
    if not result.success:
        raise PaymentProcessingError(
            result.failure_reason, status_code=status.HTTP_402_PAYMENT_REQUIRED
        )
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    new_balance = profile.credit(amount)
    return BalanceTopUpResult(
        transaction_id=result.transaction_id,
        credited_amount=amount,
        balance=new_balance,
    )


@transaction.atomic
def handle_stripe_webhook_event(event: dict) -> dict:
    """Idempotently reconcile asynchronous Stripe PaymentIntent webhook events."""
    event_type = str(event.get("type", ""))
    obj = event.get("data", {}).get("object", {}) or {}
    intent_id = str(obj.get("id", "")).strip()
    if not intent_id:
        return {"handled": False, "reason": "missing_intent_id"}

    payment = (
        Payment.objects.select_for_update()
        .select_related("booking__user")
        .filter(transaction_id=intent_id)
        .first()
    )
    if payment is None:
        return {"handled": False, "reason": "payment_not_found", "transaction_id": intent_id}

    if event_type == "payment_intent.succeeded":
        if payment.status == PaymentStatus.SUCCEEDED:
            return {"handled": True, "idempotent": True, "transaction_id": intent_id}
        payment.status = PaymentStatus.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.failure_reason = ""
        payment.save(update_fields=["status", "paid_at", "failure_reason"])
        PAYMENTS_TOTAL.labels(provider="stripe", status="SUCCEEDED").inc()
        if payment.booking.status == BookingStatus.RESERVED:
            _finalize_paid_booking(payment.booking, payment)
        return {"handled": True, "status": PaymentStatus.SUCCEEDED, "transaction_id": intent_id}

    if event_type == "payment_intent.payment_failed":
        if payment.status == PaymentStatus.FAILED:
            return {"handled": True, "idempotent": True, "transaction_id": intent_id}
        last_err = (obj.get("last_payment_error") or {}).get("message") or "Stripe payment failed."
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = str(last_err)[:255]
        payment.save(update_fields=["status", "failure_reason"])
        PAYMENTS_TOTAL.labels(provider="stripe", status="FAILED").inc()
        return {"handled": True, "status": PaymentStatus.FAILED, "transaction_id": intent_id}

    return {"handled": False, "reason": "ignored_event_type", "event_type": event_type}
