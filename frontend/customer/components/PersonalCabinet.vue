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
            Sign in with your emailed booking credentials or Google account to view upcoming &amp; previous flights, balance, online check-in, and QR PDF boarding passes.
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

          <!-- Optional #2: Google OAuth2 Social Login -->
          <div v-if="googleConfig.enabled" class="border-top pt-3 mb-3">
            <button
              id="google-oauth-toggle-btn"
              type="button"
              class="btn btn-outline-dark w-100 d-flex align-items-center justify-content-center gap-2 fw-semibold"
              @click="showGooglePanel = !showGooglePanel"
            >
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
              </svg>
              Continue with Google
            </button>

            <div v-if="showGooglePanel" class="bg-light border rounded p-3 mt-2">
              <div v-if="googleConfig.dev_mock_enabled">
                <div class="small fw-semibold mb-2">Simulated Google Account Picker (Dev Mode)</div>
                <form @submit.prevent="loginWithGoogleMock">
                  <div class="mb-2">
                    <input
                      id="google-mock-email"
                      v-model="googleMock.email"
                      type="email"
                      class="form-control form-control-sm"
                      placeholder="traveler@gmail.com"
                      required
                    />
                  </div>
                  <div class="row g-2 mb-2">
                    <div class="col-6">
                      <input v-model="googleMock.first_name" class="form-control form-control-sm" placeholder="First name" />
                    </div>
                    <div class="col-6">
                      <input v-model="googleMock.last_name" class="form-control form-control-sm" placeholder="Last name" />
                    </div>
                  </div>
                  <button id="google-mock-submit-btn" type="submit" class="btn btn-dark btn-sm w-100" :disabled="loading">
                    Sign In with Google Account
                  </button>
                </form>
              </div>
              <div v-else>
                <div class="small text-muted mb-2">Paste your Google OAuth2 ID token:</div>
                <div class="input-group input-group-sm">
                  <input v-model="googleIdToken" class="form-control" placeholder="Google ID Token" />
                  <button class="btn btn-dark" type="button" @click="loginWithGoogleToken">Verify</button>
                </div>
              </div>
            </div>
          </div>

          <div class="border-top pt-3 text-center">
            <small class="text-muted d-block mb-2">Want to try a seeded customer account?</small>
            <button id="fill-demo-customer-btn" class="btn btn-outline-secondary btn-sm" @click="fillDemoCustomer">
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
              <div class="mt-3 pt-2 border-top d-flex justify-content-between align-items-center flex-wrap gap-2">
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
import CopilotAssistant from "./CopilotAssistant.vue";

export default {
  name: "PersonalCabinet",
  components: { CopilotAssistant },
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
      showGooglePanel: false,
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
        this.showGooglePanel = false;
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
        this.showGooglePanel = false;
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
