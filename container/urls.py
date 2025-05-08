from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container, invoice, rmorder, inventory,pdfprocess,weekrecord,payment
from .pyviews import user, login

urlpatterns = [
    # main page
    path("", views.home, name="home"),
    path("index/", views.index, name="index"),    
    path("invoice/", views.invoice_view, name="invoice"),
    path("payment/", views.payment_view, name="payment"),
    path("aline_payment/", views.aline_payment_view, name="aline_payment"),    
    path("inventory/", rmorder.inventory_view, name="inventory"),
    path("inventory_diff/", rmorder.inventory_diff_view, name="inventory_diff"),
    path("export_stock/", rmorder.export_stock, name="export_stock"),    
    path("order_history/<int:product_id>/", rmorder.order_history, name="order_history"),
    path("permission/", views.permission_view, name ="permission"),
    path("temporary/", views.temporary_view, name="temporary"),    

    path("container/", views.container_view, name="container"),    
    path("container_finished/", views.container_view_finished, name="container_finished"),
    path("rimeiorder/", views.rimeiorder_view, name="rimeiorder"),
    path("rimeiorder_finished/", views.rimeiorder_view_finished, name="rimeiorder_finished"),
    path("rimeiorder_officedepot/", views.rimeiorder_officedepot, name="rimeiorder_officedepot"),
    path("rimeiorder_cancel/", views.rimeiorder_cancel, name="rimeiorder_cancel"),    

    # login
    path('login/', login.login_view, name='login'),
    path('register/', login.register_view, name='register'),
    path("logout", login.logout_view, name="logout"),

    # container
    path('add_container/', container.add_container, name='add_container'), 
    path('add_container_view/', container.add_container_view, name='add_container_view'),
    path("edit_container/<str:container_id>/", container.edit_container, name="edit_container"), 
    path("receivedin_inventory/<str:container_id>/", container.receivedin_inventory, name="receivedin_inventory"), 
    path('container_ispay/<str:container_id>/', container.container_ispay, name='container_ispay'),     

    # Invoice    
    path('add_invoice/', invoice.add_invoice, name='add_invoice'),
    path('add_invoice_view/', invoice.add_invoice_view, name='add_invoice_view'),
    path("edit_invoice/<str:container_id>/", pdfprocess.edit_invoice, name="edit_invoice"),

    # Payment
    path("edit_aline/<str:order_number>/", payment.edit_aline, name="edit_aline"), 

    # user
    path('add_user/', user.add_user_view, name='add_user'),
    path('assign_permission/', user.assign_permission_view, name='assign_permission'),
    path('update_user_permissions/<str:user_id>/', user.update_user_permissions, name='update_user_permissions'),
    
    # rimei order
    path('add_order/', rmorder.add_order, name='add_order'),
    path("edit_order/<str:so_num>/", rmorder.edit_order, name="edit_order"), 
    path('order_images/<int:order_id>/', rmorder.order_images, name='order_images'),    

    # Temporary
    path("import_inventory/", rmorder.import_inventory, name="import_inventory"), 
    path("import_aline/", rmorder.import_aline, name="import_aline"), 
    path('export_pallet/',rmorder.export_pallet,name='export_pallet'),
    path("preview_email/<int:number>/", rmorder.preview_email,name="preview_email"), 
    path('print_label_only/', pdfprocess.print_label_containerid_lot, name='print_label_only'),  
  
    # Inventory    
    path("add_stock/", inventory.add_stock_view, name="add_stock"),  # 入库路径
    path("remove_stock/", inventory.remove_stock_view, name="remove_stock"),  # 出库路径
    
    # pdf
    path("upload_pdf/", pdfprocess.upload_pdf, name="upload_pdf"),
    path("upload_orderpdf/", pdfprocess.upload_orderpdf, name="upload_orderpdf"),

    path('print_original_order/<str:so_num>/', pdfprocess.print_original_order, name='print_original_order'),
    path('print_converted_order/<str:so_num>/', pdfprocess.print_converted_order, name='print_converted_order'),
    path('print_label/<str:so_num>/', pdfprocess.print_label, name='print_label'),    
    path('print_bol/<str:so_num>/', pdfprocess.print_bol, name='print_bol'),
    path('print_container_detail/<str:container_num>/', pdfprocess.print_container_detail, name='print_container_detail'),
    path('print_container_label/<str:container_num>/', pdfprocess.print_container_label, name='print_container_label'),
    path('print_container_color_label/<str:container_num>/', pdfprocess.print_container_color_label, name='print_container_color_label'),
    path('print_container_delivery_order/<str:container_num>/', pdfprocess.print_container_delivery_order, name='print_container_delivery_order'),
    
    path('pickup_tomorrow/', pdfprocess.pickup_tomorrow, name='pickup_tomorrow'),
    path('pickup_today/', pdfprocess.pickup_today, name='pickup_today'),
    path('pickup_third/', pdfprocess.pickup_third, name='pickup_third'),   

    # 打卡记录
    path('week_record/', weekrecord.week_record, name='week_record'),
    path('add_week_records/', weekrecord.add_week_records, name='add_week_records'),
    path('edit_week_records/<int:employee_id>/', weekrecord.edit_week_records, name='edit_week_records'),
    path("export_week_records", weekrecord.export_week_records,name="export_week_records"),
]