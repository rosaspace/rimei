from django.shortcuts import render, redirect
from django.contrib import messages
from ..models import RMOrder, RMCustomer, OrderImage, Container, RMProduct,RMInventory, OrderItem, AlineOrderRecord, UserAndPermission
from .pdfextract import get_product_qty_with_inventory_from_order
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import JsonResponse
from django.db.models import Count
from datetime import datetime
from django.http import HttpResponse
import pandas as pd
import json
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from datetime import datetime
import os
from django.conf import settings

def add_order(request):
    if request.method == "POST":
        try:
            # 检查SO号是否已存在
            so_num = request.POST.get('so_num')
            if RMOrder.objects.filter(so_num=so_num).exists():
                messages.error(request, f'创建订单失败：SO号 {so_num} 已存在')

                customers = RMCustomer.objects.all()
                return render(request, 'container/rmorder/add_order.html', {
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
    return render(request, 'container/rmorder/add_order.html', {'customers': customers})

@require_http_methods(["GET", "POST"])
def edit_order(request, so_num):
    print("--------edit_order------",so_num)
    try:
        if request.method == "GET":
            order = RMOrder.objects.get(so_num=so_num)
            customers = RMCustomer.objects.all()
            order_items = OrderItem.objects.filter(order=order)
            orderitems_new = get_product_qty_with_inventory_from_order(order_items)
            print("---:",len(order_items),order.so_num)
            products = RMProduct.objects.all().order_by('name')
            return render(request, 'container/rmorder/edit_order.html', {
                'order': order,
                'customers': customers,
                'order_items': orderitems_new,
                'products': products,  # 加上这行
            })
        elif request.method == "POST":
            try:
                order = RMOrder.objects.get(so_num=so_num)
                new_so_num = request.POST.get('so_num')
                if new_so_num != so_num and RMOrder.objects.filter(so_num=new_so_num).exists():
                    messages.error(request, f'更新订单失败：SO号 {new_so_num} 已存在')
                    customers = RMCustomer.objects.all()
                    return render(request, 'container/rmorder/edit_order.html', {
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

                order.save()

                # 更新订单项目
                items_json  = request.POST.get('orderitems')
                print("---:",items_json)
                if items_json :
                    items = json.loads(items_json )

                    # ⚠️ 先清空旧的条目（如果你是编辑页面）
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
                return render(request, 'container/rmorder/edit_order.html', {
                    'order': order,
                    'customers': customers,
                    'order_items': order_items,
                    'products': products,
                })
        
        
    except RMOrder.DoesNotExist:
        messages.error(request, '订单不存在')
        return redirect('rimeiorder')


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
    
def export_pallet(request):
    # 获取请求中的月份和年份
    month = request.GET.get('month')
    year = request.GET.get('year')

    if month and year:
        # 过滤出指定月份的订单
        start_date = datetime(int(year), int(month), 1)
        if month == '12':
            end_date = datetime(int(year) + 1, 1, 1)  # 下一年1月1日
        else:
            end_date = datetime(int(year), int(month) + 1, 1)  # 下个月的1日

        # 查询 "gloves in" 数据
        gloves_in_orders = Container.objects.filter(empty_date__gte=start_date, empty_date__lt=end_date).order_by('empty_date')
        print("golve in : ",len(gloves_in_orders))

        # 创建 "gloves in" DataFrame
        gloves_in_data = {
            'Empty Date': [order.empty_date for order in gloves_in_orders],  # 假设有 empty_date 字段
            'Container ID': [order.container_id for order in gloves_in_orders],  # 假设有 container_id 字段
            'PLTS': [order.plts for order in gloves_in_orders],
        }
        gloves_in_df = pd.DataFrame(gloves_in_data)

        # 查询 "gloves out" 数据（根据您的需求进行调整）
        gloves_out_orders = RMOrder.objects.filter(outbound_date__gte=start_date, outbound_date__lt=end_date).order_by('outbound_date')
        print("golve in : ",len(gloves_out_orders))

        # 创建 "gloves out" DataFrame
        gloves_out_data = {
            'Outbound Date': [order.outbound_date for order in gloves_out_orders],
            'SO': [order.so_num for order in gloves_out_orders],
            'PLTS': [order.plts for order in gloves_out_orders],
        }
        gloves_out_df = pd.DataFrame(gloves_out_data)

        # 创建 Excel 文件
        with pd.ExcelWriter(f'orders_{year}_{month}_pallets.xlsx', engine='openpyxl') as writer:
            gloves_in_df.to_excel(writer, sheet_name='gloves in', index=False)
            gloves_out_df.to_excel(writer, sheet_name='gloves out', index=False)

        # 返回 Excel 文件
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="rmorders_{year}_{month}_pallets.xlsx"'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            gloves_in_df.to_excel(writer, sheet_name='gloves in', index=False)
            gloves_out_df.to_excel(writer, sheet_name='gloves out', index=False)

        return response
    else:
        return HttpResponse("Invalid month or year", status=400)
    
def import_inventory(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read the Excel file into a DataFrame
        df = pd.read_excel(excel_file, engine='openpyxl')

        # Ensure column names match the model fields
        for index, row in df.iterrows():
            # Create RMProduct instance
            product = RMProduct.objects.create(
                name=row["Display Name"],
                shortname = row["Short Name"],
                size = row["Size"],
                description=""  # description 为空
            )
            # Create RMInventory instance
            RMInventory.objects.create(
                product=product,
                quantity=row["Quantity On Hand"],
                quantity_for_neworder=row["Quantity On Hand"],
                quantity_to_stock=row["Quantity On Hand"],
            )

        return JsonResponse({"message": "Excel data imported successfully!"})
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

def import_aline(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read only the "Matched Records" sheet
        try:
            df = pd.read_excel(excel_file, sheet_name="Matched Records", engine="openpyxl")
        except ValueError:
            return JsonResponse({"error": "Sheet 'Matched Records' not found in the uploaded file"}, status=400)

        # Loop through each row and save to database
        for _, row in df.iterrows():
            try:
                AlineOrderRecord.objects.create(
                    document_number=row.get("Document Number", ""),  # 文档编号
                    order_number=row.get("Order No", ""),  # 订单编号
                    po_number=row.get("P.O. No.", ""),  # PO编号
                    invoice_date=pd.to_datetime(row.get("Date", None), errors="coerce").date()
                        if pd.notna(row.get("Date", None)) else None,  # 发票日期
                    due_date=pd.to_datetime(row.get("Due Date", None), errors="coerce").date()
                        if pd.notna(row.get("Due Date", None)) else None,  # 截止日期
                    pdf_name=row.get("PDFFileName", ""),  # 文档名称
                    price=row.get("Total", 0) if pd.notna(row.get("Total", 0)) else 0  # 价格
                )
            except Exception as e:
                return JsonResponse({"error": f"Failed to import row {row.to_dict()} - {str(e)}"}, status=400)

        return JsonResponse({"message": "Excel data imported successfully!"})
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

def preview_email(request, number):
    template = "container/temporary.html"
    recipient = "omarorders@omarllc.com;omarwarehouse@rimeius.com"
    recipient_advance = "jovana@advance77.com;tijana@advance77.com;raluca@advance77.com;intermodal@advance77.com"
    current_date = timezone.now().strftime("%m/%d/%Y")
    officedepot_id = request.POST.get('officedepot_number')
    print("officedepot_id: ",officedepot_id)

    if number == 1:
        context = {
            "recipient": recipient,
            "subject": f"INVENTORY {current_date}",
            "body": f"Hello,\n\nINVENTORY SUMMARY {current_date}. Paperwork attached.\n\nJing"
        }
    elif number == 4:
        context = {
            "recipient": recipient,
            "subject": f"OFFICE DEPOT #{officedepot_id} shipped out",
            "body": f"Hello,\n\nOffice Depot# {officedepot_id} has been shipped out. \nPaperwork is attached.\n\nThank you!\nJing"
        }
    elif number == 5:
        context = {
            "recipient": recipient,
            "subject": "Received Order Email",
            "body": "Well Received.\n\nThank you!\nJing"
        }
    else:
        context = {
            "recipient": recipient,
            "subject": "Received Order Email",
            "body": "Well Received.\n\nThank you!\nJing"
        }
    return render(request, template, context)

def get_user_permissions(user):
    # Use permissionIndex__name to get the name of the permission related to the UserAndPermission instance
    permissions = UserAndPermission.objects.filter(username=user).values_list('permissionIndex__name', flat=True)
    
    # Print the length of the permissions list (or log it)
    print("permissions: ", len(permissions))
    
    return permissions

def order_is_allocated_to_stock(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    order.is_allocated_to_stock = not order.is_allocated_to_stock
    order.save()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)

def order_email(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    email_type = request.GET.get("type", "shippeout")  # default to 'do' if not provided

    template = "container/temporary.html"
    recipient = "omarorders@omarllc.com;omarwarehouse@rimeius.com"
    recipient_advance = "jovana@advance77.com;tijana@advance77.com;raluca@advance77.com;intermodal@advance77.com"
    current_date = timezone.now().strftime("%m/%d/%Y")

    if email_type == "shippeout":
        context = {
            "recipient": recipient,
            "subject": f"SO# {order.so_num} PO# {order.po_num} shipped out",
            "body": f"Hello,\n\nSO# {order.so_num} PO# {order.po_num}  has been shipped out.\nPaperwork is attached.\n\nThank you!\nJing"
        }
    else:
        context = {
            "recipient": recipient,
            "subject": f"SO# {order.so_num} PO# {order.po_num} shipped out",
            "body": f"Hello,\n\nSO# {order.so_num} PO# {order.po_num}  has been shipped out.\nPaperwork is attached.\n\nThank you!\nJing"
        }
    return render(request, template, context)