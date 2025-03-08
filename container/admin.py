from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型
from .models import RMOrder, RMCustomer,OrderImage
from .forms import OrderForm

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'container_pdfname', 'created_at', 'created_user')  # Updated field name

class RMOrderAdmin(admin.ModelAdmin):
    form = OrderForm
    list_display = ('so_num', 'po_num', 'plts', 'customer_name', 'pickup_date', 
                   'outbound_date', 'is_sendemail', 'is_updateInventory')
    search_fields = ('so_num', 'po_num', 'customer_name__name')
    list_filter = ('is_sendemail', 'is_updateInventory', 'pickup_date', 'outbound_date')

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)
admin.site.register(RMOrder, RMOrderAdmin)
admin.site.register(RMCustomer)
admin.site.register(OrderImage)