import secrets

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CustomerProfile
from apps.bookings.models import Booking, BookingStatus, TicketStatus
from apps.bookings.serializers import BookingSerializer
from apps.integrations.events import publish_domain_event
from apps.notifications.tasks import send_booking_confirmation_email

from .gateway import EmulatedGatewayProvider
from .models import Payment, PaymentStatus
from .serializers import BalanceTopUpSerializer, PaymentChargeInputSerializer, PaymentSerializer


class PaymentChargeView(APIView):
    """Process emulated card or balance payment for a RESERVED booking."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PaymentChargeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        booking = get_object_or_404(
            Booking.objects.select_for_update().select_related("user"),
            booking_reference__iexact=data["booking_reference"].strip(),
        )
        if booking.status == BookingStatus.PAID:
            return Response(
                {"detail": "Booking is already paid."}, status=status.HTTP_400_BAD_REQUEST
            )
        if booking.status == BookingStatus.CANCELLED:
            return Response(
                {"detail": "Cannot pay for a cancelled booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = data["payment_method"]
        if payment_method == "BALANCE":
            profile, _ = CustomerProfile.objects.get_or_create(user=booking.user)
            try:
                profile.debit(booking.total_amount)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
            payment = Payment.objects.create(
                booking=booking,
                transaction_id=f"BAL-{secrets.token_hex(6).upper()}",
                provider="cabinet_balance",
                amount=booking.total_amount,
                status=PaymentStatus.SUCCEEDED,
                card_last4="BAL",
                paid_at=timezone.now(),
            )
        else:
            gateway = EmulatedGatewayProvider()
            result = gateway.charge(
                amount=booking.total_amount,
                card_number=data["card_number"],
                exp_month=data["exp_month"],
                exp_year=data["exp_year"],
                cvv=data["cvv"],
                cardholder_name=data["cardholder_name"],
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
            if not result.success:
                return Response(
                    {
                        "detail": result.failure_reason,
                        "payment": PaymentSerializer(payment).data,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        # Transition booking & tickets to PAID
        booking.status = BookingStatus.PAID
        booking.save(update_fields=["status"])
        booking.tickets.filter(status=TicketStatus.RESERVED).update(status=TicketStatus.PAID)

        # Auto-provision password for newly created guest accounts so they can access Personal Cabinet
        generated_password = None
        if not booking.user.has_usable_password():
            generated_password = f"Air-{secrets.token_hex(4)}"
            booking.user.set_password(generated_password)
            booking.user.save(update_fields=["password"])

        # Enqueue confirmation email with tickets, invoice/bill, and Personal Cabinet credentials
        send_booking_confirmation_email.delay(
            booking_id=str(booking.id),
            generated_password=generated_password,
            invoice_number=payment.invoice_number,
        )

        # Reload booking for response & domain events
        booking = (
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
        first_ticket = booking.tickets.first()
        flight_number = first_ticket.flight.flight_number if first_ticket else ""

        publish_domain_event(
            "booking.confirmed",
            {
                "booking_reference": booking.booking_reference,
                "flight_number": flight_number,
                "total_amount": str(booking.total_amount),
                "invoice_number": payment.invoice_number,
                "ticket_codes": [t.ticket_code for t in booking.tickets.all()],
            },
        )
        publish_domain_event(
            "payment.succeeded",
            {
                "booking_reference": booking.booking_reference,
                "transaction_id": payment.transaction_id,
                "invoice_number": payment.invoice_number,
                "amount": str(payment.amount),
                "provider": payment.provider,
            },
        )

        return Response(
            {
                "booking": BookingSerializer(booking).data,
                "payment": PaymentSerializer(payment).data,
                "cabinet_credentials_emailed": True,
                "new_cabinet_account": generated_password is not None,
            },
            status=status.HTTP_200_OK,
        )


class InvoiceDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("booking__discount").prefetch_related(
                "booking__tickets__passenger",
                "booking__tickets__flight__origin",
                "booking__tickets__flight__destination",
                "booking__tickets__seat_type",
                "booking__tickets__ticket_options__option",
            ),
            pk=pk,
        )
        booking = payment.booking
        items = []
        for t in booking.tickets.all():
            items.append(
                {
                    "ticket_code": t.ticket_code,
                    "passenger": t.passenger.full_name,
                    "flight": f"{t.flight.flight_number} ({t.flight.origin.code} -> {t.flight.destination.code})",
                    "seat": f"{t.seat_number} ({t.seat_type.name})",
                    "base_fare": str(t.base_fare),
                    "options_total": str(t.options_total),
                    "luggage_fee": str(t.luggage_fee),
                }
            )
        return Response(
            {
                "invoice_number": payment.invoice_number,
                "transaction_id": payment.transaction_id,
                "booking_reference": booking.booking_reference,
                "contact_email": booking.contact_email,
                "status": payment.status,
                "paid_at": payment.paid_at,
                "subtotal": str(booking.subtotal_amount),
                "discount": str(booking.discount_amount),
                "total": str(payment.amount),
                "currency": payment.currency,
                "items": items,
            }
        )


class CabinetBalanceTopUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BalanceTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        gateway = EmulatedGatewayProvider()
        result = gateway.charge(
            amount=data["amount"],
            card_number=data["card_number"],
            exp_month=data["exp_month"],
            exp_year=data["exp_year"],
            cvv=data["cvv"],
        )
        if not result.success:
            return Response(
                {"detail": result.failure_reason}, status=status.HTTP_402_PAYMENT_REQUIRED
            )
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        new_balance = profile.credit(data["amount"])
        return Response(
            {
                "transaction_id": result.transaction_id,
                "credited_amount": str(data["amount"]),
                "balance": str(new_balance),
            },
            status=status.HTTP_200_OK,
        )


class InvoicePdfView(APIView):
    """Download an itemized PDF receipt/invoice for a payment."""

    permission_classes = [AllowAny]

    def get(self, _request, pk):
        from django.http import HttpResponse

        from apps.bookings.pdf import generate_invoice_pdf

        payment = get_object_or_404(Payment.objects.select_related("booking"), pk=pk)
        pdf_bytes = generate_invoice_pdf(payment)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice-{payment.invoice_number}.pdf"'
        )
        return response
