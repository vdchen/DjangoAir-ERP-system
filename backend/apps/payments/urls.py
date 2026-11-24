from django.urls import path

from .views import CabinetBalanceTopUpView, InvoiceDetailView, InvoicePdfView, PaymentChargeView

urlpatterns = [
    path("payments/charge/", PaymentChargeView.as_view(), name="payment-charge"),
    path("payments/<uuid:pk>/invoice/", InvoiceDetailView.as_view(), name="payment-invoice"),
    path("payments/<uuid:pk>/invoice.pdf", InvoicePdfView.as_view(), name="payment-invoice-pdf"),
    path("cabinet/balance/top-up/", CabinetBalanceTopUpView.as_view(), name="cabinet-balance-topup"),
]
