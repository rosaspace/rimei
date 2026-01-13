from django.shortcuts import render, redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Q

from reportlab.platypus  import SimpleDocTemplate, Image
from reportlab.platypus import Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from django.contrib import messages

import os
import re
import tempfile
import fitz  # PyMuPDF 解析 PDF

from datetime import datetime
from decimal import Decimal

from ..models import Container,RMProduct
from .pdfextract import extract_invoice_data, extract_customer_invoice_data
from ..constants import constants_address, constants_view
from .pdfgenerate import extract_text_from_pdf, converter_customer_invoice
from .inventory_count import get_month_pallet_number, get_quality, get_product_qty
from .getPermission import get_user_permissions
from ..models import InvoicePaidCustomer,Carrier,InvoiceVendor,InvoicePurposeFor,InvoiceAPRecord,InvoiceARRecord

# print original delivery order
def print_original_do(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.container_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    do_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.ORIGINAL_DO_FOUDER)
    os.makedirs(do_path , exist_ok=True)  # 如果目录不存在，则创建

    # 构建完整 PDF 文件路径
    pdf_path = os.path.join(do_path, container.container_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{container.container_pdfname}"'
        return response

# print advance invoice
def print_original_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_FOUDER, container.invoice_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{container.invoice_pdfname}"'
        return response

# print invoice to omar
def print_converted_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.customer_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    invoice_dir  = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.ORDER_CONVERTED_FOLDER)
    os.makedirs(invoice_dir , exist_ok=True)  # 如果目录不存在，则创建

    # 构建完整 PDF 文件路径
    pdf_path = os.path.join(invoice_dir, container.customer_invoice_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{container.customer_invoice_pdfname}"'
        return response

# generate invoice for omar
def print_customer_invoice(request, container_id, isEmptyContainerRelocate=0, isClassisSplit = 0, isPrepull = 0):
    print("----------print_customer_invoice----------")
    print("isEmptyContainerRelocate: ", isEmptyContainerRelocate)
    print("isClassisSplit: ", isClassisSplit)
    container = get_object_or_404(Container, container_id=container_id)

    amount_items = []
    total_original = 0

    # ============================
    # ✅ NEW CASE: logistics.id == 3
    # ============================
    if container.logistics and container.logistics.id == 3:
        print("✅ logistics.id == 3, using fixed invoice pricing")

        # 计算天数（包含 delivery_date 和 empty_date）
        delivery_date = container.delivery_date
        empty_date = container.empty_date

        days = (empty_date - delivery_date).days + 1  # ✅ 两头都包括
        rate = 40.00
        chassis_total = days * rate

        amount_items = [
            ("Drayage (FSC all included)", 1, 450.00, 450.00),
            ("Chassis", days, rate, chassis_total),
        ]
        total_original = 560.00

    # ============================
    # ✅ ORIGINAL LOGIC (unchanged)
    # ============================
    else:

        if not container.invoice_pdfname:
            return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

        # 构建PDF文件路径
        input_pdf_path  = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_FOUDER, container.invoice_pdfname)    
        # 检查文件是否存在
        if not os.path.exists(input_pdf_path ):
            return HttpResponse("PDF文件未找到", status=404)
        
        # 打开原始 PDF
        original_doc  = fitz.open(input_pdf_path)
        amount_items = []
        total_original = 0
        lines = []
        # 提取所有行文本
        for page in original_doc:
            lines += page.get_text().splitlines()

        # 清洗空行
        lines = [line.strip() for line in lines if line.strip()]
        
        i = 0
        while i < len(lines) - 4:
            # 特例：Flat rate 前面是有效描述行
            if lines[i+1].lower() == "flat rate":
                desc = lines[i]  # 正确描述
                try:
                    units = float(lines[i+2])
                    rate = float(lines[i+3])
                    amount = float(lines[i+4])

                    amount_items.append((desc.strip(), units, rate, amount))
                    total_original += amount

                    print(f"✔✔ {desc} | Units: {units} | Rate: {rate} | Amount: {amount}")
                    i += 5  # 向后跳 5 行
                except (ValueError, IndexError):
                    i += 1
            else:
                desc_line = lines[i].strip()

                # ✅ 特例修正：INTERM1 的正确格式
                if desc_line == "INTERM1" or desc_line == "INTERM2":
                    try:
                        # 跳过无用的 weight 行
                        units = 1
                        rate = float(lines[i + 3])  # 应该跳过几行到金额
                        amount = float(lines[i + 4])

                        amount_items.append((desc_line, units, rate, amount))
                        total_original += amount

                        print(f"✔ [FIXED] {desc_line} | Units: {units} | Rate: {rate} | Amount: {amount}")
                        i += 5
                        continue
                    except (ValueError, IndexError):
                        i += 1
                        continue

                # 通用解析逻辑（小心不要误入）
                if re.match(r'^[A-Za-z][A-Za-z0-9 \-/]+$', desc_line) and not desc_line.lower().startswith("min"):
                    try:
                        units = float(lines[i + 1])
                        rate = float(lines[i + 2])
                        amount = float(lines[i + 3])

                        amount_items.append((desc_line, int(units), rate, amount))
                        total_original += amount

                        print(f"✔* {desc_line} | Units: {units} | Rate: {rate} | Amount: {amount}")
                        i += 4
                    except (ValueError, IndexError):
                        i += 1
                else:
                    i += 1

        print(f"✅ 共抓取 {len(amount_items)} 条价格记录，总金额: {total_original:.2f}")
        original_doc.close()

    # ============================
    # 生成客户发票 PDF（共用）
    # ============================
    new_filename = f"{container.container_id}.pdf"
    output_dir = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.CUSTOMER_INVOICE_FOLDER)
    output_file_path = os.path.join(output_dir, new_filename)  # ✅ 拼接完整路径
    converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate, isClassisSplit, isPrepull)
    
    # 打开并读取PDF文件
    with open(output_file_path , 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{new_filename}"'
        return response

# advance statement
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_path = temp_pdf.name

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

    # 删除临时文件
    os.remove(temp_path)
    return response

# omar statement
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_path = temp_pdf.name

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

    # 删除临时文件
    os.remove(temp_path)
    return response

# upload advance invoice
def edit_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    invoice_file = request.FILES.get('invoice_file')

    if not invoice_file:
        return HttpResponse("No file uploaded.", status=404)

    try:
        # 保存文件
        container.invoice_pdfname = invoice_file.name
        file_path = os.path.join(constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_FOUDER, invoice_file.name)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        with open(full_path, 'wb+') as destination:
            for chunk in invoice_file.chunks():
                destination.write(chunk)

        # 解析发票内容
        text = extract_text_from_pdf(file_path)
        data = extract_invoice_data(text)

        # 更新 container 部分字段（不保存付款相关信息）
        if data['invoice_id']:
            container.invoice_id = data['invoice_id']
        if data['invoice_date']:
            container.invoice_date = data['invoice_date']
        if data['due_date']:
            container.due_date = data['due_date']
        if data['price']:
            container.price = Decimal(data['price'])
        container.save()

        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id,
        })
    
    except Exception as e:
        return JsonResponse({"error": f"Failed to process invoice: {e}"}, status=500)

# upload ladingcargo invoice
def edit_ladingcargo_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    # ✅ 文件
    invoice_file = request.FILES.get('ladingcargo_invoice_file')
    
    # ✅ 表单字段（必须用 POST）
    invoice_id = request.POST.get('ladingcargo_invoice_id')
    invoice_price = request.POST.get('ladingcargo_invoice_price')
    invoice_date = request.POST.get('ladingcargo_invoice_date')
    invoice_duedate = request.POST.get('ladingcargo_invoice_duedate')

    if not invoice_file:
        return HttpResponse("No file uploaded.", status=404)

    try:
        # 保存文件
        container.invoice_pdfname = invoice_file.name
        file_path = os.path.join(constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_FOUDER, invoice_file.name)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        with open(full_path, 'wb+') as destination:
            for chunk in invoice_file.chunks():
                destination.write(chunk)

        # 不用解析发票内容，价格为450

        # 更新 container 部分字段（不保存付款相关信息）
        container.invoice_id = invoice_id
        container.invoice_date = invoice_date
        container.due_date = invoice_duedate
        container.price = Decimal(invoice_price)
        container.save()

        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id,
        })
    
    except Exception as e:
        return JsonResponse({"error": f"Failed to process invoice: {e}"}, status=500)


# upload invoice to omar
def edit_customer_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    invoice_file = request.FILES.get('invoice_file')

    if not invoice_file:
        return HttpResponse("No file uploaded.", status=404)

    try:        
        container.customer_invoice_pdfname = invoice_file.name
        file_path = os.path.join(constants_address.UPLOAD_DIR_invoice, constants_address.ORDER_CONVERTED_FOLDER, invoice_file.name) 
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # 保存文件
        with open(full_path, 'wb+') as destination:
            for chunk in invoice_file.chunks():
                destination.write(chunk)

        # 解析 PDF 内容
        text = extract_text_from_pdf(file_path)
        data = extract_customer_invoice_data(text)

        # 更新模型字段
        if data['invoice_id']:
            container.customer_invoiceId = data['invoice_id']
        if data['invoice_date']:
            container.customer_invoice_date = data['invoice_date']
        if data['due_date']:
            container.customer_due_date = data['due_date']
        if data['price']:
            container.customer_price = Decimal(data['price'])
        container.save()

        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id
        })

    except Exception as e:
        return JsonResponse({"error": f"Failed to process invoice: {e}"}, status=500)

# update advance invoice price
def edit_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if request.method == "GET":
        print("date: ",container.customer_payment_date, type(container.customer_payment_date))
        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id,
        })

    elif request.method == 'POST':

        # 获取并更新价格
        price  = request.POST.get('invoice_price_new')
        is_pay = 'is_pay' in request.POST
        pay_date = request.POST.get('pay_date')

        if price :
            container.price = Decimal(price)

        container.ispay = is_pay
        container.payment_date = pay_date or None
        container.save()

        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id,
        })

# update omar invoice pay status
def edit_customer_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if request.method == 'POST':
        is_pay = 'is_pay' in request.POST
        pay_date = request.POST.get('pay_date')

        container.customer_ispay = is_pay
        container.customer_payment_date = pay_date or None
        container.save()

        return render(request, constants_view.template_edit_invoice, {
            'container': container,
            'container_id': container_id
        })

    return render(request, constants_view.template_edit_invoice, {
        'container': container,
        'container_id': container_id,
    })

# export pallet and labor invoice monthly
def export_pallet_invoice(request):
    # 获取请求中的月份和年份
    select_month = request.GET.get('month')
    select_year = request.GET.get('year')
    inboundNumber_str = request.GET.get('inboundNumber')
    outboundNumber_str = request.GET.get('outboundNumber')
    palletstoragenumber_str = request.GET.get('palletstoragenumber')

    try:
        inboundNumber = int(inboundNumber_str)
        outboundNumber = int(outboundNumber_str)
        palletstoragenumber = int(palletstoragenumber_str)
    except (TypeError, ValueError):
        inboundNumber = 0  # 或根据你的需求设为其他默认值
        outboundNumber = 0
        palletstoragenumber = 0

    # 当月剩余托盘数
    inventory_items = RMProduct.objects.filter(type = "Rimei")
    total_storage_pallets = 0
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)
        total_storage_pallets += productTemp.totalPallet

    # ✅ 出入库托盘数
    total_container,total_in_plts,total_out_plts, gloves_in_data,container_in_orders = get_month_pallet_number(select_month, select_year)

    if inboundNumber > total_in_plts :
        total_in_plts = inboundNumber
    if outboundNumber > total_out_plts :
        total_out_plts = outboundNumber
    if palletstoragenumber > total_storage_pallets :
        total_storage_pallets = palletstoragenumber
    total_plts = total_in_plts + total_out_plts

    # ✅ 总价格
    total_price = total_container * 450 + total_in_plts * 4 + total_out_plts * 4 + total_plts * 12 + total_storage_pallets * 6

    # ✅ 拼接 container 名字（每行 3~4 个）
    container_list = list(container_in_orders.values_list('container_id', flat=True))
    wrapped_container = ""
    for i in range(0, len(container_list), 3):  # 每行3个
        wrapped_container += "  ".join(container_list[i:i+3]) + "\n"
    print(wrapped_container)
    
    title = 'Payment Invoice Report'
    temp_path = invoice_template(title,wrapped_container,total_container, total_in_plts, total_out_plts, total_plts, total_storage_pallets, total_price)

    # ✅ 读取 PDF 文件并返回
    new_filename = "invoice_month_warehouse.pdf"
    with open(temp_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{new_filename}"'

    # 删除临时文件
    os.remove(temp_path)
    return response

# Template -- export pallet and labor invoice monthly
def invoice_template(title,wrapped_container, total_container, total_in_plts,total_out_plts,total_plts,total_pallets,total_price):
    # ✅ 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_path = temp_pdf.name

    # ✅ 使用 ReportLab 写入该 PDF 文件
    doc = SimpleDocTemplate(temp_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # 样式
    normal = ParagraphStyle(name='Normal', fontSize=10, leading=12)
    bold = ParagraphStyle(name='Bold', parent=normal, fontName='Helvetica-Bold')
    invoice_title_style = ParagraphStyle(
        name="InvoiceTitle",
        fontSize=20,
        leading=24,
        alignment=TA_RIGHT,
        textColor=colors.black,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )
    invoice_cell_style = ParagraphStyle(
        name="InvoiceCell",
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
    )

    # ✅ Logo 和标题
    logo = Image(constants_address.Rimei_LOGO_PATH, width=2 * inch, height=0.7 * inch)
    rm_address_str = "<br/>".join(constants_address.RM_ADDRESS)
    company_info = Paragraph(rm_address_str, normal)

    # ✅ 用 Table 将 logo 和公司地址垂直排列在一列，左对齐
    left_column = Table(
        [[logo], [company_info]],
        colWidths=[3.2 * inch],  # 可微调宽度
        hAlign='LEFT'
    )
    left_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # 发票信息
    today_str = datetime.today().strftime("%m%d%Y")
    today_display = datetime.today().strftime("%-m/%-d/%Y")
    invoice_title = Paragraph("INVOICE", invoice_title_style)
    invoice_spacer = Spacer(1, 10)  # 加一个高度为6的空行
    invoice_data = [
        [Paragraph("<b>Invoice#</b>", invoice_cell_style), Paragraph(f"RM{today_str}", invoice_cell_style)],
        [Paragraph("<b>Date</b>", invoice_cell_style), Paragraph(today_display, invoice_cell_style)],
    ]
    invoice_table = Table(invoice_data, colWidths=[60, 100], hAlign='RIGHT')
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # ✅ 将标题和表格垂直堆叠
    right_column = Table([[invoice_title], [invoice_spacer], [invoice_table]], hAlign='RIGHT')
    right_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ✅ 主布局：左右两列
    header_table = Table(
        [[left_column, right_column]],
        colWidths=[4.0 * inch, 3.2 * inch]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    #region Bill To
    # 收款人地址, Bill To
    elements.extend(add_section_header("Bill to:", bold, 40))
    elements.append(Paragraph(
        'Omar supplies Inc.<br/>400 E. Randolph St.<br/>Suite 705<br/>Chicago IL 60601<br/>United States',
        normal
    ))
    elements.append(Spacer(1, 12))
    #endregion

    #region 表格
    # 项目表格
    data = [
        ["Item", "Description", "Qty", "Unit Price", "Total Price"],
        ["Container Unload Fee", wrapped_container.strip(), total_container, "$450.00", f'${total_container * 450:.2f}'],
        ["Pallet Fee", "", total_plts, "$12.00", f'${total_plts * 12:.2f}'],
        ["Pallet Storage Per Month", "", total_pallets, "$6.00", f'${total_pallets * 6:.2f}'],
        ["Pallet Inbound Labor Fee", "", total_in_plts, "$4.00", f'${total_in_plts * 4:.2f}'],
        ["Pallet Outbound Labor Fee", "", total_out_plts, "$4.00", f'${total_out_plts * 4:.2f}'],
        ["Omar Labor cost", "", "0", "$0.25", "$0.00"]
    ]
    table = Table(data, colWidths=[130, 230, 40, 50, 55])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # 右对齐的 TOTAL 小计行
    right_align_style = ParagraphStyle(
        name='RightAlign',
        fontSize=14,
        textColor=colors.black,
        alignment=TA_RIGHT
    )

    # 添加右对齐的 TOTAL 段落
    elements.append(Paragraph(f'<b>TOTAL: ${total_price:.2f}</b>', right_align_style))
    elements.append(Spacer(1, 20))
    #endregion

    #region 汇款信息
    # 汇款信息标题部分，左右对齐
    left_title = add_section_header("Please remit all payments to:", bold, 160)[0]
    right_title = add_section_header("Bank information for payment:", bold, 160)[0]

    left_para = Paragraph(constants_address.labor_left_text, normal)
    right_para = Paragraph(constants_address.labor_right_text, normal)

    # 拼接标题 + 正文的表格（两行两列）
    info_table = Table(
        [
            [left_title, right_title],
            [left_para, right_para],
        ],
        colWidths=[4.0 * inch, 4.0 * inch],
        hAlign='LEFT',
    )

    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(info_table)
    #endregion

    # 构建 PDF
    doc.build(elements)

    return temp_path

# Template -- add title with underline
def add_section_header(title, style, width):
    """使用表格边框生成段落标题和下划线，左侧对齐。"""
    table = Table(
        [[Paragraph(f'<b>{title}</b>', style)]],  # 只有一行一列
        colWidths=[width],
        hAlign='LEFT'
    )
    table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # 在第一行下方画一条线
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return [table, Spacer(1, 6)]

# add received invoice
def add_ar_invoice(request):
    paidcustomer = InvoicePaidCustomer.objects.all()
    receivedcompany = Carrier.objects.all()
    user_permissions = get_user_permissions(request.user)  
    
    user_permissions = get_user_permissions(request.user)  
    return render(request, constants_view.template_add_ar_invoice,{'user_permissions': user_permissions,
    'paidcustomer':paidcustomer,
    'receivedcompany':receivedcompany,
    })

# add paidable invoice
def add_ap_invoice(request):
    vendor = InvoiceVendor.objects.all()
    receivedcompany = Carrier.objects.all()
    purposefor = InvoicePurposeFor.objects.all()
    user_permissions = get_user_permissions(request.user) 

    return render(request, constants_view.template_add_ap_invoice,{'user_permissions': user_permissions,
    'vendor':vendor,
    'purposefor':purposefor,
    'receivedcompany':receivedcompany,
    })

# edit paidable invoice
def edit_ap_invoice(request, invoice_id):

    try:
        if request.method == "GET":
            ap_record = InvoiceAPRecord.objects.get(invoice_id=invoice_id)
            vendor = InvoiceVendor.objects.all()
            receivedcompany = Carrier.objects.all()
            purposefor = InvoicePurposeFor.objects.all()
            user_permissions = get_user_permissions(request.user) 
                        
            return render(request, constants_view.template_edit_ap_invoice, {
                'record': ap_record,
                'vendor':vendor,
                'purposefor':purposefor,
                'receivedcompany':receivedcompany,
                'user_permissions': user_permissions,
            })
        elif request.method == "POST":
            try:
                ap_record = InvoiceAPRecord.objects.get(invoice_id=invoice_id)

                vendor = InvoiceVendor.objects.get(id=request.POST.get('vendor_name'))
                receivedcompany = Carrier.objects.get(id=request.POST.get('company_name'))
                purposefor = InvoicePurposeFor.objects.get(id=request.POST.get('purpose_for'))

                ap_record.vendor = vendor
                ap_record.company = receivedcompany
                ap_record.purposefor = purposefor
                ap_record.invoice_id = request.POST.get('invoice_id')
                ap_record.invoice_price = request.POST.get('invoice_price')
                ap_record.due_date = clean_date(request.POST.get('due_date'))
                ap_record.givetoboss_date = clean_date(request.POST.get('givetoboss_date'))
                ap_record.payment_date = clean_date(request.POST.get('paid_date'))
                ap_record.note = request.POST.get('note')
                # ap_record.ar_invoice_pdfname = request.POST.get('note') or None 

                # 处理PDF文件
                if 'invoice_pdf' in request.FILES:
                    uploaded_file = request.FILES['invoice_pdf']
                    ap_record.ar_invoice_pdfname = uploaded_file.name  # 保存文件名到模型字段（如果需要）

                    # 打印 PDF 文件名
                    print(f"Uploaded PDF file name: {uploaded_file.name}")

                    # 构造保存路径
                    order_dir = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_AP)
                    os.makedirs(order_dir, exist_ok=True)  # 确保目录存在
                    file_path = os.path.join(order_dir, uploaded_file.name)

                    # 保存文件
                    with open(file_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)

                ap_record.save()
                
                return redirect('invoice_ap')
            except Exception as e:
                messages.error(request, f'更新信息失败：{str(e)}')
                ap_record = InvoiceAPRecord.objects.get(invoice_id=invoice_id)
                vendor = InvoiceVendor.objects.all()
                receivedcompany = Carrier.objects.all()
                purposefor = InvoicePurposeFor.objects.all()
                user_permissions = get_user_permissions(request.user) 
                            
                return render(request, constants_view.template_edit_ap_invoice, {
                    'record': ap_record,
                    'vendor':vendor,
                    'purposefor':purposefor,
                    'receivedcompany':receivedcompany,
                    'user_permissions': user_permissions,
                })
        
        
    except InvoiceAPRecord.DoesNotExist:
        messages.error(request, '订单不存在')
        return redirect('invoice_ap')

# Template -- format the data
def clean_date(value):
    if value in ["", None]:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

# print Invoice
def print_original_ap_invoice(request, so_num):
    order = get_object_or_404(InvoiceAPRecord, invoice_id=so_num)

    if not order.ar_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_AP, order.ar_invoice_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{order.ar_invoice_pdfname}"'
        return response
