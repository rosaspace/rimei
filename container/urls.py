from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container
from .pyviews import user

urlpatterns = [
    path("", views.index, name="index"),
    path("container/", views.container_view, name="container"),
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),
    path("permission/", views.permission_view, name ="permission"),

    path("add_invoice/<str:container_id>/", views.add_invoice, name="add_invoice"),

    path("upload_pdf/", container.upload_pdf, name="upload_pdf"),
    path("save_container/", container.save_container, name="save_container"),

    path('add_user/', user.add_user_view, name='add_user'),
    path('assign_permission/', user.assign_permission_view, name='assign_permission'),
    path('update_user_permissions/<str:user_id>/', user.update_user_permissions, name='update_user_permissions'),
]