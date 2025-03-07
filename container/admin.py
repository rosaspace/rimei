from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型

class ContainerAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'container_pdfname', 'created_at', 'created_user')  # Updated field name

# Register your models here.
admin.site.register(Container, ContainerAdmin)
admin.site.register(Permission)
admin.site.register(UserAndPermission)