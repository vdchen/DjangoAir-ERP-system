<template>
  <div>
    <header class="da-navbar py-3 mb-4">
      <div class="container d-flex flex-wrap justify-content-between align-items-center gap-3">
        <a href="#" class="da-brand fs-4" @click.prevent="activeView = 'booking'">
          DjangoAir
        </a>
        <nav class="d-flex align-items-center gap-2">
          <button
            id="nav-book-flights"
            class="btn btn-sm"
            :class="activeView === 'booking' ? 'btn-light fw-semibold' : 'btn-outline-light'"
            @click="activeView = 'booking'"
          >
            Book Flight
          </button>
          <button
            id="nav-personal-cabinet"
            class="btn btn-sm"
            :class="activeView === 'cabinet' ? 'btn-light fw-semibold' : 'btn-outline-light'"
            @click="activeView = 'cabinet'"
          >
            Personal Cabinet
          </button>
          <a href="/staff/" class="btn btn-sm btn-outline-warning ms-2">Staff Portal</a>
        </nav>
      </div>
    </header>

    <main class="container pb-5">
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
