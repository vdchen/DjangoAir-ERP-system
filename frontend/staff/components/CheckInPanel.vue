<template>
  <section class="row g-4">
    <div class="col-lg-5">
      <div class="da-card p-4">
        <h1 class="h5 fw-bold mb-2">Check-in Counter &amp; Luggage Fee</h1>
        <p class="small text-muted mb-3">
          Check in passengers, attach extra options (meals, luggage), and record overweight/checked luggage fees.
        </p>

        <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
        <div v-if="success" class="alert alert-success py-2 small">{{ success }}</div>

        <form @submit.prevent="submitCheckIn">
          <div class="mb-3">
            <label for="checkin-ticket-code" class="form-label fw-semibold">Ticket Code</label>
            <input
              id="checkin-ticket-code"
              v-model="form.ticket_code"
              type="text"
              class="form-control"
              placeholder="e.g. DA-ALICE101"
              required
            />
          </div>

          <div class="mb-3">
            <label class="form-label fw-semibold">Attach Additional Options</label>
            <div v-for="opt in options" :key="opt.id" class="form-check">
              <input
                :id="'ci-opt-' + opt.id"
                v-model="form.option_ids"
                class="form-check-input"
                type="checkbox"
                :value="opt.id"
              />
              <label :for="'ci-opt-' + opt.id" class="form-check-label small">
                {{ opt.name }} (+${{ opt.price }})
              </label>
            </div>
          </div>

          <div class="mb-3">
            <label for="checkin-luggage-fee" class="form-label fw-semibold">Extra Luggage Fee ($)</label>
            <input
              id="checkin-luggage-fee"
              v-model.number="form.luggage_fee"
              type="number"
              min="0"
              step="0.01"
              class="form-control"
            />
          </div>

          <button id="staff-checkin-submit" type="submit" class="btn da-btn-primary w-100" :disabled="loading">
            {{ loading ? "Processing..." : "Complete Check-in & Save Fees" }}
          </button>
        </form>
      </div>
    </div>

    <div class="col-lg-7">
      <div class="da-card p-4">
        <div class="d-flex justify-content-between align-items-center mb-3 gap-2">
          <h2 class="h6 fw-bold mb-0">Passenger Tickets</h2>
          <div class="input-group input-group-sm" style="max-width: 260px;">
            <input v-model="query" class="form-control" placeholder="Search ticket / flight / name" @keyup.enter="loadTickets" />
            <button class="btn btn-outline-primary" @click="loadTickets">Search</button>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Passenger</th>
                <th>Flight</th>
                <th>Options / Luggage</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tickets" :key="t.id">
                <td><span class="da-ticket-code">{{ t.ticket_code }}</span></td>
                <td>{{ t.passenger.full_name }}</td>
                <td>{{ t.flight_number }}</td>
                <td class="small">${{ t.options_total }} / ${{ t.luggage_fee }}</td>
                <td><span class="badge text-bg-secondary">{{ t.status }}</span></td>
                <td>
                  <button class="btn btn-link btn-sm p-0" @click="form.ticket_code = t.ticket_code">Select</button>
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
  name: "CheckInPanel",
  props: { api: { type: Object, required: true } },
  data() {
    return {
      query: "",
      tickets: [],
      options: [],
      form: {
        ticket_code: "",
        option_ids: [],
        luggage_fee: 0,
      },
      loading: false,
      error: "",
      success: "",
    };
  },
  async mounted() {
    await Promise.all([this.loadTickets(), this.loadOptions()]);
  },
  methods: {
    async loadTickets() {
      const qs = this.query.trim() ? `?q=${encodeURIComponent(this.query.trim())}` : "";
      this.tickets = await this.api.request(`/staff/tickets/${qs}`);
    },
    async loadOptions() {
      this.options = await this.api.request("/staff/options/");
    },
    async submitCheckIn() {
      this.error = "";
      this.success = "";
      this.loading = true;
      try {
        const res = await this.api.request("/staff/checkin/", {
          method: "POST",
          body: {
            ticket_code: this.form.ticket_code.trim(),
            option_ids: this.form.option_ids,
            luggage_fee: this.form.luggage_fee || 0,
          },
        });
        this.success = `Checked in ${res.passenger.full_name} (${res.ticket_code}). Options: $${res.options_total}, Luggage Fee: $${res.luggage_fee}.`;
        this.form.option_ids = [];
        this.form.luggage_fee = 0;
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
