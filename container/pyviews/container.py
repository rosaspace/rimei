from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from ..models import Container,RMProduct,ContainerItem,InvoiceCustomer,LogisticsCompany,InboundCategory,RailwayStation,Carrier
from django.utils import timezone
from datetime import datetime
import json
from django.shortcuts import render, redirect
from django.contrib import messages

# 打开添加Container页面
def add_container_view(request):
    """显示添加Container的页面"""
    customers = InvoiceCustomer.objects.all()
    logistics = LogisticsCompany.objects.all()
    return render(request, 'container/containerManager/add_container.html',{'customers': customers,'logistics':logistics})

# 新增Container
def add_container(request):
    """处理添加Container的API请求"""
    print("----------add_container-----------")
    if request.method == 'POST':
        try:
            # 检查SO号是否已存在
            container_id = request.POST.get('container_id')
            print("---:", container_id)
            if Container.objects.filter(container_id=container_id).exists():
                print("---已存在")
                messages.error(request, f'创建Container失败：ID号 {container_id} 已存在')

                return JsonResponse({
                    'error': True,
                    'message': f'创建Container失败：ID号 {container_id} 已存在'
                })
            
            # 获取基本字段
            # container_id = request.POST.get('container_id')
            pickup_number = request.POST.get('pickup_number')
            plts_value = request.POST.get('plts')
            # customer_name = request.POST.get('customer_name')
            # logistics_name = request.POST.get('logistics_name')
            customer_name = InvoiceCustomer.objects.get(id=request.POST.get('customer_name'))
            logistics_name = LogisticsCompany.objects.get(id=request.POST.get('logistics_name'))
            print("plts_value: ",plts_value)
            print("customer_name: ",customer_name)
            print("logistics_name: ",logistics_name)
            
            # 创建新的Container实例
            container = Container(
                container_id=container_id,
                pickup_number=pickup_number,
                plts = plts_value,
                customer = customer_name,
                logistics = logistics_name,
                created_at=timezone.now(),
                created_user=request.user,  # ✅ 保存创建人
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
        customers = InvoiceCustomer.objects.all()
        logistics = LogisticsCompany.objects.all()
        inboundCategory = InboundCategory.objects.all()
        railstation = RailwayStation.objects.all()
        carrier = Carrier.objects.all()

        # 显示编辑页面
        return render(request, 'container/containerManager/edit_container.html', {
            'container': container,
            "products": products,
            'customers': customers,
            'logistics': logistics,
            'inboundCategory':inboundCategory,
            'railstation':railstation,
            'carrier':carrier,
            "container_items":container_items})
        
    elif request.method == 'POST':
        try:
            # 更新基本字段
            container.pickup_number = request.POST.get('pickup_number', container.pickup_number)
            container.lot = request.POST.get('lot_number', container.lot)
            container.refnumber = request.POST.get('ref_number', container.refnumber)
            container.mbl = request.POST.get('mbl', container.mbl)
            print(f"pickup_number: {container.pickup_number}")

            # 更新 PLTS 字段
            plts_value = request.POST.get('plts')
            if plts_value is not None:
                container.plts = int(plts_value)  # 将 PLTS 转换为整数并保存
                print(f"PLTS updated to: {container.plts}")

            print("---:",request.POST.get('carrier_name'))
            container.customer = InvoiceCustomer.objects.get(id=request.POST.get('customer_name'))
            container.logistics = LogisticsCompany.objects.get(id=request.POST.get('logistics_name'))
            container.inboundCategory= InboundCategory.objects.get(id=request.POST.get('inbound_category'))
            container.railwayStation= RailwayStation.objects.get(id=request.POST.get('station_name'))
            container.Carrier = Carrier.objects.get(id=request.POST.get('carrier_name'))
            
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

            # 🟢 保存 containeritems
            items_json  = request.POST.get('containeritems')
            if items_json :
                items = json.loads(items_json )

                # ⚠️ 先清空旧的条目（如果你是编辑页面）
                container.containeritem_set.all().delete()

                for item in items:
                    product = RMProduct.objects.get(id=item['product_id'])
                    quantity = int(item['quantity'])

                    ContainerItem.objects.create(
                        container=container,
                        product=product,
                        quantity=quantity
                    )
            
            messages.success(request, 'Container更新成功！')
            return redirect('container')
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# 更新库存
def receivedin_inventory(request, container_id):
    print("-------------receivedin_inventory--------------")
    print(container_id)
    if request.method == 'POST':
        try:
            container = Container.objects.get(container_id=container_id)
            container.is_updateInventory = not container.is_updateInventory
            container.save()

            return JsonResponse({
                        'success': True,
                        'is_updateInventory': container.is_updateInventory,
                        'redirect_url': '/container/'  # 这里添加你要跳转的订单列表页面的URL
                    })
        except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)})
        
def container_ispay(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    container.ispay = not container.ispay
    container.save()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)

def container_customer_ispay(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    container.customer_ispay = not container.customer_ispay
    container.save()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)