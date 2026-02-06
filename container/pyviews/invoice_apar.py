import os

from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from ..constants import constants_address, constants_view
from ..models import InvoicePaidCustomer, Carrier, InvoiceVendor, InvoicePurposeFor, InvoiceAPRecord, InvoiceARRecord
from ..models import InvoicePurposeFor

from .utils.getPermission import get_user_permissions
from .utils.date_utils import clean_date, parse_date
from .utils.file_utils import get_media_path, ensure_dir_exists, save_uploaded_file, serve_pdf_file

# AP list
def invoice_ap_view(request):

    apRecord = InvoiceAPRecord.objects.select_related(
        'vendor', 'company', 'purposefor'
    ).all().order_by('-due_date')

    vendor_id = request.GET.get('vendor')
    company_id = request.GET.get('company')
    purpose_id = request.GET.get('purposefor')

    if vendor_id:
        apRecord = apRecord.filter(vendor_id=vendor_id)

    if company_id:
        apRecord = apRecord.filter(company_id=company_id)

    if purpose_id:
        apRecord = apRecord.filter(purposefor_id=purpose_id)

    vendors = InvoiceVendor.objects.all()
    companies = Carrier.objects.all()
    purposefor = InvoicePurposeFor.objects.all()
    user_permissions = get_user_permissions(request.user)    

    return render(request, constants_view.template_ap_invoice, {
        'user_permissions': user_permissions,
        'apRecord': apRecord,
        "vendors": vendors,
        "companies": companies,
        "purposefor": purposefor,
    })

# AR list
def invoice_ar_view(request):
    
    arRecord = InvoiceARRecord.objects.select_related(
        'customer', 'company'
    ).all().order_by('-due_date')

    customer_id = request.GET.get('customer')
    company_id = request.GET.get('company')

    if customer_id:
        arRecord = arRecord.filter(customer_id=customer_id)

    if company_id:
        arRecord = arRecord.filter(company_id=company_id)

    customers = InvoicePaidCustomer.objects.all().order_by('name')
    companies = Carrier.objects.all().order_by('shortname')
    user_permissions = get_user_permissions(request.user)  

    return render(request, constants_view.template_ar_invoice, {
        'user_permissions': user_permissions,
        'arRecord': arRecord,
        'customers': customers,
        'companies': companies,
    })

# add received invoice
def add_ar_invoice(request):
    paidcustomer = InvoicePaidCustomer.objects.all()
    receivedcompany = Carrier.objects.all()
    user_permissions = get_user_permissions(request.user)  
    
    if request.method == "POST":
        try:
            # 先获取 POST 值
            invoice_id = request.POST.get("invoice_id") or ""
            invoice_price = request.POST.get("invoice_price") or "0"
            customer_id = request.POST.get("customer_name")
            customer_id = int(customer_id) if customer_id else None
            company_id = request.POST.get("company_name")
            company_id = int(company_id) if company_id else None

            # 日期字段，空字符串转换为 None
            due_date = parse_date(request.POST.get("due_date"))
            givetoboss_date = parse_date(request.POST.get("givetoboss_date"))
            payment_date = parse_date(request.POST.get("payment_date"))
            note = request.POST.get("note") or ""

            try:
                invoice_price = Decimal(invoice_price)
            except Exception:
                invoice_price = Decimal("0")
            
            # 创建记录
            # 先实例化，不直接 create
            ar_invoice = InvoiceARRecord(
                customer_id=customer_id,
                invoice_id=invoice_id,
                invoice_price=invoice_price,
                company_id=company_id,
                due_date=due_date,
                givetoboss_date=givetoboss_date,
                payment_date=payment_date,
                note=note
            )
            
            pdf_file = request.FILES.get("invoice_pdf")
            if pdf_file:
                ar_invoice.ar_invoice_pdfname = pdf_file.name

                save_dir = get_media_path(
                    constants_address.UPLOAD_DIR_invoice,
                    constants_address.INVOICE_AR
                )
                ensure_dir_exists(save_dir)

                file_path = os.path.join(save_dir, pdf_file.name)
                save_uploaded_file(pdf_file, file_path, pdf_file.name)

            # 校验 + 保存
            ar_invoice.full_clean()  # 🔑 先校验字段
            ar_invoice.save()

            messages.success(request, "AR Invoice added successfully")
            return redirect("invoice_ar")

        except Exception as e:
            messages.error(request, f"Add AR Invoice failed: {e}")
            return render(request, constants_view.template_add_ar_invoice, {
                'user_permissions': user_permissions,
                'paidcustomer': paidcustomer,
                'receivedcompany': receivedcompany,
                'form_data': request.POST
            })

    return render(request, constants_view.template_add_ar_invoice, {
        'user_permissions': user_permissions,
        'paidcustomer': paidcustomer,
        'receivedcompany': receivedcompany,
        'form_data': {}  # 空表单
    })

# edit receivable invoice
def edit_ar_invoice(request, id):
    ar_invoice = get_object_or_404(InvoiceARRecord, id=id)
    paidcustomer = InvoicePaidCustomer.objects.all()
    receivedcompany = Carrier.objects.all()
    user_permissions = get_user_permissions(request.user)

    if request.method == "POST":
        try:
            # ===== 外键 =====
            ar_invoice.customer = InvoicePaidCustomer.objects.get(id=request.POST.get("customer_name"))
            ar_invoice.company = Carrier.objects.get(id=request.POST.get("company_name"))

            # ===== 基本字段 =====
            ar_invoice.invoice_id = request.POST.get("invoice_id")
            ar_invoice.invoice_price = Decimal(request.POST.get("invoice_price") or "0")            

            # ===== 日期字段 =====
            ar_invoice.due_date = parse_date(request.POST.get("due_date"))
            ar_invoice.givetoboss_date = parse_date(request.POST.get("givetoboss_date"))
            ar_invoice.payment_date = parse_date(request.POST.get("payment_date"))

            ar_invoice.note = request.POST.get("note") or ""

            # ===== PDF 文件处理（和 AP 完全一致）=====
            if "invoice_pdf" in request.FILES:
                uploaded_file = request.FILES["invoice_pdf"]
                ar_invoice.ar_invoice_pdfname = uploaded_file.name

                save_dir = get_media_path(
                    constants_address.UPLOAD_DIR_invoice,
                    constants_address.INVOICE_AR
                )
                ensure_dir_exists(save_dir)

                file_path = os.path.join(save_dir, uploaded_file.name)
                save_uploaded_file(uploaded_file, file_path, uploaded_file.name)

            ar_invoice.full_clean()
            ar_invoice.save()

            messages.success(request, "AR Invoice updated successfully")
            return redirect("invoice_ar")

        except Exception as e:
            messages.error(request, f"Update failed: {e}")

    return render(
        request,
        constants_view.template_edit_ar_invoice,
        {
            "ar_invoice": ar_invoice,
            "paidcustomer": paidcustomer,
            "receivedcompany": receivedcompany,
            "user_permissions": user_permissions,
        }
    )

# delete received invoice
def delete_ar_invoice(request, invoice_id):
    ar_record = InvoiceARRecord.objects.get(invoice_id=invoice_id)
    ar_record.delete()
    messages.success(request, "AR Invoice deleted successfully")
    return redirect("invoice_ar")

# print Invoice
def print_original_ar_invoice(request, so_num):
    order = get_object_or_404(InvoiceARRecord, id=so_num)

    if not order.ar_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.INVOICE_AR,
        order.ar_invoice_pdfname
    )
    return serve_pdf_file(pdf_path, order.ar_invoice_pdfname)

# add paidable invoice
def add_ap_invoice(request):
    vendor = InvoiceVendor.objects.all()
    receivedcompany = Carrier.objects.all()
    purposefor = InvoicePurposeFor.objects.all()
    user_permissions = get_user_permissions(request.user) 

    if request.method == "POST":
        try:
            print("---------------POST add_ap_invoice-------------------")
            vendor_id = request.POST.get("vendor")
            invoice_id = request.POST.get("invoice_id")
            invoice_price = request.POST.get("invoice_price")
            company_id = request.POST.get("company")
            due_date = request.POST.get("due_date")
            givetoboss_date = request.POST.get("givetoboss_date")
            payment_date = request.POST.get("payment_date")
            purposefor_id = request.POST.get("purposefor")
            note = request.POST.get("note")

            pdf_file = request.FILES.get("invoice_pdf")

            ap_invoice = InvoiceAPRecord.objects.create(
                vendor_id=vendor_id,
                invoice_id=invoice_id,
                invoice_price=invoice_price,
                company_id=company_id,
                due_date=due_date if due_date else None,
                givetoboss_date=givetoboss_date if givetoboss_date else None,
                payment_date=payment_date if payment_date else None,
                purposefor_id=purposefor_id,
                note=note or ""
            )
            print("pdf_file:", pdf_file)

            # ⚠️ 保留 CharField：只存文件名
            if pdf_file:
                ap_invoice.ar_invoice_pdfname = pdf_file.name

                save_dir = get_media_path(
                    constants_address.UPLOAD_DIR_invoice,
                    constants_address.INVOICE_AP
                )
                ensure_dir_exists(save_dir)

                file_path = os.path.join(save_dir, pdf_file.name)
                save_uploaded_file(pdf_file, file_path, pdf_file.name)

            # 校验 + 保存
            ap_invoice.full_clean()  # 🔑 先校验字段
            ap_invoice.save()

            messages.success(request, "AP Invoice added successfully")
            return redirect('invoice_ap')

        except Exception as e:
            messages.error(request, f"Add AP Invoice failed: {e}")

    # GET 或 POST 失败都走这里
    return render(
        request,
        constants_view.template_add_ap_invoice,
        {
            'user_permissions': user_permissions,
            'vendors': vendor,
            'companies': receivedcompany,
            'purposefors': purposefor,
        }
    )

# edit paidable invoice
def edit_ap_invoice(request, invoice_id):

    ap_record = InvoiceAPRecord.objects.get(invoice_id=invoice_id)
    vendor = InvoiceVendor.objects.all()
    receivedcompany = Carrier.objects.all()
    purposefor = InvoicePurposeFor.objects.all()
    user_permissions = get_user_permissions(request.user)                         
            
    if request.method == "POST":
        try:
            # ===== 外键 =====
            ap_record.vendor = InvoiceVendor.objects.get(id=request.POST.get('vendor_name'))
            ap_record.company = Carrier.objects.get(id=request.POST.get('company_name'))
            ap_record.purposefor = InvoicePurposeFor.objects.get(id=request.POST.get('purpose_for'))

            # ===== 基本字段 =====
            ap_record.invoice_id = request.POST.get('invoice_id')
            ap_record.invoice_price = request.POST.get('invoice_price')

             # ===== 日期 =====
            ap_record.due_date = clean_date(request.POST.get('due_date'))
            ap_record.givetoboss_date = clean_date(request.POST.get('givetoboss_date'))
            ap_record.payment_date = clean_date(request.POST.get('paid_date'))
            ap_record.note = request.POST.get('note')

            # 处理PDF文件
            if 'invoice_pdf' in request.FILES:
                uploaded_file = request.FILES['invoice_pdf']
                ap_record.ar_invoice_pdfname = uploaded_file.name  # 保存文件名到模型字段（如果需要）

                # 打印 PDF 文件名
                print(f"Uploaded PDF file name: {uploaded_file.name}")

                # 构造保存路径
                order_dir = get_media_path(
                    constants_address.UPLOAD_DIR_invoice,
                    constants_address.INVOICE_AP
                )
                ensure_dir_exists(order_dir)              

                # 保存文件
                file_path = os.path.join(order_dir, uploaded_file.name)
                save_uploaded_file(uploaded_file, file_path, uploaded_file.name)

            ap_record.full_clean()
            ap_record.save()
            
            messages.success(request, "AP Invoice updated successfully")
            return redirect('invoice_ap')
        except Exception as e:
            messages.error(request, f"更新信息失败：{str(e)}")
                        
    return render(request, constants_view.template_edit_ap_invoice, {
        'record': ap_record,
        'vendor': vendor,
        'purposefor': purposefor,
        'receivedcompany': receivedcompany,
        'user_permissions': user_permissions,
    })

# delete payable invoice
def delete_ap_invoice(request, invoice_id):
    ap_record = InvoiceAPRecord.objects.get(id=invoice_id)
    ap_record.delete()
    messages.success(request, 'AP Invoice deleted successfully')
    return redirect('invoice_ap')

# print Invoice
def print_original_ap_invoice(request, so_num):
    order = get_object_or_404(InvoiceAPRecord, id=so_num)
    print("AP id:", so_num)

    if not order.ar_invoice_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.INVOICE_AP,
        order.ar_invoice_pdfname
    )
    return serve_pdf_file(pdf_path, order.ar_invoice_pdfname)

