<template>
  <div class="da-hero p-4 p-md-5">
    <div class="row align-items-center">
      <div class="col-lg-11 mx-auto">
        <div class="da-hero-eyebrow mb-2">Direct Routes &bull; Live Cabin Seat Maps &bull; Instant QR Boarding Passes</div>
        <h1 class="display-6 fw-bold mb-2">Where would you like to fly?</h1>
        <p class="opacity-75 mb-4" style="max-width: 60ch;">
          Search one-way or round-trip departures, lock exact cabin seats with 10-minute Redis holds, and manage check-in or AI disruption rebooking in your Personal Cabinet.
        </p>

        <form class="da-search-shell p-4 text-dark" @submit.prevent="$emit('search')">
          <div class="btn-group mb-3" role="group" aria-label="Trip type">
            <button
              id="trip-type-oneway"
              type="button"
              class="btn btn-sm"
              :class="search.tripType === 'one_way' ? 'btn-primary fw-semibold' : 'btn-outline-primary'"
              @click="search.tripType = 'one_way'"
            >
              One-Way
            </button>
            <button
              id="trip-type-roundtrip"
              type="button"
              class="btn btn-sm"
              :class="search.tripType === 'round_trip' ? 'btn-primary fw-semibold' : 'btn-outline-primary'"
              @click="search.tripType = 'round_trip'"
            >
              Round-Trip
            </button>
          </div>

          <div class="row g-3 align-items-end">
            <div v-if="search.tripType === 'round_trip'" class="col-md-3">
              <label for="search-origin" class="form-label fw-semibold small text-uppercase text-muted">Origin</label>
              <select
                id="search-origin"
                v-model="search.origin"
                class="form-select form-select-lg"
              >
                <option value="">Any origin</option>
                <option v-for="ap in airports" :key="ap.id" :value="ap.code">
                  {{ ap.city }} ({{ ap.code }})
                </option>
              </select>
            </div>
            <div :class="search.tripType === 'round_trip' ? 'col-md-3' : 'col-md-5'">
              <label for="search-destination" class="form-label fw-semibold small text-uppercase text-muted">Destination</label>
              <select
                id="search-destination"
                v-model="search.destination"
                class="form-select form-select-lg"
                required
              >
                <option value="" disabled>Select destination airport...</option>
                <option v-for="ap in airports" :key="ap.id" :value="ap.code">
                  {{ ap.city }} ({{ ap.code }}) — {{ ap.country }}
                </option>
              </select>
            </div>
            <div :class="search.tripType === 'round_trip' ? 'col-md-2' : 'col-md-4'">
              <label for="search-date" class="form-label fw-semibold small text-uppercase text-muted">Departure Date</label>
              <input
                id="search-date"
                v-model="search.date"
                type="date"
                class="form-control form-control-lg"
                required
              />
            </div>
            <div v-if="search.tripType === 'round_trip'" class="col-md-2">
              <label for="search-return-date" class="form-label fw-semibold small text-uppercase text-muted">Return Date</label>
              <input
                id="search-return-date"
                v-model="search.returnDate"
                type="date"
                class="form-control form-control-lg"
                :min="search.date"
                required
              />
            </div>
            <div :class="search.tripType === 'round_trip' ? 'col-md-2' : 'col-md-3'">
              <label for="search-passengers" class="form-label fw-semibold small text-uppercase text-muted">Passengers</label>
              <input
                id="search-passengers"
                v-model.number="search.passengers"
                type="number"
                min="1"
                max="9"
                class="form-control form-control-lg"
                required
              />
            </div>
          </div>

          <div class="d-flex justify-content-between align-items-center mt-4 flex-wrap gap-2">
            <small class="text-muted">
              Seeded daily departures run for the next 5 days — try <span class="da-route-code">JFK &harr; LHR</span> or <span class="da-route-code">JFK &harr; CDG</span>.
            </small>
            <button id="search-submit-btn" type="submit" class="btn da-btn-primary btn-lg px-4" :disabled="loading">
              {{ loading ? "Searching..." : "Find Flights" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "BookingSearchHero",
  props: {
    search: { type: Object, required: true },
    airports: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  emits: ["search"],
};
</script>
