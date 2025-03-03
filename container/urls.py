from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container

urlpatterns = [
    path("", views.index, name="index"),
    path("container/", views.container_view, name="container"),
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),

    path("upload_pdf/", container.upload_pdf, name="upload_pdf"),
    path("save_container/", container.save_container, name="save_container"),
]