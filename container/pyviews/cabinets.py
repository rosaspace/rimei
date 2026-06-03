import os
import re

from .utils.getPermission import get_user_permissions
from django.shortcuts import get_object_or_404, render, redirect
from django.core.files.storage import default_storage

from ..constants import constants_address, constants_view
from .utils.file_utils import get_media_path, ensure_dir_exists
from .utils.pdfgenerate import extract_text_from_pdf, converter_metal_invoice

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
        }  
        
        return render(request, constants_view.template_cabinets_add,context)

    return render(request, constants_view.template_cabinets_list)


def parse_sales_order(raw_text):
    data = {}    

    # 1️⃣ 提取 Order # 和 PO No
    order_match = re.search(r'Order #\s+P\.O\. No\.\s+(\S+)\s+(\S+)', raw_text)
    if order_match:
        data["order_no"] = order_match.group(1)
        data["po_no"] = order_match.group(2)

    # 2️⃣ 提取所有 SKU 行
    pattern = re.compile(
        r'\d+\s+(SW-[A-Z0-9\-\(\)]+).*?\s(\d+)\s+\$(\d+\.\d{2})\s+\$',
        re.DOTALL
    )

    items = []
    total_amount = 0   # ⭐新增
    for match in pattern.findall(raw_text):
        sku, qty, price = match
        qty = int(qty)
        price = float(price)

        line_total = qty * price      # ⭐每行金额
        total_amount += line_total    # ⭐累加总金额

        items.append({
            "sku": sku,
            "qty": qty,
            "price": price,
            "line_total": line_total   # 可选显示
        })

    data["items"] = items
    data["total_amount"] = round(total_amount, 2)  # ⭐最终总价
    return data
