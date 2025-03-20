from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container, invoice, rmorder, inventory,pdfprocess,weekrecord
from .pyviews import user

urlpatterns = [
    # main page
    path("", views.index, name="index"),
    path("container/", views.container_view, name="container"),
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),
    path("rimeiorder/", views.rimeiorder_view, name="rimeiorder"),
    path("temporary/", views.temporary_view, name="temporary"),
    path("preview_email/<int:number>/", views.preview_email,name="preview_email"),   

    # container
    path('add_container/', container.add_container, name='add_container'), 
    path('add_container_view/', container.add_container_view, name='add_container_view'),
    path("edit_container/<str:container_id>/", container.edit_container, name="edit_container"), 

    # Invoice    
    path('add_invoice/', invoice.add_invoice, name='add_invoice'),
    path('add_invoice_view/', invoice.add_invoice_view, name='add_invoice_view'),
    path("edit_invoice/<str:container_id>/", invoice.edit_invoice, name="edit_invoice"),

    # user
    path('add_user/', user.add_user_view, name='add_user'),
    path('assign_permission/', user.assign_permission_view, name='assign_permission'),
    path('update_user_permissions/<str:user_id>/', user.update_user_permissions, name='update_user_permissions'),
    path("permission/", user.permission_view, name ="permission"),

    # rimei order
    path('add_order/', rmorder.add_order, name='add_order'),
    path("edit_order/<str:so_num>/", rmorder.edit_order, name="edit_order"), 
    path("search_order/", rmorder.search_order, name="search_order"),
    path('order_images/<int:order_id>/', rmorder.order_images, name='order_images'),
    path('export_pallet/',rmorder.export_pallet,name='export_pallet'),
    path("import_excel/", rmorder.import_excel, name="import_excel"),  
  
    # Inventory
    path("inventory/", inventory.inventory_view, name="inventory"),
    path("add_stock/", inventory.add_stock_view, name="add_stock"),  # 入库路径
    path("remove_stock/", inventory.remove_stock_view, name="remove_stock"),  # 出库路径
    
    # pdf
    path("upload_pdf/", pdfprocess.upload_pdf, name="upload_pdf"),
    path("upload_orderpdf/", pdfprocess.upload_orderpdf, name="upload_orderpdf"),

    path('print_original_order/<str:so_num>/', pdfprocess.print_original_order, name='print_original_order'),
    path('print_converted_order/<str:so_num>/', pdfprocess.print_converted_order, name='print_converted_order'),
    path('print_label/<str:so_num>/', pdfprocess.print_label, name='print_label'),
    path('print_bol/<str:so_num>/', pdfprocess.print_bol, name='print_bol'),

    # 打卡记录
    path('week_record/', weekrecord.week_record, name='week_record'),
    path('add_week_records/', weekrecord.add_week_records, name='add_week_records'),
    path('edit_week_records/<int:employee_id>/', weekrecord.edit_week_records, name='edit_week_records'),
    path("export_week_records", weekrecord.export_week_records,name="export_week_records"),
]