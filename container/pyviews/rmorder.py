import json
import os

from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse

from datetime import datetime,date
from decimal import Decimal, ROUND_HALF_UP

from ..models import RMOrder, RMCustomer, OrderImage, RMProduct,OrderItem, UserAndPermission
from .pdfextract import get_product_qty_with_inventory_from_order,extract_order_info,extract_items_from_pdf,get_product_qty_with_inventory
from ..constants import constants_address,constants_view
from .pdfgenerate import extract_text_from_pdf, converter_metal_invoice

def add_order(request):
    if request.method == "POST":
        try:
            # 检查SO号是否已存在
            so_num = request.POST.get('so_num')
            if RMOrder.objects.filter(so_num=so_num).exists():
                messages.error(request, f'创建订单失败：SO号 {so_num} 已存在')

                customers = RMCustomer.objects.all()
                return render(request, constants_view.template_add_order, {
                    'so_no': so_num,
                    'po_no': request.POST.get('po_num'),
                    'plts': request.POST.get('plts'),
                    'bill_to': request.POST.get('bill_to'),
                    'ship_to': request.POST.get('ship_to'),
                    "order_date": request.POST.get('order_date'),
                    'pickup_date': request.POST.get('pickup_date'),
                    'outbound_date': request.POST.get('outbound_date'),
                    'customers':customers,
                    'customer_name': RMCustomer.objects.get(id=request.POST.get('customer_name')),
                    'is_sendemail': request.POST.get('is_sendemail') == 'on',
                    'is_updateInventory': request.POST.get('is_updateInventory') == 'on',
                    'is_canceled': request.POST.get('is_canceled') == 'on',
                    'is_allocated_to_stock': request.POST.get('is_allocated_to_stock') == 'on',
                    'order_pdfname':request.POST.get('order_pdfname')  # 添加这一行
                })
            
            print("------add_order-----")
            customer = RMCustomer.objects.get(id=request.POST.get('customer_name'))
            order = RMOrder(
                so_num=request.POST.get('so_num'),
                po_num=request.POST.get('po_num'),
                plts=request.POST.get('plts'),
                customer_name=customer,
                bill_to=request.POST.get('bill_to'),
                ship_to=request.POST.get('ship_to'),
                order_pdfname = request.POST.get('order_pdfname'),
                order_date = request.POST.get('order_date') or None,
                pickup_date=request.POST.get('pickup_date') or None,
                outbound_date=request.POST.get('outbound_date') or None,
                is_sendemail=request.POST.get('is_sendemail') == 'on',
                is_updateInventory=request.POST.get('is_updateInventory') == 'on',
                is_canceled=request.POST.get('is_canceled') == 'on',
                is_allocated_to_stock=request.POST.get('is_allocated_to_stock') == 'on',  
                created_user=request.user,  # ✅ 保存创建人           
            )
            order.save()

            # 假设您从 PDF 中提取的产品信息存储在一个字典中
            order_items_json = request.POST.get('orderitems')  # 获取产品信息
            print("hello??",order_items_json)
            if order_items_json:
                print("hello??")
                order_items = json.loads(order_items_json)  # 解析JSON
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
                        # 创建订单明细
                        OrderItem.objects.create(order=order, product=product, quantity=int(quantity))
                    else:
                        print(f"警告: 未找到匹配的产品 '{product_name}'")
            
            # 更新库存for neworder


            return redirect('rimeiorder')
        except Exception as e:
            messages.error(request, f'创建订单失败：{str(e)}')
    # GET请求处理
    customers = RMCustomer.objects.all()
    return render(request, constants_view.template_add_order, {'customers': customers})

@require_http_methods(["GET", "POST"])
def edit_order(request, so_num):
    print("--------edit_order------",so_num) 
    try:
        if request.method == "GET":
            order = RMOrder.objects.get(so_num=so_num)
            print("customer_name:",order.customer_name)
            customers = RMCustomer.objects.all()
            order_items = OrderItem.objects.filter(order=order)
            orderitems_new = get_product_qty_with_inventory_from_order(order_items)
            # ✅ 计算总重量（假设每项是字典，键名为 'weight'）
            total_weight = sum(float(item.weight) for item in orderitems_new if item.weight)
            total_quantity = sum(int(item.quantity) for item in orderitems_new)
            total_pallet = sum(int(item.pallet_qty) for item in orderitems_new)

            # price
            total_price = sum((Decimal(item.totalprice) for item in orderitems_new), Decimal('0.00'))
            total_price = total_price.quantize(Decimal('0.00'),rounding=ROUND_HALF_UP)
            total_tax = (total_price * Decimal('0.0825')).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            total_grand = total_price + total_tax
            total_credit_price = total_grand + (total_grand * Decimal('0.025')).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

            # products = RMProduct.objects.all().order_by('name')
            if order.customer_name.id != 19:
                products = RMProduct.objects.exclude(type="Metal").order_by('name')
                print("Hello, Gloves")
            else:
                products = RMProduct.objects.filter(type="Metal").order_by('name')
                print("Hello, OBL")

            return render(request, constants_view.template_edit_order, {
                'order': order,
                'customers': customers,
                'order_items': orderitems_new, 
                'products': products,  # 加上这行
                'total_weight': total_weight,  # ✅ 加入模板变量
                'total_quantity': total_quantity,  # ✅ 加入模板变量
                'total_pallet':total_pallet,
                'total_price':total_price,
                'total_grand':total_grand,
                'total_credit_price':total_credit_price,
            })
        elif request.method == "POST":
            try:
                order = RMOrder.objects.get(so_num=so_num)
                new_so_num = request.POST.get('so_num')
                if new_so_num != so_num and RMOrder.objects.filter(so_num=new_so_num).exists():
                    messages.error(request, f'更新订单失败：SO号 {new_so_num} 已存在')
                    customers = RMCustomer.objects.all()
                    return render(request, constants_view.template_edit_order, {
                        'order': order,
                        'customers': customers
                    })

                customer = RMCustomer.objects.get(id=request.POST.get('customer_name'))
                order.so_num = new_so_num
                order.po_num = request.POST.get('po_num')
                order.plts = request.POST.get('plts')
                order.customer_name = customer
                order.bill_to = request.POST.get('bill_to')
                order.ship_to = request.POST.get('ship_to')
                order.pickup_date = request.POST.get('pickup_date') or None 
                order.outbound_date = request.POST.get('outbound_date') or None
                order.is_sendemail = request.POST.get('is_sendemail') == 'on'
                order.is_updateInventory = request.POST.get('is_updateInventory') == 'on'
                order.is_canceled = request.POST.get('is_canceled') == 'on'
                order.is_allocated_to_stock = request.POST.get('is_allocated_to_stock') == 'on' 

                # 处理PDF文件
                if 'order_pdf' in request.FILES:
                    uploaded_file = request.FILES['order_pdf']
                    order.order_pdfname = uploaded_file.name  # 保存文件名到模型字段（如果需要）

                    # 打印 PDF 文件名
                    print(f"Uploaded PDF file name: {order.order_pdfname}")

                    # 构造保存路径
                    order_dir = os.path.join(settings.MEDIA_ROOT, "orders", "ORDER")
                    os.makedirs(order_dir, exist_ok=True)  # 确保目录存在
                    file_path = os.path.join(order_dir, uploaded_file.name)

                    # 保存文件
                    with open(file_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)
                
                if 'invoice_pdf' in request.FILES:
                    uploaded_file = request.FILES['invoice_pdf']
                    order.invoice_pdfname = uploaded_file.name  # 保存文件名到模型字段（如果需要）

                    # 打印 PDF 文件名
                    print(f"Uploaded Invoice PDF file name: {order.invoice_pdfname}")

                    # 构造保存路径
                    order_dir = os.path.join(settings.MEDIA_ROOT, "orders", "INVOICE")
                    os.makedirs(order_dir, exist_ok=True)  # 确保目录存在
                    file_path = os.path.join(order_dir, uploaded_file.name)

                    # 保存文件
                    with open(file_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)

                order.save()

                # 更新订单项目
                items_json  = request.POST.get('orderitems')
                print("---:",items_json)
                if items_json :
                    items = json.loads(items_json )

                    # 先清空旧的条目（如果你是编辑页面）
                    OrderItem.objects.filter(order=order).delete()
                    for item in items:
                        product = RMProduct.objects.get(id=item['product_id'])
                        quantity = int(item['quantity'])
                        print("---:",product,quantity)
                        
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=int(quantity)
                        )                            

                
                return redirect('rimeiorder')
            except Exception as e:
                messages.error(request, f'更新订单失败：{str(e)}')
                customers = RMCustomer.objects.all()
                order_items = OrderItem.objects.filter(order=order)
                products = RMProduct.objects.all().order_by('name')
                return render(request, constants_view.template_edit_order, {
                    'order': order,
                    'customers': customers,
                    'order_items': order_items,
                    'products': products,
                })
        
        
    except RMOrder.DoesNotExist:
        messages.error(request, '订单不存在')
        return redirect('rimeiorder')

# Order pdf
def upload_orderpdf(request):
    print("------upload_orderpdf--------\n")
    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf_file = request.FILES["pdf_file"]

        upload_dir = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order)  # 确保路径在 MEDIA_ROOT 目录下

        # ✅ 如果目录不存在，则创建
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(constants_address.UPLOAD_DIR_order, constants_address.ORDER_FOLDER, pdf_file.name)

        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)

        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        # print(extracted_text)
        so_no, order_date, po_no, pickup_date, bill_to, ship_to, items, quantities = extract_order_info(extracted_text)
        orderitems = extract_items_from_pdf(extracted_text)
        orderitems_new = get_product_qty_with_inventory(orderitems)

        # Convert to a datetime object
        if isinstance(order_date, str):
            order_date = datetime.strptime(order_date, "%Y-%m-%d").date()  # Convert to date
        elif isinstance(order_date, datetime):
            order_date = order_date.date()  # Convert datetime to date
        elif not isinstance(order_date, date):
            order_date = date.today()  # Default fallback if somehow not a date
        if isinstance(pickup_date, str):
            pickup_date = datetime.strptime(pickup_date, "%Y-%m-%d").date()  # Convert to date
        elif isinstance(pickup_date, datetime):
            pickup_date = pickup_date.date()  # Convert datetime to date
        elif not isinstance(pickup_date, date):
            pickup_date = date.today()  # Default fallback if somehow not a date

        context = {
            "so_no": so_no,
            "order_date": order_date,
            "po_no": po_no,
            "pickup_date":pickup_date,
            "bill_to":bill_to,
            "ship_to":ship_to,
            "items":items,
            "quantities":quantities,
            "orderitems":orderitems_new,
            'customers': RMCustomer.objects.all(),
            'order_pdfname': pdf_file.name
        }        
        
        return render(request, constants_view.template_add_order,context)

    return render(request, constants_view.template_rmorder)

@require_http_methods(["POST"])
def order_images(request, order_id):
    try:
        order = RMOrder.objects.get(id=order_id)
        images = request.FILES.getlist('images')  # 获取上传的图片

        for image in images:
            OrderImage.objects.create(order=order, image=image)  # 保存图片与订单的关联

        return JsonResponse({"success": True})
    except RMOrder.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order does not exist."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def order_is_allocated_to_stock(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    order.is_allocated_to_stock = not order.is_allocated_to_stock
    order.save()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)

def edit_order_simple(request, so_num):
    print("--------edit_order------",so_num)
    try:
        if request.method == "GET":
            order = RMOrder.objects.get(so_num=so_num)
            customers = RMCustomer.objects.all()
            order_items = OrderItem.objects.filter(order=order)
            orderitems_new = get_product_qty_with_inventory_from_order(order_items)
            # ✅ 计算总重量（假设每项是字典，键名为 'weight'）
            total_weight = sum(float(item.weight) for item in orderitems_new if item.weight)
            total_quantity = sum(int(item.quantity) for item in orderitems_new)
            total_pallet = sum(int(item.pallet_qty) for item in orderitems_new)
            products = RMProduct.objects.all().order_by('name')
            return render(request, constants_view.template_edit_simple_order, {
                'order': order,
                'customers': customers,
                'order_items': orderitems_new,
                'products': products,  # 加上这行
                'total_weight': total_weight,  # ✅ 加入模板变量
                'total_quantity': total_quantity,  # ✅ 加入模板变量
                'total_pallet':total_pallet,
            })
        
    except RMOrder.DoesNotExist:
        messages.error(request, '订单不存在')
        return redirect('rimeiorder')

def print_metal_invoice(request, order_id, isInvoice=0, discount_percent=20):
    print("----------print_metal_invoice----------")
    print("isInvoice: ", isInvoice)

    discount_percent = int(request.GET.get("discount", 0))
    
    order = get_object_or_404(RMOrder, so_num=order_id)
    order_items = OrderItem.objects.filter(order=order)
    orderitems_new = get_product_qty_with_inventory_from_order(order_items)

    # 填充发票条目
    amount_items = []
    for obj in orderitems_new:
        item = obj.so_num  # 保留原始 item 对象（不是字符串）

        desc = (getattr(obj, "description", "") or "").strip()
        units = Decimal(str(getattr(obj, "quantity", 0) or 0))
        rate = Decimal(str(getattr(obj, "price", 0) or 0))

        # totalprice 优先
        if hasattr(item, "totalprice") and item.totalprice:
            amount = Decimal(item.totalprice)
        else:
            amount = Decimal(units) * Decimal(rate)

        amount_items.append((item, desc, units, rate, amount))
        print("desc: ",desc)


    # 构造新的文件路径
    new_filename = f"{order.so_num}.pdf"
    output_dir = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_METAL_ORDER)
    output_file_path = os.path.join(output_dir, new_filename)  # ✅ 拼接完整路径
    converter_metal_invoice(order, amount_items, output_dir, new_filename, isInvoice, discount_percent)
    
    # 打开并读取PDF文件
    with open(output_file_path , 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{new_filename}"'
        return response