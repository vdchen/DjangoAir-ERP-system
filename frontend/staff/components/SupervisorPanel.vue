<template>
  <section>
    <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
    <div v-if="success" class="alert alert-success py-2 small">{{ success }}</div>

    <div class="mb-4">
      <SupervisorFlightsCard
        :flight-form="flightForm"
        :airports="airports"
        :airplanes="airplanes"
        :flights="flights"
        @create-flight="createFlight"
        @cancel-flight="cancelFlight"
      />
    </div>

    <SupervisorTeamOptionsGrid
      :staff-form="staffForm"
      :staff-users="staffUsers"
      :option-form="optionForm"
      :options="options"
      @create-staff="createStaff"
      @delete-staff="deleteStaff"
      @create-option="createOption"
      @delete-option="deleteOption"
    />
  </section>
</template>

<script>
import SupervisorFlightsCard from "./SupervisorFlightsCard.vue";
import SupervisorTeamOptionsGrid from "./SupervisorTeamOptionsGrid.vue";

export default {
  name: "SupervisorPanel",
  components: { SupervisorFlightsCard, SupervisorTeamOptionsGrid },
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
