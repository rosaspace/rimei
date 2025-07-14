from django.urls import path
from django.views.generic import TemplateView

from . import views
from .pyviews import container, invoice, rmorder, pdfprocess,weekrecord,payment
from .pyviews import user, login, inventory_count,temporary,statistics

urlpatterns = [
    # login
    path('login/', login.login_view, name='login'),
    path('register/', login.register_view, name='register'),
    path("logout", login.logout_view, name="logout"),

    # main page
    path("", views.home, name="index"),
    path("index/", views.index, name="index"),    
    path("invoice_all/", views.invoice_view, name="invoice_all"),
    path("invoice_unpaid/", views.invoice_unpaid, name="invoice_unpaid"),
    path("invoice_statement/", views.invoice_statement, name="invoice_statement"),
    path("invoice_pallet_labor/", views.invoice_pallet_labor, name="invoice_pallet_labor"), 

    path("statement_selected_invoices/", views.statement_selected_invoices, name="statement_selected_invoices"),
    path('delete_statement/', views.delete_statement, name='delete_statement'),
    path("paid_invoice_advance/", views.paid_invoice_advance, name="paid_invoice_advance"),
    path("paid_invoice_customer/", views.paid_invoice_customer, name="paid_invoice_customer"),    
    
    path("aline_payment/", views.aline_payment_view, name="aline_payment"),    
    path("permission_view/", views.permission_view, name ="permission_view"),
    path("temporary/", views.temporary_view, name="temporary"),    

    path("container_advance77/", views.container_advance77, name="container_advance77"), 
    path("container_omar/", views.container_omar, name="container_omar"), 
    path("container_mcd/", views.container_mcd, name="container_mcd"),     
    path("container_metal/", views.container_metal, name="container_metal"),

    path("rimeiorder/", views.rimeiorder_view, name="rimeiorder"),
    path("rimeiorder_metal/", views.rimeiorder_metal, name="rimeiorder_metal"),
    path("rimeiorder_mcdonalds/", views.rimeiorder_mcdonalds, name="rimeiorder_mcdonalds"),
    path("rimeiorder_officedepot/", views.rimeiorder_officedepot, name="rimeiorder_officedepot"),
    path("rimeiorder_cancel/", views.rimeiorder_cancel, name="rimeiorder_cancel"),    

    # inventory count
    path("inventory/", inventory_count.inventory_view, name="inventory"),
    path("inventory_diff/", inventory_count.inventory_diff_view, name="inventory_diff"), 
    path("inventory_metal/", inventory_count.inventory_metal, name="inventory_metal"), 
    path("inventory_mcd/", inventory_count.inventory_mcd, name="inventory_mcd"),     
    path("order_history/<int:product_id>/", inventory_count.order_history, name="order_history"),
    path("export_stock/", inventory_count.export_stock, name="export_stock"),    
    path("inventory_summary", inventory_count.inventory_summary, name="inventory_summary"),
    path('export_pallet_number/',inventory_count.export_pallet_number,name='export_pallet_number'),

    # container
    path('add_container/', container.add_container, name='add_container'), 
    path('add_container_view/', container.add_container_view, name='add_container_view'),
    path("edit_container/<str:container_id>/", container.edit_container, name="edit_container"), 
    path("receivedin_inventory/<str:container_id>/", container.receivedin_inventory, name="receivedin_inventory"), 
    path('container_ispay/<str:container_id>/', container.container_ispay, name='container_ispay'), 
    path('container_customer_ispay/<str:container_id>/', container.container_customer_ispay, name='container_customer_ispay'),

    path('print_container_detail/<str:container_num>/', container.print_container_detail, name='print_container_detail'),
    path('print_container_label/<str:container_num>/', container.print_container_label, name='print_container_label'),
    path('print_container_color_label/<str:container_num>/', container.print_container_color_label, name='print_container_color_label'),
    path('print_container_delivery_order/<str:container_num>/', container.print_container_delivery_order, name='print_container_delivery_order'),
    
    # Invoice
    path("edit_invoice_file/<str:container_id>/", invoice.edit_invoice_file, name="edit_invoice_file"),
    path("edit_invoice/<str:container_id>/", invoice.edit_invoice, name="edit_invoice"),
    path("edit_customer_invoice_file/<str:container_id>/", invoice.edit_customer_invoice_file, name="edit_customer_invoice_file"),
    path("edit_customer_invoice/<str:container_id>/", invoice.edit_customer_invoice, name="edit_customer_invoice"),
    path("print_statement_invoice_pdf/", invoice.print_statement_invoice_pdf, name="print_statement_invoice_pdf"),
    path('print_original_do/<str:container_id>/', invoice.print_original_do, name='print_original_do'),
    path('print_original_invoice/<str:container_id>/', invoice.print_original_invoice, name='print_original_invoice'),
    path('print_converted_invoice/<str:container_id>/', invoice.print_converted_invoice, name='print_converted_invoice'),
    path('print_customer_invoice/<str:container_id>/<str:isEmptyContainerRelocate>/', invoice.print_customer_invoice, name='print_customer_invoice'),
    path("export_pallet_invoice/", invoice.export_pallet_invoice, name="export_pallet_invoice"),    
    
    # Payment
    path("edit_aline/<str:order_number>/", payment.edit_aline, name="edit_aline"), 
    path("aline_ispay/<str:order_number>/", payment.aline_ispay, name="aline_ispay"), 

    # user
    path('add_user/', user.add_user_view, name='add_user'),
    path('assign_permission/', user.assign_permission_view, name='assign_permission'),
    path('update_user_permissions/<str:user_id>/', user.update_user_permissions, name='update_user_permissions'),
    
    # rimei order
    path('add_order/', rmorder.add_order, name='add_order'),
    path("edit_order/<str:so_num>/", rmorder.edit_order, name="edit_order"), 
    path("upload_orderpdf/", rmorder.upload_orderpdf, name="upload_orderpdf"),
    path('order_images/<int:order_id>/', rmorder.order_images, name='order_images'),
    path('order_is_allocated_to_stock/<str:so_num>/', rmorder.order_is_allocated_to_stock, name='order_is_allocated_to_stock'),
    
    # Temporary
    path("import_inventory/", temporary.import_inventory, name="import_inventory"), 
    path("import_aline/", temporary.import_aline, name="import_aline"), 
    path('export_pallet/',temporary.export_pallet,name='export_pallet'),    
    path("preview_email/", temporary.preview_email,name="preview_email"), 
    path('order_email/<str:so_num>/', temporary.order_email, name='order_email'),
    path('container_email/<str:container_id>/', temporary.container_email, name='container_email'),     
    path('print_label_only/', temporary.print_label_only, name='print_label_only'),
    path('print_label_containerid_lot/', temporary.print_label_containerid_lot, name='print_label_containerid_lot'),
    
    # pdf     
    path('print_original_order/<str:so_num>/', pdfprocess.print_original_order, name='print_original_order'),
    path('print_converted_order/<str:so_num>/', pdfprocess.print_converted_order, name='print_converted_order'),
    path('print_order_label/<str:so_num>/', pdfprocess.print_order_label, name='print_order_label'),    
    path('print_order_bol/<str:so_num>/', pdfprocess.print_order_bol, name='print_order_bol'),
    path('print_order_mcd/<str:so_num>/', pdfprocess.print_order_mcd, name='print_order_mcd'),

    path('pickup_tomorrow/', pdfprocess.pickup_tomorrow, name='pickup_tomorrow'),
    path('pickup_today/', pdfprocess.pickup_today, name='pickup_today'),
    path('pickup_third/', pdfprocess.pickup_third, name='pickup_third'),   
    path('pickup_fourth/', pdfprocess.pickup_fourth, name='pickup_fourth'),  
    path('pickup_week/', pdfprocess.pickup_week, name='pickup_week'),

    # 打卡记录
    path('week_record/', weekrecord.week_record, name='week_record'),
    path('add_week_records/', weekrecord.add_week_records, name='add_week_records'),
    path('edit_week_records/<int:employee_id>/', weekrecord.edit_week_records, name='edit_week_records'),
    path("export_week_records", weekrecord.export_week_records,name="export_week_records"),

    # 统计表
    path("statistics_invoice", statistics.statistics_invoice,name="statistics_invoice"),
    path("statistics_weekreord", statistics.statistics_weekreord,name="statistics_weekreord"),
    path("statistics_inbound", statistics.statistics_inbound,name="statistics_inbound"),
    path("statistics_outbound", statistics.statistics_outbound,name="statistics_outbound"),
    path("statistics_warehouse", statistics.statistics_warehouse,name="statistics_warehouse"),
]