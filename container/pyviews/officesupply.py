import os

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from ..constants import constants_address, constants_view
from ..models import (
    OfficeSupplyItem,
    OfficeSupplyPurpose,
    OfficeSupplyPlatform,
    OfficeSupplyRecord
)

from .utils.getPermission import get_user_permissions
from .utils.file_utils import get_media_path, ensure_dir_exists, save_uploaded_file, serve_pdf_file

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

            save_dir = get_media_path(
                constants_address.UPLOAD_DIR_invoice,
                constants_address.INVOICE_OFFICE_SUPPLY
            )
            ensure_dir_exists(save_dir)
            file_path = os.path.join(save_dir, uploaded_file.name)
            save_uploaded_file(uploaded_file, file_path, uploaded_file.name)

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

    supply_item_id = request.GET.get('supply_item')
    purpose_id = request.GET.get('purpose')
    platform_id = request.GET.get('platform')

    if supply_item_id:
        records = records.filter(supply_item_id=supply_item_id)

    if purpose_id:
        records = records.filter(purpose_id=purpose_id)

    if platform_id:
        records = records.filter(platform_id=platform_id)

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_officesupply_list, {
        "records": records,
        'user_permissions': user_permissions,
        'supply_items': OfficeSupplyItem.objects.all(),
        'purposes': OfficeSupplyPurpose.objects.all(),
        'platforms': OfficeSupplyPlatform.objects.all(),
    })

# print Invoice
def print_original_officesupply_invoice(request, so_num):
    order = get_object_or_404(OfficeSupplyRecord, pk=so_num)

    if not order.storage_pdf:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_invoice,
        constants_address.INVOICE_OFFICE_SUPPLY,
        order.storage_pdf
    )
    return serve_pdf_file(pdf_path, order.storage_pdf)

def delete_officesupply_invoice(request, so_num):
    office_supply_record = get_object_or_404(OfficeSupplyRecord, pk=so_num)
    office_supply_record.delete()
    messages.success(request, 'Office Supply Invoice deleted successfully')
    return redirect('office_supply_list')