from django.contrib import admin
from .models import Container,Permission,UserAndPermission  # 导入 Container 模型

# Register your models here.
admin.site.register(Container)
admin.site.register(Permission)
admin.site.register(UserAndPermission)