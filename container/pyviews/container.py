from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from ..models import Container,RMProduct
from django.utils import timezone
from datetime import datetime

# 打开添加Container页面
def add_container_view(request):
    """显示添加Container的页面"""
    return render(request, 'container/containerManager/add_container.html')

# 新增Container
def add_container(request):
    """处理添加Container的API请求"""
    print("----------add_container-----------")
    if request.method == 'POST':
        try:
            # 获取基本字段
            container_id = request.POST.get('container_id')
            pickup_number = request.POST.get('pickup_number')
            plts_value = request.POST.get('plts')
            
            # 创建新的Container实例
            container = Container(
                container_id=container_id,
                pickup_number=pickup_number,
                plts = plts_value,
                created_at=timezone.now()
            )
            
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
            if 'container_pdf' in request.FILES:
                container.container_pdfname = request.FILES['container_pdf'].name
            
            container.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Container saved successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# 修改Container
def edit_container(request, container_id):
    """处理编辑Container的API请求"""
    container = get_object_or_404(Container, container_id=container_id)
    
    if request.method == 'GET':
        products = RMProduct.objects.all()
        # 显示编辑页面
        return render(request, 'container/containerManager/edit_container.html', {'container': container,"products":products})
        
    elif request.method == 'POST':
        try:
            # 更新基本字段
            container.pickup_number = request.POST.get('pickup_number', container.pickup_number)
            print(f"pickup_number: {container.pickup_number}")

            # 更新 PLTS 字段
            plts_value = request.POST.get('plts')
            if plts_value is not None:
                container.plts = int(plts_value)  # 将 PLTS 转换为整数并保存
                print(f"PLTS updated to: {container.plts}")
            
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
            if 'container_pdf' in request.FILES:
                container.container_pdfname = request.FILES['container_pdf']                
                # 打印 PDF 文件名
                print(f"Uploaded PDF file name: {container.container_pdfname}")

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

def save_containeritems(request, container_id):
    print("----------save_containeritems-------------",container_id)
    return JsonResponse({
                'success': True,
                'message': 'Container updated successfully'
            })