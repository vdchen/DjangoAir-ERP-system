<template>
  <div class="row justify-content-center py-2">
    <div class="col-md-5">
      <div class="da-card p-4 p-md-5">
        <div class="small text-uppercase fw-bold text-primary mb-1" style="letter-spacing: 0.08em;">
          Passenger Self-Service
        </div>
        <h1 class="h4 fw-bold mb-2">Personal Cabinet</h1>
        <p class="text-muted small mb-4">
          Sign in with your emailed booking credentials or Google account to manage flights, balance, online check-in, QR PDF boarding passes, and the AI Disruption Copilot.
        </p>

        <form @submit.prevent="$emit('login')">
          <div class="mb-3">
            <label for="cabinet-email" class="form-label fw-semibold small">Email</label>
            <input id="cabinet-email" v-model="loginForm.email" type="email" class="form-control" required />
          </div>
          <div class="mb-3">
            <label for="cabinet-password" class="form-label fw-semibold small">Password</label>
            <input id="cabinet-password" v-model="loginForm.password" type="password" class="form-control" required />
          </div>
          <button id="cabinet-login-btn" type="submit" class="btn da-btn-primary w-100 py-2 mb-3" :disabled="loading">
            {{ loading ? "Signing in..." : "Sign In" }}
          </button>
        </form>

        <!-- Google OAuth2 Social Login -->
        <div v-if="googleConfig.enabled" class="border-top pt-3 mb-3">
          <button
            id="google-oauth-toggle-btn"
            type="button"
            class="btn btn-outline-dark w-100 d-flex align-items-center justify-content-center gap-2 fw-semibold"
            @click="showGooglePanel = !showGooglePanel"
          >
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
            </svg>
            Continue with Google
          </button>

          <div v-if="showGooglePanel" class="bg-light border rounded p-3 mt-2">
            <div v-if="googleConfig.dev_mock_enabled">
              <div class="small fw-semibold mb-2">Simulated Google Account Picker (Dev Mode)</div>
              <form @submit.prevent="$emit('google-mock')">
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
                <input
                  :value="googleIdToken"
                  class="form-control"
                  placeholder="Google ID Token"
                  @input="$emit('update:googleIdToken', $event.target.value)"
                />
                <button class="btn btn-dark" type="button" @click="$emit('google-token')">Verify</button>
              </div>
            </div>
          </div>
        </div>

        <div class="border-top pt-3 text-center">
          <small class="text-muted d-block mb-2">Want to try a seeded customer account?</small>
          <button id="fill-demo-customer-btn" class="btn btn-outline-secondary btn-sm" @click="$emit('fill-demo')">
            Fill Demo Customer (alice@example.com)
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "CabinetAuthCard",
  props: {
    loginForm: { type: Object, required: true },
    googleConfig: { type: Object, required: true },
    googleMock: { type: Object, required: true },
    googleIdToken: { type: String, default: "" },
    loading: { type: Boolean, default: false },
  },
  emits: ["login", "google-mock", "google-token", "fill-demo", "update:googleIdToken"],
  data() {
    return {
      showGooglePanel: false,
    };
  },
};
</script>
