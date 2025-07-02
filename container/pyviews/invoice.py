from django.shortcuts import render, redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.conf import settings

from reportlab.platypus  import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors

import os
import re
import tempfile
import fitz  # PyMuPDF 解析 PDF

from datetime import datetime
from decimal import Decimal

from ..models import Container
from .pdfextract import extract_invoice_data, extract_customer_invoice_data
from ..constants import constants_address, constants_view
from .pdfgenerate import extract_text_from_pdf, converter_customer_invoice

# Invoice
def print_original_do(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.container_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_container, constants_address.ORIGINAL_DO_FOUDER, container.container_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{container.container_pdfname}"'
        return response

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
    
def print_converted_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.customer_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.ORDER_CONVERTED_FOLDER, container.customer_invoice_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{container.customer_invoice_pdfname}"'
        return response

def print_customer_invoice(request, container_id, isEmptyContainerRelocate=0):
    print("----------print_customer_invoice----------")
    print("isEmptyContainerRelocate: ", isEmptyContainerRelocate)
    container = get_object_or_404(Container, container_id=container_id)

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
            if desc_line == "INTERM1":
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

                    print(f"✔ {desc_line} | Units: {units} | Rate: {rate} | Amount: {amount}")
                    i += 4
                except (ValueError, IndexError):
                    i += 1
            else:
                i += 1

    print(f"✅ 共抓取 {len(amount_items)} 条价格记录，总金额: {total_original:.2f}")
    original_doc.close()

    # 构造新的文件路径
    new_filename = f"{container.container_id}.pdf"
    output_dir = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.CUSTOMER_INVOICE_FOLDER)
    output_file_path = os.path.join(output_dir, new_filename)  # ✅ 拼接完整路径
    converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate)
    
    # 打开并读取PDF文件
    with open(output_file_path , 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{new_filename}"'
        return response

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
    elements.append(Paragraph(f"Payment Statement - {datetime.now().strftime('%m/%d/%Y')}", large_title_style))
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

def edit_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    invoice_file = request.FILES.get('invoice_file')

    if not invoice_file:
        return JsonResponse({"error": "No file uploaded."}, status=400)

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
        })
    
    except Exception as e:
        return JsonResponse({"error": f"Failed to process invoice: {e}"}, status=500)

def edit_customer_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    invoice_file = request.FILES.get('invoice_file')

    if not invoice_file:
        return JsonResponse({"error": "No file uploaded."}, status=400)

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

def edit_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if request.method == "GET":
        print("date: ",container.customer_payment_date, type(container.customer_payment_date))
        return render(request, constants_view.template_edit_invoice, {
            'container': container,
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
        })

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

def export_pallet_invoice(request):
    # 获取请求中的月份和年份
    month = request.GET.get('month')
    year = request.GET.get('year')
    print(month,year)
    
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
    elements.append(Paragraph(f"Payment Invoice Report", large_title_style))
    elements.append(Spacer(1, 12))

    # 添加生成日期和月份年份信息
    elements.append(Paragraph(f"Generated Date: {datetime.now().strftime('%B %d, %Y')}", styles["Normal"]))
    elements.append(Paragraph(f"Month: {month} / Year: {year}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # 示例正文内容
    elements.append(Paragraph("This is a sample pallet invoice PDF file generated by the system.", styles["Normal"]))

    # 构建 PDF
    doc.build(elements)

    # ✅ 读取 PDF 文件并返回
    new_filename = "invoice_month_warehouse.pdf"
    with open(temp_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{new_filename}"'

    # 删除临时文件
    os.remove(temp_path)
    return response