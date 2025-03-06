from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container

urlpatterns = [
    # main page
    path("", views.index, name="index"),
    path("container/", views.container_view, name="container"),
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),

    # Edit container and Invoice
    path("edit_invoice/<str:container_id>/", views.edit_invoice, name="edit_invoice"),
    path("edit_container/<str:container_id>/", views.edit_container, name="edit_container"),

    path("upload_pdf/", container.upload_pdf, name="upload_pdf"),
    path("save_container/", container.save_container, name="save_container"),

    # Add container and Invoice
    path('add_container_view/', container.add_container_view, name='add_container_view'),
    path('add_container/', container.add_container, name='add_container'),    
    path('add_invoice_view/', views.add_invoice_view, name='add_invoice_view'),
]