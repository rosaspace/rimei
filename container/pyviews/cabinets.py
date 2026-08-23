import os
import re
import math

from decimal import Decimal

from .utils.getPermission import get_user_permissions
from django.shortcuts import get_object_or_404, render, redirect
from django.core.files.storage import default_storage

from ..constants import constants_address, constants_view
from .utils.file_utils import get_media_path, ensure_dir_exists
from .utils.pdfgenerate import extract_text_from_pdf, converter_metal_invoice
from ..models import CabinetProductType

def cabinets_list(request):

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_cabinets_list, {
        'user_permissions': user_permissions,
        
        })

def cabinets_add(request):

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_cabinets_add, {
        'user_permissions': user_permissions,
        
        })

def add_cabinet_packing(request):

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_cabinets_add_packing, {
        'user_permissions': user_permissions,
        
        })

def upload_cabinetspdf(request):
    print("------upload_cabinetspdf--------\n")
    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf_file = request.FILES["pdf_file"]

        upload_dir = get_media_path(constants_address.UPDATE_DIR_cabinets, constants_address.ORDER_FOLDER)
        ensure_dir_exists(upload_dir)

        file_path = os.path.join(upload_dir, pdf_file.name)

        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk) 

        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        # print(extracted_text)
        parsed = parse_sales_order(extracted_text)        
        
        context = {
            "extracted_text": extracted_text,
            "order_no": parsed["order_no"],
            "po_no": parsed["po_no"],
            "items": parsed["items"],
            "total_amount": parsed["total_amount"],
            "total_pallet": parsed["total_pallet"],
            "total_pallet_ceiling": parsed["total_pallet_ceiling"],
        }  
        
        return render(request, constants_view.template_cabinets_add,context)

    return render(request, constants_view.template_cabinets_list)

def upload_cabinetspdf_packing(request):
    print("------upload_cabinetspdf--------\n")
    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf_file = request.FILES["pdf_file"]

        upload_dir = get_media_path(constants_address.UPDATE_DIR_cabinets, constants_address.ORDER_FOLDER)
        ensure_dir_exists(upload_dir)

        file_path = os.path.join(upload_dir, pdf_file.name)

        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk) 

        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        # print(extracted_text)
        parsed = parse_packing_list(extracted_text)        
        
        context = {
            "extracted_text": extracted_text,
            "order_no": parsed["order_no"],
            "po_no": parsed["po_no"],
            "items": parsed["items"],
            "total_amount": parsed["total_amount"],
            "total_pallet": parsed["total_pallet"],
            "total_pallet_ceiling": parsed["total_pallet_ceiling"],
        }  
        
        return render(request, constants_view.template_cabinets_add_packing,context)

    return render(request, constants_view.template_cabinets_add_packing)


def parse_sales_order(raw_text):
    data = {}    

    # 1️⃣ 提取 Order # 和 PO No
    order_match = re.search(r'Order #\s+P\.O\. No\.\s+(\S+)\s+(\S+)', raw_text)
    if order_match:
        data["order_no"] = order_match.group(1)
        data["po_no"] = order_match.group(2)

    # 2️⃣ 提取所有 SKU 行
    pattern = re.compile(
        r'\d+\s+((?:SW|GR|NB|SE|SDW|AG|TC|SAO|SWO|LWSW)-[A-Z0-9\-\(\)]+).*?\s(\d+)\s+\$(\d+\.\d{2})\s+\$',
        re.DOTALL
    )

    items = []
    total_amount = 0   # ⭐新增
    total_pallet = Decimal("0")
    for match in pattern.findall(raw_text):
        sku, qty, price = match
        qty = int(qty)
        price = float(price)

        sku_sim = sku.split("-", 1)[1] if "-" in sku else sku

        line_total = qty * price      # ⭐每行金额
        total_amount += line_total    # ⭐累加总金额

        # 查询托盘占用
        pallet_usage = Decimal("0")
        product_type = CabinetProductType.objects.filter(
            name=sku_sim
        ).first()

        if product_type:
            pallet_usage = product_type.pallet_usage

        each_pallet = pallet_usage
        line_pallet = qty * pallet_usage
        total_pallet += line_pallet

        items.append({
            "sku": sku,
            "sku_sim": sku_sim,
            "qty": qty,
            "price": price,
            "line_total": line_total,   # 可选显示

            # 新增
            "line_pallet": float(line_pallet),
            "each_pallet": float(each_pallet),
        })

    data["items"] = items
    data["total_amount"] = round(total_amount, 2)
    # 总托盘
    data["total_pallet"] = float(total_pallet)

    # 向上取整
    data["total_pallet_ceiling"] = math.ceil(total_pallet)

    return data

def parse_packing_list(raw_text):
    data = {}

    # 1️⃣ Order No
    order_match = re.search(
        r'Picking Ticket\s+(SOTX\d+)',
        raw_text
    )
    if order_match:
        data["order_no"] = order_match.group(1)

    # 2️⃣ PO No（保留完整 -0R）
    po_match = re.search(
        r'PO#.*?([A-Z0-9\-]+)\s+\d{1,2}/\d{1,2}/\d{4}',
        raw_text,
        re.DOTALL
    )
    if po_match:
        data["po_no"] = po_match.group(1)

    # 3️⃣ 精确截取 ITEM 区域（关键修复）
    item_section_match = re.search(
        r'Committed\s+.*?SKU.*?Committed\s+(.*?)\n\s*(Approved by:|$)',
        raw_text,
        re.DOTALL
    )

    items = []
    total_amount = 0
    total_pallet = Decimal("0")
    item_text = ""

    m = re.search(r'Committed\s+(.*)', raw_text, re.DOTALL)

    if not m:
        data["items"] = []
        data["total_pallet"] = 0
        data["total_pallet_ceiling"] = 0
        return data

    # item_text = m.group(1)
    # pattern = re.compile(
    #     r'(\d+)\s+([A-Z0-9]+-[A-Z0-9\-]+)'
    # )
    # item_text = raw_text.split("Committed", 1)[1]
    # pattern = re.compile(
    #     r'(\d+)\s+(.*?)\s+\S+\s+(\d+)'
    # )

    m = re.search(r'Committed\s+(.*)', raw_text, re.DOTALL)

    if not m:
        return data

    item_text = m.group(1)
    pattern = re.compile(
        r'(\d+)\s+(.+?)\s+(?:[A-Za-z0-9.\- ]+)\s+(\d+)(?=\s+\d+\s+|$)'
    )

    for qty_str, sku, committed_qty in pattern.findall(item_text):

        qty = int(qty_str)

        # sku_sim = sku.split("-", 1)[1] if "-" in sku else sku
        sku = sku.strip()
        if sku.startswith("SW-"):
            sku_sim = sku[3:]
        elif sku.startswith("LWSE-"):
            sku_sim = sku[5:]
        elif sku.startswith("LWSW-"):
            sku_sim = sku[5:]
        else:
            sku_sim = sku

        pallet_usage = Decimal("0")
        product_type = CabinetProductType.objects.filter(
            name=sku_sim
        ).first()

        if product_type:
            pallet_usage = product_type.pallet_usage

        line_pallet = qty * pallet_usage
        total_pallet += line_pallet

        items.append({
            "sku": sku,
            "sku_sim": sku_sim,
            "qty": qty,
            "each_pallet": float(pallet_usage),
            "line_pallet": float(line_pallet),
        })

    data["items"] = items
    data["total_amount"] = round(total_amount, 2)
    data["total_pallet"] = float(total_pallet)
    data["total_pallet_ceiling"] = math.ceil(total_pallet)

    return data
