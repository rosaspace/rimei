from django.shortcuts import render, redirect
from .models import Container

# Create your views here.
def index(request):
    template = "container/base.html"
    return render(request, template)

def container_view(request):
    template = "container/container.html"
    return render(request, template)

def invoice_view(request):
    template = "container/invoice.html"
    containers = Container.objects.all()
    return render(request, template,{'containers': containers})

def payment_view(request):
    template = "container/payment.html"
    return render(request, template)

def add_invoice(request, container_id):
    if request.method == "POST":
        # 处理上传的发票 PDF 文件和解析逻辑
        # 这里需要实现解析 PDF 文件的逻辑
        # 假设解析后得到的地址、日期和金额
        address = "解析出的地址"
        date = "解析出的日期"
        amount = "解析出的金额"

        # 保存发票信息到数据库
        container = Container.objects.get(id=container_id)
        container.invoice_id = "生成的发票ID"  # 生成或获取发票ID
        container.invoice_pdfname = request.FILES['invoice_file'].name  # 保存文件名
        container.content = "解析出的内容"  # 保存解析内容
        container.save()

        return redirect('invoice')  # 重定向到发票页面

    # 查询容器的完整信息
    container = Container.objects.get(container_id=container_id)  # 获取完整的容器信息
    return render(request, 'container/invoice/add_invoice.html', {
        'container_id': container_id,
        'container': container  # 将容器信息传递给模板
    })

