from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole

from .agent import (
    CopilotActionError,
    confirm_rebooking_proposal,
    get_active_copilot_provider,
    reject_rebooking_proposal,
    run_copilot_assist,
)
from .models import RebookingProposal
from .rag import get_policy_kb
from .serializers import CopilotAssistInputSerializer, RebookingProposalSerializer
from .tools import COPILOT_TOOL_SCHEMAS


class CopilotConfigView(APIView):
    """Inspect active AI Copilot provider, available read-only tools, and RAG policy corpus size."""

    permission_classes = [AllowAny]

    def get(self, _request):
        kb = get_policy_kb()
        return Response(
            {
                "provider": get_active_copilot_provider(),
                "human_in_the_loop_required": True,
                "policy_chunks_indexed": len(kb.chunks),
                "tools": [t["function"]["name"] for t in COPILOT_TOOL_SCHEMAS],
            }
        )


class CopilotAssistView(APIView):
    """Ask the AI Disruption & Rebooking Copilot a policy question or request rebooking options."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CopilotAssistInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = run_copilot_assist(
            user=request.user,
            message=data["message"],
            ticket_code=data.get("ticket_code") or None,
        )
        proposal = result["proposal"]
        proposal_data = None
        if proposal is not None:
            proposal = (
                RebookingProposal.objects.select_related(
                    "original_ticket__flight",
                    "proposed_flight__origin",
                    "proposed_flight__destination",
                    "proposed_seat_type",
                )
                .get(pk=proposal.pk)
            )
            proposal_data = RebookingProposalSerializer(proposal).data

        return Response(
            {
                "provider": result["provider"],
                "answer": result["answer"],
                "citations": result["citations"],
                "tool_trace": result["tool_trace"],
                "alternatives": result["alternatives"],
                "proposal": proposal_data,
            },
            status=status.HTTP_200_OK,
        )


class CopilotProposalListView(generics.ListAPIView):
    """List rebooking proposals for the authenticated customer (or all for Supervisors)."""

    permission_classes = [IsAuthenticated]
    serializer_class = RebookingProposalSerializer

    def get_queryset(self):
        qs = RebookingProposal.objects.select_related(
            "original_ticket__flight",
            "proposed_flight__origin",
            "proposed_flight__destination",
            "proposed_seat_type",
            "new_booking__discount",
        ).prefetch_related(
            "new_booking__tickets__flight__origin",
            "new_booking__tickets__flight__destination",
            "new_booking__tickets__passenger",
            "new_booking__tickets__seat_type",
            "new_booking__tickets__ticket_options__option",
        )
        if self.request.user.is_superuser or self.request.user.role == UserRole.SUPERVISOR:
            return qs
        return qs.filter(user=self.request.user)


class CopilotProposalConfirmView(APIView):
    """Human-in-the-loop confirmation endpoint that executes an approved RebookingProposal."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            proposal = confirm_rebooking_proposal(proposal_id=pk, actor=request.user)
        except CopilotActionError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        proposal = (
            RebookingProposal.objects.select_related(
                "original_ticket__flight",
                "proposed_flight__origin",
                "proposed_flight__destination",
                "proposed_seat_type",
                "new_booking__discount",
            )
            .prefetch_related(
                "new_booking__tickets__flight__origin",
                "new_booking__tickets__flight__destination",
                "new_booking__tickets__passenger",
                "new_booking__tickets__seat_type",
                "new_booking__tickets__ticket_options__option",
            )
            .get(pk=proposal.pk)
        )
        return Response(RebookingProposalSerializer(proposal).data, status=status.HTTP_200_OK)


class CopilotProposalRejectView(APIView):
    """Reject a pending AI RebookingProposal without modifying any booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            proposal = reject_rebooking_proposal(proposal_id=pk, actor=request.user)
        except CopilotActionError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        proposal = RebookingProposal.objects.select_related(
            "original_ticket__flight",
            "proposed_flight__origin",
            "proposed_flight__destination",
            "proposed_seat_type",
        ).get(pk=proposal.pk)
        return Response(RebookingProposalSerializer(proposal).data, status=status.HTTP_200_OK)
