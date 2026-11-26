<template>
  <div class="d-flex flex-column min-vh-100">
    <header class="da-navbar py-3 mb-4">
      <div class="container d-flex flex-wrap justify-content-between align-items-center gap-3">
        <a href="#" class="da-brand fs-4" @click.prevent="activeView = 'booking'">
          <span class="da-brand-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
            </svg>
          </span>
          <span>DjangoAir</span>
        </a>
        <nav class="d-flex align-items-center flex-wrap gap-2" aria-label="Customer navigation">
          <button
            id="nav-book-flights"
            class="btn da-nav-btn"
            :class="activeView === 'booking' ? 'btn-light text-dark' : 'btn-outline-light'"
            @click="activeView = 'booking'"
          >
            Book Flight
          </button>
          <button
            id="nav-personal-cabinet"
            class="btn da-nav-btn"
            :class="activeView === 'cabinet' ? 'btn-light text-dark' : 'btn-outline-light'"
            @click="activeView = 'cabinet'"
          >
            Personal Cabinet
          </button>
          <a href="/staff/" class="btn da-nav-btn btn-outline-warning ms-1">Staff Portal</a>
        </nav>
      </div>
    </header>

    <main class="container pb-5 flex-grow-1">
      <BookingFlow
        v-if="activeView === 'booking'"
        :api="api"
        @open-cabinet="openCabinetWithEmail"
      />
      <PersonalCabinet
        v-else
        :api="api"
        :prefill-email="prefillEmail"
      />
    </main>

    <footer class="da-footer py-3 mt-auto">
      <div class="container d-flex flex-wrap justify-content-between align-items-center gap-2">
        <span>DjangoAir ERP &bull; Precision Aviation Booking &amp; Operations</span>
        <div class="d-flex flex-wrap gap-3">
          <a href="/api/v1/docs/" target="_blank" rel="noopener">API Docs</a>
          <a href="/mobile-mock/" target="_blank" rel="noopener">Mobile WS</a>
          <a href="/mock-webhook/" target="_blank" rel="noopener">Webhook Inspector</a>
          <a href="/staff/">Staff Portal</a>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>
import { createApiClient } from "../shared/api";
import BookingFlow from "./components/BookingFlow.vue";
import PersonalCabinet from "./components/PersonalCabinet.vue";

export default {
  name: "CustomerApp",
  components: { BookingFlow, PersonalCabinet },
  data() {
    return {
      api: createApiClient("djangoair_customer_token"),
      activeView: "booking",
      prefillEmail: "",
    };
  },
  methods: {
    openCabinetWithEmail(email) {
      this.prefillEmail = email || "";
      this.activeView = "cabinet";
    },
  },
};
</script>
