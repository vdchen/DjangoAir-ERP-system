import re
import secrets
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class GatewayResult:
    success: bool
    transaction_id: str
    card_last4: str
    failure_reason: str = ""
    provider: str = "emulated_gateway"


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
