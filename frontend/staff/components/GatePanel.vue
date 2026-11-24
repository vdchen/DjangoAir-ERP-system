<template>
  <section class="row g-4">
    <div class="col-lg-5">
      <div class="da-card p-4">
        <h1 class="h5 fw-bold mb-2">Gate Boarding Scanner</h1>
        <p class="small text-muted mb-3">
          Enter or scan a passenger's <code>ticket_code</code> to verify check-in status and register boarding.
        </p>

        <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
        <div v-if="success" class="alert alert-success py-2 small">{{ success }}</div>

        <form @submit.prevent="boardPassenger">
          <div class="mb-3">
            <label for="gate-ticket-code" class="form-label fw-semibold">Ticket Code</label>
            <input
              id="gate-ticket-code"
              v-model="ticketCode"
              type="text"
              class="form-control form-control-lg"
              placeholder="e.g. DA-ALICE101"
              required
            />
          </div>
          <div class="d-flex gap-2">
            <button type="button" class="btn btn-outline-primary" @click="lookupTicket">Inspect Ticket</button>
            <button id="gate-board-btn" type="submit" class="btn da-btn-primary flex-grow-1" :disabled="loading">
              {{ loading ? "Boarding..." : "Register Boarding" }}
            </button>
          </div>
        </form>

        <div v-if="inspectedTicket" class="border-top mt-4 pt-3 small">
          <div class="d-flex justify-content-between mb-1">
            <span class="da-ticket-code">{{ inspectedTicket.ticket_code }}</span>
            <span class="badge text-bg-info">{{ inspectedTicket.status }}</span>
          </div>
          <div><strong>{{ inspectedTicket.passenger.full_name }}</strong> ({{ inspectedTicket.passenger.document_number }})</div>
          <div class="text-muted">
            Flight {{ inspectedTicket.flight_number }} &bull; Gate {{ inspectedTicket.gate }} &bull; Seat {{ inspectedTicket.seat_number }}
          </div>
        </div>
      </div>
    </div>

    <div class="col-lg-7">
      <div class="da-card p-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2 class="h6 fw-bold mb-0">Recent Tickets</h2>
          <button class="btn btn-outline-secondary btn-sm" @click="loadTickets">Refresh</button>
        </div>
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th>Ticket Code</th>
                <th>Passenger</th>
                <th>Flight / Gate</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tickets" :key="t.id">
                <td><span class="da-ticket-code">{{ t.ticket_code }}</span></td>
                <td>{{ t.passenger.full_name }}</td>
                <td>{{ t.flight_number }} (Gate {{ t.gate }})</td>
                <td><span class="badge text-bg-secondary">{{ t.status }}</span></td>
                <td>
                  <button class="btn btn-link btn-sm p-0" @click="selectTicket(t)">Use</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: "GatePanel",
  props: { api: { type: Object, required: true } },
  data() {
    return {
      ticketCode: "",
      inspectedTicket: null,
      tickets: [],
      loading: false,
      error: "",
      success: "",
    };
  },
  async mounted() {
    await this.loadTickets();
  },
  methods: {
    async loadTickets() {
      try {
        this.tickets = await this.api.request("/staff/tickets/");
      } catch (err) {
        this.error = err.message;
      }
    },
    selectTicket(t) {
      this.ticketCode = t.ticket_code;
      this.inspectedTicket = t;
      this.error = "";
      this.success = "";
    },
    async lookupTicket() {
      if (!this.ticketCode.trim()) return;
      this.error = "";
      this.success = "";
      try {
        this.inspectedTicket = await this.api.request(
          `/staff/tickets/${encodeURIComponent(this.ticketCode.trim())}/`
        );
      } catch (err) {
        this.inspectedTicket = null;
        this.error = err.message;
      }
    },
    async boardPassenger() {
      this.error = "";
      this.success = "";
      this.loading = true;
      try {
        const res = await this.api.request("/staff/gate/board/", {
          method: "POST",
          body: { ticket_code: this.ticketCode.trim() },
        });
        this.inspectedTicket = res;
        this.success = `Passenger ${res.passenger.full_name} (${res.ticket_code}) boarded at Gate ${res.gate}.`;
        await this.loadTickets();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>
