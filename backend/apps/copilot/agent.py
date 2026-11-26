import json
import logging
import secrets
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.bookings.models import BookingStatus, TicketStatus
from apps.bookings.services import create_booking
from apps.flights.models import FlightStatus
from apps.integrations.events import publish_domain_event
from apps.payments.models import Payment, PaymentStatus

from .models import ProposalStatus, RebookingProposal
from .tools import COPILOT_TOOL_SCHEMAS, execute_copilot_tool

logger = logging.getLogger("djangoair.copilot")

SYSTEM_PROMPT = (
    "You are the DjangoAir AI Disruption & Rebooking Copilot. "
    "Use the provided read-only tools to inspect passenger tickets, retrieve official DjangoAir "
    "policies, and find available alternative flights. "
    "NEVER claim to have already booked a flight or issued a refund unilaterally — always explain "
    "that human confirmation is required. Ground policy statements in the retrieved clauses."
)

REBOOK_INTENT_KEYWORDS = (
    "rebook",
    "cancel",
    "cancelled",
    "canceled",
    "disrupt",
    "alternative",
    "change flight",
    "reschedule",
    "move my flight",
    "next flight",
)


class CopilotActionError(Exception):
    def __init__(self, detail: str, *, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def get_active_copilot_provider() -> str:
    configured = getattr(settings, "AI_COPILOT_PROVIDER", "deterministic").strip().lower()
    if configured == "openai" and getattr(settings, "OPENAI_API_KEY", "").strip():
        return "openai"
    if configured == "gemini" and getattr(settings, "GEMINI_API_KEY", "").strip():
        return "gemini"
    return "deterministic"


def _wants_rebooking(message: str, ticket_code: str | None) -> bool:
    if ticket_code:
        return True
    lowered = message.lower()
    return any(kw in lowered for kw in REBOOK_INTENT_KEYWORDS)


def _select_target_ticket(tickets: list[dict], ticket_code: str | None) -> dict | None:
    if not tickets:
        return None
    if ticket_code:
        match = next(
            (t for t in tickets if t["ticket_code"].upper() == ticket_code.strip().upper()),
            None,
        )
        if match:
            return match
    # Prefer cancelled flights first (involuntary disruption), then active upcoming tickets
    cancelled = next((t for t in tickets if t["flight_status"] == FlightStatus.CANCELLED), None)
    if cancelled:
        return cancelled
    return next((t for t in tickets if t["ticket_status"] != TicketStatus.CANCELLED), tickets[0])


def _run_openai_tool_loop(
    *, message: str, user: User, ticket_code: str | None
) -> tuple[str, list[dict], list[dict], list[dict], list[dict]]:
    """Execute a live OpenAI Chat Completions tool-calling loop."""
    api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
    model = getattr(settings, "OPENAI_COPILOT_MODEL", "gpt-4o-mini")
    user_prompt = f"{message}\n(Ticket context: {ticket_code})" if ticket_code else message
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    tool_trace: list[dict] = []
    citations: list[dict] = []
    tickets_seen: list[dict] = []
    alternatives_seen: list[dict] = []

    for _ in range(4):
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": COPILOT_TOOL_SCHEMAS,
                "tool_choice": "auto",
                "temperature": 0.2,
            },
            timeout=15,
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]["message"]
        messages.append(choice)

        tool_calls = choice.get("tool_calls") or []
        if not tool_calls:
            return (
                str(choice.get("content") or "").strip(),
                tool_trace,
                citations,
                tickets_seen,
                alternatives_seen,
            )

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments") or "{}"
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            result = execute_copilot_tool(fn_name, args, user=user)
            tool_trace.append({"tool": fn_name, "arguments": args, "result_summary": list(result.keys())})
            if "citations" in result:
                citations.extend(result["citations"])
            if "tickets" in result:
                tickets_seen = result["tickets"]
            if "alternatives" in result:
                alternatives_seen = result["alternatives"]
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, default=str),
                }
            )

    return (
        "I have gathered your flight options and applicable DjangoAir policies.",
        tool_trace,
        citations,
        tickets_seen,
        alternatives_seen,
    )


def _run_gemini_with_grounding(
    *, message: str, context_bundle: dict
) -> str:
    """Call Google Gemini generateContent with grounded tool outputs & policy citations."""
    api_key = getattr(settings, "GEMINI_API_KEY", "").strip()
    model = getattr(settings, "GEMINI_COPILOT_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Passenger message: {message}\n\n"
        f"Grounded DjangoAir tool outputs (JSON):\n{json.dumps(context_bundle, default=str)}\n\n"
        "Respond concisely, cite exact policy sections, and remind the passenger to click "
        "Confirm Rebooking if a proposal was created."
    )
    resp = requests.post(
        url,
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    return "".join(str(p.get("text", "")) for p in parts).strip()


def run_copilot_assist(
    *, user: User, message: str, ticket_code: str | None = None
) -> dict:
    """Run the read-only Copilot tool-calling + RAG pipeline and optionally create a HITL proposal."""
    provider = get_active_copilot_provider()
    tool_trace: list[dict] = []
    citations: list[dict] = []
    tickets_seen: list[dict] = []
    alternatives_seen: list[dict] = []
    answer = ""

    # 1. Always execute deterministic grounded RAG + ticket lookup so every provider is auditable
    policy_res = execute_copilot_tool(
        "search_airline_policies", {"query": message, "top_k": 3}, user=user
    )
    citations = policy_res.get("citations", [])
    tool_trace.append(
        {
            "tool": "search_airline_policies",
            "arguments": {"query": message, "top_k": 3},
            "matches": len(citations),
        }
    )

    wants_rebook = _wants_rebooking(message, ticket_code)
    target_ticket = None

    if wants_rebook:
        ticket_res = execute_copilot_tool(
            "lookup_passenger_tickets", {"ticket_code": ticket_code}, user=user
        )
        tickets_seen = ticket_res.get("tickets", [])
        tool_trace.append(
            {
                "tool": "lookup_passenger_tickets",
                "arguments": {"ticket_code": ticket_code},
                "matches": len(tickets_seen),
            }
        )
        target_ticket = _select_target_ticket(tickets_seen, ticket_code)

        if target_ticket:
            involuntary = target_ticket["flight_status"] == FlightStatus.CANCELLED
            alt_args = {
                "origin_code": target_ticket["origin"],
                "destination_code": target_ticket["destination"],
                "seat_type_code": target_ticket["seat_type_code"],
                "exclude_flight_id": target_ticket["flight_id"],
                "original_fare": target_ticket["base_fare"],
                "involuntary_cancellation": involuntary,
            }
            alt_res = execute_copilot_tool("find_alternative_flights", alt_args, user=user)
            alternatives_seen = alt_res.get("alternatives", [])
            tool_trace.append(
                {
                    "tool": "find_alternative_flights",
                    "arguments": alt_args,
                    "matches": len(alternatives_seen),
                }
            )

    # 2. Optional live LLM synthesis (OpenAI or Gemini) with graceful fallback to deterministic mode
    effective_provider = provider
    if provider == "openai":
        try:
            llm_answer, llm_trace, llm_cites, llm_tickets, llm_alts = _run_openai_tool_loop(
                message=message, user=user, ticket_code=ticket_code
            )
            if llm_answer:
                answer = llm_answer
            if llm_trace:
                tool_trace = llm_trace
            if llm_cites:
                citations = llm_cites
            if llm_tickets:
                tickets_seen = llm_tickets
                target_ticket = _select_target_ticket(tickets_seen, ticket_code)
            if llm_alts:
                alternatives_seen = llm_alts
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("OpenAI copilot call failed; falling back to deterministic mode: %s", exc)
            effective_provider = "deterministic_fallback"
    elif provider == "gemini":
        try:
            answer = _run_gemini_with_grounding(
                message=message,
                context_bundle={
                    "target_ticket": target_ticket,
                    "alternatives": alternatives_seen,
                    "policy_citations": citations,
                },
            )
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Gemini copilot call failed; falling back to deterministic mode: %s", exc)
            effective_provider = "deterministic_fallback"

    # 3. Create a Human-in-the-Loop RebookingProposal (NEVER mutates bookings directly!)
    proposal: RebookingProposal | None = None
    if target_ticket and alternatives_seen:
        best_alt = alternatives_seen[0]
        proposal = RebookingProposal.objects.create(
            user=user,
            original_ticket_id=target_ticket["ticket_id"],
            proposed_flight_id=best_alt["flight_id"],
            proposed_seat_type_id=best_alt["seat_type_id"],
            fee_waived=bool(best_alt["fee_waived"]),
            fare_difference=Decimal(best_alt["fare_difference"]),
            status=ProposalStatus.PENDING_CONFIRMATION,
            provider=effective_provider,
            policy_citations=citations,
            tool_trace=tool_trace,
        )

    # 4. Deterministic grounded synthesis if no live LLM answer was generated
    if not answer:
        parts: list[str] = []
        if proposal and target_ticket and alternatives_seen:
            best = alternatives_seen[0]
            if best["fee_waived"]:
                parts.append(
                    f"Your flight {target_ticket['flight_number']} ({target_ticket['origin']} -> "
                    f"{target_ticket['destination']}) was cancelled. Under DjangoAir's Free Same-Route "
                    f"Involuntary Rebooking policy, I prepared a complimentary ($0.00 fee waiver) "
                    f"rebooking proposal on flight {best['flight_number']} departing "
                    f"{best['departure_time']} in {best['seat_type_name']}."
                )
            else:
                parts.append(
                    f"I found an alternative flight for ticket {target_ticket['ticket_code']} "
                    f"({target_ticket['origin']} -> {target_ticket['destination']}): flight "
                    f"{best['flight_number']} departing {best['departure_time']} in "
                    f"{best['seat_type_name']} (estimated fare difference: ${best['fare_difference']})."
                )
            parts.append(
                "No booking has been changed yet — please review and click Confirm Rebooking "
                "to approve this change (Human-in-the-Loop safeguard)."
            )
        elif wants_rebook and target_ticket and not alternatives_seen:
            parts.append(
                f"I inspected ticket {target_ticket['ticket_code']} on {target_ticket['flight_number']} "
                f"({target_ticket['origin']} -> {target_ticket['destination']}), but no scheduled "
                "alternative flights with open seats are currently available on that route."
            )
        elif wants_rebook and not target_ticket:
            parts.append(
                "I checked your account and did not find an active or cancelled ticket to rebook. "
                "You can book a new flight on the main search page or specify a ticket code."
            )

        if citations:
            top_cite = citations[0]
            parts.append(
                f"Relevant policy ({top_cite['source']} — {top_cite['section']}): {top_cite['excerpt']}"
            )
        elif not parts:
            parts.append(
                "I can help with disrupted/cancelled flight rebooking, refund policies, baggage "
                "allowances, and check-in rules. Ask about a policy or your ticket!"
            )
        answer = "\n\n".join(parts)

    if proposal is not None:
        proposal.rationale = answer
        proposal.save(update_fields=["rationale"])

    return {
        "provider": effective_provider,
        "answer": answer,
        "citations": citations,
        "tool_trace": tool_trace,
        "alternatives": alternatives_seen,
        "proposal": proposal,
    }


@transaction.atomic
def confirm_rebooking_proposal(*, proposal_id, actor: User) -> RebookingProposal:
    """Execute a human-approved RebookingProposal inside a single atomic transaction."""
    proposal = get_object_or_404(
        RebookingProposal.objects.select_for_update().select_related(
            "user",
            "original_ticket__passenger",
            "original_ticket__booking",
            "original_ticket__flight",
            "proposed_flight",
            "proposed_seat_type",
        ),
        pk=proposal_id,
    )

    is_supervisor = actor.is_superuser or actor.role == UserRole.SUPERVISOR
    if proposal.user_id != actor.id and not is_supervisor:
        raise CopilotActionError(
            "You do not have permission to confirm this rebooking proposal.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if proposal.status != ProposalStatus.PENDING_CONFIRMATION:
        raise CopilotActionError(
            f"Proposal is already {proposal.status}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if proposal.proposed_flight.status != FlightStatus.SCHEDULED:
        raise CopilotActionError(
            "The proposed alternative flight is no longer scheduled.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Debit positive fare difference from cabinet balance for voluntary changes
    if not proposal.fee_waived and proposal.fare_difference > Decimal("0.00"):
        profile, _ = CustomerProfile.objects.get_or_create(user=proposal.user)
        try:
            profile.debit(proposal.fare_difference)
        except ValueError as exc:
            raise CopilotActionError(
                str(exc), status_code=status.HTTP_402_PAYMENT_REQUIRED
            ) from exc

    orig_passenger = proposal.original_ticket.passenger
    new_booking = create_booking(
        flight_id=proposal.proposed_flight_id,
        seat_type_id=proposal.proposed_seat_type_id,
        contact_email=proposal.original_ticket.booking.contact_email,
        passengers_data=[
            {
                "first_name": orig_passenger.first_name,
                "last_name": orig_passenger.last_name,
                "document_number": orig_passenger.document_number,
                "date_of_birth": orig_passenger.date_of_birth,
            }
        ],
        authenticated_user=proposal.user,
    )

    # Transition new booking & ticket to PAID and record settlement Payment
    new_booking.status = BookingStatus.PAID
    new_booking.save(update_fields=["status"])
    new_booking.tickets.filter(status=TicketStatus.RESERVED).update(status=TicketStatus.PAID)

    settled_amount = Decimal("0.00") if proposal.fee_waived else proposal.fare_difference
    Payment.objects.create(
        booking=new_booking,
        transaction_id=f"REBK-{secrets.token_hex(6).upper()}",
        provider="copilot_waiver" if proposal.fee_waived else "cabinet_balance",
        amount=settled_amount,
        status=PaymentStatus.SUCCEEDED,
        card_last4="WVR" if proposal.fee_waived else "BAL",
        paid_at=timezone.now(),
    )

    # Cancel original non-cancelled ticket on voluntary change
    if proposal.original_ticket.status != TicketStatus.CANCELLED:
        proposal.original_ticket.status = TicketStatus.CANCELLED
        proposal.original_ticket.save(update_fields=["status"])

    proposal.status = ProposalStatus.CONFIRMED
    proposal.new_booking = new_booking
    proposal.confirmed_at = timezone.now()
    proposal.save(update_fields=["status", "new_booking", "confirmed_at"])

    publish_domain_event(
        "copilot.rebooking_confirmed",
        {
            "proposal_id": str(proposal.id),
            "original_ticket_code": proposal.original_ticket.ticket_code,
            "new_booking_reference": new_booking.booking_reference,
            "new_flight_number": proposal.proposed_flight.flight_number,
            "fee_waived": proposal.fee_waived,
            "fare_difference": str(settled_amount),
        },
    )
    return proposal


@transaction.atomic
def reject_rebooking_proposal(*, proposal_id, actor: User) -> RebookingProposal:
    proposal = get_object_or_404(
        RebookingProposal.objects.select_for_update(),
        pk=proposal_id,
    )
    is_supervisor = actor.is_superuser or actor.role == UserRole.SUPERVISOR
    if proposal.user_id != actor.id and not is_supervisor:
        raise CopilotActionError(
            "You do not have permission to reject this rebooking proposal.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if proposal.status != ProposalStatus.PENDING_CONFIRMATION:
        raise CopilotActionError(
            f"Proposal is already {proposal.status}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    proposal.status = ProposalStatus.REJECTED
    proposal.save(update_fields=["status"])
    return proposal
