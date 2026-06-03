import os
import re
import fitz  # PyMuPDF 解析 PDF

from django.contrib.auth.decorators import login_required
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings

from decimal import Decimal

from ..constants import constants_address, constants_view
from ..models import (
    Container, RMProduct, InvoiceCustomer, LogisticsCompany,
    InvoicePaidCustomer, Carrier, InvoiceVendor, InvoicePurposeFor,
    InvoiceAPRecord, InvoiceARRecord
)
from .invoice_statement import filter_containers
from .utils.getPermission import get_user_permissions
from .utils.pdfgenerate import extract_text_from_pdf, converter_customer_invoice
from .utils.file_utils import get_media_path, serve_pdf_file, ensure_dir_exists, save_uploaded_file
from .utils.invoice_utils import extract_invoice_data, extract_customer_invoice_data
from .utils.date_utils import parse_date

# container invoice list
@login_required(login_url='/login/')
def invoice_view(request):
    containers = Container.objects.select_related(
        'customer', 'logistics'
    ).all().exclude(
        logistics=2
    ).order_by('-delivery_date')

    containerss = filter_containers(request).exclude(
        logistics=2
    ).order_by('-delivery_date')

    
    
    customers = InvoiceCustomer.objects.all().order_by('name')
    logistics_list = LogisticsCompany.objects.all().order_by('name')
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_invoice, {
        'containers': containerss,'user_permissions': user_permissions,
        'customers': customers,
        'logistics_list': logistics_list,
        })

# print original delivery order
def print_original_do(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    if not container.container_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_container,
        constants_address.ORIGINAL_DO_FOUDER,
        container.container_pdfname
    )
    return serve_pdf_file(pdf_path, container.container_pdfname)

# print advance invoice
def print_original_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.INVOICE_FOLDER,
        container.invoice_pdfname
    )
    return serve_pdf_file(pdf_path, container.invoice_pdfname)

# print invoice to omar
def print_converted_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.customer_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    invoice_dir = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.ORDER_CONVERTED_FOLDER
    )
    ensure_dir_exists(invoice_dir)

    # 构建完整 PDF 文件路径
    pdf_path = os.path.join(invoice_dir, container.customer_invoice_pdfname)    
    return serve_pdf_file(pdf_path, container.customer_invoice_pdfname)

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
    if container.logistics and container.logistics.id in [3, 4, 5]:
        print("✅ logistics.id == 3, using fixed invoice pricing")

        # 计算天数（包含 delivery_date 和 empty_date）
        delivery_date = container.delivery_date
        empty_date = container.empty_date

        days = (empty_date - delivery_date).days + 1  # ✅ 两头都包括
        rate = 40.00
        chassis_total = days * rate
        liftfee = 120

        amount_items = [
            ("Drayage (FSC all included)", 1, 450.00, 450.00),
            ("Chassis", days, rate, chassis_total),
            # ("Flip", 1, liftfee, liftfee*1)
        ]
        total_original = 560.00

    # ============================
    # ✅ ORIGINAL LOGIC (unchanged)
    # ============================
    else:

        if not container.invoice_pdfname:
            return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

        # 构建PDF文件路径
        input_pdf_path = get_media_path(
            constants_address.UPLOAD_DIR_invoice,
            constants_address.INVOICE_FOLDER,
            container.invoice_pdfname
        )

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
    output_dir = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.CUSTOMER_INVOICE_FOLDER
    )
    output_file_path = os.path.join(output_dir, new_filename)
    converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate, isClassisSplit, isPrepull)
    # 打开并读取PDF文件
    return serve_pdf_file(output_file_path, new_filename)

def print_clearence_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    print("----------print_clearence_invoice----------")
    print("container: ", container)
    print("container.clearance_pdfname: ", container.clearance_pdfname)
    if not container.clearance_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_container,
        constants_address.CLEARANCE_INVOICE_FOLDER,
        container.clearance_pdfname,
        # container.clearance_pdfname
    )
    print("pdf_path: ", pdf_path)
    return serve_pdf_file(pdf_path, container.clearance_pdfname)

# upload advance invoice
def edit_invoice_file(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    invoice_file = request.FILES.get('invoice_file')

    if not invoice_file:
        return HttpResponse("No file uploaded.", status=404)

    try:
        # 保存文件
        container.invoice_pdfname = invoice_file.name
        file_path = get_media_path(
            constants_address.UPLOAD_DIR_invoice,
            constants_address.INVOICE_FOLDER
        )
        save_uploaded_file(invoice_file, file_path)

        # 解析发票内容
        new_file_path = os.path.join(file_path, invoice_file.name)
        text = extract_text_from_pdf(new_file_path)
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

    # ✅ 日期安全处理
    invoice_date = invoice_date or None
    invoice_duedate = invoice_duedate or None

    if invoice_date:
        invoice_date = parse_date(invoice_date)

    if invoice_duedate:
        invoice_duedate = parse_date(invoice_duedate)

    if not invoice_file:
        return HttpResponse("No file uploaded.", status=404)

    try:
        # 保存文件
        container.invoice_pdfname = invoice_file.name
        full_path = get_media_path(
            constants_address.UPLOAD_DIR_invoice,
            constants_address.INVOICE_FOLDER,
        )
        save_uploaded_file(invoice_file, full_path, invoice_file.name)

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
        full_path = get_media_path(
            constants_address.UPLOAD_DIR_invoice,
            constants_address.ORDER_CONVERTED_FOLDER
        )
        save_uploaded_file(invoice_file, full_path, invoice_file.name)

        # 解析 PDF 内容
        new_file_path = os.path.join(full_path, invoice_file.name)
        text = extract_text_from_pdf(new_file_path)
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

# update omar invoice price
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

