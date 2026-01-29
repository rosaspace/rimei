from collections import defaultdict
from datetime import datetime, date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Table, TableStyle, Paragraph
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import inch

from ..constants import constants_view
from ..models import Container, InvoiceCustomer, LogisticsCompany, ContainerStatement

from .utils.getPermission import get_user_permissions
from .utils.pdf_temp_utils import create_temp_pdf, cleanup_temp_file


# statement list
@login_required(login_url='/login/')
def invoice_statement(request):
    statements = ContainerStatement.objects.all().order_by('-statement_date', '-id')
    container_ids = [stmt.container_id_str for stmt in statements if stmt.container_id_str]
    containers_map = {
        c.container_id: c for c in Container.objects.filter(container_id__in=container_ids)
    }

    # 使用 defaultdict 按日期分组
    grouped = defaultdict(list)
    for statement in statements:
        container = containers_map.get(statement.container_id_str)  # 用 container_id 找对应 Container 实例
        if container:
            grouped[(statement.statement_date, statement.statement_number)].append((container,statement))
            print("group:", container.container_id)

    # 构建合并后的结构，每个日期只显示一条
    merged_statements = []
    for (date, statement_number), container_statement_pairs  in grouped.items():
        containers = [c for c, _ in container_statement_pairs]
        total_amount = sum(c.price for c in containers )

        # ✅ 判断是否全部已付款
        all_paid = all(c.ispay for c in containers)
        paid_status = "Paid" if all_paid else "Unpaid"

        # 从任意一个 statement 获取 created_user
        _, sample_statement = container_statement_pairs[0]
        operator = sample_statement.created_user

        merged_entry = {
            "statement_number": statement_number,
            "statement_date": date,
            "container_count": len(containers),
            "total_amount": total_amount,
            "paid_status": paid_status,  # 如果需要动态取，可额外查询或改逻辑
            "operator" : operator,
            "containers": containers,
        }
        merged_statements.append(merged_entry)

    # 按日期排序（可选，因 defaultdict 顺序可能不是稳定的）
    merged_statements.sort(
        key=lambda x: (x["statement_date"], x["statement_number"]),
        reverse=True
    )

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statement, {"statements":merged_statements,'user_permissions': user_permissions})

#  enter one statement
@login_required(login_url='/login/')
def statement_selected_invoices(request):

    # ==================================================
    # GET：查看已有 Statement
    # ==================================================
    if request.method == "GET":
        statement_number = request.GET.get("statement_number")

        if not statement_number:
            return redirect("invoice_unpaid")

        container_statements = ContainerStatement.objects.filter(
            statement_number=statement_number
        ).select_related("container")

        containers = [cs.container for cs in container_statements]
        total_price = sum(c.price or 0 for c in containers)

        return render(
            request,
            constants_view.template_statement_invoice_preview,
            {
                "containers": containers,
                "total_price": total_price,
                "current_date": datetime.now(),
                "statement_number": statement_number,
            }
        )
        
    return redirect("invoice_unpaid")

# statement delete
@login_required(login_url='/login/')
def delete_statement(request):
    print("---------delete_statement---------")
    statement_number = request.POST.get("statement_number")
    print("statement_number: ",statement_number)
    if statement_number:
        ContainerStatement.objects.filter(statement_number=statement_number).delete()
        return redirect("invoice_statement")
    return JsonResponse({"success": False, "error": "No statement number provided"})

# print advance statement
def print_statement_invoice_pdf(request):
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_ids")
    elif request.method == "GET":
        selected_ids = request.GET.getlist("selected_ids")
    else:
        return redirect("invoice_unpaid") 

    if not selected_ids:
        return HttpResponse("No container IDs provided.", status=400)
    
    containers = Container.objects.filter(container_id__in=selected_ids)
    total_price = sum([c.price or 0 for c in containers])

    # ✅ 创建临时文件
    temp_path = create_temp_pdf()

    # ✅ 使用 ReportLab 写入该 PDF 文件
    doc = SimpleDocTemplate(temp_path, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # 标题
    large_title_style = ParagraphStyle(
        name="LargeTitle",
        parent=styles["Title"],
        fontSize=20,  # 设置大标题字体大小
        leading=24
    )
    elements.append(Paragraph(f"Advance77 Payment Statement - {datetime.now().strftime('%m/%d/%Y')}", large_title_style))
    elements.append(Spacer(1, 12))

    # 表格数据
    index = 0
    data = [["ID", "Container#", "Customer", "Invoice#", "Price", "Invoice Date", "Due Date"]]
    for c in containers:
        index += 1
        data.append([
            index,
            c.container_id,
            c.customer.name,
            c.invoice_id,
            f"${c.price or 0:.2f}",
            c.invoice_date.strftime("%m/%d/%Y") if c.invoice_date else "",
            c.due_date.strftime("%m/%d/%Y") if c.due_date else "",
            # c.payment_date.strftime("%m/%d/%Y") if c.payment_date else "",
        ])
    # 合计行
    data.append(["", "Total", "", "", f"${total_price:.2f}", "", ""])

    table = Table(data, colWidths=[50, 100, 90, 70, 60, 70, 70, 70])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),  # ✅ 设置字体大小为12
        ("LEADING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),              # 增加下边距
        ("TOPPADDING", (0, 0), (-1, -1), 6),                 # 增加上边距
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    doc.build(elements)

    # ✅ 读取 PDF 文件并返回
    new_filename = "invoice_statement.pdf"
    with open(temp_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{new_filename}"'

    cleanup_temp_file(temp_path)
    return response

# print omar statement
def print_statement_customer_invoice_pdf(request):
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_ids")
    elif request.method == "GET":
        selected_ids = request.GET.getlist("selected_ids")
    else:
        return redirect("invoice_unpaid") 

    if not selected_ids:
        return HttpResponse("No container IDs provided.", status=400)
    
    containers = Container.objects.filter(container_id__in=selected_ids)
    total_price = sum([c.customer_price or 0 for c in containers])

    # ✅ 创建临时文件
    temp_path = create_temp_pdf()

    # ✅ 使用 ReportLab 写入该 PDF 文件
    doc = SimpleDocTemplate(temp_path, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # 标题
    large_title_style = ParagraphStyle(
        name="LargeTitle",
        parent=styles["Title"],
        fontSize=20,  # 设置大标题字体大小
        leading=24
    )
    elements.append(Paragraph(f"Customer Payment Statement - {datetime.now().strftime('%m/%d/%Y')}", large_title_style))
    elements.append(Spacer(1, 12))

    # 表格数据
    index = 0
    data = [["ID", "Container#", "Customer", "Invoice#", "Price", "Invoice Date", "Due Date"]]
    for c in containers:
        index += 1
        data.append([
            index,
            c.container_id,
            c.customer.name,
            c.customer_invoiceId,
            f"${c.customer_price or 0:.2f}",
            c.customer_invoice_date.strftime("%m/%d/%Y") if c.customer_invoice_date else "",
            c.customer_due_date.strftime("%m/%d/%Y") if c.customer_due_date else "",
            # c.payment_date.strftime("%m/%d/%Y") if c.payment_date else "",
        ])
    # 合计行
    data.append(["", "Total", "", "", f"${total_price:.2f}", "", ""])

    table = Table(data, colWidths=[50, 100, 90, 70, 60, 70, 70, 70])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),  # ✅ 设置字体大小为12
        ("LEADING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),              # 增加下边距
        ("TOPPADDING", (0, 0), (-1, -1), 6),                 # 增加上边距
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    doc.build(elements)

    # ✅ 读取 PDF 文件并返回
    new_filename = "invoice_statement.pdf"
    with open(temp_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{new_filename}"'

    cleanup_temp_file(temp_path)
    return response

# set paid advance
@login_required(login_url='/login/')
def paid_invoice_advance(request):
    print("POST data:", request.POST)  # 🔍 打印全部 POST 数据
    ids = request.POST.getlist('all_ids')
    date_str = request.POST.get('payment_date')
    payment_date = timezone.now().date()  # 默认今天

    print("Received container_ids:", ids)  # 检查你是否收到了 container_id 列表

    if date_str:
        try:
            payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # 如果解析失败就用默认

    Container.objects.filter(id__in=ids).update(
        ispay=True,
        payment_date=payment_date
    )

    return redirect("invoice_statement")

# set paid customer
@login_required(login_url='/login/')
def paid_invoice_customer(request):
    
    ids = request.POST.getlist('all_ids')
    date_str = request.POST.get('payment_date')
    customer_payment_date = timezone.now().date()

    if date_str:
        try:
            customer_payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    Container.objects.filter(id__in=ids).update(
        customer_ispay=True,
        customer_payment_date=customer_payment_date
    )
    return redirect("invoice_statement")

# generate statement
def statement_by_filter(request):
    containers = filter_containers(request)

    if not containers.exists():
        return HttpResponse("No data for statement")
    
    total_price = sum(
        (c.price or Decimal("0.00")) for c in containers
    )
    statement_number = "STM" + datetime.now().strftime("%Y%m%d%H%M%S")

    # ✅ 用事务，防止部分写入
    with transaction.atomic():
        for container in containers:
            ContainerStatement.objects.get_or_create(
                container=container,
                statement_number=statement_number,
                defaults={
                    "statement_date": timezone.now().date(),
                    "created_at": timezone.now(),
                    "created_user": request.user.username
                    if hasattr(request.user, "username")
                    else str(request.user),
                }
            )

    return render(request, constants_view.template_statement_invoice_preview, {
        "containers": containers, 
        "total_price": total_price,
        "current_date": datetime.now(),
        "statement_number" : statement_number,
        },)

# sub function
def filter_containers(request):
    qs = Container.objects.select_related('customer', 'logistics')

    customer_id = request.GET.get('customer')
    logistics_id = request.GET.get('logistics')
    ispay = request.GET.get('ispay')
    customer_ispay = request.GET.get('customer_ispay')

    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    if logistics_id:
        qs = qs.filter(logistics_id=logistics_id)

    if ispay == 'false':
        qs = qs.filter(
            ispay=False,
            invoice_id__isnull=False
        ).exclude(invoice_id='')

    if customer_ispay == 'false':
        qs = qs.filter(
            customer_ispay=False,
            customer_invoiceId__isnull=False
        ).exclude(customer_invoiceId='')

    return qs

