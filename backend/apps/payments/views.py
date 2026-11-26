from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.pdf import generate_invoice_pdf
from apps.bookings.serializers import BookingSerializer
from apps.integrations.idempotency import idempotent_endpoint

from .models import Payment
from .serializers import BalanceTopUpSerializer, PaymentChargeInputSerializer, PaymentSerializer
from .services import (
    PaymentProcessingError,
    charge_booking_payment,
    handle_stripe_webhook_event,
    top_up_customer_balance,
)


class PaymentChargeView(APIView):
    """Process card (emulated or Stripe) or cabinet-balance payment for a RESERVED booking."""

    permission_classes = [AllowAny]

    @idempotent_endpoint
    def post(self, request):
        serializer = PaymentChargeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = charge_booking_payment(
                booking_reference=data["booking_reference"],
                payment_method=data["payment_method"],
                card_number=data["card_number"],
                exp_month=data["exp_month"],
                exp_year=data["exp_year"],
                cvv=data["cvv"],
                cardholder_name=data["cardholder_name"],
                idempotency_key=request.headers.get("Idempotency-Key"),
            )
        except PaymentProcessingError as exc:
            body: dict = {"detail": exc.detail}
            if exc.payment is not None:
                body["payment"] = PaymentSerializer(exc.payment).data
            return Response(body, status=exc.status_code)

        if not result.success:
            return Response(
                {
                    "detail": result.error_detail,
                    "payment": PaymentSerializer(result.payment).data,
                },
                status=result.status_code,
            )

        return Response(
            {
                "booking": BookingSerializer(result.booking).data,
                "payment": PaymentSerializer(result.payment).data,
                "cabinet_credentials_emailed": True,
                "new_cabinet_account": result.generated_password is not None,
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
        items = [
            {
                "ticket_code": t.ticket_code,
                "passenger": t.passenger.full_name,
                "flight": f"{t.flight.flight_number} ({t.flight.origin.code} -> {t.flight.destination.code})",
                "seat": f"{t.seat_number} ({t.seat_type.name})",
                "base_fare": str(t.base_fare),
                "options_total": str(t.options_total),
                "luggage_fee": str(t.luggage_fee),
            }
            for t in booking.tickets.all()
        ]
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
        try:
            res = top_up_customer_balance(
                user=request.user,
                amount=data["amount"],
                card_number=data["card_number"],
                exp_month=data["exp_month"],
                exp_year=data["exp_year"],
                cvv=data["cvv"],
            )
        except PaymentProcessingError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        return Response(
            {
                "transaction_id": res.transaction_id,
                "credited_amount": str(res.credited_amount),
                "balance": str(res.balance),
            },
            status=status.HTTP_200_OK,
        )


class InvoicePdfView(APIView):
    """Download an itemized PDF receipt/invoice for a payment."""

    permission_classes = [AllowAny]

    def get(self, _request, pk):
        payment = get_object_or_404(Payment.objects.select_related("booking"), pk=pk)
        pdf_bytes = generate_invoice_pdf(payment)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice-{payment.invoice_number}.pdf"'
        )
        return response


class StripeWebhookView(APIView):
    """Receive and verify signed Stripe PaymentIntent webhook events."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        import stripe

        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "").strip()
        if not webhook_secret:
            return Response(
                {"detail": "Stripe webhook receiver is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        sig_header = request.headers.get("Stripe-Signature", "")
        if not sig_header:
            return Response(
                {"detail": "Missing Stripe-Signature header."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event = stripe.Webhook.construct_event(request.body, sig_header, webhook_secret)
        except ValueError:
            return Response(
                {"detail": "Invalid Stripe webhook payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.SignatureVerificationError:
            return Response(
                {"detail": "Invalid Stripe webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = handle_stripe_webhook_event(event)
        return Response(result, status=status.HTTP_200_OK)
