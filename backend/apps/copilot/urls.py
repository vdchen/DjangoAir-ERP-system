from django.urls import path

from .views import (
    CopilotAssistView,
    CopilotConfigView,
    CopilotProposalConfirmView,
    CopilotProposalListView,
    CopilotProposalRejectView,
)

urlpatterns = [
    path("copilot/config/", CopilotConfigView.as_view(), name="copilot-config"),
    path("copilot/assist/", CopilotAssistView.as_view(), name="copilot-assist"),
    path("copilot/proposals/", CopilotProposalListView.as_view(), name="copilot-proposals"),
    path(
        "copilot/proposals/<uuid:pk>/confirm/",
        CopilotProposalConfirmView.as_view(),
        name="copilot-proposal-confirm",
    ),
    path(
        "copilot/proposals/<uuid:pk>/reject/",
        CopilotProposalRejectView.as_view(),
        name="copilot-proposal-reject",
    ),
]
