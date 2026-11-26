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

    <!-- Unauthenticated Sign-In & Google OAuth2 -->
    <CabinetAuthCard
      v-if="!overview"
      :login-form="loginForm"
      :google-config="googleConfig"
      :google-mock="googleMock"
      v-model:google-id-token="googleIdToken"
      :loading="loading"
      @login="login"
      @google-mock="loginWithGoogleMock"
      @google-token="loginWithGoogleToken"
      @fill-demo="fillDemoCustomer"
    />

    <!-- Authenticated Personal Cabinet -->
    <div v-else>
      <div class="row g-4 mb-4">
        <div class="col-lg-8">
          <div class="da-card p-4 h-100 d-flex justify-content-between align-items-center flex-wrap gap-3">
            <div>
              <div class="small text-uppercase fw-bold text-muted" style="letter-spacing: 0.06em;">
                Personal Cabinet
              </div>
              <h1 class="h4 fw-bold mb-1">
                Welcome back, {{ overview.user.first_name || overview.user.email }}
                <span
                  v-if="overview.user.social_providers && overview.user.social_providers.includes('GOOGLE')"
                  class="badge text-bg-light border text-dark ms-2 align-middle"
                  style="font-size: 0.72rem;"
                >
                  Google Connected
                </span>
              </h1>
              <div class="text-muted small">{{ overview.user.email }}</div>
            </div>
            <button id="cabinet-signout-btn" class="btn btn-outline-secondary btn-sm" @click="logout">Sign Out</button>
          </div>
        </div>
        <div class="col-lg-4">
          <div class="da-card p-4 h-100">
            <div class="small text-uppercase fw-bold text-muted" style="letter-spacing: 0.06em;">Account Balance</div>
            <div class="fs-3 fw-bold text-primary mb-2">${{ overview.balance }}</div>
            <div class="input-group input-group-sm">
              <input v-model.number="topUpAmount" type="number" min="10" class="form-control" />
              <button class="btn btn-outline-primary fw-semibold" :disabled="loading" @click="topUpBalance">
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
                <div class="fw-bold fs-5 da-route-code">
                  {{ t.origin.code }} &rarr; {{ t.destination.code }}
                  <span class="fs-6 fw-normal text-muted ms-1">({{ t.flight_number }})</span>
                </div>
                <div class="small text-muted mb-2">
                  {{ formatDateTime(t.departure_time) }} &bull; Gate {{ t.gate }} &bull; Seat {{ t.seat_number }} ({{ t.seat_type.name }})
                </div>
                <div class="small">Passenger: <strong>{{ t.passenger.full_name }}</strong></div>
              </div>
              <div class="da-boarding-divider mt-3 pt-2 d-flex justify-content-between align-items-center flex-wrap gap-2">
                <small class="text-muted">Booking {{ t.booking_reference }}</small>
                <div class="d-flex gap-2 align-items-center">
                  <button
                    v-if="t.status !== 'CANCELLED'"
                    class="btn btn-outline-secondary btn-sm"
                    @click="downloadBoardingPass(t.ticket_code)"
                  >
                    PDF Boarding Pass (QR)
                  </button>
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
      </div>

      <!-- AI Disruption & Rebooking Copilot -->
      <CopilotAssistant :api="api" @rebooked="loadOverview" />

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
                <td class="fw-semibold">{{ t.flight_number }}</td>
                <td class="da-route-code small">{{ t.origin.code }} &rarr; {{ t.destination.code }}</td>
                <td class="small">{{ formatDateTime(t.departure_time) }}</td>
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
import CabinetAuthCard from "./CabinetAuthCard.vue";
import CopilotAssistant from "./CopilotAssistant.vue";

export default {
  name: "PersonalCabinet",
  components: { CabinetAuthCard, CopilotAssistant },
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
      googleConfig: {
        enabled: false,
        client_id: "",
        dev_mock_enabled: false,
      },
      googleMock: {
        email: "google.traveler@gmail.com",
        first_name: "Elena",
        last_name: "Sky",
      },
      googleIdToken: "",
    };
  },
  async mounted() {
    try {
      this.googleConfig = await this.api.request("/auth/google/config/");
    } catch {
      this.googleConfig.enabled = false;
    }
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
    async loginWithGoogleMock() {
      this.error = "";
      this.loading = true;
      try {
        const res = await this.api.request("/auth/google/", {
          method: "POST",
          body: { dev_mock: true, ...this.googleMock },
        });
        this.api.setToken(res.access);
        this.success = "Signed in with Google successfully.";
        await this.loadOverview();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    async loginWithGoogleToken() {
      if (!this.googleIdToken.trim()) return;
      this.error = "";
      this.loading = true;
      try {
        const res = await this.api.request("/auth/google/", {
          method: "POST",
          body: { id_token: this.googleIdToken.trim() },
        });
        this.api.setToken(res.access);
        this.success = "Signed in with Google successfully.";
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
      } catch {
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
    async downloadBoardingPass(ticketCode) {
      this.error = "";
      try {
        await this.api.downloadBlob(
          `/cabinet/tickets/${ticketCode}/boarding-pass.pdf`,
          `boarding-pass-${ticketCode}.pdf`
        );
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
