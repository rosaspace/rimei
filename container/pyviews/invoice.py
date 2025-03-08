from ..models import Container
from django.shortcuts import render, redirect
from django.http import JsonResponse

def add_invoice(request):
    print("--------------add_invoice-----------------")
    if request.method == "POST":
        print("-----------------add_invoice_post-----------------")
        # 创建新容器实例
        container = Container()  
        container.invoice_id = "生成的发票ID"  # 生成或获取发票ID
        print("----------hello1----------------")
        if 'invoice_file' in request.FILES:
            print("----------hello2----------------")
            container.invoice_pdfname = request.FILES['invoice_file']  # 保存文件名
            print("----------hello2----------------",container.invoice_pdfname)
        container.content = "解析出的内容"  # 保存解析内容
        container.save()

        # return redirect('invoice')  # 重定向到发票页面
        return JsonResponse({"success": True})  # 返回成功的 JSON 响应

    return render(request, 'container/invoiceManager/add_invoice.html', {
        'container_id': None,
        'container': None  # 新增发票时没有容器信息
    })

def edit_invoice(request, container_id):
    print("--------------edit_invoice-----------------", container_id)
    if request.method == "POST":
        print("-----------------edit_invoice_post-----------------")
        container = Container.objects.get(container_id=container_id)  # 获取现有容器实例
        container.invoice_id = "生成的发票ID"  # 生成或获取发票ID
        if 'invoice_file' in request.FILES:
            container.invoice_pdfname = request.FILES['invoice_file']  # 保存文件名
        container.content = "解析出的内容"  # 保存解析内容
        container.save()

        return JsonResponse({"success": True})

    # 查询容器的完整信息
    print("-----------------edit_invoice_get-----------------")
    container = Container.objects.get(container_id=container_id)  # 获取完整的容器信息

    return render(request, 'container/invoiceManager/add_invoice.html', {
        'container_id': container_id,
        'container': container  # 将容器信息传递给模板 
    })

def add_invoice_view(request):
    """显示添加Invoice的页面"""
    return render(request, 'container/invoiceManager/add_invoice.html')
