import calendar
import datetime
import pandas as pd
import json
import os

from decimal import Decimal, ROUND_HALF_UP

from collections import defaultdict
from datetime import date, timedelta, datetime

from django.db.models import Case, When, Value, FloatField, F, ExpressionWrapper, Sum, Q, Min, Max, Count, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, Coalesce
from django.shortcuts import render, redirect
from django.utils import timezone

from ..constants import constants_address, constants_view
from ..models import Container, Employee, ClockRecord, ContainerItem, OrderItem, RMProduct, RMOrder
from ..models import InvoiceAPRecord, InvoiceARRecord, OfficeSupplyRecord
from ..models import RMCustomer

from .inventory_count import get_quality, get_product_qty
from .utils.pdfgenerate import converter_commision_pdf
from .utils.getPermission import get_user_permissions
from .utils.date_utils import month_workdays
from .utils.pdf_utils import create_pdf_canvas, finalize_pdf_and_response
from .utils.file_utils import get_media_path, ensure_dir_exists

def statistics_invoice_summary(request):
    start_date = date(2025, 1, 1)
    end_date = date(2025, 12, 31)

    ap_data = (
        InvoiceAPRecord.objects
        .filter(payment_date__range=(start_date, end_date))
        .values('vendor__id', 'vendor__name')
        .annotate(
            total_count=Count('id'),
            total_amount=Sum('invoice_price')
        )
        .order_by('vendor__name')
    )
    ar_data = (
        InvoiceARRecord.objects
        .filter(payment_date__range=(start_date, end_date))
        .values('customer__id', 'customer__name')
        .annotate(
            total_count=Count('id'),
            total_amount=Sum('invoice_price')
        )
        .order_by('customer__name')
    )

    # ===== 按 supply_item 分类 =====
    office_data = (
        OfficeSupplyRecord.objects
        .filter(purchase_date__year=2025)
        .values('supply_item__name')
        .annotate(
            record_count=Count('id'),
            total_quantity=Coalesce(              # 总数量
                Sum('quantity'),
                Value(0)
            ),
            total_amount=Coalesce(
                Sum('unit_price'),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        .order_by('supply_item__name')
    )

    # ===== 年度总金额 =====
    ar_total_year = InvoiceARRecord.objects.filter(
        payment_date__range=(start_date, end_date)
    ).aggregate(total=Sum('invoice_price'))

    ap_total_year = InvoiceAPRecord.objects.filter(
        payment_date__range=(start_date, end_date)
    ).aggregate(total=Sum('invoice_price'))

    # ===== 年度总花费 =====    
    office_total_year = OfficeSupplyRecord.objects.filter(
        purchase_date__year=2025
    ).aggregate(
        total=Coalesce(
            Sum('unit_price'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )

    # ===== AP 按 purposefor 分类 =====
    ap_purpose_data = (
        InvoiceAPRecord.objects
        .filter(payment_date__year=2025)
        .values('purposefor__name')
        .annotate(
            record_count=Count('id'),
            total_amount=Coalesce(
                Sum('invoice_price'),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        .order_by('purposefor__name')
    )

    ap_purpose_total_year = InvoiceAPRecord.objects.filter(
        payment_date__year=2025
    ).aggregate(
        total=Coalesce(
            Sum('invoice_price'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )

    # ===== Container 盈利汇总 =====
    containers = (
        Container.objects
        .exclude(customer=6)
        .exclude(empty_date__isnull=True)
        .exclude(container_id__icontains='pack')
        .exclude(container_id__icontains='self')
        .annotate(
            price_diff=Case(
                When(customer_price__lt=F('price'), then=Value(0)),
                default=ExpressionWrapper(
                    F('customer_price') - F('price'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        .order_by('-delivery_date')
    )

    container_summary = containers.aggregate(
        total_income=Coalesce(
            Sum('customer_price'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        total_cost=Coalesce(
            Sum('price'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        total_profit=Coalesce(
            Sum('price_diff'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        total_count=Count('id')
    )

    print("AP num:", len(ap_data), "AR num:", len(ar_data))
    print("AP num:", len(ap_total_year), "AR num:", len(ar_total_year))
    print("AP num:", len(office_data), "AR num:", len(office_total_year))

    # ===== 正常页面显示 =====
    user_permissions = get_user_permissions(request.user)
    context = {
        "ar_data": ar_data,
        "ap_data": ap_data,
        "ar_total_year": ar_total_year["total"],
        "ap_total_year": ap_total_year["total"],
        "office_data": office_data,
        "office_total_year": office_total_year["total"],
        "ap_purpose_data": ap_purpose_data,
        "ap_purpose_total_year": ap_purpose_total_year["total"],
        'container_summary': container_summary,
        'user_permissions': user_permissions,
    }
    
    return render(request, constants_view.template_statistics_aparInvoice, context) 

def statistics_invoice_container(request):

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
    ).order_by('-delivery_date') 

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
        current = date(year, month, 1)

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

def statistics_outbound_metal(request):
    order_items = OrderItem.objects.filter(
        order__outbound_date__isnull=False,
        product__type='Metal'  # ✅ 仅保留 Rimei 产品
    )

    # 按产品+月份分组统计数量
    grouped = order_items.annotate(month=TruncMonth('order__outbound_date')) \
        .values('product_actual__name', 'month') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('-month')

    # 构造结构化数据：行是产品，列是月份
    product_set = set()
    month_set = set()
    data_map = defaultdict(lambda: defaultdict(int))

    for row in grouped:
        product = row['product_actual__name']
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
        product = row['product_actual__name']
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
    return render(request, constants_view.template_statistics_outbound_metal, {        
        'table_data': table_data,
        'month_list': month_list,
        'chart_datasets': chart_datasets,  # for chart
        'user_permissions': user_permissions
    })

def statistics_mcd_trend(request):

    # ✅ ORM 查询
    order_items = OrderItem.objects.filter(
        order__pickup_date__isnull=False,
        product__type='MCD'
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

    result['table_average'] = []

    if not monthly_df.empty:

        # 复制，避免修改原来的 monthly_df
        avg_monthly_df = monthly_df.copy()

        avg_monthly_df['month'] = pd.to_datetime(
            avg_monthly_df['month']
        )

        # 找到最早和最后一个月份
        first_month = avg_monthly_df['month'].min().to_period('M')
        last_month = avg_monthly_df['month'].max().to_period('M')

        # 排除首月和最后一个月
        avg_monthly_df = avg_monthly_df[
            (avg_monthly_df['month'].dt.to_period('M') != first_month) &
            (avg_monthly_df['month'].dt.to_period('M') != last_month)
        ]

        # 每个产品计算月平均值
        product_monthly_average = (
            avg_monthly_df
            .groupby('product__name')['total_qty']
            .mean()
            .round(2)
            .reset_index()
        )

        result['table_average'] = [
            {
                'product': row['product__name'],
                'average': float(row['total_qty'])
            }
            for _, row in product_monthly_average.iterrows()
        ]


    # ---------- 最近3个完整月份的平均数量 ----------

    result['recent_3_month_average'] = []

    if not monthly_df.empty:

        recent_df = monthly_df.copy()

        recent_df['month'] = pd.to_datetime(
            recent_df['month']
        )

        # 当前月份
        current_month = pd.Timestamp.today().to_period('M')

        # 排除当前月份
        recent_df = recent_df[
            recent_df['month'].dt.to_period('M') < current_month
        ]

        # 找到最近3个完整月份
        recent_months = sorted(
            recent_df['month'].dt.to_period('M').unique()
        )[-3:]

        recent_df = recent_df[
            recent_df['month'].dt.to_period('M').isin(recent_months)
        ]

        # 每个产品计算最近3个月平均值
        recent_3_month_avg = (
            recent_df
            .groupby('product__name')['total_qty']
            .mean()
            .round(2)
            .reset_index()
        )

        result['recent_3_month_average'] = [
            {
                'product': row['product__name'],
                'average': float(row['total_qty'])
            }
            for _, row in recent_3_month_avg.iterrows()
        ]

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

def statistics_metal_customer_trend(request):
    order_items = OrderItem.objects.filter(
        order__pickup_date__isnull=False,
        order__customer_name__classification__in=['Metal', 'Wholesaler'],
        order__is_canceled=False,
        product__isnull=False
    )

    amount_expr = ExpressionWrapper(
        F('quantity') * F('product__price'),
        output_field=DecimalField(
            max_digits=12,
            decimal_places=2
        )
    )

    item_df = pd.DataFrame(list(
        order_items
        .annotate(
            month=TruncMonth('order__pickup_date')
        )
        .annotate(
            item_amount=amount_expr
        )
        .values(
            'order__customer_name__name',
            'month'
        )
        .annotate(
            product_amount=Sum('item_amount')
        )
    ))
    
    #客户消费
    orders = RMOrder.objects.filter(
        pickup_date__isnull=False,
        customer_name__classification__in=['Metal','Wholesaler'],
        is_canceled=False
    )

    order_df = pd.DataFrame(list(
        orders
        .annotate(month=TruncMonth('pickup_date'))
        .values('customer_name__name', 'month')
        .annotate(order_amount=Sum('customer_price'))
    ))

    monthly_df = pd.merge(
        order_df,
        item_df,
        left_on=['customer_name__name', 'month'],
        right_on=['order__customer_name__name', 'month'],
        how='outer'
    )

    # ⭐ 统一客户名称
    monthly_df['customer'] = (
        monthly_df['customer_name__name']
        .combine_first(monthly_df['order__customer_name__name'])
    )

    # 删除旧字段（非常关键）
    monthly_df = monthly_df.drop(
        columns=['customer_name__name', 'order__customer_name__name'],
        errors='ignore'
    )

    # 空值补0
    monthly_df['order_amount'] = monthly_df['order_amount'].fillna(0)
    monthly_df['product_amount'] = monthly_df['product_amount'].fillna(0)

    # 日期格式
    monthly_df['month'] = pd.to_datetime(monthly_df['month'])

    monthly_df = monthly_df.groupby(
        ['customer', 'month'],
        as_index=False
    ).agg({
        'order_amount': 'sum',
        'product_amount': 'sum'
    })

    # ---------- chart data ----------
    def build_chart_data(df):

        if df.empty:
            return {"labels": [], "datasets": []}

        labels = sorted(df['month'].dt.strftime("%Y-%m").unique())
        customers = df['customer'].unique()

        datasets = []

        for customer in customers:

            order_data = []
            product_data = []

            for label in labels:
                row = df[
                    (df['customer'] == customer) &
                    (df['month'].dt.strftime("%Y-%m") == label)
                ]

                if not row.empty:
                    order_data.append(float(row['order_amount'].values[0]))
                    product_data.append(float(row['product_amount'].values[0]))
                else:
                    order_data.append(0)
                    product_data.append(0)

            # 客户真实消费
            datasets.append({
                "label": f"{customer} - Order Amount",
                "data": order_data
            })

            # 按数量计算金额
            datasets.append({
                "label": f"{customer} - Product Amount",
                "data": product_data
            })

        return {"labels": labels, "datasets": datasets}

    # ---------- table ----------
    table_data = []

    if not monthly_df.empty:

        monthly_df = monthly_df.sort_values(
            ['month','customer'],
            ascending=[False, True]
        )

        for _, row in monthly_df.iterrows():

            table_data.append({
                "customer": row['customer'],
                "month": row['month'].strftime("%Y-%m"),

                # 客户真实消费
                "order_amount": float(row['order_amount']),

                # 按数量金额
                "product_amount": float(row['product_amount']),

                # ⭐ 差额（非常有用）
                "difference": float(row['order_amount'] - row['product_amount'])
            })

    result = {
        "table": table_data,
        "monthly": build_chart_data(monthly_df)
    }

    user_permissions = get_user_permissions(request.user)

    return render(request, constants_view.template_statistics_metalCustomerTrend, {
        'result': result,   # 给 table 用
        'result_json': json.dumps(result), # 给 chart 用
        'user_permissions': user_permissions
    })

def statistics_metal_product_trend(request):

    customer_id = request.GET.get('customer')
    customers = (
        RMCustomer.objects
        .filter(Q(classification="Metal") | Q(classification="Wholesaler"))
        .order_by("name")
    )

    # =========================================================
    # Default values
    # =========================================================

    chart_labels = []
    datasets = []

    # Customer Summary
    ytd_invoice = Decimal("0")
    ytd_sales = Decimal("0")
    ytd_cost = Decimal("0.00")
    ytd_gross_profit = Decimal("0.00")
    ytd_carrier = Decimal("0.00")
    ytd_sub_profit = Decimal("0.00")
    ytd_profit = Decimal("0.00")
    ytd_total_profit = Decimal("0.00")
    gross_margin = Decimal("0.00")

    ytd_quantity = Decimal("0")
    avg_monthly_quantity = Decimal("0")
    avg_order_quantity = Decimal("0")

    order_count = 0
    order_frequency = None

    # Customer Activity
    last_order_date = None
    days_since_last_order = None
    avg_order_cycle = None
    expected_next_order = None

    # Top Products
    top_products = []

    # Inventory
    inventory_products = []

    # Demand Analysis
    last_3_month_avg = Decimal("0")
    last_6_month_avg = Decimal("0")
    recent_growth = Decimal("0")

    # =========================================================
    # Selected Customer
    # =========================================================

    selected_customer_obj = None

    if customer_id:

        selected_customer_obj = (
            RMCustomer.objects
            .filter(
                id=customer_id,
            )
            .first()
        )


    # =========================================================
    # Main calculation
    # =========================================================

    if selected_customer_obj:

        # -----------------------------------------------------
        # Base OrderItem Query
        # -----------------------------------------------------

        commission_orders = (
            get_metal_commission_orders(
                customer_id,
                None
            )
        )


        # =====================================================
        # Customer Summary
        # =====================================================

        current_year = timezone.now().year

        ytd_orders = [
            order
            for order in commission_orders
            if order.pickup_date
            and order.pickup_date.year == current_year
        ]


        for order in ytd_orders:

            invoice_amount = (
                order.customer_price
                or Decimal("0.00")
            )

            amount = (
                order.total_amount
                or Decimal("0.00")
            )

            cost = (
                order.total_cost
                or Decimal("0.00")
            )

            # 注意：
            # get_metal_commission_orders() 中
            # order.carrier_price 已经保留原始 carrier_price
            carrier = (
                order.carrier_price
                or Decimal("0.00")
            )

            # 业务上 carrier = 0 时使用 $150
            actual_carrier = (
                Decimal("150.00")
                if carrier == Decimal("0.00")
                else carrier
            )

            sub_profit = (
                order.sub_profit
                or Decimal("0.00")
            )

            profit = (
                order.profit
                or Decimal("0.00")
            )

            total_profit = (
                order.total_profit
                or Decimal("0.00")
            )


            ytd_invoice += invoice_amount
            ytd_sales += amount
            ytd_cost += cost
            ytd_carrier += actual_carrier
            ytd_sub_profit += sub_profit
            ytd_profit += profit
            ytd_total_profit += total_profit


        # Gross Margin
        if ytd_sales > 0:

            gross_margin = (
                ytd_total_profit
                / ytd_sales
                * Decimal("100")
            )

            ytd_gross_profit = ytd_sales - ytd_cost

        if int(customer_id) != 35:
            ytd_total_profit = 0


        # =====================================================
        # 3. Order Items
        #
        # 这里只负责数量和产品趋势
        # 不再计算 Cost / Profit
        # =====================================================

        order_items = (
            OrderItem.objects
            .filter(
                order__customer_name_id=
                    selected_customer_obj.id,

                order__pickup_date__isnull=False,

                order__is_canceled=False,

            )
            .select_related(
                "order",
                "product",
                "product_actual",
            )
        )

        # =====================================================
        # 4. YTD Quantity
        # =====================================================

        ytd_quantity = (
            order_items
            .filter(
                order__pickup_date__year=current_year
            )
            .aggregate(
                total=Sum("quantity")
            )["total"]
            or Decimal("0")
        )


        # =====================================================
        # 5. Order Count
        # =====================================================

        order_ids = list(
            order_items
            .values_list(
                "order_id",
                flat=True
            )
            .distinct()
        )

        order_count = len(order_ids)


        if order_count > 0:

            avg_order_quantity = (
                ytd_quantity
                /
                Decimal(str(order_count))
            )


        # =====================================================
        # Last Order
        # =====================================================

        last_order = (
            RMOrder.objects
            .filter(
                id__in=order_ids
            )
            .order_by(
                "-pickup_date"
            )
            .first()
        )


        if last_order:

            last_order_date = last_order.pickup_date

            today = timezone.now().date()

            if hasattr(last_order_date, "date"):
                last_order_date_only = (
                    last_order_date.date()
                )
            else:
                last_order_date_only = last_order_date

            days_since_last_order = (
                today -
                last_order_date_only
            ).days


        # =====================================================
        # Order Frequency
        # =====================================================

        order_dates = list(
            RMOrder.objects
            .filter(
                id__in=order_ids,
                pickup_date__isnull=False
            )
            .order_by("pickup_date")
            .values_list(
                "pickup_date",
                flat=True
            )
        )


        if len(order_dates) >= 2:

            total_days = (
                order_dates[-1] -
                order_dates[0]
            ).days

            intervals = len(order_dates) - 1

            if intervals > 0:

                avg_order_cycle = round(
                    total_days / intervals,
                    1
                )

                order_frequency = (
                    f"Every {avg_order_cycle} days"
                )


                # Expected next order

                if last_order_date:

                    expected_next_order = (
                        last_order_date +
                        timedelta(
                            days=avg_order_cycle
                        )
                    )


        # =====================================================
        # Monthly Quantity
        # =====================================================

        monthly_data = list(
            order_items
            .annotate(
                month=TruncMonth(
                    "order__pickup_date"
                )
            )
            .values(
                "month",
                "product_actual__name"
            )
            .annotate(
                total_qty=Sum("quantity")
            )
            .order_by(
                "month",
                "product_actual__name"
            )
        )


        # =====================================================
        # Chart
        # =====================================================

        if monthly_data:

            chart_labels = sorted(
                set(
                    item["month"].strftime("%Y-%m")
                    for item in monthly_data
                    if item["month"]
                )
            )


            products = sorted(
                set(
                    item["product_actual__name"]
                    for item in monthly_data
                    if item["product_actual__name"]
                )
            )


            data_map = {}


            for item in monthly_data:

                month = item["month"]

                product_name = item[
                    "product_actual__name"
                ]

                if not month or not product_name:
                    continue

                month_str = month.strftime(
                    "%Y-%m"
                )

                data_map.setdefault(
                    product_name,
                    {}
                )

                data_map[
                    product_name
                ][month_str] = (
                    item["total_qty"] or 0
                )


            for product_name in products:

                product_data = []

                for month in chart_labels:

                    quantity = (
                        data_map
                        .get(product_name, {})
                        .get(month, 0)
                    )

                    product_data.append(
                        quantity
                    )


                datasets.append({

                    "label": product_name,

                    "data": product_data,

                    "fill": False,

                    "tension": 0.2,

                })


        # =====================================================
        # Average Monthly Demand
        # =====================================================

        monthly_total = list(
            order_items
            .annotate(
                month=TruncMonth(
                    "order__pickup_date"
                )
            )
            .values("month")
            .annotate(
                total_qty=Sum("quantity")
            )
            .order_by("month")
        )


        if monthly_total:

            total_qty = sum(
                (
                    item["total_qty"] or 0
                )
                for item in monthly_total
            )

            month_count = len(
                monthly_total
            )

            if month_count > 0:

                avg_monthly_quantity = (
                    Decimal(str(total_qty)) /
                    Decimal(str(month_count))
                )


        # =====================================================
        # Last 3 / 6 Month Average
        # =====================================================

        today = timezone.now()

        current_month = today.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )


        # Last 3 months

        three_month_data = list(
            order_items
            .filter(
                order__pickup_date__gte=(
                    current_month -
                    timedelta(days=92)
                )
            )
            .values(
                "order__pickup_date"
            )
            .annotate(
                total_qty=Sum("quantity")
            )
        )


        if three_month_data:

            total_3 = sum(
                (
                    item["total_qty"] or 0
                )
                for item in three_month_data
            )

            last_3_month_avg = (
                Decimal(str(total_3)) /
                Decimal("3")
            )


        # Last 6 months

        six_month_data = list(
            order_items
            .filter(
                order__pickup_date__gte=(
                    current_month -
                    timedelta(days=184)
                )
            )
            .values(
                "order__pickup_date"
            )
            .annotate(
                total_qty=Sum("quantity")
            )
        )


        if six_month_data:

            total_6 = sum(
                (
                    item["total_qty"] or 0
                )
                for item in six_month_data
            )

            last_6_month_avg = (
                Decimal(str(total_6)) /
                Decimal("6")
            )


        # =====================================================
        # Recent Growth
        # =====================================================

        if last_6_month_avg > 0:

            recent_growth = (
                (
                    last_3_month_avg -
                    last_6_month_avg
                )
                /
                last_6_month_avg
                *
                Decimal("100")
            )


        # =====================================================
        # Top Products
        # =====================================================

        top_product_data = list(
            order_items
            .values(
                "product_actual_id",
                "product_actual__name"
            )
            .annotate(
                total_qty=Sum("quantity")
            )
            .order_by(
                "-total_qty"
            )[:10]
        )


        total_customer_qty = sum(
            (
                item["total_qty"] or 0
            )
            for item in top_product_data
        )


        for item in top_product_data:

            qty = (
                item["total_qty"] or 0
            )

            percentage = Decimal("0")

            if total_customer_qty:

                percentage = (
                    Decimal(str(qty))
                    /
                    Decimal(str(
                        total_customer_qty
                    ))
                    *
                    Decimal("100")
                )


            top_products.append({

                "name":
                    item["product_actual__name"],

                "quantity":
                    qty,

                "percentage":
                    round(
                        percentage,
                        2
                    ),

            })


        # =====================================================
        # Inventory / Demand
        # =====================================================

        product_ids = (
            order_items
            .values_list(
                "product_actual_id",
                flat=True
            )
            .exclude(
                product_actual_id__isnull=True
            )
            .distinct()
        )


        products = RMProduct.objects.filter(
            id__in=product_ids
        )

        # -----------------------------------------------------
        # Calculate Current Inventory
        # -----------------------------------------------------

        product_qty = {}


        for p in products:

            inbound, outbound, oa, os, ia = get_quality(p)

            pt = get_product_qty(
                p,
                inbound,
                outbound,
                oa,
                os,
                ia
            )

            # 使用 product ID 作为 key
            product_qty[p.id] = (
                pt.shownumber or 0
            )


        # -----------------------------------------------------
        # Inventory / Demand
        # -----------------------------------------------------

        for product in products:

            # -------------------------------
            # Product Demand
            # -------------------------------

            product_items = order_items.filter(
                product_actual_id=product.id
            )


            product_monthly = list(
                product_items
                .annotate(
                    month=TruncMonth(
                        "order__pickup_date"
                    )
                )
                .values("month")
                .annotate(
                    total_qty=Sum("quantity")
                )
                .order_by("month")
            )


            avg_demand = Decimal("0")


            if product_monthly:

                total = sum(
                    (
                        item["total_qty"] or 0
                    )
                    for item in product_monthly
                )


                months = len(
                    product_monthly
                )


                if months:

                    avg_demand = (
                        Decimal(str(total))
                        /
                        Decimal(str(months))
                    )


            # -------------------------------
            # Current Inventory
            # -------------------------------

            current_inventory = (
                product_qty.get(
                    product.id,
                    0
                )
            )


            # -------------------------------
            # Coverage
            # -------------------------------

            coverage = Decimal("0")


            if avg_demand > 0:

                coverage = (
                    Decimal(str(
                        current_inventory
                    ))
                    /
                    avg_demand
                )


            inventory_products.append({

                "name":
                    product.name,

                "avg_demand":
                    round(
                        avg_demand,
                        0
                    ),

                "inventory":
                    current_inventory,

                "coverage":
                    round(
                        coverage,
                        1
                    ),

            })


    # =========================================================
    # JSON
    # =========================================================

    chart_labels_json = json.dumps(
        chart_labels
    )

    datasets_json = json.dumps(
        datasets
    )

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_metalCustomerProductTrend, {
        'customers': customers,
        'selected_customer': customer_id,
        "selected_customer_obj": selected_customer_obj,

        # Summary
        "ytd_invoice": ytd_invoice,
        "ytd_sales": ytd_sales,
        "ytd_cost": ytd_cost,
        "ytd_gross_profit": ytd_gross_profit,
        "ytd_carrier": ytd_carrier,
        "ytd_sub_profit": ytd_sub_profit,
        "ytd_profit": ytd_profit,
        "ytd_total_profit": ytd_total_profit,
        "gross_margin": gross_margin,

        # Quantity
        "ytd_quantity": ytd_quantity,
        "avg_monthly_quantity": avg_monthly_quantity,
        "avg_order_quantity": avg_order_quantity,
        "order_count": order_count,
        "order_frequency": order_frequency,


        # Activity
        "last_order_date": last_order_date,
        "days_since_last_order": days_since_last_order,
        "avg_order_cycle": avg_order_cycle,
        "expected_next_order": expected_next_order,

        # Products
        "top_products": top_products,

        # Inventory
        "inventory_products": inventory_products,


        # Demand Analysis
        "last_3_month_avg": last_3_month_avg,
        "last_6_month_avg": last_6_month_avg,
        "recent_growth": recent_growth,

        'chart_labels': json.dumps(chart_labels),
        'datasets': json.dumps(datasets),
        'user_permissions': user_permissions
    })

def statistics_metal_product_trend_customer_outbound(request):
    """
    显示所有 Metal / Wholesaler 客户的出库量
    """

    current_year = timezone.now().year

    # =========================================================
    # Customers
    # =========================================================

    customers = (
        RMCustomer.objects
        .filter(
            Q(classification="Metal") |
            Q(classification="Wholesaler")
        )
        .order_by("name")
    )

    # =========================================================
    # Base OrderItem Query
    # =========================================================

    order_items = (
        OrderItem.objects
        .filter(
            order__customer_name__classification__in=[
                "Metal",
                "Wholesaler",
            ],
            order__pickup_date__isnull=False,
            order__is_canceled=False,
        )
        .select_related(
            "order",
            "order__customer_name",
            "product",
            "product_actual",
        )
    )

    # =========================================================
    # YTD Outbound by Customer
    # =========================================================

    customer_data = (
        order_items
        .filter(
            order__pickup_date__year=current_year
        )
        .values(
            "order__customer_name_id",
            "order__customer_name__name",
        )
        .annotate(
            outbound_qty=Sum("quantity"),
            order_count=Count(
                "order_id",
                distinct=True
            ),
        )
        .order_by(
            "-outbound_qty",
            "order__customer_name__name",
        )
    )

    # =========================================================
    # Convert to list
    # =========================================================

    customer_outbound = []

    total_outbound = Decimal("0")

    for item in customer_data:

        qty = item["outbound_qty"] or Decimal("0")

        total_outbound += qty

        customer_outbound.append({
            "customer_id": item[
                "order__customer_name_id"
            ],

            "customer_name": item[
                "order__customer_name__name"
            ],

            "outbound_qty": qty,

            "order_count": item[
                "order_count"
            ],
        })

    # =========================================================
    # Percentage
    # =========================================================

    for item in customer_outbound:

        if total_outbound > 0:

            percentage = (
                Decimal(str(item["outbound_qty"]))
                / total_outbound
                * Decimal("100")
            )

        else:

            percentage = Decimal("0")

        item["percentage"] = round(
            percentage,
            2
        )

    # =========================================================
    # Monthly Outbound by Customer
    # =========================================================

    monthly_data = (
        order_items
        .filter(
            order__pickup_date__year=current_year
        )
        .annotate(
            month=TruncMonth(
                "order__pickup_date"
            )
        )
        .values(
            "month",
            "order__customer_name_id",
            "order__customer_name__name",
        )
        .annotate(
            total_qty=Sum("quantity")
        )
        .order_by(
            "month",
            "order__customer_name__name",
        )
    )


    # =========================================================
    # Build monthly data
    # =========================================================

    monthly_map = {}

    customer_names = set()

    for item in monthly_data:

        month = item["month"]

        customer_name = item[
            "order__customer_name__name"
        ]

        if not month or not customer_name:
            continue

        month_str = month.strftime("%Y-%m")

        quantity = item["total_qty"] or 0

        customer_names.add(customer_name)

        monthly_map.setdefault(
            month_str,
            {}
        )

        monthly_map[
            month_str
        ][customer_name] = quantity


    # =========================================================
    # Convert to HTML-friendly data
    # =========================================================

    monthly_outbound = []

    for month_str in sorted(monthly_map.keys(), reverse=True):

        customers_data = []

        month_total = sum(
            monthly_map[month_str].values()
        )

        for customer_name in sorted(customer_names):

            quantity = monthly_map[
                month_str
            ].get(customer_name, 0)

            percentage = 0

            if month_total > 0:
                percentage = (
                    quantity / month_total
                ) * 100

            customers_data.append({
                "name": customer_name,
                "quantity": quantity,
                "percentage": percentage,
            })

        monthly_outbound.append({
            "month": month_str,
            "customers": customers_data,
            "total": month_total,
        })


    # =========================================================
    # Render
    # =========================================================

    user_permissions = get_user_permissions(
        request.user
    )

    return render(
        request,
        constants_view.template_statistics_metalCustomerOutbound,
        {
            "customers": customers,

            "customer_outbound":
                customer_outbound,

            "total_outbound":
                total_outbound,

            "monthly_outbound":
                monthly_outbound,

            "current_year":
                current_year,

            "user_permissions":
                user_permissions,
        }
    )

def statistics_glove_customer_product_outbound(request):
    return product_outbound_inventory(request, ["Rimei"],["Rimei"] )

def statistics_metal_customer_product_outbound(request):
    return product_outbound_inventory(request, ["Metal", "Wholesaler"], ["Metal"] )

# sub function
def product_outbound_inventory(request, classifications,productType):

    # =========================================================
    # Basic information
    # =========================================================

    current_year = timezone.now().year
    current_month = timezone.now().month

    # =========================================================
    # Customers
    # =========================================================

    customers = (
        RMCustomer.objects
        .filter(classification__in=classifications)
        .order_by("name")
    )

    # =========================================================
    # Base OrderItem Query
    # =========================================================

    order_items = (
        OrderItem.objects
        .filter(
            product_actual__type__in=productType,
            order__pickup_date__isnull=False,
            order__pickup_date__year=current_year,
            order__is_canceled=False,
            product_actual_id__isnull=False,
        )
        .select_related(
            "order",
            "product_actual",
        )
    )

    # =========================================================
    # Total outbound quantity
    # =========================================================

    total_outbound_raw = (
        order_items
        .aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    total_outbound = Decimal(
        str(total_outbound_raw)
    )

    # =========================================================
    # Product outbound quantity
    # =========================================================

    product_outbound_data = list(
        order_items
        .values(
            "product_actual_id",
            "product_actual__name",
        )
        .annotate(
            outbound_qty=Sum("quantity")
        )
        .order_by("-outbound_qty")
    )

    # =========================================================
    # Product IDs
    # =========================================================

    product_ids = [
        item["product_actual_id"]
        for item in product_outbound_data
        if item["product_actual_id"]
    ]

    products = (
        RMProduct.objects
        .filter(
            id__in=product_ids
        )
    )

    # =========================================================
    # Calculate Current Inventory
    # =========================================================

    product_qty = {}

    for product in products:

        inbound, outbound, oa, os, ia = get_quality(
            product
        )

        pt = get_product_qty(
            product,
            inbound,
            outbound,
            oa,
            os,
            ia,
        )

        product_qty[product.id] = Decimal(
            str(
                pt.shownumber or 0
            )
        )

    # =========================================================
    # Create ONE combined table
    # =========================================================

    product_data = []

    for item in product_outbound_data:

        product_id = item[
            "product_actual_id"
        ]

        product_name = item[
            "product_actual__name"
        ]

        # -----------------------------------------------------
        # Outbound Quantity
        # -----------------------------------------------------

        outbound_qty = Decimal(
            str(
                item["outbound_qty"] or 0
            )
        )

        # -----------------------------------------------------
        # Percentage of total outbound
        # -----------------------------------------------------

        percentage = Decimal("0")

        if total_outbound > 0:

            percentage = (
                outbound_qty
                / total_outbound
                * Decimal("100")
            )

        # -----------------------------------------------------
        # Monthly Average
        # -----------------------------------------------------

        monthly_avg = Decimal("0")

        if current_month > 0:

            monthly_avg = (
                outbound_qty
                / Decimal(
                    str(current_month)
                )
            )

        # -----------------------------------------------------
        # Current Inventory
        # -----------------------------------------------------

        current_inventory = Decimal(
            str(
                product_qty.get(
                    product_id,
                    0
                )
            )
        )

        # -----------------------------------------------------
        # Inventory Coverage
        # -----------------------------------------------------

        coverage = Decimal("0")

        if monthly_avg > 0:

            coverage = (
                current_inventory
                / monthly_avg
            )

        # -----------------------------------------------------
        # Add to combined table
        # -----------------------------------------------------

        product_data.append({

            "product_id":
                product_id,

            "product_name":
                product_name,

            "outbound_qty":
                outbound_qty,

            "percentage":
                percentage,

            "monthly_avg":
                monthly_avg,

            "inventory":
                current_inventory,

            "coverage":
                coverage,
        })

    # =========================================================
    # Average Monthly Total
    #
    # Total YTD outbound / elapsed months
    # =========================================================

    avg_monthly_total = Decimal("0")

    if current_month > 0:

        avg_monthly_total = (
            total_outbound
            / Decimal(
                str(current_month)
            )
        )

    # =========================================================
    # Product Count
    #
    # Number of products in the combined table
    # =========================================================

    product_count = len(product_data)

    # =========================================================
    # Coverage ranking
    # Lowest coverage first
    # =========================================================

    coverage_product_data = sorted(
        product_data,
        key=lambda x: x["coverage"]
    )

    # =========================================================
    # Context
    # =========================================================
    user_permissions = get_user_permissions(request.user)
    context = {

        "customers":
            customers,

        "current_year":
            current_year,

        "current_month":
            current_month,

        "total_outbound":
            total_outbound,

        "avg_monthly_total":
            avg_monthly_total,

        "product_count":
            product_count,

        "product_data":
            product_data,

        # Coverage table
        "coverage_product_data": coverage_product_data,

        'user_permissions': user_permissions,
    }
    
    return render(
        request,
        constants_view.template_statistics_metalCustomerProductOutbound,
        context,
    )



def statistics_metal_commission(request):

    customer_id = request.GET.get("customer")
    month = request.GET.get("month")
    orders = get_metal_commission_orders(customer_id, month)

    # 组织汇总后的数据
    report = {}
    grand_amount = 0
    grand_amount_tax = 0
    invoice_amount = 0
    ground_profit_amount = 0
    cost_amount = 0
    customer_amount = 0

    for order in orders:

        customer = order.customer_name.name
        month = order.month.strftime("%Y-%m") if order.month else "No Date"

        report.setdefault(customer, {})
        report[customer].setdefault(month, {
            "orders": [],
            "grand_amount": 0,
            "grand_amount_tax":0,
            "invoice_amount":0,
            "profit_amount":0,
            "cost_amount":0,
            "customer_amount":0,
        })

        amount = order.total_amount or 0
        profit = amount * Decimal(constants_address.Tax_rate)

        # 月份汇总
        report[customer][month]["orders"].append(order)
        report[customer][month]["grand_amount"] += amount
        report[customer][month]["grand_amount_tax"] += profit
        report[customer][month]["invoice_amount"] += amount + profit
        report[customer][month]["profit_amount"] += order.total_profit
        report[customer][month]["cost_amount"] += order.total_cost
        report[customer][month]["customer_amount"] += order.customer_price

        # 客户汇总
        grand_amount += amount
        grand_amount_tax += amount * Decimal(constants_address.Tax_rate)
        invoice_amount += order.invoice_price
        ground_profit_amount += order.total_profit
        cost_amount += order.total_cost
        customer_amount += order.customer_price

    customers = RMCustomer.objects.filter(
        classification="Metal"
    ).order_by("name")
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statistics_metalCommission, {

        'user_permissions': user_permissions,
        "orders": orders,
        "customers": customers,
        "selected_customer": customer_id,
        "selected_month": month,
        "report": report,
        "grand_amount": grand_amount,
        "grand_amount_tax":grand_amount_tax,
        "invoice_amount":invoice_amount,
        "ground_profit_amount": ground_profit_amount,
        "cost_amount": cost_amount,
        "customer_amount": customer_amount,
    })

def export_commission(request):
    customer_id = request.GET.get("customer")
    month = request.GET.get("month")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    orders = get_metal_commission_orders(
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )

    output_dir = "media/temp"
    os.makedirs(output_dir, exist_ok=True)

    filename = "Metal_Commission_Report.pdf"
    filepath = os.path.join(output_dir, filename)

    # c = canvas.Canvas(filepath, pagesize=landscape(letter))
    # PDF 保存路径（和 detail 一致）
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.INVOICR_COMMISION
    )
    ensure_dir_exists(pdf_path)

    today = datetime.now().strftime("%Y%m%d")
    filename = os.path.join(pdf_path, f"Commission_{today}.pdf")
    c, pagesize, inch, ImageReader = create_pdf_canvas(filename)
    width, height = pagesize

    converter_commision_pdf(c, orders, width, height, start_date, end_date)

    return finalize_pdf_and_response(
        c,
        filename
    )

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

def get_metal_commission_orders(customer_id, month=None, start_date=None, end_date=None):
    # ============================================================
    # 1. 基础 QuerySet
    # ============================================================

    orders = (
        RMOrder.objects
        .filter(
            is_canceled=False,
            customer_ispay=True,
        )
        .select_related("customer_name")
        .annotate(

            # 注意：
            # 这里必须继续叫 month
            # 因为你项目其他地方使用了 order.month
            month=TruncMonth("pickup_date"),

            # ====================================================
            # 销售金额
            # quantity * sales price
            # ====================================================

            total_amount=Sum(
                ExpressionWrapper(
                    F("order_items__quantity")
                    * F("order_items__price"),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2
                    )
                )
            ),

            # ====================================================
            # 成本金额
            # quantity * actual cost
            # ====================================================

            total_cost=Sum(
                ExpressionWrapper(
                    F("order_items__quantity")
                    * F("order_items__product_actual__price"),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2
                    )
                )
            ),
        )
    )

    # ============================================================
    # 2. Customer Filter
    # ============================================================

    if customer_id:
        orders = orders.filter(
            customer_name_id=customer_id
        )

    # ============================================================
    # 3. Convert Date
    # ============================================================

    if start_date and isinstance(start_date, str):
        try:
            start_date = datetime.strptime(
                start_date,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            start_date = None

    if end_date and isinstance(end_date, str):
        try:
            end_date = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            end_date = None

    # ============================================================
    # 4. 日期范围优先
    #
    # 如果用户输入 Start Date 或 End Date，
    # 就不要再用 month 限制月份。
    #
    # 例如：
    #
    # month      = 2026-08
    # start_date = 2026-08-15
    # end_date   = 2026-09-15
    #
    # 查询：
    #
    # 2026-08-15 ~ 2026-09-15
    # ============================================================

    if start_date or end_date:

        if start_date:
            orders = orders.filter(
                pickup_date__gte=start_date
            )

        if end_date:
            orders = orders.filter(
                pickup_date__lte=end_date
            )

    # ============================================================
    # 5. 没有日期范围时，才使用 month
    #
    # 例如：
    #
    # month = 2026-08
    #
    # 查询：
    #
    # 2026-08-01 ~ 2026-08-31
    # ============================================================

    elif month:

        try:
            year, mon = month.split("-")

            year = int(year)
            mon = int(mon)

            # 月初
            month_start = datetime(
                year,
                mon,
                1
            ).date()

            # 下个月月初
            if mon == 12:
                next_month = datetime(
                    year + 1,
                    1,
                    1
                ).date()
            else:
                next_month = datetime(
                    year,
                    mon + 1,
                    1
                ).date()

            # 本月最后一天
            month_end = (
                next_month
                - timedelta(days=1)
            )

            orders = orders.filter(
                pickup_date__gte=month_start,
                pickup_date__lte=month_end,
            )

        except (ValueError, AttributeError):
            pass

    # ============================================================
    # 5. 排序
    # ============================================================

    orders = orders.order_by(
        "customer_name__name",
        "month",
        "pickup_date",
        "so_num"
    )

    # ============================================================
    # 6. 计算 Commission 数据
    # ============================================================

    for order in orders:

        # --------------------------------------------------------
        # Sales Amount
        # --------------------------------------------------------

        amount = (
            order.total_amount
            or Decimal("0.00")
        )

        # --------------------------------------------------------
        # Cost
        # --------------------------------------------------------

        cost = (
            order.total_cost
            or Decimal("0.00")
        )

        # --------------------------------------------------------
        # Carrier Price
        # --------------------------------------------------------

        carrier = (
            order.carrier_price
            or Decimal("0.00")
        )

        # --------------------------------------------------------
        # Delivery Price
        # --------------------------------------------------------

        delivery = (
            order.delivery_price
            or Decimal("0.00")
        )

        # --------------------------------------------------------
        # 5% Profit
        # --------------------------------------------------------

        profit = (
            cost
            * Decimal("0.05")
        )

        # --------------------------------------------------------
        # Tax
        # --------------------------------------------------------

        total_tax = (
            amount
            * Decimal(constants_address.Tax_rate)
        )

        # --------------------------------------------------------
        # Invoice Price
        # --------------------------------------------------------

        invoice_price = (
            amount
            * (
                Decimal(constants_address.Tax_rate)
                + Decimal("1.00")
            )
        )

        # ========================================================
        # 保存计算结果
        # ========================================================

        order.total_tax = total_tax

        order.invoice_price = invoice_price

        order.carrier_price = carrier

        order.total_cost = cost

        order.profit = profit

        # ========================================================
        # Delivery Fee
        #
        # delivery = 0
        #     -> 扣 $150
        #
        # delivery != 0
        #     -> 不扣 $150
        # ========================================================

        if delivery == Decimal("0.00"):
            delivery_fee = Decimal("150.00")
        else:
            delivery_fee = Decimal("0.00")

        # ========================================================
        # Sub Profit
        # ========================================================

        order.sub_profit = (
            amount
            - delivery_fee
            - order.total_cost
        )

        # ========================================================
        # Total Profit
        # ========================================================

        order.total_profit = (
            amount
            - delivery_fee
            - order.total_cost
            + profit
        )

    # ============================================================
    # 7. 返回
    # ============================================================

    return orders