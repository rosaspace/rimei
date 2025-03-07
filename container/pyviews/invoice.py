from ..models import Container
from django.shortcuts import render, redirect

def edit_invoice(request, container_id):
    print("--------------edit_invoice-----------------", container_id)
    if request.method == "POST":

        print("-----------------edit_invoice1-----------------")
        # 保存发票信息到数据库
        container = Container.objects.get(id=container_id)
        container.invoice_id = "生成的发票ID"  # 生成或获取发票ID
        if 'invoice_file' in request.FILES:
            container.invoice_pdfname = request.FILES['invoice_file']  # 保存文件名
        container.content = "解析出的内容"  # 保存解析内容
        container.save()

        return redirect('invoice')  # 重定向到发票页面

    # 查询容器的完整信息
    print("-----------------edit_invoice2-----------------")
    container = Container.objects.get(container_id=container_id)  # 获取完整的容器信息
    return render(request, 'container/invoiceManager/edit_invoice.html', {
        'container_id': container_id,
        'container': container  # 将容器信息传递给模板
    })


def add_invoice_view(request):
    template = "container/invoiceManager/add_invoice.html"
    return render(request, template)