<template>
  <section>
    <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
    <div v-if="success" class="alert alert-success py-2 small">{{ success }}</div>

    <div class="row g-4">
      <!-- Flights Management -->
      <div class="col-12">
        <div class="da-card p-4">
          <h1 class="h5 fw-bold mb-3">Flight Schedule Management</h1>

          <form class="row g-2 align-items-end mb-4 border-bottom pb-4" @submit.prevent="createFlight">
            <div class="col-md-2">
              <label class="form-label small">Flight #</label>
              <input v-model="flightForm.flight_number" class="form-control form-control-sm" placeholder="DA888" required />
            </div>
            <div class="col-md-2">
              <label class="form-label small">Origin</label>
              <select v-model="flightForm.origin" class="form-select form-select-sm" required>
                <option v-for="a in airports" :key="a.id" :value="a.id">{{ a.code }}</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label small">Destination</label>
              <select v-model="flightForm.destination" class="form-select form-select-sm" required>
                <option v-for="a in airports" :key="a.id" :value="a.id">{{ a.code }}</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label small">Airplane</label>
              <select v-model="flightForm.airplane" class="form-select form-select-sm" required>
                <option v-for="p in airplanes" :key="p.id" :value="p.id">{{ p.registration_number }}</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label small">Base Price ($)</label>
              <input v-model.number="flightForm.base_price" type="number" min="20" class="form-control form-control-sm" required />
            </div>
            <div class="col-md-2">
              <label class="form-label small">Gate</label>
              <input v-model="flightForm.gate" class="form-control form-control-sm" required />
            </div>
            <div class="col-md-4">
              <label class="form-label small">Departure (UTC)</label>
              <input v-model="flightForm.departure_time" type="datetime-local" class="form-control form-control-sm" required />
            </div>
            <div class="col-md-4">
              <label class="form-label small">Arrival (UTC)</label>
              <input v-model="flightForm.arrival_time" type="datetime-local" class="form-control form-control-sm" required />
            </div>
            <div class="col-md-4">
              <button type="submit" class="btn da-btn-primary btn-sm w-100">Create Flight</button>
            </div>
          </form>

          <div class="table-responsive" style="max-height: 280px;">
            <table class="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>Flight</th>
                  <th>Route</th>
                  <th>Departure</th>
                  <th>Base Price</th>
                  <th>Seats Left</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in flights" :key="f.id">
                  <td class="fw-semibold">{{ f.flight_number }}</td>
                  <td>{{ f.origin.code }} &rarr; {{ f.destination.code }}</td>
                  <td class="small">{{ formatDateTime(f.departure_time) }}</td>
                  <td>${{ f.base_price }}</td>
                  <td>{{ f.total_available_seats }}</td>
                  <td>
                    <span class="badge" :class="f.status === 'CANCELLED' ? 'text-bg-danger' : 'text-bg-success'">
                      {{ f.status }}
                    </span>
                  </td>
                  <td>
                    <button
                      v-if="f.status === 'SCHEDULED'"
                      class="btn btn-outline-danger btn-sm"
                      @click="cancelFlight(f)"
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Staff Management -->
      <div class="col-lg-6">
        <div class="da-card p-4 h-100">
          <h2 class="h5 fw-bold mb-3">Staff Team (Gate &amp; Check-in Managers)</h2>
          <form class="row g-2 mb-3" @submit.prevent="createStaff">
            <div class="col-md-6">
              <input v-model="staffForm.email" type="email" class="form-control form-control-sm" placeholder="staff@djangoair.local" required />
            </div>
            <div class="col-md-6">
              <input v-model="staffForm.password" type="password" class="form-control form-control-sm" placeholder="Password (min 6)" required />
            </div>
            <div class="col-md-4">
              <input v-model="staffForm.first_name" class="form-control form-control-sm" placeholder="First name" required />
            </div>
            <div class="col-md-4">
              <input v-model="staffForm.last_name" class="form-control form-control-sm" placeholder="Last name" required />
            </div>
            <div class="col-md-4">
              <select v-model="staffForm.role" class="form-select form-select-sm">
                <option value="GATE_MANAGER">Gate Manager</option>
                <option value="CHECKIN_MANAGER">Check-in Manager</option>
              </select>
            </div>
            <div class="col-12">
              <button type="submit" class="btn da-btn-primary btn-sm">Add Staff Member</button>
            </div>
          </form>

          <ul class="list-group list-group-flush">
            <li v-for="u in staffUsers" :key="u.id" class="list-group-item px-0 d-flex justify-content-between align-items-center">
              <div>
                <div class="fw-semibold small">{{ u.first_name }} {{ u.last_name }} ({{ u.email }})</div>
                <span class="badge text-bg-secondary">{{ u.role }}</span>
              </div>
              <button class="btn btn-outline-danger btn-sm" @click="deleteStaff(u.id)">Remove</button>
            </li>
          </ul>
        </div>
      </div>

      <!-- Options Catalog Management -->
      <div class="col-lg-6">
        <div class="da-card p-4 h-100">
          <h2 class="h5 fw-bold mb-3">Flight Options Catalog</h2>
          <form class="row g-2 mb-3" @submit.prevent="createOption">
            <div class="col-md-5">
              <input v-model="optionForm.name" class="form-control form-control-sm" placeholder="Option name (e.g. Fast Track)" required />
            </div>
            <div class="col-md-4">
              <select v-model="optionForm.category" class="form-select form-select-sm">
                <option value="MEAL">Meal / Lunch</option>
                <option value="LUGGAGE">Luggage</option>
                <option value="COMFORT">Comfort</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div class="col-md-3">
              <input v-model.number="optionForm.price" type="number" min="1" step="0.01" class="form-control form-control-sm" placeholder="Price" required />
            </div>
            <div class="col-12">
              <button type="submit" class="btn da-btn-primary btn-sm">Add Option</button>
            </div>
          </form>

          <ul class="list-group list-group-flush">
            <li v-for="o in options" :key="o.id" class="list-group-item px-0 d-flex justify-content-between align-items-center">
              <div class="small">
                <strong>{{ o.name }}</strong> <span class="text-muted">({{ o.category }})</span> — ${{ o.price }}
              </div>
              <button class="btn btn-outline-danger btn-sm" @click="deleteOption(o.id)">Remove</button>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { formatDateTime } from "../../shared/api";

export default {
  name: "SupervisorPanel",
  props: { api: { type: Object, required: true } },
  data() {
    const dep = new Date(Date.now() + 48 * 3600 * 1000);
    const arr = new Date(dep.getTime() + 4 * 3600 * 1000);
    return {
      error: "",
      success: "",
      airports: [],
      airplanes: [],
      flights: [],
      staffUsers: [],
      options: [],
      flightForm: {
        flight_number: "DA850",
        origin: "",
        destination: "",
        airplane: "",
        departure_time: dep.toISOString().slice(0, 16),
        arrival_time: arr.toISOString().slice(0, 16),
        base_price: 290,
        gate: "C4",
      },
      staffForm: {
        email: "",
        password: "",
        first_name: "",
        last_name: "",
        role: "GATE_MANAGER",
      },
      optionForm: {
        name: "",
        category: "COMFORT",
        price: 25,
      },
    };
  },
  async mounted() {
    await this.loadAll();
  },
  methods: {
    formatDateTime,
    async loadAll() {
      try {
        const [airports, airplanes, flights, staffUsers, options] = await Promise.all([
          this.api.request("/fleet/airports/"),
          this.api.request("/fleet/airplanes/"),
          this.api.request("/staff/flights/"),
          this.api.request("/staff/users/"),
          this.api.request("/staff/options/"),
        ]);
        this.airports = airports;
        this.airplanes = airplanes;
        this.flights = flights;
        this.staffUsers = staffUsers;
        this.options = options;
        if (airports.length >= 2 && !this.flightForm.origin) {
          this.flightForm.origin = airports[0].id;
          this.flightForm.destination = airports[1].id;
        }
        if (airplanes.length && !this.flightForm.airplane) {
          this.flightForm.airplane = airplanes[0].id;
        }
      } catch (err) {
        this.error = err.message;
      }
    },
    async createFlight() {
      this.error = "";
      this.success = "";
      try {
        await this.api.request("/staff/flights/", {
          method: "POST",
          body: {
            ...this.flightForm,
            departure_time: new Date(this.flightForm.departure_time).toISOString(),
            arrival_time: new Date(this.flightForm.arrival_time).toISOString(),
          },
        });
        this.success = `Flight ${this.flightForm.flight_number} scheduled.`;
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
    async cancelFlight(flight) {
      this.error = "";
      this.success = "";
      try {
        const res = await this.api.request(`/staff/flights/${flight.id}/cancel/`, { method: "POST" });
        this.success = `Flight ${flight.flight_number} cancelled (${res.refunded_bookings} paid booking(s) refunded to balance).`;
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
    async createStaff() {
      this.error = "";
      this.success = "";
      try {
        await this.api.request("/staff/users/", { method: "POST", body: this.staffForm });
        this.success = `Added staff member ${this.staffForm.email}.`;
        this.staffForm = { email: "", password: "", first_name: "", last_name: "", role: "GATE_MANAGER" };
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
    async deleteStaff(id) {
      this.error = "";
      this.success = "";
      try {
        await this.api.request(`/staff/users/${id}/`, { method: "DELETE" });
        this.success = "Staff member removed.";
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
    async createOption() {
      this.error = "";
      this.success = "";
      try {
        await this.api.request("/staff/options/", { method: "POST", body: this.optionForm });
        this.success = `Added option "${this.optionForm.name}".`;
        this.optionForm = { name: "", category: "COMFORT", price: 25 };
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
    async deleteOption(id) {
      this.error = "";
      this.success = "";
      try {
        await this.api.request(`/staff/options/${id}/`, { method: "DELETE" });
        this.success = "Option removed.";
        await this.loadAll();
      } catch (err) {
        this.error = err.message;
      }
    },
  },
};
</script>
