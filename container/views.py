from django.shortcuts import render, redirect, get_object_or_404
from .models import Container
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import UserAndPermission

# Create your views here.
def index(request):
    template = "container/base.html"
    return render(request, template)

def container_view(request):
    template = "container/container.html"
    containers = Container.objects.all()
    return render(request, template, {'containers': containers})

def invoice_view(request):
    template = "container/invoice.html"
    containers = Container.objects.all()
    return render(request, template, {'containers': containers})

def payment_view(request):
    template = "container/payment.html"
    return render(request, template)

def permission_view(request):
    # 查询所有用户及其权限
    users_with_permissions = []
    users = User.objects.all()  # 获取所有用户

    for user in users:
        permissions = user.userandpermission_set.all()  # 获取用户的所有权限
        user_permissions = {
            'username': user.username,
            'permissions': [permission.permissionIndex.name for permission in permissions]  # 获取权限名称
        }
        users_with_permissions.append(user_permissions)

    template = "container/permission.html"
    return render(request, template, {'users_with_permissions': users_with_permissions})

def edit_invoice(request, container_id):
    print("--------------edit_invoice-----------------")
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
    return render(request, 'container/invoiceManager/edit_invoice.html', {
        'container_id': container_id,
        'container': container  # 将容器信息传递给模板
    })

def edit_container(request, container_id):
    """处理编辑Container的API请求"""
    print("--------------edit_container-----------------")

    container = get_object_or_404(Container, container_id=container_id)
    
    if request.method == 'GET':
        # 显示编辑页面
        return render(request, 'container/containerManager/edit_container.html', {'container': container})
        
    elif request.method == 'POST':
        try:
            # 更新基本字段
            container.pickup_number = request.POST.get('pickup_number', container.pickup_number)
            
            # 更新日期字段
            date_fields = ['railway_date', 'pickup_date', 'delivery_date', 'empty_date']
            for field in date_fields:
                value = request.POST.get(field)
                if value:
                    parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
                    setattr(container, field, parsed_date)
                else:
                    setattr(container, field, None)
            
            # 处理PDF文件
            if 'container_pdfname' in request.FILES:
                # 如果有旧文件，可以选择删除
                if container.container_pdf:
                    container.container_pdf.delete()
                
                container.container_pdf = request.FILES['container_pdfname']
                container.container_pdfname = request.FILES['container_pdfname'].name
            
            container.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Container updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def add_invoice_view(request):
    template = "container/invoiceManager/add_invoice.html"
    return render(request, template)

