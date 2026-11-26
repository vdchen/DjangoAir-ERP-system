<template>
  <div class="da-card p-4 mb-4 border-primary-subtle">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <div>
        <span class="badge text-bg-primary me-2">AI Copilot</span>
        <span class="h5 fw-bold mb-0 align-middle">Disruption &amp; Rebooking Assistant</span>
        <div class="small text-muted mt-1">
          Tool-calling + Airline Policy RAG with mandatory Human-in-the-Loop approval before any booking changes.
        </div>
      </div>
      <span v-if="config" class="badge text-bg-light border text-dark">
        Provider: {{ config.provider }} &bull; {{ config.policy_chunks_indexed }} policy clauses indexed
      </span>
    </div>

    <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
    <div v-if="notice" class="alert alert-success py-2 small">{{ notice }}</div>

    <!-- Quick Prompt Chips -->
    <div class="d-flex flex-wrap gap-2 mb-3">
      <button
        id="copilot-chip-rebook"
        type="button"
        class="btn btn-outline-primary btn-sm"
        :disabled="loading"
        @click="askPrompt('My flight was disrupted or I need to rebook to an alternative flight.')"
      >
        Find Rebooking Options
      </button>
      <button
        id="copilot-chip-policy"
        type="button"
        class="btn btn-outline-secondary btn-sm"
        :disabled="loading"
        @click="askPrompt('What is the refund and compensation policy for a cancelled flight?')"
      >
        Cancellation &amp; Refund Policy
      </button>
      <button
        type="button"
        class="btn btn-outline-secondary btn-sm"
        :disabled="loading"
        @click="askPrompt('What are the carry-on baggage and check-in gate deadlines?')"
      >
        Baggage &amp; Gate Rules
      </button>
    </div>

    <!-- Prompt Form -->
    <form class="input-group mb-3" @submit.prevent="submitPrompt">
      <input
        id="copilot-message-input"
        v-model="message"
        type="text"
        class="form-control"
        placeholder="Ask about cancelled flight rebooking, refund policies, baggage, or check-in..."
        required
      />
      <button id="copilot-send-btn" type="submit" class="btn da-btn-primary" :disabled="loading">
        {{ loading ? "Analyzing..." : "Ask Copilot" }}
      </button>
    </form>

    <!-- Copilot Response -->
    <div v-if="response" class="bg-light rounded p-3 mb-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <strong class="small text-primary">Copilot Response ({{ response.provider }})</strong>
        <button
          type="button"
          class="btn btn-link btn-sm p-0 text-decoration-none"
          @click="showTrace = !showTrace"
        >
          {{ showTrace ? "Hide Tool Trace" : `Inspect Tool Trace (${response.tool_trace.length})` }}
        </button>
      </div>
      <div class="small" style="white-space: pre-line;">{{ response.answer }}</div>

      <!-- RAG Policy Citations -->
      <div v-if="response.citations && response.citations.length" class="mt-3 pt-2 border-top">
        <div class="small fw-semibold text-muted mb-1">Cited Airline Policy Clauses (RAG)</div>
        <div class="d-flex flex-wrap gap-1">
          <span
            v-for="(c, idx) in response.citations"
            :key="idx"
            class="badge text-bg-light border text-dark fw-normal"
            :title="c.excerpt"
          >
            {{ c.source }} &rsaquo; {{ c.section }} ({{ c.score }})
          </span>
        </div>
      </div>

      <!-- Tool Call Trace Inspector -->
      <div v-if="showTrace && response.tool_trace.length" class="mt-2 pt-2 border-top">
        <pre class="small bg-dark text-light p-2 rounded mb-0" style="max-height: 180px; overflow: auto;">{{ JSON.stringify(response.tool_trace, null, 2) }}</pre>
      </div>
    </div>

    <!-- Human-in-the-Loop Rebooking Proposal Card -->
    <div
      v-if="activeProposal"
      class="border rounded p-3"
      :class="activeProposal.status === 'CONFIRMED' ? 'border-success bg-success-subtle' : 'border-warning bg-warning-subtle'"
    >
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
        <div>
          <span
            class="badge mb-1"
            :class="
              activeProposal.status === 'CONFIRMED'
                ? 'text-bg-success'
                : activeProposal.status === 'REJECTED'
                  ? 'text-bg-secondary'
                  : 'text-bg-warning text-dark'
            "
          >
            {{ activeProposal.status }}
          </span>
          <h3 class="h6 fw-bold mb-1">
            Proposed Rebooking: {{ activeProposal.original_flight_number }} &rarr; {{ activeProposal.proposed_flight_number }}
          </h3>
          <div class="small text-muted">
            Route: {{ activeProposal.proposed_origin }} &rarr; {{ activeProposal.proposed_destination }} &bull;
            Departure: {{ formatDateTime(activeProposal.proposed_departure_time) }} &bull;
            Cabin: {{ activeProposal.proposed_seat_type_name }}
          </div>
          <div class="small mt-1">
            <strong>Fare Difference:</strong>
            <span v-if="activeProposal.fee_waived" class="text-success fw-bold">
              $0.00 (Involuntary Cancellation Waiver)
            </span>
            <span v-else>${{ activeProposal.fare_difference }}</span>
          </div>
          <div v-if="activeProposal.new_booking" class="small text-success fw-semibold mt-1">
            New Booking Issued: {{ activeProposal.new_booking.booking_reference }}
            (Ticket {{ activeProposal.new_booking.tickets[0]?.ticket_code }})
          </div>
        </div>

        <div v-if="activeProposal.status === 'PENDING_CONFIRMATION'" class="d-flex gap-2">
          <button
            id="copilot-confirm-proposal-btn"
            type="button"
            class="btn btn-success btn-sm"
            :disabled="confirming"
            @click="confirmProposal(activeProposal.id)"
          >
            {{ confirming ? "Confirming..." : "Approve & Confirm Rebooking" }}
          </button>
          <button
            id="copilot-reject-proposal-btn"
            type="button"
            class="btn btn-outline-danger btn-sm"
            :disabled="confirming"
            @click="rejectProposal(activeProposal.id)"
          >
            Decline
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDateTime } from "../../shared/api";

export default {
  name: "CopilotAssistant",
  props: {
    api: { type: Object, required: true },
  },
  emits: ["rebooked"],
  data() {
    return {
      config: null,
      message: "",
      loading: false,
      confirming: false,
      error: "",
      notice: "",
      response: null,
      activeProposal: null,
      showTrace: false,
    };
  },
  async mounted() {
    try {
      this.config = await this.api.request("/copilot/config/");
    } catch (_err) {
      // Optional banner metadata
    }
  },
  methods: {
    formatDateTime,
    askPrompt(text) {
      this.message = text;
      this.submitPrompt();
    },
    async submitPrompt() {
      if (!this.message.trim()) return;
      this.error = "";
      this.notice = "";
      this.loading = true;
      try {
        const res = await this.api.request("/copilot/assist/", {
          method: "POST",
          body: { message: this.message.trim() },
        });
        this.response = res;
        this.activeProposal = res.proposal || null;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    async confirmProposal(proposalId) {
      this.error = "";
      this.notice = "";
      this.confirming = true;
      try {
        const updated = await this.api.request(`/copilot/proposals/${proposalId}/confirm/`, {
          method: "POST",
        });
        this.activeProposal = updated;
        this.notice = `Rebooking confirmed! New booking ${updated.new_booking?.booking_reference || ""} is now PAID.`;
        this.$emit("rebooked");
      } catch (err) {
        this.error = err.message;
      } finally {
        this.confirming = false;
      }
    },
    async rejectProposal(proposalId) {
      this.error = "";
      this.notice = "";
      this.confirming = true;
      try {
        const updated = await this.api.request(`/copilot/proposals/${proposalId}/reject/`, {
          method: "POST",
        });
        this.activeProposal = updated;
        this.notice = "Rebooking proposal declined. Your original booking was not modified.";
      } catch (err) {
        this.error = err.message;
      } finally {
        this.confirming = false;
      }
    },
  },
};
</script>
