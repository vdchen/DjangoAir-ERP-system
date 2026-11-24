<template>
  <div>
    <header class="da-navbar py-3 mb-4">
      <div class="container d-flex flex-wrap justify-content-between align-items-center gap-3">
        <div class="d-flex align-items-center gap-2">
          <a href="/staff/" class="da-brand fs-4">DjangoAir Operations</a>
          <span class="badge text-bg-warning text-dark">Staff Portal</span>
        </div>

        <div class="d-flex align-items-center gap-2">
          <span v-if="user" class="text-white small me-2">
            {{ user.email }} &bull;
            <strong class="text-warning">{{ roleLabel(user.role) }}</strong>
          </span>
          <a href="/" class="btn btn-sm btn-outline-light">Customer Site</a>
          <button v-if="user" class="btn btn-sm btn-outline-danger" @click="logout">Sign Out</button>
        </div>
      </div>
    </header>

    <main class="container pb-5">
      <!-- Staff Login -->
      <div v-if="!user" class="row justify-content-center">
        <div class="col-md-5">
          <div class="da-card p-4">
            <h1 class="h4 fw-bold mb-2">Staff Sign In</h1>
            <p class="text-muted small mb-4">
              Access is granted strictly by ascending role hierarchy: Gate Manager &lt; Check-in Manager &lt; Supervisor.
            </p>

            <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>

            <form @submit.prevent="login">
              <div class="mb-3">
                <label for="staff-email" class="form-label">Staff Email</label>
                <input id="staff-email" v-model="loginForm.email" type="email" class="form-control" required />
              </div>
              <div class="mb-3">
                <label for="staff-password" class="form-label">Password</label>
                <input id="staff-password" v-model="loginForm.password" type="password" class="form-control" required />
              </div>
              <button id="staff-login-btn" type="submit" class="btn da-btn-primary w-100 mb-3" :disabled="loading">
                {{ loading ? "Authenticating..." : "Sign In to Operations" }}
              </button>
            </form>

            <div class="border-top pt-3">
              <small class="text-muted d-block mb-2 fw-semibold">Quick-Fill Demo Staff Roles:</small>
              <div class="d-grid gap-2">
                <button class="btn btn-outline-secondary btn-sm" @click="fillRole('gate@djangoair.local', 'Gate123!')">
                  Level 1 — Gate Manager (gate@djangoair.local)
                </button>
                <button class="btn btn-outline-primary btn-sm" @click="fillRole('checkin@djangoair.local', 'Checkin123!')">
                  Level 2 — Check-in Manager (checkin@djangoair.local)
                </button>
                <button class="btn btn-outline-dark btn-sm" @click="fillRole('supervisor@djangoair.local', 'Supervisor123!')">
                  Level 3 — Supervisor (supervisor@djangoair.local)
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Role-Gated Operations Workspace -->
      <div v-else>
        <ul class="nav nav-pills mb-4 gap-2">
          <li v-if="user.staff_rank >= 1" class="nav-item">
            <button
              class="nav-link"
              :class="{ active: activeTab === 'gate' }"
              @click="activeTab = 'gate'"
            >
              Gate Boarding (L1+)
            </button>
          </li>
          <li v-if="user.staff_rank >= 2" class="nav-item">
            <button
              class="nav-link"
              :class="{ active: activeTab === 'checkin' }"
              @click="activeTab = 'checkin'"
            >
              Check-in &amp; Luggage Counter (L2+)
            </button>
          </li>
          <li v-if="user.staff_rank >= 3" class="nav-item">
            <button
              class="nav-link"
              :class="{ active: activeTab === 'supervisor' }"
              @click="activeTab = 'supervisor'"
            >
              Supervisor Control (L3)
            </button>
          </li>
        </ul>

        <GatePanel v-if="activeTab === 'gate'" :api="api" />
        <CheckInPanel v-if="activeTab === 'checkin' && user.staff_rank >= 2" :api="api" />
        <SupervisorPanel v-if="activeTab === 'supervisor' && user.staff_rank >= 3" :api="api" />
      </div>
    </main>
  </div>
</template>

<script>
import { createApiClient } from "../shared/api";
import GatePanel from "./components/GatePanel.vue";
import CheckInPanel from "./components/CheckInPanel.vue";
import SupervisorPanel from "./components/SupervisorPanel.vue";

export default {
  name: "StaffApp",
  components: { GatePanel, CheckInPanel, SupervisorPanel },
  data() {
    return {
      api: createApiClient("djangoair_staff_token"),
      user: null,
      activeTab: "gate",
      loading: false,
      error: "",
      loginForm: { email: "", password: "" },
    };
  },
  async mounted() {
    if (this.api.getToken()) {
      await this.loadMe();
    }
  },
  methods: {
    roleLabel(role) {
      const labels = {
        GATE_MANAGER: "Gate Manager (L1)",
        CHECKIN_MANAGER: "Check-in Manager (L2)",
        SUPERVISOR: "Supervisor (L3)",
      };
      return labels[role] || role;
    },
    fillRole(email, password) {
      this.loginForm.email = email;
      this.loginForm.password = password;
    },
    async login() {
      this.error = "";
      this.loading = true;
      try {
        const res = await this.api.request("/auth/login/", {
          method: "POST",
          body: this.loginForm,
        });
        if (!res.user || res.user.staff_rank < 1) {
          this.error = "This portal is restricted to airline staff roles.";
          return;
        }
        this.api.setToken(res.access);
        this.user = res.user;
        this.selectDefaultTab();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    async loadMe() {
      try {
        const me = await this.api.request("/auth/me/");
        if (me.staff_rank >= 1) {
          this.user = me;
          this.selectDefaultTab();
        } else {
          this.api.setToken(null);
        }
      } catch {
        this.api.setToken(null);
      }
    },
    selectDefaultTab() {
      if (this.user.staff_rank >= 3) this.activeTab = "supervisor";
      else if (this.user.staff_rank >= 2) this.activeTab = "checkin";
      else this.activeTab = "gate";
    },
    logout() {
      this.api.setToken(null);
      this.user = null;
    },
  },
};
</script>
