<template>
  <div class="da-card p-4">
    <h1 class="h5 fw-bold mb-3">Flight Schedule Management</h1>

    <form class="row g-2 align-items-end mb-4 border-bottom pb-4" @submit.prevent="$emit('create-flight')">
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Flight #</label>
        <input v-model="flightForm.flight_number" class="form-control form-control-sm" placeholder="DA888" required />
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Origin</label>
        <select v-model="flightForm.origin" class="form-select form-select-sm" required>
          <option v-for="a in airports" :key="a.id" :value="a.id">{{ a.code }}</option>
        </select>
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Destination</label>
        <select v-model="flightForm.destination" class="form-select form-select-sm" required>
          <option v-for="a in airports" :key="a.id" :value="a.id">{{ a.code }}</option>
        </select>
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Airplane</label>
        <select v-model="flightForm.airplane" class="form-select form-select-sm" required>
          <option v-for="p in airplanes" :key="p.id" :value="p.id">{{ p.registration_number }}</option>
        </select>
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Base Price ($)</label>
        <input v-model.number="flightForm.base_price" type="number" min="20" class="form-control form-control-sm" required />
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold text-muted">Gate</label>
        <input v-model="flightForm.gate" class="form-control form-control-sm" required />
      </div>
      <div class="col-md-4">
        <label class="form-label small fw-semibold text-muted">Departure (UTC)</label>
        <input v-model="flightForm.departure_time" type="datetime-local" class="form-control form-control-sm" required />
      </div>
      <div class="col-md-4">
        <label class="form-label small fw-semibold text-muted">Arrival (UTC)</label>
        <input v-model="flightForm.arrival_time" type="datetime-local" class="form-control form-control-sm" required />
      </div>
      <div class="col-md-4">
        <button type="submit" class="btn da-btn-primary btn-sm w-100">Create Flight</button>
      </div>
    </form>

    <div class="table-responsive" style="max-height: 290px;">
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
            <td class="da-route-code small">{{ f.origin.code }} &rarr; {{ f.destination.code }}</td>
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
                @click="$emit('cancel-flight', f)"
              >
                Cancel
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { formatDateTime } from "../../shared/api";

export default {
  name: "SupervisorFlightsCard",
  props: {
    flightForm: { type: Object, required: true },
    airports: { type: Array, default: () => [] },
    airplanes: { type: Array, default: () => [] },
    flights: { type: Array, default: () => [] },
  },
  emits: ["create-flight", "cancel-flight"],
  methods: {
    formatDateTime,
  },
};
</script>
