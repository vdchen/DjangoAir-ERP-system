<template>
  <div class="row g-4">
    <!-- Staff Management -->
    <div class="col-lg-6">
      <div class="da-card p-4 h-100">
        <h2 class="h5 fw-bold mb-3">Staff Team (Gate &amp; Check-in Managers)</h2>
        <form class="row g-2 mb-3" @submit.prevent="$emit('create-staff')">
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
            <button class="btn btn-outline-danger btn-sm" @click="$emit('delete-staff', u.id)">Remove</button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Options Catalog Management -->
    <div class="col-lg-6">
      <div class="da-card p-4 h-100">
        <h2 class="h5 fw-bold mb-3">Flight Options Catalog</h2>
        <form class="row g-2 mb-3" @submit.prevent="$emit('create-option')">
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
            <button class="btn btn-outline-danger btn-sm" @click="$emit('delete-option', o.id)">Remove</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SupervisorTeamOptionsGrid",
  props: {
    staffForm: { type: Object, required: true },
    staffUsers: { type: Array, default: () => [] },
    optionForm: { type: Object, required: true },
    options: { type: Array, default: () => [] },
  },
  emits: ["create-staff", "delete-staff", "create-option", "delete-option"],
};
</script>
