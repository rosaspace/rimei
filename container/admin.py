from django.contrib import admin

from .models import (
    Container, Permission, UserAndPermission,
    RMOrder, RMCustomer, OrderImage,
    InvoiceCustomer, RMProduct,
    Employee, LogisticsCompany, OrderItem, ClockRecord, ContainerItem,
    AlineOrderRecord, Carrier, InboundCategory, RailwayStation, ContainerStatement, Manufacturer,
    InvoicePurposeFor, InvoicePaidCustomer, InvoiceVendor, InvoiceARRecord, InvoiceAPRecord,
    OfficeSupplyItem, OfficeSupplyPurpose, OfficeSupplyPlatform, OfficeSupplyRecord
)

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'plts', 'railway_date', 'pickup_date', 'delivery_date', 'empty_date',
                    'pickup_number', 'customer', 'logistics', 'is_updateInventory', 'created_user', 'inboundCategory', 'Carrier')

class RMOrderAdmin(admin.ModelAdmin):
    # form = OrderForm
    list_display = ('so_num', 'po_num', 'plts', 'customer_name', 'order_date', 'pickup_date',
                   'outbound_date', 'is_sendemail', 'is_updateInventory', 'is_allocated_to_stock', 'is_canceled',
                   'order_pdfname', 'created_user')

class ClockRecordAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'date', "weekday", "total_hours")

class RMProductdAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'shortname', 'size', 'TI', 'HI', 'Pallet', 'Color', "Location", "ShelfRecord", "blongTo", "quantity_init", "quantity_diff", "type", "price")

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'belongTo')

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product','quantity')

class ContainerItemAdmin(admin.ModelAdmin):
    list_display = ('container', 'product','quantity')

class RMCustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name','description')

class InvoiceCustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name','description')

class InboundCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'Type','Name')

class InvoiceARRecordAdmin(admin.ModelAdmin):
    list_display = ('customer', 'invoice_id', 'invoice_price', 'company', 'due_date', 'givetoboss_date', 'note')

class InvoiceAPRecordAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'invoice_id', 'invoice_price', 'company', 'due_date', 'givetoboss_date', 'purposefor', 'note')

@admin.register(OfficeSupplyItem)
class OfficeSupplyItemAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "category")


@admin.register(OfficeSupplyPurpose)
class OfficeSupplyPurposeAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(OfficeSupplyPlatform)
class OfficeSupplyPlatformAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(OfficeSupplyRecord)
class OfficeSupplyRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id", "supply_item", "purpose", "platform",
        "quantity", "purchase_date", "delivered_date"
    )

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)
admin.site.register(RMOrder, RMOrderAdmin)
admin.site.register(RMCustomer, RMCustomerAdmin)
admin.site.register(OrderImage)
admin.site.register(InvoiceCustomer, InvoiceCustomerAdmin)
admin.site.register(RMProduct, RMProductdAdmin)
admin.site.register(ClockRecord, ClockRecordAdmin)
admin.site.register(Employee, EmployeeAdmin)
admin.site.register(LogisticsCompany)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ContainerItem, ContainerItemAdmin)
admin.site.register(AlineOrderRecord)
admin.site.register(Carrier)
admin.site.register(InboundCategory, InboundCategoryAdmin)
admin.site.register(RailwayStation)
admin.site.register(ContainerStatement)
admin.site.register(Manufacturer)
admin.site.register(InvoicePaidCustomer)
admin.site.register(InvoiceVendor)
admin.site.register(InvoicePurposeFor)
admin.site.register(InvoiceARRecord, InvoiceARRecordAdmin)
admin.site.register(InvoiceAPRecord, InvoiceAPRecordAdmin)
