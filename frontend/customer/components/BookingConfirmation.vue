<template>
  <div class="da-card p-4 p-md-5">
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
      <div>
        <span class="badge text-bg-success mb-2">Booking Confirmed &amp; Paid</span>
        <h1 class="h3 fw-bold mb-1">
          Booking <span class="da-route-code">{{ confirmedResult.booking.booking_reference }}</span>
        </h1>
        <p class="text-muted mb-0">
          Tickets, itemized bill (<strong>{{ confirmedResult.payment.invoice_number }}</strong>), and your Personal Cabinet credentials have been emailed to
          <strong>{{ confirmedResult.booking.contact_email }}</strong>.
        </p>
      </div>
      <button class="btn da-btn-primary" @click="$emit('open-cabinet', confirmedResult.booking.contact_email)">
        Open Personal Cabinet
      </button>
    </div>

    <h2 class="h6 text-uppercase text-muted fw-bold mb-3" style="letter-spacing: 0.06em;">
      Issued Boarding Passes ({{ confirmedResult.booking.tickets.length }})
    </h2>
    <div class="row g-3 mb-4">
      <div v-for="t in confirmedResult.booking.tickets" :key="t.id" class="col-md-6">
        <div class="da-boarding-pass p-3 h-100 d-flex flex-column justify-content-between">
          <div>
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="da-ticket-code">{{ t.ticket_code }}</span>
              <span class="badge text-bg-primary">{{ t.status }}</span>
            </div>
            <div class="fs-5 fw-bold da-route-code my-1">
              {{ t.origin.code }} &rarr; {{ t.destination.code }}
              <span class="fs-6 fw-normal text-muted ms-1">{{ t.flight_number }}</span>
            </div>
            <div class="fw-semibold">{{ t.passenger.full_name }}</div>
          </div>
          <div class="da-boarding-divider mt-3 pt-2 d-flex justify-content-between small text-muted flex-wrap gap-2">
            <span>Seat <strong class="text-dark">{{ t.seat_number }}</strong> ({{ t.seat_type.name }})</span>
            <span>Gate <strong class="text-dark">{{ t.gate }}</strong></span>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-light border rounded p-3 d-flex justify-content-between align-items-center flex-wrap gap-2">
      <span class="small">Transaction: <code>{{ confirmedResult.payment.transaction_id }}</code></span>
      <span class="small">Invoice: <code>{{ confirmedResult.payment.invoice_number }}</code></span>
      <strong class="fs-6">Total Paid: ${{ confirmedResult.payment.amount }}</strong>
      <a
        id="download-invoice-pdf-btn"
        :href="`/api/v1/payments/${confirmedResult.payment.id}/invoice.pdf`"
        target="_blank"
        rel="noopener"
        class="btn btn-outline-primary btn-sm fw-semibold"
      >
        Download PDF Invoice
      </a>
    </div>

    <div class="mt-4">
      <button class="btn btn-outline-primary" @click="$emit('reset')">Book Another Flight</button>
    </div>
  </div>
</template>

<script>
export default {
  name: "BookingConfirmation",
  props: {
    confirmedResult: { type: Object, required: true },
  },
  emits: ["open-cabinet", "reset"],
};
</script>
