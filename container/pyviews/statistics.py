from datetime import date, timedelta
import calendar
import datetime

from collections import OrderedDict,defaultdict

from django.shortcuts import render, redirect
from django.db.models import Case, When, Value, FloatField, F, ExpressionWrapper, FloatField, Sum, Q, Min, Max,Count
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek

from collections import defaultdict
import pandas as pd

from ..models import Container,Employee,ClockRecord,ContainerItem,OrderItem,RMProduct
from .getPermission import get_user_permissions
from ..constants import constants_address,constants_view
from .inventory_count import get_quality, get_product_qty

def statistics_invoice(request):
    # containers = Container.objects.filter(
    #     Q(ispay=True, customer_ispay=True)
    # ).exclude(
    #     logistics=2
    # ).annotate(
    #     # 添加价格差字段
    #     price_diff=Case(
    #     When(customer_price__lt=F('price'), then=Value(0)),
    #     default=ExpressionWrapper(
    #         F('customer_price') - F('price'),
    #         output_field=FloatField()
    #     ),
    #     output_field=FloatField()
    #     )
    # ).order_by('-payment_date')

    containers = Container.objects.exclude(
        customer=6
    ).exclude(
        empty_date__isnull=True
    ).exclude(
        container_id__icontains='pack'   # ✅ 排除名字包含 “pack”
    ).exclude(
        container_id__icontains='self'   # 排除 self
    ).annotate(
        price_diff=Case(
            When(customer_price__lt=F('price'), then=Value(0)),
            default=ExpressionWrapper(
                F('customer_price') - F('price'),
                output_field=FloatField()
            ),
            output_field=FloatField()
        )
    )

    # 获取实际的最早和最晚 due_date（按月截断）
    date_range = containers.aggregate(
        start=Min('empty_date'),
        end=Max('empty_date')
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
    monthly_data = containers.annotate(month=TruncMonth('empty_date')) \
        .values('month') \
        .annotate(total_diff=Sum('price_diff'), container_count=Count('id')) \
        .order_by('month')

    full_data = []
    monthly_map = {
        item['month'].strftime('%Y-%m'): {
            'total_diff': item['total_diff'],
            'count': item['container_count']
        }
        for item in monthly_data
    }

    while current <= end_month:
        month_str = current.strftime('%Y-%m')
        month_info = monthly_map.get(month_str, {})

        full_data.append({
            'month': month_str,
            'total_diff': round(month_info.get('total_diff', 0.0) or 0.0, 2),
            'container_count': month_info.get('count', 0)
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
        ).order_by('-month', 'employee_name__name')

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
        .order_by('-month')

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
        .order_by('-month')

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
    result = {}

    for brand in ['Rimei', 'MCD']:
        init_qty = RMProduct.objects.filter(type=brand).aggregate(
            total=Sum('quantity_init')
        )['total'] or 0

        in_items, out_items, inbound, outbound = get_monthly_in_out(brand)
        months, table, in_map, out_map = build_monthly_table(inbound, outbound, init_qty)
        kpis = calc_inventory_kpis(brand, in_items, out_items)
        dead = get_dead_products(brand)

        result[brand] = {
            'months': months,
            'table_data': table,
            'inbound_data': [in_map.get(m, 0) for m in months],
            'outbound_data': [out_map.get(m, 0) for m in months],
            'dead_products': dead,
            **kpis
        }

    return render(request, constants_view.template_statistics_warehouse, {
        'data': result,
        'user_permissions': get_user_permissions(request.user)
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

def statistics_mcd_trend(request):

    # ✅ ORM 查询
    order_items = OrderItem.objects.filter(
        order__pickup_date__isnull=False,
        product__type='Mcdonalds'
    )

   # ---------- 转换为 DataFrame ----------
    weekly_df = pd.DataFrame(list(
        order_items
        .annotate(week=TruncWeek('order__pickup_date'))
        .values('product__name','week')
        .annotate(total_qty=Sum('quantity'))
        .order_by('week')
    ))
    if not weekly_df.empty:
        weekly_df['week'] = pd.to_datetime(weekly_df['week'])
        weekly_df = weekly_df.sort_values('week')

    monthly_df = pd.DataFrame(list(
        order_items
        .annotate(month=TruncMonth('order__pickup_date'))
        .values('product__name','month')
        .annotate(total_qty=Sum('quantity'))
        .order_by('month')
    ))
    if not monthly_df.empty:
        monthly_df['month'] = pd.to_datetime(monthly_df['month'])
        monthly_df = monthly_df.sort_values('month')

    # ---------- 构造 chart 数据函数 ----------
    def build_chart_data(df, date_field, value_field='total_qty'):
        if df.empty:
            return {"labels": [], "datasets": []}
        labels = sorted(df[date_field].dt.strftime("%Y-%m-%d").unique())
        products = df['product__name'].unique()
        datasets = []
        for p in products:
            data = []
            for l in labels:
                val = df[(df['product__name']==p) & (df[date_field].dt.strftime("%Y-%m-%d")==l)][value_field]
                data.append(int(val.values[0]) if not val.empty else 0)
            datasets.append({"label": p, "data": data})
        return {"labels": labels, "datasets": datasets}

    # ---------- 构造 result ----------
    result = {}

    # 表格默认显示月趋势
    table_data = []
    for _, row in weekly_df.iterrows():
        table_data.append({
            "product": row["product__name"],
            "date": row["week"].strftime("%Y-%m-%d"),
            "quantity": row["total_qty"]
        })
    result['table'] = table_data

    # 各类趋势图表数据
    result['weekly'] = build_chart_data(weekly_df, 'week')
    result['monthly'] = build_chart_data(monthly_df, 'month')

    # 累计趋势（基于周）
    if not weekly_df.empty:
        weekly_df['cumulative'] = weekly_df.groupby('product__name')['total_qty'].cumsum()
        result['cumulative'] = build_chart_data(weekly_df, 'week', 'cumulative')
    
    # 移动平均趋势（基于周，4周均线）
    if not weekly_df.empty:
        weekly_df['moving_avg'] = weekly_df.groupby('product__name')['total_qty'].transform(
            lambda x: x.rolling(7,1).mean()
        )
        result['moving_average'] = build_chart_data(weekly_df, 'week', 'moving_avg')

    # 增长分析（环比增长，按月）
    if not monthly_df.empty:
        monthly_df['prev_qty'] = monthly_df.groupby('product__name')['total_qty'].shift(1)
        monthly_df['mom_growth'] = (monthly_df['total_qty'] - monthly_df['prev_qty']) / monthly_df['prev_qty'] * 100
        monthly_growth = monthly_df.dropna()
        result['growth'] = build_chart_data(monthly_growth, 'month', 'mom_growth')

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_mcdTrend, {
        'result': result,
        'user_permissions': user_permissions
    })

# sub function - 每月入 / 出库统计（通用方法）
def get_monthly_in_out(type_name):
    in_items = ContainerItem.objects.filter(
        container__delivery_date__isnull=False,
        product__type=type_name
    ).annotate(month=TruncMonth('container__delivery_date'))

    out_items = OrderItem.objects.filter(
        order__pickup_date__isnull=False,
        product__type=type_name
    ).annotate(month=TruncMonth('order__pickup_date'))

    inbound = in_items.values('month').annotate(
        total_qty=Sum('quantity')
    ).order_by('month')

    outbound = out_items.values('month').annotate(
        total_qty=Sum('quantity')
    ).order_by('month')

    return in_items, out_items, inbound, outbound

# sun function - 构建月份表格数据（通用）
def build_monthly_table(inbound, outbound, init_qty):
    month_set = set()
    inbound_map, outbound_map = {}, {}

    for r in inbound:
        m = r['month'].strftime('%Y-%m')
        inbound_map[m] = r['total_qty']
        month_set.add(m)

    for r in outbound:
        m = r['month'].strftime('%Y-%m')
        outbound_map[m] = r['total_qty']
        month_set.add(m)

    months = sorted(month_set)
    if not months:
        months = [datetime.today().strftime('%Y-%m')]

    init_map = {months[0]: init_qty}

    table = []
    for m in months:
        table.append({
            'month': m,
            'initItems': init_map.get(m, 0),
            'inbound': inbound_map.get(m, 0),
            'outbound': outbound_map.get(m, 0)
        })

    return months, table, inbound_map, outbound_map

# sub function - KPI 统计（库存周转 / 准确率 / 缺货等）
def calc_inventory_kpis(type_name, in_items, out_items, days_obsolete=90):
    from datetime import date, timedelta
    products = RMProduct.objects.filter(type=type_name)

    # 1️⃣ 基础库存指标
    total_in = in_items.aggregate(total=Sum('quantity'))['total'] or 0
    total_out = out_items.aggregate(total=Sum('quantity'))['total'] or 0
    avg_inventory = (total_in + total_out) / 2 if (total_in + total_out) else 1
    inventory_turnover = total_out / avg_inventory

    total_products = products.count()
    inaccurate = products.filter(quantity_diff__gt=0).count()
    inventory_accuracy = 100 * (total_products - inaccurate) / total_products if total_products else 100

    total_init = products.aggregate(total=Sum('quantity_init'))['total'] or 0
    avg_inventory_level = total_init + total_in - total_out

    out_of_stock_orders = OrderItem.objects.filter(
        quantity__gt=F('product__quantity_init') + F('product__quantity_diff'),
        product__type=type_name
    ).count()
    total_orders = OrderItem.objects.filter(product__type=type_name).count()
    stockout_rate = 100 * out_of_stock_orders / total_orders if total_orders else 0

    # 2️⃣ Fast-Moving Inventory Ratio
    threshold_date = date.today() - timedelta(days=days_obsolete)
    active_products_count = out_items.filter(order__outbound_date__gte=threshold_date).values('product').distinct().count()
    fast_moving_ratio = 100 * active_products_count / total_products if total_products else 0

    # 3️⃣ Obsolete Inventory Ratio
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

    return {
        'inventory_turnover': round(inventory_turnover, 2),
        'inventory_accuracy': round(inventory_accuracy, 2),
        'avg_inventory': round(avg_inventory_level, 2),
        'stockout_rate': round(stockout_rate, 2),
        'fast_moving_ratio': round(fast_moving_ratio, 2),
        'obsolete_inventory_ratio': round(obsolete_inventory_ratio, 2)
    }

# sub function - 滞销库存分析（180 天无出库）
def get_dead_products(type_name, days=180):
    threshold = date.today() - timedelta(days=days)
    products = RMProduct.objects.filter(type=type_name)

    product_qty = {}
    for p in products:
        inbound, outbound, oa, os, ia = get_quality(p)
        pt = get_product_qty(p, inbound, outbound, oa, os, ia)
        if pt.quantity > 0:
            product_qty[pt.name] = pt.quantity

    last_outbound = OrderItem.objects.filter(
        product__type=type_name
    ).values('product__name').annotate(
        last_date=Max('order__outbound_date')
    )
    last_map = {r['product__name']: r['last_date'] for r in last_outbound}

    dead = []
    for name, qty in product_qty.items():
        last = last_map.get(name)
        if last is None or last < threshold:
            dead.append({'name': name, 'quantity': qty})

    return sorted(dead, key=lambda x: x['name'].lower())