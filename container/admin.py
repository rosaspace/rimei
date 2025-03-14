from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型
from .models import RMOrder, RMCustomer,OrderImage
from .forms import OrderForm
from .models import InvoiceCustomer,RMProduct,RMInventory
from .models import Employee, ClockRecord,LogisticsCompany

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'railway_date', 'pickup_date', 'delivery_date','empty_date','pickup_number')  # Updated field name

class RMOrderAdmin(admin.ModelAdmin):
    form = OrderForm
    list_display = ('so_num', 'po_num', 'plts', 'customer_name', 'pickup_date', 
                   'outbound_date', 'is_sendemail', 'is_updateInventory')
    search_fields = ('so_num', 'po_num', 'customer_name__name')
    list_filter = ('is_sendemail', 'is_updateInventory', 'pickup_date', 'outbound_date')

class RMInventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity')

class ClockRecordAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'date',"weekday","total_hours")

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)
admin.site.register(RMOrder, RMOrderAdmin)
admin.site.register(RMCustomer)
admin.site.register(OrderImage)
admin.site.register(InvoiceCustomer)
admin.site.register(RMProduct)
admin.site.register(RMInventory, RMInventoryAdmin)
admin.site.register(ClockRecord,ClockRecordAdmin)
admin.site.register(Employee)
admin.site.register(LogisticsCompany)