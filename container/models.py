from django.db import models

class Container(models.Model):
    container_pdfname = models.CharField(max_length=255)  # 上传的PDF文件名
    content = models.TextField(blank=True, null=True)  # 解析出的内容
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间
    created_user = models.CharField(max_length=255, blank=True, null=True)  # 创建用户
    container_id = models.CharField(max_length=255, blank=True, null=True)  # Container ID
    railway_date = models.DateField(blank=True, null=True)  # 铁路日期
    pickup_date = models.DateField(blank=True, null=True)  # 提货日期
    delivery_date = models.DateField(blank=True, null=True)  # 交货日期
    empty_date = models.DateField(blank=True, null=True)  # 空箱日期
    pickup_number = models.CharField(max_length=255, blank=True, null=True)  # 提货编号
    invoice_id = models.CharField(max_length=255, blank=True, null=True)  # 发票ID
    invoice_pdfname = models.CharField(max_length=255, blank=True, null=True)  # 发票PDF文件名

    def __str__(self):
        return self.container_pdfname

class Permission(models.Model):
    index = models.AutoField(primary_key=True)  # 自动生成的主键
    name = models.CharField(max_length=255, unique=True)  # 权限名称，唯一
    description = models.TextField(blank=True, null=True)  # 权限描述，可选

    def __str__(self):
        return self.name  # 返回权限名称

class UserAndPermission(models.Model):
    username = models.ForeignKey('auth.User', on_delete=models.CASCADE)  # 关联用户表，假设使用 Django 的用户模型
    permissionIndex = models.ForeignKey(Permission, on_delete=models.CASCADE, to_field='index')  # 关联权限表的 index 字段

    class Meta:
        unique_together = ('username', 'permissionIndex')  # 确保用户和权限的组合唯一

    def __str__(self):
        return f"{self.username.username} - {self.permissionIndex.name}"  # 返回用户和权限的组合