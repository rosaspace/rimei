import os

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages

from ..models import (
    OfficeSupplyItem,
    OfficeSupplyPurpose,
    OfficeSupplyPlatform,
    OfficeSupplyRecord
)
from ..constants import constants_view
from ..constants import constants_address
from .getPermission import get_user_permissions


def office_supply_add(request):
    if request.method == "POST":
        OfficeSupplyRecord.objects.create(
            supply_item_id=request.POST.get("supply_item"),
            purpose_id=request.POST.get("purpose"),
            platform_id=request.POST.get("platform"),
            quantity=request.POST.get("quantity"),
            unit_price=request.POST.get("price"),
            purchase_date=request.POST.get("purchase_date"),
            delivered_date=request.POST.get("delivered_date") or None,
            description=request.POST.get("description"),
        )
        return redirect("office_supply_list")

    context = {
        "items": OfficeSupplyItem.objects.all(),
        "purposes": OfficeSupplyPurpose.objects.all(),
        "platforms": OfficeSupplyPlatform.objects.all(),
    }
    return render(request, constants_view.template_officesupply_add, context)

def office_supply_edit(request, pk):
    record = get_object_or_404(OfficeSupplyRecord, pk=pk)

    if request.method == "POST":
        record.supply_item_id = request.POST.get("supply_item")
        record.purpose_id = request.POST.get("purpose")
        record.platform_id = request.POST.get("platform")
        record.quantity = request.POST.get("quantity")
        record.unit_price = request.POST.get("price")
        record.purchase_date = request.POST.get("purchase_date")
        record.delivered_date = request.POST.get("delivered_date") or None
        record.description = request.POST.get("description")

        # pdf
        if 'storage_pdf' in request.FILES:
            uploaded_file = request.FILES.get("storage_pdf")        
            record.storage_pdf = uploaded_file.name

            print(f"Uploaded PDF file name: {uploaded_file.name}")

            save_dir = os.path.join(
                settings.MEDIA_ROOT,
                constants_address.UPLOAD_DIR_invoice,
                constants_address.INVOICE_OFFICE_SUPPLY,
            )
            os.makedirs(save_dir, exist_ok=True)

            file_path = os.path.join(save_dir, uploaded_file.name)
            with open(file_path, "wb+") as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)

        record.save()

        return redirect("office_supply_list")

    user_permissions = get_user_permissions(request.user)
    context = {
        "record": record,
        "items": OfficeSupplyItem.objects.all(),
        "purposes": OfficeSupplyPurpose.objects.all(),
        "platforms": OfficeSupplyPlatform.objects.all(),
        'user_permissions': user_permissions,
    }
    return render(request, constants_view.template_officesupply_edit, context)

def office_supply_list(request):
    records = (
        OfficeSupplyRecord.objects
        .select_related("supply_item", "purpose", "platform")
        .order_by("-created_at")
    ).order_by('-delivered_date')

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_officesupply_list, {
        "records": records,
        'user_permissions': user_permissions,
    })

# print Invoice
def print_original_officesupply_invoice(request, so_num):
    order = get_object_or_404(OfficeSupplyRecord, pk=so_num)

    if not order.storage_pdf:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_invoice, constants_address.INVOICE_OFFICE_SUPPLY, order.storage_pdf)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{order.storage_pdf}"'
        return response

def delete_officesupply_invoice(request, so_num):
    office_supply_record = get_object_or_404(OfficeSupplyRecord, pk=so_num)
    office_supply_record.delete()
    messages.success(request, 'Office Supply Invoice deleted successfully')
    return redirect('office_supply_list')