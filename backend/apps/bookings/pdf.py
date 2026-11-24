from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _qr_image_reader(data: str) -> ImageReader:
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B2545", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def generate_boarding_pass_pdf(ticket) -> bytes:
    """Render an aviation-styled PDF boarding pass with embedded QR code for ticket_code."""
    buf = BytesIO()
    page_w, page_h = landscape((110 * mm, 210 * mm))
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle(f"DjangoAir Boarding Pass - {ticket.ticket_code}")

    navy = colors.HexColor("#0B2545")
    cobalt = colors.HexColor("#1565C0")
    muted = colors.HexColor("#5B6E84")
    light_bg = colors.HexColor("#F5F7FA")

    # Background card
    c.setFillColor(colors.white)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Top Navy Banner
    c.setFillColor(navy)
    c.rect(0, page_h - 22 * mm, page_w, 22 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(12 * mm, page_h - 14 * mm, "DJANGOAIR  |  BOARDING PASS")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(page_w - 12 * mm, page_h - 14 * mm, f"{ticket.seat_type.name.upper()}")

    # Route hero
    flight = ticket.flight
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(12 * mm, page_h - 38 * mm, f"{flight.origin.code}  ->  {flight.destination.code}")
    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawString(
        12 * mm,
        page_h - 44 * mm,
        f"{flight.origin.city} to {flight.destination.city}   |   Flight {flight.flight_number}",
    )

    # Details panel
    c.setFillColor(light_bg)
    c.roundRect(12 * mm, 12 * mm, 130 * mm, 46 * mm, 4 * mm, fill=1, stroke=0)

    def _field(x, y, label, value):
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, label.upper())
        c.setFillColor(navy)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y - 5.5 * mm, str(value))

    _field(17 * mm, 50 * mm, "Passenger", ticket.passenger.full_name)
    _field(82 * mm, 50 * mm, "Document", ticket.passenger.document_number)
    _field(17 * mm, 35 * mm, "Departure (UTC)", flight.departure_time.strftime("%Y-%m-%d %H:%M"))
    _field(82 * mm, 35 * mm, "Gate", flight.gate)
    _field(112 * mm, 35 * mm, "Seat", ticket.seat_number)
    _field(17 * mm, 21 * mm, "Ticket Code", ticket.ticket_code)
    _field(82 * mm, 21 * mm, "Booking Ref", ticket.booking.booking_reference)
    _field(118 * mm, 21 * mm, "Status", ticket.status)

    # Dashed tear separator
    c.setStrokeColor(cobalt)
    c.setDash(3, 3)
    c.line(150 * mm, 10 * mm, 150 * mm, page_h - 24 * mm)
    c.setDash()

    # QR Code on right stub (encodes ticket_code directly for Gate Manager scanning)
    qr_reader = _qr_image_reader(ticket.ticket_code)
    c.drawImage(qr_reader, 157 * mm, 24 * mm, width=44 * mm, height=44 * mm)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(179 * mm, 18 * mm, ticket.ticket_code)
    c.setFillColor(muted)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(179 * mm, 13 * mm, "Scan at Boarding Gate")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_invoice_pdf(payment) -> bytes:
    """Render an itemized PDF invoice / receipt for a DjangoAir booking payment."""
    buf = BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"DjangoAir Invoice - {payment.invoice_number}")

    navy = colors.HexColor("#0B2545")
    muted = colors.HexColor("#5B6E84")
    border = colors.HexColor("#DCE4EE")

    # Header
    c.setFillColor(navy)
    c.rect(0, page_h - 32 * mm, page_w, 32 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(18 * mm, page_h - 16 * mm, "DJANGOAIR ERP")
    c.setFont("Helvetica", 10)
    c.drawString(18 * mm, page_h - 23 * mm, "Official Ticket Receipt & Tax Invoice")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(page_w - 18 * mm, page_h - 16 * mm, payment.invoice_number)
    c.setFont("Helvetica", 9)
    c.drawRightString(page_w - 18 * mm, page_h - 23 * mm, f"Status: {payment.status}")

    booking = payment.booking
    y = page_h - 46 * mm
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(18 * mm, y, f"Booking Reference: {booking.booking_reference}")
    c.drawString(110 * mm, y, f"Transaction ID: {payment.transaction_id}")
    y -= 6 * mm
    c.setFillColor(muted)
    c.setFont("Helvetica", 9.5)
    c.drawString(18 * mm, y, f"Billed To: {booking.contact_email}")
    paid_str = payment.paid_at.strftime("%Y-%m-%d %H:%M UTC") if payment.paid_at else "Pending"
    c.drawString(110 * mm, y, f"Paid At: {paid_str} ({payment.provider})")

    # Table header
    y -= 14 * mm
    c.setFillColor(colors.HexColor("#EDF2F8"))
    c.rect(18 * mm, y - 3 * mm, page_w - 36 * mm, 9 * mm, fill=1, stroke=0)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Ticket")
    c.drawString(52 * mm, y, "Passenger")
    c.drawString(98 * mm, y, "Flight & Seat")
    c.drawRightString(155 * mm, y, "Fare")
    c.drawRightString(190 * mm, y, "Extras / Fee")

    y -= 10 * mm
    c.setFont("Helvetica", 9)
    for t in booking.tickets.select_related(
        "passenger", "flight__origin", "flight__destination", "seat_type"
    ).all():
        c.setFillColor(navy)
        c.drawString(20 * mm, y, t.ticket_code)
        c.drawString(52 * mm, y, t.passenger.full_name[:24])
        c.drawString(
            98 * mm,
            y,
            f"{t.flight.flight_number} ({t.flight.origin.code}->{t.flight.destination.code}) {t.seat_number}",
        )
        c.drawRightString(155 * mm, y, f"${t.base_fare}")
        extras = t.options_total + t.luggage_fee
        c.drawRightString(190 * mm, y, f"${extras}")
        y -= 7 * mm
        c.setStrokeColor(border)
        c.line(18 * mm, y + 3 * mm, page_w - 18 * mm, y + 3 * mm)

    # Totals
    y -= 8 * mm
    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawRightString(160 * mm, y, "Subtotal:")
    c.drawRightString(190 * mm, y, f"${booking.subtotal_amount}")
    y -= 6 * mm
    c.drawRightString(160 * mm, y, "Discount:")
    c.drawRightString(190 * mm, y, f"-${booking.discount_amount}")
    y -= 8 * mm
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(160 * mm, y, f"Total Paid ({payment.currency}):")
    c.drawRightString(190 * mm, y, f"${payment.amount}")

    c.setFillColor(muted)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(
        page_w / 2,
        18 * mm,
        "Thank you for flying with DjangoAir. Present your QR boarding pass at the departure gate.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
