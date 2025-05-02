from django.db import models
from django.utils import timezone
from datetime import datetime

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

class RMOrder(models.Model):
    so_num = models.CharField(max_length=255, unique=True)  # 销售订单号
    po_num = models.CharField(max_length=255)  # 采购订单号
    plts = models.IntegerField()  # 托盘数量
    customer_name = models.ForeignKey('RMCustomer', on_delete=models.CASCADE)  # 关联客户表
    order_pdfname = models.CharField(max_length=255, blank=True, null=True)  # Order的PDF文件名
    bol_pdfname = models.CharField(max_length=255, blank=True, null=True)  # BOL的PDF文件名
    bill_to = models.CharField(max_length=255, blank=True, null=True) # 账单地址
    ship_to = models.CharField(max_length=255, blank=True, null=True) # 邮寄地址
    order_date = models.DateField(blank=True, null=True)  # 订单日期
    pickup_date = models.DateField(blank=True, null=True)  # 提货日期
    outbound_date = models.DateField(blank=True, null=True)  # 出库日期
    is_sendemail = models.BooleanField(default=False) # 是否发送邮件
    is_allocated_to_stock = models.BooleanField(default=False) # 是否放入备货区
    is_updateInventory = models.BooleanField(default=False) # 是否更新库存
    is_canceled = models.BooleanField(default=False) # 是否被取消
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间
    created_user = models.CharField(max_length=255, blank=True, null=True)  # 创建用户

    def __str__(self):
        return f"{self.so_num} - {self.customer_name}"

class RMCustomer(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 客户名称，唯一
    description = models.TextField(blank=True, null=True)  # 客户描述

    def __str__(self):
        return self.name

class OrderImage(models.Model):
    order = models.ForeignKey(RMOrder, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='order_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
class InvoiceCustomer(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 客户名称，唯一
    description = models.TextField(blank=True, null=True)  # 客户描述

    def __str__(self):
        return self.name

class RMProduct(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 产品名称，唯一
    shortname = models.CharField(max_length=255, blank=True, null=True)  # 短名称，唯一
    size = models.CharField(max_length=255, blank=True, null=True) # 产品尺寸
    TI = models.IntegerField(default=0) # 一层数量
    HI = models.IntegerField(default=0) # 层数
    Pallet = models.IntegerField(default=0) # 一个托盘数量
    Color = models.CharField(max_length=255, default='Red')
    Location = models.CharField(max_length=255, blank=True, null=True, default='')
    ShelfRecord = models.CharField(max_length=255, blank=True, null=True, default='')
    description = models.TextField(blank=True, null=True)  # 客户描述

    def __str__(self):
        return self.name

class OrderItem(models.Model):
    order = models.ForeignKey(RMOrder, related_name='order_items', on_delete=models.CASCADE)  # 关联到 RMOrder
    product = models.ForeignKey(RMProduct, on_delete=models.CASCADE)  # 关联到 RMProduct
    quantity = models.IntegerField()  # 产品数量

    def __str__(self):
        return f"{self.product.name} - {self.quantity} pcs"

class RMInventory(models.Model):
    product = models.ForeignKey(RMProduct, on_delete=models.CASCADE)  # 关联产品
    quantity_init =  models.IntegerField(blank=True, null=True)  # 初始数量
    quantity_diff =  models.IntegerField(default=0)  # 初始差异
    quantity = models.IntegerField()  # 已完成的出库（物流发货/交付给客户）
    quantity_for_neworder = models.IntegerField(default=0)  # 因新订单预定而预留的库存，还未出库
    quantity_to_stock = models.IntegerField(default=0)  # 放入备货区（内部使用、备货用途）所减少的库存

    def save(self, *args, **kwargs):
        # 如果 quantity_init 还没设置，默认等于 quantity
        if self.quantity_init is None:
            self.quantity_init = self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"  # 返回产品

class ClockRecord(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    # id = models.AutoField(primary_key=True)  # Make sure PK exists
    employee_name = models.ForeignKey('Employee', on_delete=models.CASCADE)  # 关联客户表
    date = models.DateField(verbose_name='Date')
    weekday = models.IntegerField(verbose_name='Weekday', choices=WEEKDAY_CHOICES)
    
    morning_in = models.TimeField(verbose_name='Morning Clock In', null=True, blank=True)
    morning_out = models.TimeField(verbose_name='Morning Clock Out', null=True, blank=True)
    
    afternoon_in = models.TimeField(verbose_name='Afternoon Clock In', null=True, blank=True)
    afternoon_out = models.TimeField(verbose_name='Afternoon Clock Out', null=True, blank=True)
    
    evening_in = models.TimeField(verbose_name='Evening Clock In', null=True, blank=True)
    evening_out = models.TimeField(verbose_name='Evening Clock Out', null=True, blank=True)
    
    total_hours = models.DecimalField(verbose_name='Total Hours', max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Clock Record'
        verbose_name_plural = 'Clock Records'
        ordering = ['-date']
    
    def calculate_total_hours(self):
        total_minutes = 0
        time_pairs = [
            (self.morning_in, self.morning_out),
            (self.afternoon_in, self.afternoon_out),
            (self.evening_in, self.evening_out)
        ]
        
        for time_in, time_out in time_pairs:
            # If string, convert to time object
            if isinstance(time_in, str):
                time_in = datetime.strptime(time_in, "%H:%M").time()
            if isinstance(time_out, str):
                time_out = datetime.strptime(time_out, "%H:%M").time()           
            
            if time_in and time_out:
                # Directly calculate time difference
                time_in_minutes = time_in.hour * 60 + time_in.minute
                time_out_minutes = time_out.hour * 60 + time_out.minute
                total_minutes += (time_out_minutes - time_in_minutes)
        
        self.total_hours = round(total_minutes / 60, 2)
        return self.total_hours

    def save(self, *args, **kwargs):
        old_total_hours = self.total_hours
        
        # 转换所有时间字段为time对象
        time_fields = ['morning_in', 'morning_out', 
                      'afternoon_in', 'afternoon_out',
                      'evening_in', 'evening_out']
        
        for field in time_fields:
            value = getattr(self, field)
            if isinstance(value, str):
                try:
                    time_obj = datetime.strptime(value, "%H:%M").time()
                    setattr(self, field, time_obj)
                except (ValueError, TypeError):
                    pass
        
        self.calculate_total_hours()

        # 只在更新现有记录时使用update_fields
        if self.pk and self.total_hours != old_total_hours:
            kwargs['update_fields'] = time_fields + ['total_hours']

        super().save(*args, **kwargs)

class Employee(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 员工名称，唯一
    belongTo = models.CharField(max_length=255, default="CabinetsDepot")

    def __str__(self):
        return self.name 

class LogisticsCompany(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 物流公司名称，唯一

    def __str__(self):
        return self.name

class Carrier(models.Model):
    name = models.CharField(max_length=255, unique=True)  # 公司名称

    def __str__(self):
        return self.name
    
class InboundCategory(models.Model):
    Type = models.CharField(max_length=255, default='')
    Name = models.CharField(max_length=255, default='')
    Manufacturer = models.CharField(max_length=255, default='')
    Carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.Type}"
    
def get_default_inbound_category():
    first = InboundCategory.objects.first()
    return first.id if first else None  # 避免为空时报错

class Container(models.Model):
    container_id = models.CharField(max_length=255)  # Container ID
    container_pdfname = models.CharField(max_length=255, blank=True)  # 上传的PDF文件名
    content = models.TextField(blank=True, null=True)  # 解析出的内容
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间
    created_user = models.CharField(max_length=255, blank=True, null=True)  # 创建用户
    plts = models.IntegerField()  # 托盘数量
    railway_date = models.DateField(blank=True, null=True)  # 铁路日期
    pickup_date = models.DateField(blank=True, null=True)  # 提货日期
    delivery_date = models.DateField(blank=True, null=True)  # 交货日期
    empty_date = models.DateField(blank=True, null=True)  # 空箱日期
    pickup_number = models.CharField(max_length=255, blank=True, null=True)  # 提货编号
    invoice_id = models.CharField(max_length=255, blank=True, null=True)  # 发票ID
    invoice_pdfname = models.CharField(max_length=255, blank=True, null=True)  # 发票PDF文件名
    customer = models.ForeignKey(InvoiceCustomer, on_delete=models.CASCADE, default=3)  # 关联到 InvoiceCustomer
    logistics = models.ForeignKey(LogisticsCompany, on_delete=models.CASCADE, default=1)  # 关联到 LogisticsCompany
    is_updateInventory = models.BooleanField(default=False) # 是否更新库存
    inboundCategory = models.ForeignKey(InboundCategory, on_delete=models.CASCADE,default=get_default_inbound_category)
    lot = models.CharField(max_length=255, blank=True, default="")
    
    class Meta:
        ordering = ['delivery_date']  # 默认按 delivery_date 升序排序

    def __str__(self):
        return f"{self.container_id}（交货: {self.delivery_date or 'N/A'}，空箱: {self.empty_date or 'N/A'}）"
    
class ContainerItem(models.Model):
    container = models.ForeignKey(Container, on_delete=models.CASCADE)  # 关联到 RMOrder
    product = models.ForeignKey(RMProduct, on_delete=models.CASCADE)  # 关联到 RMProduct
    quantity = models.IntegerField()  # 产品数量

    def __str__(self):
        return f"{self.product.name} - {self.quantity} pcs"



class AlineOrderRecord(models.Model):
    document_number = models.CharField(max_length=255)  # 文档编号
    order_number = models.CharField(max_length=255)  # 订单编号
    po_number = models.CharField(max_length=255)  # PO编号
    invoice_date = models.DateField(blank=True, null=True)  # 发票日期
    due_date = models.DateField(blank=True, null=True)  # 截止日期
    pdf_name = models.CharField(max_length=255)  # 文档名称
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.order_number} - {self.po_number} - {self.price}"