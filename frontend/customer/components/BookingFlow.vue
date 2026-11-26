<template>
  <section>
    <!-- Progress Stepper -->
    <div class="da-stepper mb-4">
      <span class="da-step" :class="stepClass(1)">1. Search Flight</span>
      <span class="da-step" :class="stepClass(2)">2. Seats &amp; Options</span>
      <span class="da-step" :class="stepClass(3)">3. Passenger &amp; Payment</span>
      <span class="da-step" :class="stepClass(4)">4. Tickets &amp; Confirmation</span>
    </div>

    <div v-if="error" class="alert alert-danger d-flex justify-content-between align-items-center">
      <span>{{ error }}</span>
      <button class="btn-close" @click="error = ''"></button>
    </div>

    <!-- STEP 1: Search Hero -->
    <BookingSearchHero
      v-if="step === 1"
      :search="search"
      :airports="airports"
      :loading="loading"
      @search="searchFlights"
    />

    <!-- STEP 2: Flights, Cabin Classes, Seat Map & Options -->
    <div v-if="step === 2">
      <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
        <h1 class="h4 fw-bold mb-0">
          Available Flights to <span class="da-route-code">{{ search.destination }}</span> on {{ search.date }}
          <span v-if="search.tripType === 'round_trip'" class="badge text-bg-info ms-2">
            Round-Trip (Return {{ search.returnDate }})
          </span>
          <span class="text-muted fw-normal fs-6 ms-1">
            ({{ search.passengers }} passenger{{ search.passengers > 1 ? "s" : "" }})
          </span>
        </h1>
        <button class="btn btn-outline-secondary btn-sm" @click="step = 1">Change Search</button>
      </div>

      <div v-if="!flights.length" class="da-card p-5 text-center">
        <h2 class="h5 fw-semibold">No scheduled flights matched your date and destination.</h2>
        <p class="text-muted mb-3">Try selecting tomorrow's date or another destination airport.</p>
        <button class="btn da-btn-primary" @click="step = 1">Back to Search</button>
      </div>

      <div v-else class="row g-4">
        <div class="col-lg-8">
          <h2 v-if="search.tripType === 'round_trip'" class="h6 text-uppercase text-muted fw-bold mb-2">
            Outbound Flights
          </h2>
          <div
            v-for="flight in flights"
            :key="flight.id"
            class="da-card da-card-hover p-4 mb-3"
          >
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
              <div>
                <span class="badge text-bg-primary me-2">{{ flight.flight_number }}</span>
                <span class="fw-bold fs-5 da-route-code">{{ flight.origin.code }} &rarr; {{ flight.destination.code }}</span>
                <div class="text-muted small mt-1">
                  {{ flight.origin.city }} to {{ flight.destination.city }} &bull;
                  {{ formatDateTime(flight.departure_time) }} &rarr; {{ formatDateTime(flight.arrival_time) }} &bull;
                  {{ flight.airplane.model_name }} (Gate {{ flight.gate }})
                </div>
              </div>
              <div class="text-end">
                <div class="small text-muted">Starting from</div>
                <div class="fs-4 fw-bold text-primary">${{ flight.base_price }}</div>
              </div>
            </div>

            <div class="row g-2 mb-3">
              <div v-for="seat in flight.seat_availability" :key="seat.seat_type_id" class="col-md-4">
                <div
                  class="da-seat-card p-3 h-100"
                  :class="{
                    selected:
                      selectedFlight &&
                      selectedFlight.id === flight.id &&
                      selectedSeat &&
                      selectedSeat.seat_type_id === seat.seat_type_id,
                    'opacity-50': seat.available_seats < search.passengers,
                  }"
                  @click="seat.available_seats >= search.passengers && selectFlightSeat(flight, seat)"
                >
                  <div class="d-flex justify-content-between align-items-center">
                    <span class="fw-semibold">{{ seat.seat_type_name }}</span>
                    <span class="fw-bold text-primary">${{ seat.unit_price }}</span>
                  </div>
                  <div class="small text-muted mt-1">
                    {{ seat.available_seats }} of {{ seat.total_seats }} seats left
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selectedFlight && selectedFlight.id === flight.id" class="border-top pt-3">
              <h3 class="h6 fw-semibold mb-2">Optional Extras (per passenger)</h3>
              <div class="row g-2">
                <div v-for="opt in flight.options" :key="opt.id" class="col-md-6">
                  <label class="d-flex align-items-start gap-2 border rounded p-2 h-100 bg-light-subtle" style="cursor: pointer;">
                    <input
                      v-model="selectedOptionIds"
                      type="checkbox"
                      class="form-check-input mt-1"
                      :value="opt.id"
                    />
                    <div class="flex-grow-1">
                      <div class="d-flex justify-content-between">
                        <span class="fw-semibold small">{{ opt.name }}</span>
                        <span class="small fw-bold">+${{ opt.price }}</span>
                      </div>
                      <div class="text-muted" style="font-size: 0.78rem;">{{ opt.description }}</div>
                    </div>
                  </label>
                </div>
              </div>

              <SeatMapPicker
                v-if="selectedSeat"
                v-model="selectedSeatNumbers"
                v-model:hold-token="holdToken"
                :api="api"
                :flight-id="flight.id"
                :seat-type-id="selectedSeat.seat_type_id"
                :seat-type-name="selectedSeat.seat_type_name"
                :passenger-count="search.passengers"
              />
            </div>
          </div>

          <!-- Return Flights Section (Round-Trip Mode) -->
          <div v-if="search.tripType === 'round_trip'" class="mt-4">
            <h2 class="h6 text-uppercase text-muted fw-bold mb-2">
              Return Flights on {{ search.returnDate }}
            </h2>
            <div v-if="!returnFlights.length" class="da-card p-4 text-center text-muted">
              No scheduled return flights matched {{ search.returnDate }}. Try a different return date.
            </div>
            <div
              v-for="rflight in returnFlights"
              :key="rflight.id"
              class="da-card da-card-hover p-4 mb-3"
            >
              <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                <div>
                  <span class="badge text-bg-info me-2">{{ rflight.flight_number }}</span>
                  <span class="fw-bold fs-5 da-route-code">{{ rflight.origin.code }} &rarr; {{ rflight.destination.code }}</span>
                  <div class="text-muted small mt-1">
                    {{ rflight.origin.city }} to {{ rflight.destination.city }} &bull;
                    {{ formatDateTime(rflight.departure_time) }} &rarr; {{ formatDateTime(rflight.arrival_time) }} &bull;
                    {{ rflight.airplane.model_name }} (Gate {{ rflight.gate }})
                  </div>
                </div>
                <div class="text-end">
                  <div class="small text-muted">Starting from</div>
                  <div class="fs-4 fw-bold text-primary">${{ rflight.base_price }}</div>
                </div>
              </div>

              <div class="row g-2 mb-3">
                <div v-for="seat in rflight.seat_availability" :key="seat.seat_type_id" class="col-md-4">
                  <div
                    class="da-seat-card da-return-seat-card p-3 h-100"
                    :class="{
                      selected:
                        selectedReturnFlight &&
                        selectedReturnFlight.id === rflight.id &&
                        selectedReturnSeat &&
                        selectedReturnSeat.seat_type_id === seat.seat_type_id,
                      'opacity-50': seat.available_seats < search.passengers,
                    }"
                    @click="seat.available_seats >= search.passengers && selectReturnFlightSeat(rflight, seat)"
                  >
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="fw-semibold">{{ seat.seat_type_name }}</span>
                      <span class="fw-bold text-primary">${{ seat.unit_price }}</span>
                    </div>
                    <div class="small text-muted mt-1">
                      {{ seat.available_seats }} of {{ seat.total_seats }} seats left
                    </div>
                  </div>
                </div>
              </div>

              <SeatMapPicker
                v-if="selectedReturnFlight && selectedReturnFlight.id === rflight.id && selectedReturnSeat"
                v-model="selectedReturnSeatNumbers"
                v-model:hold-token="returnHoldToken"
                :api="api"
                :flight-id="rflight.id"
                :seat-type-id="selectedReturnSeat.seat_type_id"
                :seat-type-name="`Return: ${selectedReturnSeat.seat_type_name}`"
                :passenger-count="search.passengers"
              />
            </div>
          </div>
        </div>

        <!-- Order Summary Sidebar -->
        <div class="col-lg-4">
          <div class="da-card p-4 position-sticky" style="top: 1.5rem;">
            <h2 class="h5 fw-bold mb-3">Fare Summary</h2>
            <div v-if="!selectedFlight || !selectedSeat" class="text-muted small">
              Select a flight and seat class on the left to configure options and continue.
            </div>
            <div v-else>
              <div class="d-flex justify-content-between small mb-2">
                <span>{{ selectedFlight.flight_number }} ({{ selectedSeat.seat_type_name }}) &times; {{ search.passengers }}</span>
                <strong>${{ outboundFareSubtotal.toFixed(2) }}</strong>
              </div>
              <div v-if="selectedSeatNumbers.length" class="small text-success mb-2">
                Outbound Seats: <strong>{{ selectedSeatNumbers.join(", ") }}</strong>
              </div>

              <div v-if="selectedReturnFlight && selectedReturnSeat" class="d-flex justify-content-between small mb-2">
                <span>{{ selectedReturnFlight.flight_number }} ({{ selectedReturnSeat.seat_type_name }}) &times; {{ search.passengers }}</span>
                <strong>${{ returnFareSubtotal.toFixed(2) }}</strong>
              </div>
              <div v-if="selectedReturnSeatNumbers.length" class="small text-success mb-2">
                Return Seats: <strong>{{ selectedReturnSeatNumbers.join(", ") }}</strong>
              </div>

              <div class="d-flex justify-content-between small mb-2">
                <span>Selected Options &times; {{ search.passengers }}<span v-if="selectedReturnFlight"> &times; 2 legs</span></span>
                <strong>${{ optionsSubtotal.toFixed(2) }}</strong>
              </div>

              <div class="input-group input-group-sm my-3">
                <input
                  v-model="discountCode"
                  type="text"
                  class="form-control"
                  placeholder="Promo code (e.g. WELCOME10)"
                />
                <button class="btn btn-outline-primary" type="button" @click="applyDiscount">Apply</button>
              </div>

              <div v-if="discountPreview > 0" class="d-flex justify-content-between small text-success mb-2">
                <span>Discount ({{ discountCode.toUpperCase() }})</span>
                <strong>-${{ discountPreview.toFixed(2) }}</strong>
              </div>

              <hr />
              <div class="d-flex justify-content-between fs-5 fw-bold mb-3">
                <span>Estimated Total</span>
                <span class="text-primary">${{ estimatedTotal.toFixed(2) }}</span>
              </div>

              <button
                id="continue-checkout-btn"
                class="btn da-btn-primary w-100 py-2"
                :disabled="search.tripType === 'round_trip' && (!selectedReturnFlight || !selectedReturnSeat)"
                @click="proceedToCheckout"
              >
                {{
                  search.tripType === "round_trip" && (!selectedReturnFlight || !selectedReturnSeat)
                    ? "Select Return Flight to Continue"
                    : "Continue to Passenger & Payment"
                }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- STEP 3: Passenger Details + Payment Step -->
    <div v-if="step === 3">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h4 fw-bold mb-0">Passenger Details &amp; Payment</h1>
        <button class="btn btn-outline-secondary btn-sm" @click="step = 2">Back to Flights</button>
      </div>

      <form @submit.prevent="submitBookingAndPay">
        <div class="row g-4">
          <div class="col-lg-7">
            <div class="da-card p-4 mb-4">
              <h2 class="h6 fw-bold mb-3">Contact &amp; Personal Cabinet Email</h2>
              <label for="contact-email" class="form-label small text-muted">
                Tickets, itemized invoice &amp; cabinet credentials will be emailed here
              </label>
              <input
                id="contact-email"
                v-model="contactEmail"
                type="email"
                class="form-control"
                placeholder="you@example.com"
                required
              />
            </div>

            <div v-for="(p, idx) in passengers" :key="idx" class="da-card p-4 mb-3">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h2 class="h6 fw-bold mb-0">Passenger {{ idx + 1 }}</h2>
                <div class="small text-muted">
                  <span v-if="p.seat_number" class="badge text-bg-primary me-1">Seat {{ p.seat_number }}</span>
                  <span v-if="p.return_seat_number" class="badge text-bg-info">Return {{ p.return_seat_number }}</span>
                </div>
              </div>
              <div class="row g-3">
                <div class="col-md-4">
                  <label class="form-label small">First Name</label>
                  <input v-model="p.first_name" type="text" class="form-control" required />
                </div>
                <div class="col-md-4">
                  <label class="form-label small">Last Name</label>
                  <input v-model="p.last_name" type="text" class="form-control" required />
                </div>
                <div class="col-md-4">
                  <label class="form-label small">Passport / ID Number</label>
                  <input v-model="p.document_number" type="text" class="form-control" required />
                </div>
              </div>
            </div>
          </div>

          <div class="col-lg-5">
            <div class="da-card p-4">
              <h2 class="h6 fw-bold mb-2">Payment Gateway</h2>
              <p class="small text-muted mb-3">
                Pick a deterministic test card or enter card details:
              </p>
              <div class="d-flex flex-wrap gap-2 mb-3">
                <button type="button" class="btn btn-outline-success btn-sm" @click="fillTestCard('4242424242424242')">
                  Approved (4242)
                </button>
                <button type="button" class="btn btn-outline-danger btn-sm" @click="fillTestCard('4000000000000002')">
                  Declined (0002)
                </button>
                <button type="button" class="btn btn-outline-warning btn-sm" @click="fillTestCard('4000000000009995')">
                  Low Funds (9995)
                </button>
              </div>

              <div class="mb-3">
                <label class="form-label small">Cardholder Name</label>
                <input v-model="paymentForm.cardholder_name" type="text" class="form-control" required />
              </div>
              <div class="mb-3">
                <label class="form-label small">Card Number</label>
                <input v-model="paymentForm.card_number" type="text" class="form-control" required />
              </div>
              <div class="row g-2 mb-4">
                <div class="col-4">
                  <label class="form-label small">Exp Month</label>
                  <input v-model.number="paymentForm.exp_month" type="number" min="1" max="12" class="form-control" required />
                </div>
                <div class="col-4">
                  <label class="form-label small">Exp Year</label>
                  <input v-model.number="paymentForm.exp_year" type="number" min="2025" max="2040" class="form-control" required />
                </div>
                <div class="col-4">
                  <label class="form-label small">CVV</label>
                  <input v-model="paymentForm.cvv" type="text" maxlength="4" class="form-control" required />
                </div>
              </div>

              <div class="d-flex justify-content-between fs-5 fw-bold mb-3 border-top pt-3">
                <span>Total Due</span>
                <span class="text-primary">${{ estimatedTotal.toFixed(2) }}</span>
              </div>

              <button id="pay-and-book-btn" type="submit" class="btn da-btn-primary w-100 btn-lg" :disabled="loading">
                {{ loading ? "Processing Payment..." : "Pay & Confirm Booking" }}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>

    <!-- STEP 4: Confirmation -->
    <BookingConfirmation
      v-if="step === 4 && confirmedResult"
      :confirmed-result="confirmedResult"
      @open-cabinet="$emit('open-cabinet', $event)"
      @reset="resetFlow"
    />
  </section>
</template>

<script>
import { defaultOffsetDate, defaultTomorrowDate, formatDateTime } from "../../shared/api";
import BookingConfirmation from "./BookingConfirmation.vue";
import BookingSearchHero from "./BookingSearchHero.vue";
import SeatMapPicker from "./SeatMapPicker.vue";

export default {
  name: "BookingFlow",
  components: { BookingSearchHero, BookingConfirmation, SeatMapPicker },
  props: {
    api: { type: Object, required: true },
  },
  emits: ["open-cabinet"],
  data() {
    return {
      step: 1,
      loading: false,
      error: "",
      airports: [],
      search: {
        tripType: "one_way",
        origin: "JFK",
        destination: "LHR",
        date: defaultTomorrowDate(),
        returnDate: defaultOffsetDate(3),
        passengers: 1,
      },
      flights: [],
      returnFlights: [],
      selectedFlight: null,
      selectedSeat: null,
      selectedSeatNumbers: [],
      holdToken: "",
      selectedReturnFlight: null,
      selectedReturnSeat: null,
      selectedReturnSeatNumbers: [],
      returnHoldToken: "",
      selectedOptionIds: [],
      discountCode: "",
      discountPreview: 0,
      contactEmail: "",
      passengers: [],
      pendingBookingRef: "",
      paymentForm: {
        cardholder_name: "Alex Traveler",
        card_number: "4242424242424242",
        exp_month: 12,
        exp_year: 2030,
        cvv: "424",
      },
      confirmedResult: null,
    };
  },
  computed: {
    outboundFareSubtotal() {
      if (!this.selectedSeat) return 0;
      return parseFloat(this.selectedSeat.unit_price) * this.search.passengers;
    },
    returnFareSubtotal() {
      if (!this.selectedReturnSeat) return 0;
      return parseFloat(this.selectedReturnSeat.unit_price) * this.search.passengers;
    },
    fareSubtotal() {
      return this.outboundFareSubtotal + this.returnFareSubtotal;
    },
    optionsSubtotal() {
      if (!this.selectedFlight) return 0;
      const sum = this.selectedFlight.options
        .filter((o) => this.selectedOptionIds.includes(o.id))
        .reduce((acc, o) => acc + parseFloat(o.price), 0);
      const legs = this.selectedReturnFlight ? 2 : 1;
      return sum * this.search.passengers * legs;
    },
    estimatedTotal() {
      return Math.max(this.fareSubtotal + this.optionsSubtotal - this.discountPreview, 0);
    },
  },
  async mounted() {
    try {
      this.airports = await this.api.request("/fleet/airports/");
    } catch (err) {
      this.error = err.message;
    }
  },
  methods: {
    formatDateTime,
    stepClass(n) {
      if (this.step === n) return "active";
      if (this.step > n) return "done";
      return "";
    },
    async searchFlights() {
      this.error = "";
      this.loading = true;
      try {
        const qs = new URLSearchParams({
          destination: this.search.destination,
          date: this.search.date,
          passengers: String(this.search.passengers),
        });
        if (this.search.tripType === "round_trip") {
          if (this.search.origin) qs.set("origin", this.search.origin);
          qs.set("return_date", this.search.returnDate);
        }
        const res = await this.api.request(`/flights/search/?${qs.toString()}`);
        if (this.search.tripType === "round_trip") {
          this.flights = res.outbound || [];
          this.returnFlights = res.return || [];
        } else {
          this.flights = Array.isArray(res) ? res : res.results || [];
          this.returnFlights = [];
        }
        this.selectedFlight = null;
        this.selectedSeat = null;
        this.selectedSeatNumbers = [];
        this.holdToken = "";
        this.selectedReturnFlight = null;
        this.selectedReturnSeat = null;
        this.selectedReturnSeatNumbers = [];
        this.returnHoldToken = "";
        this.selectedOptionIds = [];
        this.discountPreview = 0;
        this.step = 2;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    selectFlightSeat(flight, seat) {
      if (!this.selectedFlight || this.selectedFlight.id !== flight.id) {
        this.selectedOptionIds = [];
        this.selectedSeatNumbers = [];
        this.holdToken = "";
      }
      this.selectedFlight = flight;
      this.selectedSeat = seat;
      this.discountPreview = 0;
    },
    selectReturnFlightSeat(flight, seat) {
      if (!this.selectedReturnFlight || this.selectedReturnFlight.id !== flight.id) {
        this.selectedReturnSeatNumbers = [];
        this.returnHoldToken = "";
      }
      this.selectedReturnFlight = flight;
      this.selectedReturnSeat = seat;
      this.discountPreview = 0;
    },
    async applyDiscount() {
      if (!this.discountCode.trim()) return;
      this.error = "";
      try {
        const subtotal = (this.fareSubtotal + this.optionsSubtotal).toFixed(2);
        const res = await this.api.request("/bookings/validate-discount/", {
          method: "POST",
          body: { code: this.discountCode.trim(), subtotal },
        });
        this.discountPreview = parseFloat(res.discount_amount);
      } catch (err) {
        this.discountPreview = 0;
        this.error = err.message;
      }
    },
    proceedToCheckout() {
      this.passengers = Array.from({ length: this.search.passengers }, (_, i) => ({
        first_name: i === 0 ? "Alex" : `Traveler${i + 1}`,
        last_name: "Morgan",
        document_number: `PASS${10001 + i}`,
        seat_number: this.selectedSeatNumbers[i] || null,
        return_seat_number: this.selectedReturnSeatNumbers[i] || null,
      }));
      this.pendingBookingRef = "";
      this.step = 3;
    },
    fillTestCard(num) {
      this.paymentForm.card_number = num;
    },
    async submitBookingAndPay() {
      this.error = "";
      this.loading = true;
      try {
        if (!this.pendingBookingRef) {
          const payload = {
            flight_id: this.selectedFlight.id,
            seat_type_id: this.selectedSeat.seat_type_id,
            contact_email: this.contactEmail,
            passengers: this.passengers,
            option_ids: this.selectedOptionIds,
            discount_code: this.discountCode.trim() || null,
          };
          if (this.holdToken) payload.hold_token = this.holdToken;
          if (this.selectedReturnFlight && this.selectedReturnSeat) {
            payload.return_flight_id = this.selectedReturnFlight.id;
            payload.return_seat_type_id = this.selectedReturnSeat.seat_type_id;
            if (this.returnHoldToken) payload.return_hold_token = this.returnHoldToken;
          }
          const booking = await this.api.request("/bookings/", {
            method: "POST",
            body: payload,
          });
          this.pendingBookingRef = booking.booking_reference;
        }

        const result = await this.api.request("/payments/charge/", {
          method: "POST",
          body: {
            booking_reference: this.pendingBookingRef,
            payment_method: "CARD",
            ...this.paymentForm,
          },
        });
        this.confirmedResult = result;
        this.step = 4;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    resetFlow() {
      this.step = 1;
      this.selectedFlight = null;
      this.selectedSeat = null;
      this.selectedSeatNumbers = [];
      this.holdToken = "";
      this.selectedReturnFlight = null;
      this.selectedReturnSeat = null;
      this.selectedReturnSeatNumbers = [];
      this.returnHoldToken = "";
      this.selectedOptionIds = [];
      this.pendingBookingRef = "";
      this.confirmedResult = null;
      this.discountCode = "";
      this.discountPreview = 0;
    },
  },
};
</script>
