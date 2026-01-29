import json
import os
import math

from datetime import datetime, date, timedelta
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, DatabaseError
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from ..constants import constants_address, constants_view
from ..models import Container, RMProduct, ContainerItem, InvoiceCustomer, LogisticsCompany, InboundCategory, RailwayStation, Carrier, Manufacturer

from .utils.getPermission import get_user_permissions
from .utils.pdfextract import get_product_qty_with_inventory_from_container
from .utils.pdfgenerate import print_containerid_lot, print_checklist_template

# container
@login_required(login_url='/login/')
def container_advance77(request):
    containers = Container.objects.select_related(
        'customer', 'logistics', 'Carrier', 'inboundCategory'
    ).order_by('-delivery_date') # logistics: 非Customer

    mode = request.GET.get("mode", "full")  # full / simple

    # 今天，计算本周的周一和周日
    today = date.today()    
    start_of_week = today - timedelta(days=today.weekday())   # 本周一
    end_of_week = start_of_week + timedelta(days=6)           # 本周日

    # GET 参数
    customer_id = request.GET.get('customer')
    logistics_id = request.GET.get('logistics')
    carrier_id = request.GET.get('carrier')
    category_id = request.GET.get('category')

    if customer_id:
        containers = containers.filter(customer_id=customer_id)

    if logistics_id:
        containers = containers.filter(logistics_id=logistics_id)

    if carrier_id:
        containers = containers.filter(Carrier_id=carrier_id)

    if category_id:
        containers = containers.filter(inboundCategory_id=category_id)

    user_permissions = get_user_permissions(request.user) 
    # 显示编辑页面
    if mode == "simple":
        template = constants_view.template_simplified_container
        containers = Container.objects.filter(Q(is_updateInventory = False)).order_by('delivery_date')
    else:
        template = constants_view.template_container  # 原完整版页面
    return render(request, constants_view.template_container, {
        'containers': containers,'user_permissions': user_permissions,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'customers': InvoiceCustomer.objects.all(),
        'logistics_list': LogisticsCompany.objects.all(),
        'carriers': Carrier.objects.filter(Q(id = 1) | Q(id=5) ),
        'inbound_categories': InboundCategory.objects.all(),
        })

@login_required(login_url='/login/')
def container_omar(request):
    containers = Container.objects.select_related(
        'customer', 'logistics', 'Carrier', 'inboundCategory'
    ).filter(Q(logistics = 2)).order_by('-delivery_date') # logistics: Customer, 排除Mcdonalds和Metal

    # 今天，计算本周的周一和周日
    today = date.today()    
    start_of_week = today - timedelta(days=today.weekday())   # 本周一
    end_of_week = start_of_week + timedelta(days=6)           # 本周日

    # GET 参数
    customer_id = request.GET.get('customer')
    logistics_id = request.GET.get('logistics')
    carrier_id = request.GET.get('carrier')
    category_id = request.GET.get('category')

    if customer_id:
        containers = containers.filter(customer_id=customer_id)

    if logistics_id:
        containers = containers.filter(logistics_id=logistics_id)

    if carrier_id:
        containers = containers.filter(Carrier_id=carrier_id)

    if category_id:
        containers = containers.filter(inboundCategory_id=category_id)

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_container, {
        'containers': containers,'user_permissions': user_permissions,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'customers': InvoiceCustomer.objects.exclude(Q(id = 1) | Q(id=2) | Q(id=3)| Q(id=12)),
        'logistics_list': LogisticsCompany.objects.all(),
        'carriers': Carrier.objects.filter(Q(id = 1) | Q(id=5) ),
        'inbound_categories': InboundCategory.objects.all(),
        })

# 新增Container
def add_container(request):
    """
    GET  : 显示添加 Container 页面
    POST : 处理新增 Container
    """

    # ===== GET：显示页面 =====
    if request.method == "GET":
        return render(request, constants_view.template_add_container, {
            'customers': InvoiceCustomer.objects.all(),
            'logistics': LogisticsCompany.objects.all(),
            'inboundCategory': InboundCategory.objects.all(),
            'manufacturer': Manufacturer.objects.all(),
            'railstation': RailwayStation.objects.all(),
            'carrier': Carrier.objects.all(),
        })

    # ===== POST：保存数据 =====
    if request.method == 'POST':
        try:
            # 检查SO号是否已存在
            container_id = request.POST.get('container_id')
            
            if Container.objects.filter(container_id=container_id).exists():
                return JsonResponse({
                    'error': True,
                    'message': f'创建Container失败：ID号 {container_id} 已存在'
                })
            
            # 获取基本字段
            pickup_number = request.POST.get('pickup_number')
            lot = request.POST.get('lot_number') or ""
            plts_value = request.POST.get('plts')
            refnumber = request.POST.get('ref_number') or ""
            mbl = request.POST.get('mbl') or ""
            weight = request.POST.get('weight') or "1"

           
            # 设置默认值（建议放在函数顶部）
            DEFAULT_INBOUND_CATEGORY = InboundCategory.objects.get(Type="BLUE GRILL")
            DEFAULT_STATION = RailwayStation.objects.get(name="CPRR/ BENSENVILLE")
            DEFAULT_CARRIER = Carrier.objects.get(name="SECURE SOURCE AMERICA")
            DEFAULT_Manufacturer = Manufacturer.objects.get(name="SUBIC MATERIALS LIMITED")
            DEFAULT_CUSTOMER = InvoiceCustomer.objects.get(name="GoldenFeather")
            DEFAULT_LOGISTICS = LogisticsCompany.objects.get(name="Advance77")            

            # ===== 外键 =====
            station = RailwayStation.objects.get(id=request.POST.get('station_name')) \
                if request.POST.get('station_name') else DEFAULT_STATION

            inbound_category = InboundCategory.objects.get(id=request.POST.get('inbound_category')) \
                if request.POST.get('inbound_category') else DEFAULT_INBOUND_CATEGORY

            carrier = Carrier.objects.get(id=request.POST.get('carrier_name')) \
                if request.POST.get('carrier_name') else DEFAULT_CARRIER

            manufacturer = Manufacturer.objects.get(id=request.POST.get('manufacturer')) \
                if request.POST.get('manufacturer') else DEFAULT_MANUFACTURER

            customer = InvoiceCustomer.objects.get(id=request.POST.get('customer_name')) \
                if request.POST.get('customer_name') else DEFAULT_CUSTOMER

            logistics = LogisticsCompany.objects.get(id=request.POST.get('logistics_name')) \
                if request.POST.get('logistics_name') else DEFAULT_LOGISTICS
            
            # 创建新的Container实例
            container = Container(
                container_id=container_id,
                pickup_number=pickup_number,
                plts = plts_value,
                lot = lot,
                refnumber = refnumber,
                mbl = mbl,
                weight = weight,
                inboundCategory= inbound_category,
                customer = customer,
                logistics = logistics,
                railwayStation = station,
                Carrier = carrier,
                manufacturer = manufacturer,
                created_at=timezone.now(),
                created_user=request.user,  # ✅ 保存创建人
            )
            
            # 更新日期字段
            date_fields = ['railway_date', 'pickup_date', 'delivery_date', 'empty_date']
            for field in date_fields:
                value = request.POST.get(field)
                setattr(container, field, datetime.strptime(value, '%Y-%m-%d').date() if value else None)
            
            # 处理PDF文件
            if 'container_pdf' in request.FILES:
                container.container_pdfname = request.FILES['container_pdf'].name
            
            container.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Container saved successfully'
            })
            
        except (IntegrityError, DatabaseError, Exception) as e:
            print("❌ Save failed:", str(e))
            return JsonResponse({
                'error': True,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# 修改Container
def edit_container(request, container_id):
    """处理编辑Container的API请求"""
    container = get_object_or_404(Container, container_id=container_id)

    mode = request.GET.get("mode", "full")  # full / simple
    
    if request.method == 'GET':
        
        if container.inboundCategory.id != 13:
            products = RMProduct.objects.exclude(type="Metal").order_by('name')
            print("Hello, Gloves")
        else:
            products = RMProduct.objects.filter(type="Metal").order_by('name')
            print("Hello, OBL")

        container_items = ContainerItem.objects.filter(container=container)
        container_items_new = get_product_qty_with_inventory_from_container(container_items)
        total_quantity = sum(int(item.quantity) for item in container_items_new)
        total_pallet = sum(int(item.pallet_qty) for item in container_items_new)
        customers = InvoiceCustomer.objects.all()
        logistics = LogisticsCompany.objects.all()
        inboundCategory = InboundCategory.objects.all()
        manufacturer = Manufacturer.objects.all()
        railstation = RailwayStation.objects.all()
        carrier = Carrier.objects.all()

        # 显示编辑页面
        if mode == "simple":
            template = constants_view.template_edit_simple_container
        else:
            template = constants_view.template_edit_container  # 原完整版页面
        return render(request, template, {
            'container': container, 
            "products": products,
            'customers': customers,
            'logistics': logistics,
            'inboundCategory':inboundCategory,
            'manufacturer':manufacturer,
            'railstation':railstation,
            'carrier':carrier,
            "container_items":container_items_new,
            'total_quantity': total_quantity,  # ✅ 加入模板变量
            'total_pallet':total_pallet,
        })
        
    elif request.method == 'POST':
        try:
            # 更新基本字段
            container.pickup_number = request.POST.get('pickup_number', container.pickup_number)
            container.lot = request.POST.get('lot_number', container.lot)
            container.refnumber = request.POST.get('ref_number', container.refnumber)
            container.mbl = request.POST.get('mbl', container.mbl)
            container.weight = request.POST.get('weight', container.weight)
            container.content = request.POST.get('description', container.content)
            container.is_updateInventory = request.POST.get('is_updateInventory') == 'on'
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
            container.manufacturer = Manufacturer.objects.get(id=request.POST.get('manufacturer'))
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
                filename = container.container_pdfname.name
                # 打印 PDF 文件名
                print(f"Uploaded PDF file name: {container.container_pdfname}")

                file_path = os.path.join(settings.MEDIA_ROOT, "containers", "original", filename)

               # 保存文件
                with open(file_path, 'wb+') as destination:
                    for chunk in container.container_pdfname.chunks():
                        destination.write(chunk)

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
            return redirect('container_advance77')  
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required(login_url='/login/')
def simplified_container_view(request):
    containers = Container.objects.filter(Q(is_updateInventory = False)).order_by('delivery_date')

    # 今天，计算本周的周一和周日
    today = date.today()    
    start_of_week = today - timedelta(days=today.weekday())   # 本周一
    end_of_week = start_of_week + timedelta(days=6)           # 本周日

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_simplified_container, {
        'containers': containers,'user_permissions': user_permissions,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,})

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
                        'redirect_url': '/container_advance77/'  # 这里添加你要跳转的订单列表页面的URL
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

# Container
def print_container_label(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    label_count = 10

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.LABEL_FOLDER)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    today_date = datetime.today().strftime("%m/%d/%Y").replace("/0", "/")  # Fix for Windows
    filename = os.path.join(pdf_path, f"{container_num}_old.pdf")  # Save inside "label" folder
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(f"Label - {container.container_id}")

    # Set font
    c.setFont("Helvetica-Bold", constants_address.FONT_SIZE_Container)
    
    y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", constants_address.FONT_SIZE_Container)  # Reset font on new page
            y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 

        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [MARGIN_LEFT, MARGIN_LEFT + LABEL_WIDTH]

            for x in x_positions:
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (LABEL_WIDTH / 2)
                text_y = y_position  - (constants_address.LABEL_HEIGHT / 2) - 10
                
                # Print first line (custom text) and second line (today's date)
                c.drawCentredString(text_x, text_y + (LINE_SPACING / 2), container_num)  # First line (higher)
                c.drawCentredString(text_x, text_y - (LINE_SPACING / 2), today_date)  # Second line (lower)
    
                # Draw label borders (for testing)
                if constants_address.DRAW_BORDERS:
                    c.rect(x, y_position - constants_address.LABEL_HEIGHT, constants_address.LABEL_WIDTH, constants_address.LABEL_HEIGHT)
    
                label_count -= 1  # Reduce remaining label count

            y_position -= constants_address.LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

    c.save()
    
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_container_color_label(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    containerItems = ContainerItem.objects.filter(container=container)

    small_font = request.GET.get("small_font") == "1"

    # 设置continuous
    continuous = False
    if(container.customer.id == 12):
        continuous = True

    # 统计每个 so_num 的数量
    so_label_map = {}
    for item in containerItems:
        pallet_qty = item.product.Pallet or 1  # 避免除以0
        plts = math.ceil(item.quantity / pallet_qty)

        try:
            product = item.product
            if product and product.shortname:
                so_num = product.shortname
                spec = product.Pallet

                if so_num not in so_label_map:
                    so_label_map[so_num] = {"count": 0, "spec": spec}

                so_label_map[so_num]["count"] += plts

        except AttributeError:
            continue

    if not so_label_map:
        return HttpResponse("找不到相关的订单号", status=400)

    # 通用信息
    container_id = container.container_id
    lot_number = container.lot
    # current_date = datetime.now().strftime('%m/%d/%Y')
    if container.delivery_date:
        current_date = container.delivery_date.strftime('%m/%d/%Y')
    else:
        current_date = "None"

    # PDF 路径设置
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container.container_id}.pdf")

    # 使用内存文件构建 PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # 设置showLot
    showLot = True
    if container.inboundCategory.id == 13:
        showLot = False

    # ===== 新增：连续打印控制 =====
    current_page_count = 0  # 当前页已打印 label 数量（最多 10）

    # for so_num, info in so_label_map.items():
    #     total_count = info["count"]
    #     spec = info["spec"]

    #     pages = (total_count + 9) // 10  # 计算需要的总页数，每页最多 10 个

    #     for page in range(pages):
    #         # 计算当前页应打印的 label 数量
    #         page_label_count = min(10, total_count - page * 10)
    #         try:
    #             print_containerid_lot(c, so_num, page_label_count, container_id, lot_number, current_date, spec, showLot)
    #             c.showPage()
    #         except Exception as e:
    #             print(f"生成标签出错：{e}")
    #             return HttpResponse(f"生成标签时出错：{e}", status=500)

    for so_num, info in so_label_map.items():
        total_count = info["count"]
        spec = info["spec"]

        remaining = total_count

        while remaining > 0:
            available_slots = 10 - current_page_count
            print_count = min(remaining, available_slots)

            try:
                print_containerid_lot(c, so_num, print_count, container_id, lot_number, current_date, spec, showLot, start_index=current_page_count, smallFont = small_font)
            except Exception as e:
                return HttpResponse(f"生成标签时出错：{e}", status=500)

            current_page_count += print_count
            remaining -= print_count

            # 页面满了才换页
            if current_page_count == 10:
                c.showPage()
                current_page_count = 0

        # 🔴 非连续模式：不同类型强制换页
        if not continuous and current_page_count > 0:
            c.showPage()
            current_page_count = 0

    # 如果最后一页没满，也要结束页面
    if current_page_count > 0:
        c.showPage()

    c.save()
    buffer.seek(0)

    # 保存到文件
    with open(filename, 'wb') as f:
        f.write(buffer.read())

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_container_detail(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    containerItems = ContainerItem.objects.filter(container=container)

    # 列表
    can_liner_details = []
    total_plts = 0

    for item in containerItems:
        pallet_qty = item.product.Pallet or 1  # 避免除以0
        plts = math.ceil(item.quantity // pallet_qty)
        plts_withextracase = math.ceil(item.quantity / pallet_qty)
        case = item.quantity % pallet_qty
        total_plts += plts_withextracase  # 累加托盘总数
        can_liner_details.append({
            "Size": item.product.size if hasattr(item.product, 'size') else "N/A",
            "Name": item.product.shortname,
            "Qty": str(item.quantity),
            "PLTS": str(plts),
            "Case": str(case),
        })

    # 基本信息
    container_info = {
        "Manufacturer": container.manufacturer,
        "Container Number": container.container_id,
        "Carrier": container.Carrier.name,
        "LOT#": container.lot,
        "Date": container.delivery_date.strftime("%m/%d/%Y") if container.delivery_date else "",
        "Product Validity": "",
        "Name": "OMAR",
        "Commodity": container.inboundCategory.Name,
        # "Can liner Size": '',
        "Total Pallets": str(total_plts),
    }

    # 保存路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.CHECKLIST_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)  # 如果目录不存在，则创建

    filename = os.path.join(pdf_path, f"container.container_id.pdf")
    title = f"Container - {container.container_id}"
    contentType = container.inboundCategory.Type
    contentTitle = f"Inbound Container {contentType} Quality Checklist"

    print_checklist_template(title,filename, contentTitle,container_info,can_liner_details, constants_address.note_lines)

    # 返回 PDF 响应
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_container_delivery_order(request, container_num):
    print("------------print_container_delivery_order------------")
    container = get_object_or_404(Container, container_id=container_num)

    # COLD ROLLING MILLS UN-COILER
    # Metal  Plastic Bag
    containerInfo = {
        "container_id": container.container_id,              # 集装箱编号
        "size_type": "40HQ",                        # 集装箱尺寸/类型
        "weight": f"{container.weight} LBS",                       # 重量
        "seal_number": "",                # 封条号
        "Remarks":"Overweight" if container.customer.id in [12, 3] else "",
        "commodity": "Metal" if container.customer.id == 12 else "Plastic Bag" ,                # 商品描述
        "vessel": "",               # 船名
        "voyage": "",                          # 航次
        "ssl": "",                          # 船公司（Shipping Line）

        "pickup_location": f"{container.railwayStation.name}\n{container.railwayStation.address}".replace("\\n", "\n").replace("\r\n", "\n"),
        "pickup_date": "Pending",                   # 提货日期
        "delivery_location": f"{container.Carrier.name}\n{container.Carrier.address}".replace("\\n", "\n").replace("\r\n", "\n"),
        "delivery_date": "Pending",                 # 送货日期

        "ref_no": container.refnumber,                 # 参考编号
        "mbl": container.mbl                   # 提单号
    }



    # PDF 路径设置
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.DO_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container.container_id}.pdf")

    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # 插入 logo
    logo_width, logo_height = 80, 80  
    logo_x = 0.5 * inch  # left_margin
    logo_y = height - logo_height - 40  # 顶部边距 10
    c.drawImage(ImageReader(constants_address.SSA_LOGO_PATH), logo_x, logo_y, width=logo_width, height=logo_height)

    # 样式设置
    left_margin = 0.5 * inch
    line_height = 18
    font_size = 10
    font_size_small = 8
    bold_font = "Helvetica-Bold"
    regular_font = "Helvetica"

    def draw_text(x, y, text, font=regular_font, size=font_size):
        c.setFont(font, size)
        c.drawString(x, y, text)

    y = height - 75

    # 标题
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2 , y, "DELIVERY ORDER")

    # US Headquarter
    y = height - 140
    draw_text(left_margin, y, "US Headquarter:", bold_font)
    for line in constants_address.Only_ADDRESS:
        draw_text(left_margin + 120, y, line)
        y -= line_height
    y += line_height

    # 右上角信息
    right_x = width - 240
    y += line_height
    draw_text(right_x, y, f"DATE: {datetime.now().strftime('%m/%d/%Y')}")
    y -= line_height
    draw_text(right_x, y, f"REF. NO: {containerInfo['ref_no']}")
    y -= line_height
    draw_text(right_x, y, f"MBL: {containerInfo['mbl']}")

    # Pickup / Delivery 信息
    # y -= 40
    y = y - line_height * 2  # 空一行

    # Pickup Location
    pickup_lines = containerInfo['pickup_location'].split('\n')
    pickup_y = y  # 记录起始高度
    draw_text(left_margin, pickup_y, "Pickup Location:", bold_font)
    for line in pickup_lines:
        draw_text(left_margin + 120, pickup_y, line, bold_font)
        pickup_y -= line_height
    # Pickup Date 与 Pickup Location 的首行对齐
    draw_text(right_x, y, f"Pickup Date:    {containerInfo['pickup_date']}")

    # Delivery Location
    y = pickup_y - line_height  # 空一行
    delivery_lines = containerInfo['delivery_location'].split('\n')
    delivery_y = y
    draw_text(left_margin, delivery_y, "Delivery Location:", bold_font)
    for line in delivery_lines:
        draw_text(left_margin + 120, delivery_y, line, bold_font)
        delivery_y -= line_height
    # Delivery Date 与 Delivery Location 的首行对齐
    draw_text(right_x, y, f"Delivery Date:    {containerInfo['delivery_date']}")
    y = delivery_y  # 更新 y 供后续使用

    # 提示
    y -= 20
    c.setFont(regular_font, font_size_small)
    for line in constants_address.DO_CONTACT_LINES:
        c.drawString(left_margin + 120, y, line)
        y -= line_height
    y += line_height

    # 表头
    y -= 20

    # 添加表头上方横线
    c.setLineWidth(1)
    c.line(left_margin, y + line_height -2, width - left_margin, y + line_height -2)

    table_headers = ["Container#", "Container Size/Type", "Weight", "Seal#", "Remarks"]
    col_widths = [120, 150, 100, 100, 100]
    x = left_margin
    for header, w in zip(table_headers, col_widths):
        draw_text(x, y, header, bold_font)
        x += w

    # 添加表头下方横线
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)

    # 数据行
    y -= line_height
    x = left_margin
    row_values = [
        containerInfo['container_id'],
        containerInfo['size_type'],
        containerInfo['weight'],
        containerInfo['seal_number'],
        containerInfo['Remarks']
    ]
    for value, w in zip(row_values, col_widths):
        draw_text(x, y, str(value))
        x += w

    # 添加数据行下方横线
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)

    # Footer
    y -= 20
    c.setFont(regular_font, font_size_small)
    footer_lines = [line.format(**containerInfo) for line in constants_address.DO_FOOTER_LINES_TEMPLATE]
    for line in footer_lines:
        c.drawString(left_margin + 120, y, line)
        y -= line_height

    # 签名区
    y -= 60
    for line in constants_address.DO_SIGNATURE_LINES:
        draw_text(width / 2, y, line)
        y -= line_height

    c.save()

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

