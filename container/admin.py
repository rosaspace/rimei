from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型
from .models import RMOrder, RMCustomer,OrderImage
from .forms import OrderForm
from .models import InvoiceCustomer,RMProduct,RMInventory
from .models import Employee, LogisticsCompany,OrderItem,ClockRecord,ContainerItem

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'railway_date', 'pickup_date', 'delivery_date','empty_date','pickup_number')
    fields = ('container_id', 'railway_date', 'pickup_date', 'delivery_date','empty_date','pickup_number')

class RMOrderAdmin(admin.ModelAdmin):
    form = OrderForm
    list_display = ('so_num', 'po_num', 'plts', 'customer_name', 'order_date','pickup_date', 
                   'outbound_date', 'is_sendemail', 'is_updateInventory',
                   'order_pdfname')
    search_fields = ('so_num', 'po_num', 'customer_name__name')
    list_filter = ('is_sendemail', 'is_updateInventory', 'pickup_date', 'outbound_date')
    fields = ('so_num', 'po_num', 'plts', 'customer_name', 'order_date', 
              'pickup_date', 'outbound_date', 'is_sendemail', 'is_updateInventory',
              'order_pdfname')

class RMInventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity')

class ClockRecordAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'date',"weekday","total_hours")

class RMProductdAdmin(admin.ModelAdmin):
    list_display = ('name', 'id','shortname',"description")

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'id','belongTo')

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product','quantity')

class ContainerItemAdmin(admin.ModelAdmin):
    list_display = ('container', 'product','quantity')

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)
admin.site.register(RMOrder, RMOrderAdmin)
admin.site.register(RMCustomer)
admin.site.register(OrderImage)
admin.site.register(InvoiceCustomer)
admin.site.register(RMProduct, RMProductdAdmin)
admin.site.register(RMInventory, RMInventoryAdmin)
admin.site.register(ClockRecord,ClockRecordAdmin)
admin.site.register(Employee,EmployeeAdmin)
admin.site.register(LogisticsCompany)
admin.site.register(OrderItem,OrderItemAdmin)
admin.site.register(ContainerItem,ContainerItemAdmin)
