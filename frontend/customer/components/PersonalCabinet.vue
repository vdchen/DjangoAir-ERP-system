<template>
  <section>
    <div v-if="error" class="alert alert-danger d-flex justify-content-between align-items-center">
      <span>{{ error }}</span>
      <button class="btn-close" @click="error = ''"></button>
    </div>
    <div v-if="success" class="alert alert-success d-flex justify-content-between align-items-center">
      <span>{{ success }}</span>
      <button class="btn-close" @click="success = ''"></button>
    </div>

    <!-- Login Card -->
    <div v-if="!overview" class="row justify-content-center">
      <div class="col-md-5">
        <div class="da-card p-4">
          <h1 class="h4 fw-bold mb-2">Personal Cabinet</h1>
          <p class="text-muted small mb-4">
            Sign in with your emailed booking credentials to view upcoming &amp; previous flights, balance, and complete online check-in.
          </p>

          <form @submit.prevent="login">
            <div class="mb-3">
              <label for="cabinet-email" class="form-label">Email</label>
              <input id="cabinet-email" v-model="loginForm.email" type="email" class="form-control" required />
            </div>
            <div class="mb-3">
              <label for="cabinet-password" class="form-label">Password</label>
              <input id="cabinet-password" v-model="loginForm.password" type="password" class="form-control" required />
            </div>
            <button id="cabinet-login-btn" type="submit" class="btn da-btn-primary w-100 mb-3" :disabled="loading">
              {{ loading ? "Signing in..." : "Sign In" }}
            </button>
          </form>

          <div class="border-top pt-3 text-center">
            <small class="text-muted d-block mb-2">Want to try a seeded customer account?</small>
            <button class="btn btn-outline-secondary btn-sm" @click="fillDemoCustomer">
              Fill Demo Customer (alice@example.com)
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Authenticated Personal Cabinet -->
    <div v-else>
      <div class="row g-4 mb-4">
        <div class="col-lg-8">
          <div class="da-card p-4 h-100 d-flex justify-content-between align-items-center flex-wrap gap-3">
            <div>
              <h1 class="h4 fw-bold mb-1">Welcome back, {{ overview.user.first_name || overview.user.email }}</h1>
              <div class="text-muted small">{{ overview.user.email }}</div>
            </div>
            <button class="btn btn-outline-secondary btn-sm" @click="logout">Sign Out</button>
          </div>
        </div>
        <div class="col-lg-4">
          <div class="da-card p-4 h-100">
            <div class="small text-muted">Account Balance</div>
            <div class="fs-3 fw-bold text-primary mb-2">${{ overview.balance }}</div>
            <div class="input-group input-group-sm">
              <input v-model.number="topUpAmount" type="number" min="10" class="form-control" />
              <button class="btn btn-outline-primary" @click="topUpBalance" :disabled="loading">
                + Top Up (Test Card)
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Upcoming Flights -->
      <div class="da-card p-4 mb-4">
        <h2 class="h5 fw-bold mb-3">Upcoming Flights &amp; Online Check-In</h2>
        <div v-if="!overview.upcoming_tickets.length" class="text-muted small">
          No upcoming flights found.
        </div>
        <div v-else class="row g-3">
          <div v-for="t in overview.upcoming_tickets" :key="t.id" class="col-md-6">
            <div class="da-boarding-pass p-3 h-100 d-flex flex-column justify-content-between">
              <div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="da-ticket-code">{{ t.ticket_code }}</span>
                  <span class="badge" :class="statusBadge(t.status)">{{ t.status }}</span>
                </div>
                <div class="fw-bold fs-5">{{ t.origin.code }} &rarr; {{ t.destination.code }} ({{ t.flight_number }})</div>
                <div class="small text-muted mb-2">
                  {{ formatDateTime(t.departure_time) }} &bull; Gate {{ t.gate }} &bull; Seat {{ t.seat_number }} ({{ t.seat_type.name }})
                </div>
                <div class="small">Passenger: <strong>{{ t.passenger.full_name }}</strong></div>
              </div>
              <div class="mt-3 pt-2 border-top d-flex justify-content-between align-items-center">
                <small class="text-muted">Booking {{ t.booking_reference }}</small>
                <button
                  v-if="t.status === 'PAID'"
                  class="btn da-btn-primary btn-sm"
                  @click="onlineCheckIn(t.ticket_code)"
                >
                  Online Check-In
                </button>
                <span v-else-if="t.status === 'CHECKED_IN'" class="text-success small fw-semibold">
                  Boarding Pass Ready
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Previous Flights -->
      <div class="da-card p-4">
        <h2 class="h5 fw-bold mb-3">Previous Flights</h2>
        <div v-if="!overview.previous_tickets.length" class="text-muted small">
          No previous flights yet.
        </div>
        <div v-else class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Flight</th>
                <th>Route</th>
                <th>Departure</th>
                <th>Seat</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in overview.previous_tickets" :key="t.id">
                <td><span class="da-ticket-code">{{ t.ticket_code }}</span></td>
                <td>{{ t.flight_number }}</td>
                <td>{{ t.origin.code }} &rarr; {{ t.destination.code }}</td>
                <td>{{ formatDateTime(t.departure_time) }}</td>
                <td>{{ t.seat_number }}</td>
                <td><span class="badge" :class="statusBadge(t.status)">{{ t.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { formatDateTime } from "../../shared/api";

export default {
  name: "PersonalCabinet",
  props: {
    api: { type: Object, required: true },
    prefillEmail: { type: String, default: "" },
  },
  data() {
    return {
      loading: false,
      error: "",
      success: "",
      overview: null,
      topUpAmount: 100,
      loginForm: {
        email: this.prefillEmail || "",
        password: "",
      },
    };
  },
  async mounted() {
    if (this.api.getToken()) {
      await this.loadOverview();
    }
  },
  methods: {
    formatDateTime,
    statusBadge(status) {
      const map = {
        PAID: "text-bg-primary",
        CHECKED_IN: "text-bg-success",
        BOARDED: "text-bg-dark",
        CANCELLED: "text-bg-danger",
        RESERVED: "text-bg-warning",
      };
      return map[status] || "text-bg-secondary";
    },
    fillDemoCustomer() {
      this.loginForm.email = "alice@example.com";
      this.loginForm.password = "Customer123!";
    },
    async login() {
      this.error = "";
      this.loading = true;
      try {
        const res = await this.api.request("/auth/login/", {
          method: "POST",
          body: this.loginForm,
        });
        this.api.setToken(res.access);
        await this.loadOverview();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    async loadOverview() {
      try {
        this.overview = await this.api.request("/cabinet/overview/");
      } catch (err) {
        this.api.setToken(null);
        this.overview = null;
      }
    },
    async onlineCheckIn(ticketCode) {
      this.error = "";
      this.success = "";
      try {
        await this.api.request(`/cabinet/tickets/${ticketCode}/check-in/`, { method: "POST" });
        this.success = `Online check-in completed for ticket ${ticketCode}!`;
        await this.loadOverview();
      } catch (err) {
        this.error = err.message;
      }
    },
    async topUpBalance() {
      this.error = "";
      this.success = "";
      this.loading = true;
      try {
        const res = await this.api.request("/cabinet/balance/top-up/", {
          method: "POST",
          body: {
            amount: this.topUpAmount,
            card_number: "4242424242424242",
            exp_month: 12,
            exp_year: 2030,
            cvv: "424",
          },
        });
        this.success = `Added $${res.credited_amount} to your balance.`;
        await this.loadOverview();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    logout() {
      this.api.setToken(null);
      this.overview = null;
      this.success = "";
    },
  },
};
</script>
