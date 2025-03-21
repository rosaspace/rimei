from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from ..models import Container,RMProduct,ContainerItem
from django.utils import timezone
from datetime import datetime
import json
from django.shortcuts import render, redirect

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
        container_items = ContainerItem.objects.filter(container=container)
        # 显示编辑页面
        return render(request, 'container/containerManager/edit_container.html', {
            'container': container,
            "products":products,
            "container_items":container_items})
        
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

# 保存Container Item
def save_containeritems(request, container_id):
    print("----------save_containeritems-------------",container_id)
    if request.method == "POST":
        container = Container.objects.get(container_id=container_id)
        # 假设您从 PDF 中提取的产品信息存储在一个字典中
        container_items_json = request.POST.get('containeritems')  # 获取产品信息
        print("订单项目JSON:", container_items_json)
        if container_items_json:
            order_items = json.loads(container_items_json)  # 解析JSON
            print("解析后的订单项目:", order_items)
            for item in order_items:
                product_name = item['item']
                quantity = item['qty']
                print(f"处理商品: {product_name}, 数量: {quantity}")
                products = RMProduct.objects.all()
                product = None
                for p in products:
                    if (p.shortname and p.shortname.strip() in product_name) or (p.name in product_name):
                        product = p
                        break
                if product:
                    ContainerItem.objects.create(container=container, product=product, quantity=int(quantity))
                else:
                    print(f"警告: 未找到匹配的产品 '{product_name}'")
        
        return redirect('rimeiorder')
    
    return JsonResponse({"error": "Invalid request"}, status=400)