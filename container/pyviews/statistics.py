from datetime import date, timedelta
import calendar
import datetime

from collections import OrderedDict,defaultdict

from django.shortcuts import render, redirect
from django.db.models import F, ExpressionWrapper, FloatField, Sum, Q, Min, Max,Count
from django.db.models.functions import TruncMonth

from ..models import Container,Employee,ClockRecord,ContainerItem,OrderItem,RMProduct
from .getPermission import get_user_permissions
from ..constants import constants_address,constants_view

def statistics_invoice(request):
    containers = Container.objects.filter(
        Q(ispay=True, customer_ispay=True)
    ).exclude(
        logistics=2
    ).annotate(
        # 添加价格差字段
        price_diff=ExpressionWrapper(
            F('customer_price') - F('price'),
            output_field=FloatField()
        )
    ).order_by('-payment_date')

    # 获取实际的最早和最晚 due_date（按月截断）
    date_range = containers.aggregate(
        start=Min('payment_date'),
        end=Max('payment_date')
    )

    if not date_range['start'] or not date_range['end']:
        # 如果没有数据，返回空页面
        return render(request, constants_view.template_statistics_invoice, {
            'containers': [],
            'chart_data_list': [],
            'chart_labels': [],
            'chart_data': []
        })    

    # 生成完整的月份序列（根据实际数据范围）
    start_month = date_range['start'].replace(day=1)
    end_month = date_range['end'].replace(day=1)
    current = start_month

    # 聚合：每月总的 price_diff
    monthly_data = containers.annotate(month=TruncMonth('payment_date')) \
        .values('month') \
        .annotate(total_diff=Sum('price_diff')) \
        .order_by('month')

    full_data = []
    monthly_map = {item['month'].strftime('%Y-%m'): item['total_diff'] for item in monthly_data}

    while current <= end_month:
        month_str = current.strftime('%Y-%m')
        full_data.append({
            'month': month_str,
            'total_diff': round(monthly_map.get(month_str, 0.0), 2)
        })

        # 进入下一个月
        year = current.year + (current.month // 12)
        month = (current.month % 12) + 1
        current = datetime.date(year, month, 1)

    # 拆分 labels 和 data（给图表用）
    chart_labels = [item['month'] for item in full_data]
    chart_data = [item['total_diff'] for item in full_data]

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_invoice,{
        'containers': containers,
        'chart_data_list': full_data,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'user_permissions': user_permissions
    }) 

def statistics_weekreord(request):
    employees = Employee.objects.filter(belongTo="CabinetsDepot")
    # 获取选定周的打卡记录
    weekly_records = ClockRecord.objects.filter(employee_name__in=employees)

    # 按人、按月分组
    grouped = weekly_records.annotate(month=TruncMonth('date')) \
        .values('employee_name__name', 'month') \
        .annotate(
            total_hours=Sum('total_hours'),
            days_present=Count('id')
        ).order_by('month', 'employee_name__name')

    # 构造结构化数据 [{name:..., month:..., hours:..., rate:...}]
    attendance_data = []
    for entry in grouped:
        workdays  = month_workdays(entry['month'])
        max_work_hours = workdays  * 8  # 该月最多工作小时数（每天8小时）
        attendance_rate = (float(entry['total_hours']) / max_work_hours) * 100 if max_work_hours else 0
        attendance_data.append({
            'employee': entry['employee_name__name'],
            'month': entry['month'].strftime('%Y-%m'),
            'total_hours': float(entry['total_hours']),
            'workdays': workdays,
            'attendance_rate': float(attendance_rate)
        })

    # 准备图表数据（每人每月小时统计）
    chart_series = defaultdict(lambda: [])
    month_labels = sorted(list({e['month'] for e in attendance_data}))

    for employee in employees:
        name = employee.name
        month_to_hours = {e['month']: e['total_hours'] for e in attendance_data if e['employee'] == name}
        chart_series[name] = [month_to_hours.get(month, 0) for month in month_labels]

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_weekrecord, {
        'attendance_data': attendance_data,
        'chart_labels': month_labels,
        'chart_series': dict(chart_series),
        'user_permissions': user_permissions
    })

def statistics_inbound(request):
    container_items = ContainerItem.objects.filter(
        container__delivery_date__isnull=False,
        product__type='Rimei'  # ✅ 仅保留 Rimei 产品
    )

     # 按产品+月份分组统计数量
    grouped = container_items.annotate(month=TruncMonth('container__delivery_date')) \
        .values('product__name', 'month') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('month')

    # 构造结构化数据：行是产品，列是月份
    product_set = set()
    month_set = set()
    data_map = defaultdict(lambda: defaultdict(int))

    for row in grouped:
        product = row['product__name']
        month = row['month'].strftime('%Y-%m')
        qty = row['total_qty']
        data_map[product][month] = qty
        product_set.add(product)
        month_set.add(month)

    month_list = sorted(list(month_set))
    product_list = sorted(list(product_set))

    # 构造图表数据结构
    chart_datasets = []
    for product in product_list:
        chart_datasets.append({
            'label': product,
            'data': [data_map[product].get(month, 0) for month in month_list],
        })

    table_data = []
    chart_data_map = {}
    for row in grouped:
        product = row['product__name']
        month = row['month'].strftime('%Y-%m')
        qty = row['total_qty']
        table_data.append({
            'product': product,
            'month': month,
            'quantity': qty
        })
        month_set.add(month)
        if product not in chart_data_map:
            chart_data_map[product] = {}
        chart_data_map[product][month] = qty

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_inbound, {        
        'table_data': table_data,
        'month_list': month_list,
        'chart_datasets': chart_datasets,  # for chart
        'user_permissions': user_permissions
    })

def statistics_outbound(request):
    order_items = OrderItem.objects.filter(
        order__outbound_date__isnull=False,
        product__type='Rimei'  # ✅ 仅保留 Rimei 产品
    )

     # 按产品+月份分组统计数量
    grouped = order_items.annotate(month=TruncMonth('order__outbound_date')) \
        .values('product__name', 'month') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('month')

    # 构造结构化数据：行是产品，列是月份
    product_set = set()
    month_set = set()
    data_map = defaultdict(lambda: defaultdict(int))

    for row in grouped:
        product = row['product__name']
        month = row['month'].strftime('%Y-%m')
        qty = row['total_qty']
        data_map[product][month] = qty
        product_set.add(product)
        month_set.add(month)

    month_list = sorted(list(month_set))
    product_list = sorted(list(product_set))

    # 构造图表数据结构
    chart_datasets = []
    for product in product_list:
        chart_datasets.append({
            'label': product,
            'data': [data_map[product].get(month, 0) for month in month_list],
        })

    table_data = []
    chart_data_map = {}
    for row in grouped:
        product = row['product__name']
        month = row['month'].strftime('%Y-%m')
        qty = row['total_qty']
        table_data.append({
            'product': product,
            'month': month,
            'quantity': qty
        })
        month_set.add(month)
        if product not in chart_data_map:
            chart_data_map[product] = {}
        chart_data_map[product][month] = qty

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_outbound, {        
        'table_data': table_data,
        'month_list': month_list,
        'chart_datasets': chart_datasets,  # for chart
        'user_permissions': user_permissions
    })

def statistics_warehouse(request):
    # 限定产品类型
    init_items = RMProduct.objects.filter(type='Rimei')

    in_items = ContainerItem.objects.filter(
        container__delivery_date__isnull=False,
        product__type='Rimei'
    ).annotate(month=TruncMonth('container__delivery_date'))

    out_items = OrderItem.objects.filter(
        order__outbound_date__isnull=False,
        product__type='Rimei'
    ).annotate(month=TruncMonth('order__outbound_date'))

    inbound_by_month = in_items.values('month').annotate(total_qty=Sum('quantity')).order_by('month')
    outbound_by_month = out_items.values('month').annotate(total_qty=Sum('quantity')).order_by('month')

    # 构造数据映射
    month_set = set()
    inbound_map = {}
    outbound_map = {}

    for row in inbound_by_month:
        m = row['month'].strftime('%Y-%m')
        inbound_map[m] = row['total_qty']
        month_set.add(m)

    for row in outbound_by_month:
        m = row['month'].strftime('%Y-%m')
        outbound_map[m] = row['total_qty']
        month_set.add(m)

    sorted_months = sorted(month_set)

    # 初始库存：放在最早的月份
    if sorted_months:
        first_month = sorted_months[0]
    else:
        first_month = datetime.today().strftime('%Y-%m')
        sorted_months = [first_month]

    total_init_qty = sum(p.get('quantity_init') or 0 for p in init_items.values('quantity_init'))
    initbound_map = {first_month: total_init_qty}

    initbound_data = [initbound_map.get(m, 0) for m in sorted_months]
    inbound_data = [inbound_map.get(m, 0) for m in sorted_months]
    outbound_data = [outbound_map.get(m, 0) for m in sorted_months]

    table_data = []
    for i, month in enumerate(sorted_months):
        table_data.append({
            'month': month,
            'initItems': initbound_data[i],
            'inbound': inbound_data[i],
            'outbound': outbound_data[i]
        })

    # 库存周转率
    total_in = sum(inbound_data)
    total_out = sum(outbound_data)
    average_inventory = (total_in + total_out) / 2 if (total_in + total_out) > 0 else 1
    inventory_turnover = total_out / average_inventory

    # 滞销库存：过去90天无出库
    reference_date = date.today()
    threshold_date = reference_date - timedelta(days=90)

    # 所有产品名称和库存数量
    all_products_qs = list(RMProduct.objects.filter(type='Rimei').values('name', 'quantity_init', 'quantity_diff'))
    product_quantity_map = {}
    for p in all_products_qs:
        name = p.get('name')
        init_qty = p.get('quantity_init') or 0
        diff_qty = p.get('quantity_diff') or 0
        product_quantity_map[name] = init_qty + diff_qty

    # 累加产品入库数量
    inbound_by_product = in_items.values('product__name').annotate(total_qty=Sum('quantity'))
    for row in inbound_by_product:
        name = row['product__name']
        qty = row['total_qty'] or 0
        product_quantity_map[name] = product_quantity_map.get(name, 0) + qty

    # 获取每个产品最近出库时间
    last_outbound = out_items.values('product__name').annotate(
        last_date=Max('order__outbound_date')
    )
    last_outbound_map = {r['product__name']: r['last_date'] for r in last_outbound}

    # 识别滞销产品及其库存
    dead_products = []
    for name, qty in product_quantity_map.items():
        last_date = last_outbound_map.get(name)
        if last_date is None or last_date < threshold_date:
            dead_products.append({'name': name, 'quantity': qty})

    # ---- 计算库存准确率 ----
    products = RMProduct.objects.filter(type='Rimei')
    total_products = products.count()
    inaccurate_count = products.filter(quantity_diff__gt=0).count()
    inventory_accuracy = 100 * (total_products - inaccurate_count) / total_products if total_products > 0 else 100
    print(inaccurate_count,total_products)

    # ---- 平均库存水平 ----
    # 库存 = 初始库存 + 入库总量 - 出库总量
    total_init_stock = products.aggregate(total=Sum('quantity_init'))['total'] or 0
    total_inbound = in_items.aggregate(total=Sum('quantity'))['total'] or 0
    total_outbound = out_items.aggregate(total=Sum('quantity'))['total'] or 0
    avg_inventory = total_init_stock + total_inbound - total_outbound
    print(total_init_stock,total_inbound,total_outbound)

    # ---- 缺货率 ----
    # 这里用Q模拟，实际字段需替换
    out_of_stock_orders = OrderItem.objects.filter(
        Q(quantity__gt=F('product__quantity_init') + F('product__quantity_diff'))  # 模拟缺货
    ).count()
    total_orders = OrderItem.objects.count()
    stockout_rate = 100 * out_of_stock_orders / total_orders if total_orders > 0 else 0

    # ---- 高周转库存比例 ----
    # 统计过去90天内有出库的产品数 / 总产品数
    active_products = out_items.filter(order__outbound_date__gte=threshold_date).values('product').distinct().count()
    total_products_count = products.count()
    fast_moving_ratio = 100 * active_products / total_products_count if total_products_count > 0 else 0

    # ---- 呆滞库存占比 ----
    # 过去90天无出库的产品库存占比
    last_outbound = out_items.values('product__name').annotate(last_date=Max('order__outbound_date'))
    last_outbound_map = {r['product__name']: r['last_date'] for r in last_outbound}
    dead_stock_qty = 0
    total_stock_qty = 0
    for p in products:
        qty = (p.quantity_init or 0) + (p.quantity_diff or 0)
        total_stock_qty += qty
        last_date = last_outbound_map.get(p.name)
        if last_date is None or last_date < threshold_date:
            dead_stock_qty += qty
    obsolete_inventory_ratio = 100 * dead_stock_qty / total_stock_qty if total_stock_qty > 0 else 0

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_warehouse, {
        'months': sorted_months,
        'table_data':table_data,
        'inbound_data': inbound_data,
        'outbound_data': outbound_data,
        'inventory_turnover': round(inventory_turnover, 2),
        'inventory_accuracy': round(inventory_accuracy, 2),
        'avg_inventory': round(avg_inventory, 2),
        'stockout_rate':round(stockout_rate, 2),
        'fast_moving_ratio':round(fast_moving_ratio, 2),
        'obsolete_inventory_ratio':round(obsolete_inventory_ratio, 2),
        'dead_products': dead_products,
        'user_permissions': user_permissions
    })

def month_workdays(dt) -> int:
    """
    计算指定年月中，周一到周五的工作日数量（不含周末）
    """
    year = dt.year
    month = dt.month

    total_days = calendar.monthrange(year, month)[1]
    workdays = 0
    for day in range(1, total_days + 1):
        weekday = date(year, month, day).weekday()
        # weekday: 0=周一, ..., 6=周日，排除周六(5)和周日(6)
        if weekday < 5:
            workdays += 1
    return workdays