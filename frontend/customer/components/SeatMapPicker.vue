<template>
  <div class="border rounded p-3 bg-white mt-3 da-seat-map-panel">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
      <div>
        <h4 class="h6 fw-bold mb-0">
          Interactive Cabin Seat Map — {{ seatTypeName }}
        </h4>
        <div class="small text-muted">
          Optional: pick up to {{ passengerCount }} seat{{ passengerCount > 1 ? "s" : "" }} (held for 10 min in Redis) or leave blank for auto-assign.
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span v-if="modelValue.length" class="badge text-bg-success">
          Held: {{ modelValue.join(", ") }} ({{ formattedCountdown }})
        </span>
        <button
          type="button"
          class="btn btn-outline-secondary btn-sm"
          :disabled="loading"
          @click="loadSeatMap"
        >
          Refresh Map
        </button>
      </div>
    </div>

    <div v-if="mapError" class="alert alert-warning py-1 px-2 small mb-2">{{ mapError }}</div>

    <div class="d-flex flex-wrap gap-3 small mb-3">
      <span><span class="da-seat-legend bg-white border border-primary"></span> Available</span>
      <span><span class="da-seat-legend bg-primary"></span> Your Held Seat</span>
      <span><span class="da-seat-legend bg-warning"></span> Held by Other</span>
      <span><span class="da-seat-legend bg-secondary-subtle border"></span> Occupied</span>
    </div>

    <div v-if="loading && !cabinRows.length" class="text-muted small py-2">Loading cabin layout...</div>

    <div v-else class="da-cabin-grid">
      <div
        v-for="row in cabinRows"
        :key="row.row_number"
        class="d-flex align-items-center justify-content-center gap-1 mb-1"
      >
        <span class="text-muted small fw-semibold me-2" style="width: 24px; text-align: right;">
          {{ row.row_number }}
        </span>
        <template v-for="(seat, idx) in row.seats" :key="seat.seat_number">
          <span
            v-if="idx === row.aisle_after"
            class="d-inline-block text-center text-muted"
            style="width: 20px; font-size: 0.7rem;"
          >
            |
          </span>
          <button
            type="button"
            class="btn btn-sm da-cabin-seat"
            :data-seat="seat.seat_number"
            :class="seatBtnClass(seat)"
            :disabled="isSeatDisabled(seat) || busy"
            :title="`${seat.seat_number} (${seat.status})`"
            @click="toggleSeat(seat)"
          >
            {{ seat.seat_number }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SeatMapPicker",
  props: {
    api: { type: Object, required: true },
    flightId: { type: String, required: true },
    seatTypeId: { type: String, required: true },
    seatTypeName: { type: String, default: "Cabin" },
    passengerCount: { type: Number, default: 1 },
    modelValue: { type: Array, default: () => [] },
    holdToken: { type: String, default: "" },
  },
  emits: ["update:modelValue", "update:holdToken"],
  data() {
    return {
      loading: false,
      busy: false,
      mapError: "",
      rows: [],
      remainingSeconds: 0,
      timerId: null,
    };
  },
  computed: {
    cabinRows() {
      return this.rows.filter((r) => r.seat_type_id === this.seatTypeId);
    },
    formattedCountdown() {
      const m = Math.floor(this.remainingSeconds / 60);
      const s = this.remainingSeconds % 60;
      return `${m}:${String(s).padStart(2, "0")}`;
    },
  },
  watch: {
    flightId: {
      immediate: true,
      handler() {
        this.loadSeatMap();
      },
    },
    seatTypeId() {
      // Clear seat picks when switching cabin class
      if (this.modelValue.length) {
        this.releaseCurrentSeats();
      }
    },
  },
  beforeUnmount() {
    if (this.timerId) clearInterval(this.timerId);
  },
  methods: {
    startCountdown(seconds) {
      if (this.timerId) clearInterval(this.timerId);
      this.remainingSeconds = seconds;
      this.timerId = setInterval(() => {
        if (this.remainingSeconds > 0) {
          this.remainingSeconds -= 1;
        } else {
          clearInterval(this.timerId);
          this.timerId = null;
        }
      }, 1000);
    },
    async loadSeatMap() {
      if (!this.flightId) return;
      this.loading = true;
      this.mapError = "";
      try {
        const qs = this.holdToken ? `?hold_token=${encodeURIComponent(this.holdToken)}` : "";
        const data = await this.api.request(`/flights/${this.flightId}/seat-map/${qs}`);
        this.rows = data.rows || [];
      } catch (err) {
        this.mapError = err.message;
      } finally {
        this.loading = false;
      }
    },
    isSelected(seatNumber) {
      return this.modelValue.includes(seatNumber);
    },
    isSeatDisabled(seat) {
      if (this.isSelected(seat.seat_number)) return false;
      return seat.status === "OCCUPIED" || seat.status === "HELD";
    },
    seatBtnClass(seat) {
      if (this.isSelected(seat.seat_number) || seat.status === "HELD_BY_ME") {
        return "btn-primary text-white fw-bold";
      }
      if (seat.status === "OCCUPIED") {
        return "btn-light text-muted border";
      }
      if (seat.status === "HELD") {
        return "btn-warning text-dark";
      }
      return "btn-outline-primary";
    },
    async releaseCurrentSeats() {
      if (this.holdToken && this.modelValue.length) {
        try {
          await this.api.request(`/flights/${this.flightId}/seat-holds/`, {
            method: "DELETE",
            body: { seat_numbers: this.modelValue, hold_token: this.holdToken },
          });
        } catch (_err) {
          // Best-effort release
        }
      }
      this.$emit("update:modelValue", []);
      await this.loadSeatMap();
    },
    async toggleSeat(seat) {
      this.mapError = "";
      this.busy = true;
      const sn = seat.seat_number;
      try {
        if (this.isSelected(sn)) {
          if (this.holdToken) {
            await this.api.request(`/flights/${this.flightId}/seat-holds/`, {
              method: "DELETE",
              body: { seat_numbers: [sn], hold_token: this.holdToken },
            });
          }
          const updated = this.modelValue.filter((s) => s !== sn);
          this.$emit("update:modelValue", updated);
        } else {
          let nextSeats = [...this.modelValue];
          if (nextSeats.length >= this.passengerCount) {
            const evicted = nextSeats.shift();
            if (evicted && this.holdToken) {
              await this.api.request(`/flights/${this.flightId}/seat-holds/`, {
                method: "DELETE",
                body: { seat_numbers: [evicted], hold_token: this.holdToken },
              });
            }
          }
          nextSeats.push(sn);
          const res = await this.api.request(`/flights/${this.flightId}/seat-holds/`, {
            method: "POST",
            body: {
              seat_numbers: nextSeats,
              hold_token: this.holdToken || null,
            },
          });
          this.$emit("update:holdToken", res.hold_token);
          this.$emit("update:modelValue", res.held_seats);
          this.startCountdown(res.expires_in_seconds || 600);
        }
        await this.loadSeatMap();
      } catch (err) {
        this.mapError = err.message;
        await this.loadSeatMap();
      } finally {
        this.busy = false;
      }
    },
  },
};
</script>

<style scoped>
.da-cabin-grid {
  max-height: 280px;
  overflow-y: auto;
  padding: 0.5rem 0;
}
.da-cabin-seat {
  width: 44px;
  padding: 0.2rem 0.15rem;
  font-size: 0.72rem;
}
.da-seat-legend {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  vertical-align: middle;
  margin-right: 4px;
}
</style>
