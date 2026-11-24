from django.urls import path

from .views import CabinetBalanceTopUpView, InvoiceDetailView, PaymentChargeView

urlpatterns = [
    path("payments/charge/", PaymentChargeView.as_view(), name="payment-charge"),
    path("payments/<uuid:pk>/invoice/", InvoiceDetailView.as_view(), name="payment-invoice"),
    path("cabinet/balance/top-up/", CabinetBalanceTopUpView.as_view(), name="cabinet-balance-topup"),
]
