from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型
from .models import RMOrder, RMCustomer,OrderImage
from .forms import OrderForm
from .models import InvoiceCustomer,RMProduct,RMInventory
from .models import Employee, LogisticsCompany,OrderItem,ClockRecord,ContainerItem
from .models import AlineOrderRecord,Carrier,InboundCategory,RailwayStation,ContainerStatement

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'plts','railway_date', 'pickup_date', 'delivery_date','empty_date',
                    'pickup_number','customer','logistics','is_updateInventory','created_user','inboundCategory','Carrier')

class RMOrderAdmin(admin.ModelAdmin):
    # form = OrderForm
    list_display = ('so_num', 'po_num', 'plts', 'customer_name', 'order_date','pickup_date', 
                   'outbound_date', 'is_sendemail', 'is_updateInventory','is_allocated_to_stock','is_canceled',
                   'order_pdfname','created_user')

class RMInventoryAdmin(admin.ModelAdmin):
    list_display = ('product','quantity_init', 'quantity','quantity_for_neworder','quantity_to_stock','quantity_diff')

class ClockRecordAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'date',"weekday","total_hours")

class RMProductdAdmin(admin.ModelAdmin):
    list_display = ('name', 'id','shortname','size','TI','HI','Pallet','Color',"Location","ShelfRecord","blongTo")

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'id','belongTo')

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product','quantity')

class ContainerItemAdmin(admin.ModelAdmin):
    list_display = ('container', 'product','quantity')

class RMCustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name','description')

class InvoiceCustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name','description')

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)
admin.site.register(RMOrder, RMOrderAdmin)
admin.site.register(RMCustomer,RMCustomerAdmin)
admin.site.register(OrderImage)
admin.site.register(InvoiceCustomer,InvoiceCustomerAdmin)
admin.site.register(RMProduct, RMProductdAdmin)
admin.site.register(RMInventory, RMInventoryAdmin)
admin.site.register(ClockRecord,ClockRecordAdmin)
admin.site.register(Employee,EmployeeAdmin)
admin.site.register(LogisticsCompany)
admin.site.register(OrderItem,OrderItemAdmin)
admin.site.register(ContainerItem,ContainerItemAdmin)
admin.site.register(AlineOrderRecord)
admin.site.register(Carrier)
admin.site.register(InboundCategory)
admin.site.register(RailwayStation)
admin.site.register(ContainerStatement)

