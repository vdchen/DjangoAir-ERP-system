# DjangoAir ERP — API & Integration Contracts

All REST API endpoints are served under `/api/v1/` through Nginx. Authenticated requests use `Authorization: Bearer <access_token>`.

## 1. Authentication & Accounts

| Method | Path | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health/` | Public | Service health check (DB & app status) |
| `POST` | `/api/v1/auth/login/` | Public | Obtain JWT `access`, `refresh`, and `user` profile |
| `POST` | `/api/v1/auth/refresh/` | Public | Refresh JWT access token |
| `POST` | `/api/v1/auth/register/` | Public | Register a new customer account |
| `GET` | `/api/v1/auth/google/config/` | Public | Check if Google OAuth2 / dev mock is enabled |
| `POST` | `/api/v1/auth/google/` | Public | Authenticate or link customer via Google OAuth2 ID token (or guarded dev mock) |
| `GET` | `/api/v1/auth/me/` | Authenticated | Current user profile, role, linked providers, and customer balance |
| `GET` | `/api/v1/staff/users/` | Supervisor | List Gate Managers and Check-in Managers |
| `POST` | `/api/v1/staff/users/` | Supervisor | Create a Gate Manager or Check-in Manager |
| `DELETE` | `/api/v1/staff/users/<id>/` | Supervisor | Remove a Gate Manager or Check-in Manager |

## 2. Fleet & Flights

| Method | Path | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/fleet/airports/` | Public | List airports (destinations) |
| `GET` | `/api/v1/fleet/airplanes/` | Public | List aircraft and cabin seat configurations |
| `GET` | `/api/v1/fleet/seat-types/` | Public | List seat types and price multipliers |
| `GET` | `/api/v1/flights/search/` | Public | Search flights by `destination`, `date`, `passengers` |
| `GET` | `/api/v1/flights/<id>/` | Public | Flight details, live seat availability, and options |
| `GET/POST` | `/api/v1/staff/flights/` | Check-in+ / Supervisor | List all flights; Supervisor creates new flights |
| `POST` | `/api/v1/staff/flights/<id>/cancel/` | Supervisor | Cancel flight, refund paid bookings to balance, email passengers |
| `GET/POST` | `/api/v1/staff/options/` | Check-in+ / Supervisor | List options; Supervisor creates options |
| `PATCH/DELETE` | `/api/v1/staff/options/<id>/` | Supervisor | Update or delete an option |

## 3. Bookings, Payments & Customer Personal Cabinet

| Method | Path | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/bookings/validate-discount/` | Public | Validate discount promo code and preview discount |
| `POST` | `/api/v1/bookings/` | Public | Create booking (`RESERVED`), lock seats, provision cabinet user |
| `GET` | `/api/v1/bookings/<reference>/` | Public / Owner | Retrieve booking details and tickets |
| `POST` | `/api/v1/payments/charge/` | Public | Process emulated payment (card or cabinet balance), send emails with PDF attachments |
| `GET` | `/api/v1/payments/<id>/invoice/` | Public / Owner | Retrieve itemized invoice/bill JSON |
| `GET` | `/api/v1/payments/<id>/invoice.pdf` | Public / Owner | Download printable itemized PDF invoice |
| `GET` | `/api/v1/cabinet/overview/` | Authenticated | Personal cabinet: profile, balance, upcoming & previous tickets |
| `POST` | `/api/v1/cabinet/balance/top-up/` | Authenticated | Top up personal cabinet balance via emulated card |
| `POST` | `/api/v1/cabinet/tickets/<ticket_code>/check-in/` | Authenticated | Online check-in (`PAID` -> `CHECKED_IN`) |
| `GET` | `/api/v1/cabinet/tickets/<ticket_code>/boarding-pass.pdf` | Authenticated | Download printable PDF boarding pass with embedded QR code (`ticket_code`) |

## 4. Staff Airport Operations

| Method | Path | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/staff/tickets/` | Gate Manager+ | Search tickets by `ticket_code`, booking reference, or flight |
| `GET` | `/api/v1/staff/tickets/<ticket_code>/` | Gate Manager+ | Lookup full ticket & passenger details |
| `POST` | `/api/v1/staff/gate/board/` | Gate Manager+ | Register passenger boarding at gate using `ticket_code` |
| `POST` | `/api/v1/staff/checkin/` | Check-in Manager+ | Check in passenger, attach options, collect luggage fee |

## 5. Mobile WebSocket API (`services/mobile_ws`)

- **Endpoint**: `ws://<host>/socket.io/` (Socket.IO protocol)
- **Client Events**:
  - `subscribe_flight` — `{"flight_number": "DA101"}`
  - `subscribe_ticket` — `{"ticket_code": "DA-XXXX"}`
  - `ping_mobile` — health ping
- **Server Events**:
  - `connected` — connection confirmation
  - `subscribed` — room subscription confirmation
  - `flight_event` — real-time domain events (`booking.confirmed`, `payment.succeeded`, `passenger.checked_in`, `passenger.boarded`, `flight.cancelled`, `flight.created`)

## 6. Third-Party Webhook API (`services/webhook_mock` & `apps.integrations`)

- **Header**: `X-DjangoAir-Signature: sha256=<hmac_sha256_hex>`
- **Header**: `X-DjangoAir-Event: <event_type>`
- **Mock Receiver**: `POST /mock-webhook/events` (verifies HMAC signature), `GET /mock-webhook/events` (lists received deliveries), `GET /mock-webhook/` (HTML live inspector).
