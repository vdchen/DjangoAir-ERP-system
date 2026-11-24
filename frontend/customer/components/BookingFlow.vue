<template>
  <section>
    <!-- Progress Stepper -->
    <div class="da-stepper mb-4">
      <span class="da-step" :class="stepClass(1)">1. Search Flight</span>
      <span class="da-step" :class="stepClass(2)">2. Seats & Options</span>
      <span class="da-step" :class="stepClass(3)">3. Passenger & Payment</span>
      <span class="da-step" :class="stepClass(4)">4. Tickets & Confirmation</span>
    </div>

    <div v-if="error" class="alert alert-danger d-flex justify-content-between align-items-center">
      <span>{{ error }}</span>
      <button class="btn-close" @click="error = ''"></button>
    </div>

    <!-- STEP 1: Simple 3-Field Welcome Screen -->
    <div v-if="step === 1" class="da-hero p-4 p-md-5 shadow-sm">
      <div class="row align-items-center">
        <div class="col-lg-10 mx-auto">
          <h1 class="display-6 fw-bold mb-2">Where would you like to fly?</h1>
          <p class="opacity-75 mb-4">
            Choose your destination, travel date, and number of passengers to view live fares and seat availability.
          </p>

          <form class="da-card p-4 text-dark" @submit.prevent="searchFlights">
            <div class="row g-3 align-items-end">
              <div class="col-md-5">
                <label for="search-destination" class="form-label fw-semibold">Destination</label>
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
              <div class="col-md-4">
                <label for="search-date" class="form-label fw-semibold">Departure Date</label>
                <input
                  id="search-date"
                  v-model="search.date"
                  type="date"
                  class="form-control form-control-lg"
                  required
                />
              </div>
              <div class="col-md-3">
                <label for="search-passengers" class="form-label fw-semibold">Passengers</label>
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
                Tip: Seeded flights run daily for the next 5 days (try LHR, CDG, BER, DXB, or NRT).
              </small>
              <button id="search-submit-btn" type="submit" class="btn da-btn-primary btn-lg px-4" :disabled="loading">
                {{ loading ? "Searching..." : "Find Flights" }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- STEP 2: Flights, Seat Types, Prices & Options -->
    <div v-if="step === 2">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h4 fw-bold mb-0">
          Available Flights to {{ search.destination }} on {{ search.date }}
          <span class="text-muted fw-normal fs-6">({{ search.passengers }} passenger{{ search.passengers > 1 ? "s" : "" }})</span>
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
          <div
            v-for="flight in flights"
            :key="flight.id"
            class="da-card p-4 mb-3"
          >
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
              <div>
                <span class="badge text-bg-primary me-2">{{ flight.flight_number }}</span>
                <span class="fw-bold fs-5">{{ flight.origin.code }} &rarr; {{ flight.destination.code }}</span>
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
                <strong>${{ fareSubtotal.toFixed(2) }}</strong>
              </div>
              <div class="d-flex justify-content-between small mb-2">
                <span>Selected Options &times; {{ search.passengers }}</span>
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

              <button id="continue-checkout-btn" class="btn da-btn-primary w-100" @click="proceedToCheckout">
                Continue to Passenger &amp; Payment
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- STEP 3: Passenger Details + Emulated Payment Step -->
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
              <label for="contact-email" class="form-label">Email address (tickets, bill &amp; cabinet credentials will be sent here)</label>
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
              <h2 class="h6 fw-bold mb-3">Passenger {{ idx + 1 }}</h2>
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
              <h2 class="h6 fw-bold mb-2">Emulated Payment Gateway</h2>
              <p class="small text-muted mb-3">
                Safe open-source style payment simulator. Pick a test card or enter card details:
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

    <!-- STEP 4: Confirmation Screen -->
    <div v-if="step === 4 && confirmedResult" class="da-card p-4 p-md-5">
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
        <div>
          <span class="badge text-bg-success mb-2">Booking Confirmed &amp; Paid</span>
          <h1 class="h3 fw-bold mb-1">Booking {{ confirmedResult.booking.booking_reference }}</h1>
          <p class="text-muted mb-0">
            Tickets, itemized bill (<strong>{{ confirmedResult.payment.invoice_number }}</strong>), and your Personal Cabinet credentials have been emailed to
            <strong>{{ confirmedResult.booking.contact_email }}</strong>.
          </p>
        </div>
        <button class="btn da-btn-primary" @click="$emit('open-cabinet', confirmedResult.booking.contact_email)">
          Open Personal Cabinet
        </button>
      </div>

      <h2 class="h6 fw-bold mb-3">Issued Tickets</h2>
      <div class="row g-3 mb-4">
        <div v-for="t in confirmedResult.booking.tickets" :key="t.id" class="col-md-6">
          <div class="da-boarding-pass p-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="da-ticket-code">{{ t.ticket_code }}</span>
              <span class="badge text-bg-primary">{{ t.status }}</span>
            </div>
            <div class="fw-bold">{{ t.passenger.full_name }}</div>
            <div class="small text-muted">
              Flight {{ t.flight_number }} ({{ t.origin.code }} &rarr; {{ t.destination.code }}) &bull;
              Seat {{ t.seat_number }} ({{ t.seat_type.name }}) &bull; Gate {{ t.gate }}
            </div>
          </div>
        </div>
      </div>

      <div class="bg-light rounded p-3 d-flex justify-content-between align-items-center flex-wrap gap-2">
        <span>Transaction: <code>{{ confirmedResult.payment.transaction_id }}</code></span>
        <span>Invoice: <code>{{ confirmedResult.payment.invoice_number }}</code></span>
        <strong>Total Paid: ${{ confirmedResult.payment.amount }}</strong>
        <a
          id="download-invoice-pdf-btn"
          :href="`/api/v1/payments/${confirmedResult.payment.id}/invoice.pdf`"
          target="_blank"
          rel="noopener"
          class="btn btn-outline-primary btn-sm"
        >
          Download PDF Invoice
        </a>
      </div>

      <div class="mt-4">
        <button class="btn btn-outline-primary" @click="resetFlow">Book Another Flight</button>
      </div>
    </div>
  </section>
</template>

<script>
import { defaultTomorrowDate, formatDateTime } from "../../shared/api";

export default {
  name: "BookingFlow",
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
        destination: "LHR",
        date: defaultTomorrowDate(),
        passengers: 1,
      },
      flights: [],
      selectedFlight: null,
      selectedSeat: null,
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
    fareSubtotal() {
      if (!this.selectedSeat) return 0;
      return parseFloat(this.selectedSeat.unit_price) * this.search.passengers;
    },
    optionsSubtotal() {
      if (!this.selectedFlight) return 0;
      const sum = this.selectedFlight.options
        .filter((o) => this.selectedOptionIds.includes(o.id))
        .reduce((acc, o) => acc + parseFloat(o.price), 0);
      return sum * this.search.passengers;
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
        this.flights = await this.api.request(`/flights/search/?${qs.toString()}`);
        this.selectedFlight = null;
        this.selectedSeat = null;
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
      }
      this.selectedFlight = flight;
      this.selectedSeat = seat;
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
          const booking = await this.api.request("/bookings/", {
            method: "POST",
            body: {
              flight_id: this.selectedFlight.id,
              seat_type_id: this.selectedSeat.seat_type_id,
              contact_email: this.contactEmail,
              passengers: this.passengers,
              option_ids: this.selectedOptionIds,
              discount_code: this.discountCode.trim() || null,
            },
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
      this.selectedOptionIds = [];
      this.pendingBookingRef = "";
      this.confirmedResult = null;
      this.discountCode = "";
      this.discountPreview = 0;
    },
  },
};
</script>
