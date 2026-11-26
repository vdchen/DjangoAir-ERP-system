import re
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from django.conf import settings


@dataclass
class GatewayResult:
    success: bool
    transaction_id: str
    card_last4: str
    failure_reason: str = ""
    provider: str = "emulated_gateway"


class PaymentProvider(Protocol):
    """Strategy interface implemented by all DjangoAir payment gateway adapters."""

    def charge(
        self,
        *,
        amount: Decimal,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        cardholder_name: str = "",
        currency: str = "USD",
        idempotency_key: str | None = None,
    ) -> GatewayResult: ...


class EmulatedGatewayProvider:
    """Open-source style emulated payment processor for testing card outcomes safely.

    Deterministic test cards:
    - Ending in '0002': Declined by issuer
    - Ending in '9995': Insufficient funds
    - Any other 13-19 digit card (e.g., 4242 4242 4242 4242): Approved
    """

    def charge(
        self,
        *,
        amount: Decimal,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        cardholder_name: str = "",
        currency: str = "USD",
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        digits = re.sub(r"\D", "", card_number or "")
        tx_id = f"TXN-{secrets.token_hex(6).upper()}"

        if len(digits) < 13 or len(digits) > 19:
            return GatewayResult(
                success=False,
                transaction_id=tx_id,
                card_last4=digits[-4:] if len(digits) >= 4 else "0000",
                failure_reason="Invalid card number length.",
            )

        if not (1 <= int(exp_month) <= 12) or int(exp_year) < 2025:
            return GatewayResult(
                success=False,
                transaction_id=tx_id,
                card_last4=digits[-4:],
                failure_reason="Card expiration date is invalid or expired.",
            )

        if not re.fullmatch(r"\d{3,4}", str(cvv or "")):
            return GatewayResult(
                success=False,
                transaction_id=tx_id,
                card_last4=digits[-4:],
                failure_reason="Invalid CVV security code.",
            )

        last4 = digits[-4:]
        if last4 == "0002":
            return GatewayResult(
                success=False,
                transaction_id=tx_id,
                card_last4=last4,
                failure_reason="Card declined by issuing bank.",
            )
        if last4 == "9995":
            return GatewayResult(
                success=False,
                transaction_id=tx_id,
                card_last4=last4,
                failure_reason="Insufficient funds on card.",
            )

        return GatewayResult(
            success=True,
            transaction_id=tx_id,
            card_last4=last4,
        )


class StripeGatewayProvider:
    """Stripe Sandbox / Live PaymentIntents adapter implementing PaymentProvider.

    Activated when PAYMENT_PROVIDER=stripe and STRIPE_SECRET_KEY is configured.
    Accepts either a Stripe PaymentMethod ID (e.g. 'pm_card_visa' / 'pm_...')
    or maps deterministic test card suffixes to Stripe test payment methods
    when operating in Stripe test mode ('sk_test_...').
    """

    TEST_CARD_TO_PM = {
        "0002": "pm_card_chargeDeclined",
        "9995": "pm_card_chargeDeclinedInsufficientFunds",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else getattr(settings, "STRIPE_SECRET_KEY", "")).strip()

    def _resolve_payment_method(self, card_number: str) -> tuple[str, str]:
        raw = (card_number or "").strip()
        if raw.startswith("pm_"):
            return raw, "4242"
        digits = re.sub(r"\D", "", raw)
        last4 = digits[-4:] if len(digits) >= 4 else "4242"
        pm_id = self.TEST_CARD_TO_PM.get(last4, "pm_card_visa")
        return pm_id, last4

    def charge(
        self,
        *,
        amount: Decimal,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        cardholder_name: str = "",
        currency: str = "USD",
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        import stripe

        fallback_tx = f"STRIPE-ERR-{secrets.token_hex(5).upper()}"
        pm_id, last4 = self._resolve_payment_method(card_number)

        if not self.api_key:
            return GatewayResult(
                success=False,
                transaction_id=fallback_tx,
                card_last4=last4,
                failure_reason="Stripe gateway is not configured (missing STRIPE_SECRET_KEY).",
                provider="stripe",
            )

        cents = int((Decimal(amount) * 100).quantize(Decimal("1")))
        params: dict = {
            "amount": cents,
            "currency": currency.lower(),
            "payment_method": pm_id,
            "confirm": True,
            "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
            "description": f"DjangoAir payment ({cardholder_name or 'Customer'})",
        }
        if idempotency_key:
            params["idempotency_key"] = idempotency_key

        try:
            intent = stripe.PaymentIntent.create(api_key=self.api_key, **params)
        except stripe.CardError as exc:
            return GatewayResult(
                success=False,
                transaction_id=fallback_tx,
                card_last4=last4,
                failure_reason=exc.user_message or str(exc),
                provider="stripe",
            )
        except stripe.StripeError as exc:
            return GatewayResult(
                success=False,
                transaction_id=fallback_tx,
                card_last4=last4,
                failure_reason=f"Stripe gateway error: {exc.user_message or str(exc)}",
                provider="stripe",
            )

        intent_id = str(intent.get("id", fallback_tx))
        intent_status = str(intent.get("status", ""))
        if intent_status == "succeeded":
            return GatewayResult(
                success=True,
                transaction_id=intent_id,
                card_last4=last4,
                provider="stripe",
            )
        return GatewayResult(
            success=False,
            transaction_id=intent_id,
            card_last4=last4,
            failure_reason=f"Stripe PaymentIntent status: {intent_status or 'unknown'}",
            provider="stripe",
        )


def get_payment_provider(provider_name: str | None = None) -> PaymentProvider:
    """Factory returning the configured PaymentProvider strategy."""
    selected = (
        provider_name
        if provider_name is not None
        else getattr(settings, "PAYMENT_PROVIDER", "emulated")
    ).strip().lower()
    if selected == "stripe":
        return StripeGatewayProvider()
    return EmulatedGatewayProvider()
