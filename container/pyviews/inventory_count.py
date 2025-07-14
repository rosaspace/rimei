import openpyxl
import math

from ..models import RMOrder, RMCustomer, OrderImage, Container, RMProduct, OrderItem, AlineOrderRecord, ContainerItem, UserAndPermission

from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.http import HttpResponse

from datetime import datetime, date, time
from openpyxl.utils import get_column_letter
from io import BytesIO
from collections import defaultdict
from django.db.models import Q

from ..constants import constants_view
from .getPermission import get_user_permissions

def inventory_view(request):
    inventory_items = RMProduct.objects.filter(type = "Rimei")
    print("----------inventory_view------------",len(inventory_items))
    inventory_items_converty = []
    total_pallets = 0
    total_pallets2 = 0
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)
        total_pallets += productTemp.totalPallet
        total_pallets2 += product.quantity // product.Pallet

        inventory_items_converty.append(productTemp)
        inventory_items_converty = sorted(inventory_items_converty, key=lambda x: x.name)

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_inventory, {
        "inventory_items": inventory_items_converty,
        'user_permissions': user_permissions,
        'total_pallets' : total_pallets,
        'total_pallets2' : total_pallets2
    })

def inventory_diff_view(request):
    inventory_items = RMProduct.objects.filter(type = "Rimei")

    diff_items = []  # 用来存储有差异的库存记录
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list, inbound_actual_list = get_quality(product)

        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        if productTemp.quantity != productTemp.quantity_for_neworder:
            diff_items.append(productTemp)

        diff_items = sorted(diff_items, key=lambda x: x.quantity_for_neworder)

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_inventory, {"inventory_items": diff_items,'user_permissions': user_permissions})

def inventory_metal(request):
    inventory_items = RMProduct.objects.filter(type = "Metal")

    inventory_items_converty = []  # 用来存储有差异的库存记录
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list, inbound_actual_list = get_quality(product)

        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        inventory_items_converty.append(productTemp)
        inventory_items_converty = sorted(inventory_items_converty, key=lambda x: x.name)

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_inventory, {"inventory_items": inventory_items_converty,'user_permissions': user_permissions})

def inventory_mcd(request):
    inventory_items = RMProduct.objects.filter(Q(type="Mcdonalds") | Q(type="Other"))

    inventory_items_converty = []  # 用来存储有差异的库存记录
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list, inbound_actual_list = get_quality(product)

        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        inventory_items_converty.append(productTemp)
        inventory_items_converty = sorted(inventory_items_converty, key=lambda x: (x.type,x.name))

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_inventory, {"inventory_items": inventory_items_converty,'user_permissions': user_permissions})

def export_stock(request):
    inventory_items = RMProduct.objects.all()
    print("----------export_stock------------", len(inventory_items))
    inventory_items_converty = []

    for product in inventory_items:
        inbound_list, outbound_list, outbound_actual_list, outbound_stock_list, inbound_actual_list = get_quality(product)

        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        inventory_items_converty.append(productTemp)

    inventory_items_converty = sorted(inventory_items_converty, key=lambda x: (x.type, x.name))
    user_permissions = get_user_permissions(request.user)

    # 🔽 Export to Excel if requested
    if request.GET.get("export") == "1":
        return export_inventory_to_excel(inventory_items_converty)

    return render(request, constants_view.template_inventory, {
        "inventory_items": inventory_items_converty,
        "user_permissions": user_permissions
    })

def order_history(request,product_id):
    product = get_object_or_404(RMProduct, id=product_id)

    # 查询库存记录
    inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)

    # 计算入库总数量
    total_inbound_quantity = sum(item['quantity'] or 0 for item in inbound_list)
    # 计算出库总数量
    total_outbound_quantity = sum(item['quantity'] or 0 for item in outbound_list)
    # 计算实际入库数量
    total_inbound_actual_quantity = sum(item['quantity'] or 0 for item in inbound_actual_list)
    # 计算实际出库数量
    total_outbound_actual_quantity = sum(item['quantity'] or 0 for item in outbound_actual_list)
    # 计算备货区数量
    total_outbound_stock_quantity = sum(item['quantity'] or 0 for item in outbound_stock_list)

    total_surplus_quantity = total_inbound_quantity - total_outbound_quantity
    total_quality = total_inbound_actual_quantity - total_outbound_actual_quantity
    total_stock = total_inbound_actual_quantity - total_outbound_actual_quantity - total_outbound_stock_quantity

    return render(request, constants_view.template_order_history, {
        'product': product,
        'inbound_logs': inbound_list,
        'outbound_logs': outbound_list,
        'total_inbound_quantity': total_inbound_quantity,
        'total_outbound_quantity': total_outbound_quantity,
        'total_surplus_quantity': total_surplus_quantity,
        'total_inbound_actual_quantity':total_inbound_actual_quantity,
        'total_outbound_actual_quantity':total_outbound_actual_quantity,
        'total_quantity': total_quality,
        'total_stock': total_stock,
        "today": date.today(),
    })

def inventory_summary(request):
    inventory_items = RMProduct.objects.all()  # 获取所有库存信息
    print("----------inventory_summary------------",len(inventory_items))
    inventory_items_converty = []
    employee_data = {}

    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        inventory_items_converty.append(productTemp)

        # 统计员工库存
        employee = product.blongTo.name if product.blongTo else "Unknown"
        qty = product.quantity
        
        if employee not in employee_data:
            employee_data[employee] = {
                'total_qty': 0,
                'qty_list': [],
                'product_set': set(),
                'total_diff': 0,
            }

        employee_data[employee]['total_qty'] += qty
        employee_data[employee]['total_diff'] += product.quantity_diff
        employee_data[employee]['qty_list'].append(qty)
        employee_data[employee]['product_set'].add(product.id)

    # 总数量
    total_qty_all = sum(v['total_qty'] for v in employee_data.values())
    total_qty_diff = sum(v['total_diff'] for v in employee_data.values())

    # 构造 summary 列表
    summary = []
    for employee, qty_list in employee_data.items():
        percentage = round((qty_list['total_qty'] / total_qty_all) * 100, 2) if total_qty_all else 0
        summary.append({
            "employee": employee,
            "total_qty": qty_list['total_qty'],
            "total_diff": qty_list['total_diff'],
            'qty_expression': ' + '.join(str(q) for q in qty_list['qty_list']),
            'product_count': len(qty_list['product_set']),
            'percentage': percentage,
            })

    summary = sorted(summary, key=lambda x: x['percentage'], reverse=True)
    # 汇总总数量
    total_qty_all = sum(row['total_qty'] for row in summary)
    total_qty_diff = sum(row['total_diff'] for row in summary)

    user_permissions = get_user_permissions(request.user)
    years = [2025]
    months = list(range(1, 13))  # 1 到 12 月
    return render(request, constants_view.template_temporary, {
        'user_permissions': user_permissions,
        'years':years,'months':months,'summary':summary,
        'total_qty_all': total_qty_all,
        'total_qty_diff': total_qty_diff,
    })

def export_pallet_number(request):
    # 获取请求中的月份和年份
    month = request.GET.get('month')
    year = request.GET.get('year')
    inventory_items = RMProduct.objects.filter(type = "Rimei")

    # 过滤出指定月份的订单
    start_date = datetime(int(year), int(month), 1)
    if month == '12':
        end_date = datetime(int(year) + 1, 1, 1)  # 下一年1月1日
    else:
        end_date = datetime(int(year), int(month) + 1, 1)  # 下个月的1日

    container_in_orders = Container.objects.filter(
        empty_date__gte=start_date, 
        empty_date__lt=end_date
    ).exclude(Q(customer="3") | Q(customer="6")| Q(customer="12")).order_by('empty_date')
    print("container in : ",len(container_in_orders))

    # 查询 "gloves in" 数据
    gloves_in_orders = Container.objects.filter(
        empty_date__gte=start_date, 
        empty_date__lt=end_date
    ).exclude(Q(customer="3") | Q(customer="12")).order_by('empty_date')
    print("golve in : ",len(gloves_in_orders))

    # 创建 "gloves in" DataFrame
    gloves_in_data = [{
        'inbound_date': order.empty_date,
        'container_id': order.container_id,
        'plts': order.plts,
        'customer': order.customer,
        'description': order.content
        }for order in gloves_in_orders
    ]

    # 查询 "gloves out" 数据（根据您的需求进行调整）
    gloves_out_orders = RMOrder.objects.filter(
        outbound_date__gte=start_date, 
        outbound_date__lt=end_date
    ).exclude(Q(customer_name="8") | Q(customer_name="19")).order_by('outbound_date')
    print("golve out : ",len(gloves_out_orders))

    # ✅ 计算 Container in 总数
    total_container = len(container_in_orders)

    # ✅ 计算 gloves in 总托盘数
    total_in_plts = sum(order.plts for order in gloves_in_orders)

    # ✅ 计算 gloves out 总托盘数
    total_out_plts = sum(order.plts for order in gloves_out_orders)

    # ✅ 总托盘数
    total_plts = total_in_plts + total_out_plts

    # 当月剩余托盘数
    inventory_items_converty = []
    total_pallets = 0
    total_pallets2 = 0
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)
        total_pallets += productTemp.totalPallet
        total_pallets2 += product.quantity // product.Pallet

        inventory_items_converty.append(productTemp)
        inventory_items_converty = sorted(inventory_items_converty, key=lambda x: x.name)

    # 成本统计表格
    cost_table = [{
        'type': 'Monthly Container Unload Fee', 'pallets': total_container, 'unit': 450, 'value': total_container * 450
    }, {
        'type': 'Monthly Inbound Pallets Labor Fee', 'pallets': total_in_plts, 'unit': 4, 'value': total_in_plts * 4
    }, {
        'type': 'Monthly Outbound Pallets Labor Fee', 'pallets': total_out_plts, 'unit': 4, 'value': total_out_plts * 4
    }, {
        'type': 'Monthly Pallet Fee', 'pallets': total_plts, 'unit': 12, 'value': total_plts * 12
    }, {
        'type': 'Total Pallets', 'pallets': total_pallets, 'unit': 6, 'value': total_pallets * 6
    }]

    # ✅ 总价格
    total_price = total_container * 450 + total_in_plts * 4 + total_out_plts * 4+total_plts * 12+total_pallets * 6


    years = [2025]
    months = list(range(1, 13))  # 1 到 12 月
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_generete_monthLabor, {
        'gloves_in_data':gloves_in_data,
        'user_permissions': user_permissions,
        'years':years,'months':months,
        'total_in_plts': total_in_plts,
        'total_out_plts': total_out_plts,
        'cost_table': cost_table,
        'total_plts': total_plts,
        'total_container': total_container,
        'total_pallets' : total_pallets,
        'total_price': total_price,
        'years':year,'months':month
    }) 
    
def get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list):
     
      # 计算入库总数量
    total_inbound_quantity = sum(item['quantity'] or 0 for item in inbound_list)
    # 计算出库总数量
    total_outbound_quantity = sum(item['quantity'] for item in outbound_list)
    # 计算实际入库数量
    total_inbound_actual_quantity = sum(item['quantity'] or 0 for item in inbound_actual_list)
    # 计算实际出库数量
    total_outbound_actual_quantity = sum(item['quantity'] for item in outbound_actual_list)
    # 计算备货区数量
    total_outbound_stock_quantity = sum(item['quantity'] for item in outbound_stock_list)

    product.quantity_for_neworder = total_inbound_actual_quantity - total_outbound_quantity
    product.quantity = total_inbound_actual_quantity - total_outbound_actual_quantity
    product.quantity_to_stock = product.quantity - total_outbound_stock_quantity
    product.shownumber  = product.quantity_to_stock + product.quantity_diff
    product.pallet = product.Pallet
    product.color = product.Color
    product.palletnumber = product.shownumber//product.Pallet
    product.case = product.shownumber % product.Pallet
    product.Location = product.Location
    product.ShelfRecord = product.ShelfRecord
    product.totalPallet = math.ceil(product.quantity / product.Pallet)

    return product

def get_quality(product):
    
    # 创建一个“初始记录”对象，模拟一个类似入库日志的结构
    initial_log = {
        'date': 'Initial',
        'quantity': product.quantity_init,
        'operator': 'System',
        'note': 'Initial stock quantity'
    }

    # 入库记录：ContainerItem + Container 的 empty_date
    inbound_logs = ContainerItem.objects.filter(product=product).select_related('container')
    inbound_list = [{
        'date': item.container.empty_date if item.container else None,
        'quantity': item.quantity,
        'operator': getattr(item.container, 'created_user', str(item.container)) if hasattr(item, 'container') else 'N/A',
        'note': getattr(item.container, 'container_id', '')
    } for item in inbound_logs]

    # 排序
    inbound_list = sorted(inbound_list, key=lambda x: sort_by_date(x, "date"), reverse=True)

    # 插入初始记录到入库列表最前
    inbound_list.insert(0, initial_log)    

    # 出库记录：OrderItem + RMOrder 的 outbound_date
    outbound_logs = OrderItem.objects.filter(
        product=product,
        order__is_canceled=False  # 排除已取消订单
    ).select_related('order')
    outbound_list = [{
        'date': item.order.pickup_date if item.order and item.order.pickup_date else 'N/A',
        'pickup_date': item.order.pickup_date if item.order and item.order.pickup_date else 'N/A',
        'quantity': item.quantity,
        'operator': getattr(item.order, 'created_user', 'N/A'),  # 使用 RMOrder 中的 created_user 或者其他字段作为操作员
        'note': getattr(item.order, 'so_num', '')
    } for item in outbound_logs]

    # 排序
    outbound_list = sorted(outbound_list, key=lambda x: sort_by_date(x, "pickup_date"), reverse=True)

    # 实际入库记录
    inbound_actual_logs = ContainerItem.objects.filter(product=product,container__is_updateInventory=True).select_related('container')
    inbound_actual_list = [{
        'date': item.container.delivery_date if item.container and item.container.delivery_date else 'N/A',
        'quantity': item.quantity,
        'operator': getattr(item.container, 'created_user', str(item.container)) if hasattr(item, 'container') else 'N/A',  # 使用 RMOrder 中的 created_user 或者其他字段作为操作员
        'note': getattr(item.container, 'container_id', '')
    } for item in inbound_actual_logs]
    # 插入初始记录到入库列表最前
    inbound_actual_list.insert(0, initial_log)    

    outbound_actual_logs = OrderItem.objects.filter(product=product,order__is_updateInventory=True).select_related('order')
    outbound_actual_list = [{
        'date': item.order.pickup_date if item.order and item.order.pickup_date else 'N/A',
        'date_shipped': item.order.outbound_date if item.order and item.order.outbound_date else 'N/A',
        'quantity': item.quantity,
        'operator': getattr(item.order, 'created_user', 'N/A'),  # 使用 RMOrder 中的 created_user 或者其他字段作为操作员
        'note': getattr(item.order, 'so_num', '')
    } for item in outbound_actual_logs]

    outbound_stock_logs = OrderItem.objects.filter(product=product,order__is_allocated_to_stock=True).select_related('order')
    outbound_stock_list = [{
        'date': item.order.pickup_date if item.order and item.order.pickup_date else 'N/A',
        'date_shipped': item.order.outbound_date if item.order and item.order.outbound_date else 'N/A',
        'quantity': item.quantity,
        'operator': getattr(item.order, 'created_user', 'N/A'),  # 使用 RMOrder 中的 created_user 或者其他字段作为操作员
        'note': getattr(item.order, 'so_num', '')
    } for item in outbound_stock_logs]

    return inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list

# 排序逻辑：将'N/A'视为最小（或最大）值，按需要可修改
def sort_by_date(entry, field_name):
    date_val = entry.get(field_name)
    if date_val is None:
        return datetime.min  # 或 datetime.max，如果想将空值排在最后
    if isinstance(date_val, datetime):
        return date_val
    elif isinstance(date_val, date):
        return datetime.combine(date_val, time.min)
    return datetime.min

def export_inventory_to_excel(items):
    wb = openpyxl.Workbook()
    ws = wb.active
    today_str = datetime.now().strftime("%Y_%m_%d")
    ws.title = f"Inventory_{today_str}"

    # 按 type 分类
    type_groups = defaultdict(list)
    for item in items:
        type_groups[item.type].append(item)

    # Define headers
    headers = ["Product", "Diff","Show Number","Each","Color", "Location", "Pallets", "Cases","ShelfRecord"]
    ws.append(headers)

    # Write data rows
    for i, (type_name, grouped_items) in enumerate(type_groups.items()):

        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = str(type_name)[:31] or "Sheet"  # Excel sheet name max 31 chars

        ws.append(headers)

        for item in grouped_items:
            ws.append([
                str(item),
                item.quantity_diff,
                item.shownumber,
                item.pallet,
                item.color,
                item.Location,
                item.palletnumber,
                item.case,
                item.ShelfRecord,
            ])

        # 自动列宽
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max_len + 2

    # Save to in-memory file
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Create HTTP response
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"Inventory_{today_str}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


