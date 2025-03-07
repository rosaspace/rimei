from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container, invoice
from .pyviews import user

urlpatterns = [
    # main page
    path("", views.index, name="index"),
    path("container/", views.container_view, name="container"),
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),

    # container
    path("upload_pdf/", container.upload_pdf, name="upload_pdf"),
    path("save_container/", container.save_container, name="save_container"),
    path('add_container_view/', container.add_container_view, name='add_container_view'),
    path('add_container/', container.add_container, name='add_container'),   
    path("edit_container/<str:container_id>/", container.edit_container, name="edit_container"), 

    # Invoice    
    path("edit_invoice/<str:container_id>/", invoice.edit_invoice, name="edit_invoice"),
    path('add_invoice_view/', invoice.add_invoice_view, name='add_invoice_view'),

    # user manager
    path('add_user/', user.add_user_view, name='add_user'),
    path('assign_permission/', user.assign_permission_view, name='assign_permission'),
    path('update_user_permissions/<str:user_id>/', user.update_user_permissions, name='update_user_permissions'),
    path("permission/", user.permission_view, name ="permission"),
]