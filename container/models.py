from django.db import models

class Container(models.Model):
    file_name = models.CharField(max_length=255)  # 上传的PDF文件名
    content = models.TextField()  # 解析出的内容
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间

    def __str__(self):
        return self.file_name
