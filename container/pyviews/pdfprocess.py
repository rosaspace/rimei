from django.conf import settings
import os
from django.http import JsonResponse
from django.core.files.storage import default_storage
import fitz  # PyMuPDF 解析 PDF
from django.shortcuts import render
import re
from ..models import RMCustomer
from datetime import datetime,date

UPLOAD_DIR = "uploads/"
UPLOAD_DIR_order = "orders/"

def upload_orderpdf(request):
    print("------upload_orderpdf--------\n")
    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf_file = request.FILES["pdf_file"]

        upload_dir = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order)  # 确保路径在 MEDIA_ROOT 目录下

        # ✅ 如果目录不存在，则创建
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(UPLOAD_DIR_order, pdf_file.name)

        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)

        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        # print(extracted_text)
        so_no, order_date, po_no, pickup_date, bill_to, ship_to, items, quantities = extract_order_info(extracted_text)
        orderitems = extract_items_from_pdf(extracted_text)

        # Convert to a datetime object
        if isinstance(order_date, str):
            order_date = datetime.strptime(order_date, "%Y-%m-%d").date()  # Convert to date
        elif isinstance(order_date, datetime):
            order_date = order_date.date()  # Convert datetime to date
        elif not isinstance(order_date, date):
            order_date = date.today()  # Default fallback if somehow not a date
        if isinstance(pickup_date, str):
            pickup_date = datetime.strptime(pickup_date, "%Y-%m-%d").date()  # Convert to date
        elif isinstance(pickup_date, datetime):
            pickup_date = pickup_date.date()  # Convert datetime to date
        elif not isinstance(pickup_date, date):
            pickup_date = date.today()  # Default fallback if somehow not a date

        context = {
            "so_no": so_no,
            "order_date": order_date,
            "po_no": po_no,
            "pickup_date":pickup_date,
            "bill_to":bill_to,
            "ship_to":ship_to,
            "items":items,
            "quantities":quantities,
            "orderitems":orderitems,
            'customers': RMCustomer.objects.all(),
        }        
        
        return render(request, 'container/rmorder/add_order.html',context)

    return JsonResponse({"error": "Invalid request"}, status=400)

# 处理上传
def upload_pdf(request):
    if request.method == "POST" and request.FILES.get("pdf_file"):

        pdf_file = request.FILES["pdf_file"]

        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")  # 确保路径在 MEDIA_ROOT 目录下

        # ✅ 如果目录不存在，则创建
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(UPLOAD_DIR, pdf_file.name)

        # 保存文件
        with default_storage.open(file_path, "wb+") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)

        # 解析 PDF
        extracted_text = extract_text_from_pdf(file_path)
        
        return JsonResponse({
            "message": "文件上传并解析成功",
            "file_path": file_path,
            "content": extracted_text[:500]  # 只返回部分文本，防止太长
        })

    return JsonResponse({"error": "Invalid request"}, status=400)

# PDF 解析函数
def extract_text_from_pdf(pdf_path):
    """ 解析 PDF 并提取文本 """
    full_path = os.path.join(settings.MEDIA_ROOT, pdf_path)  # 获取完整路径

    # ✅ 检查文件是否存在
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"PDF 文件未找到: {full_path}")
    print("hello: ",  full_path)

    doc = fitz.open(full_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()
    return text.strip()

# 提取订单信息
def extract_order_info(text):
    so_no = None
    order_date = None
    po_no = None
    pickup_date = None
    bill_to = None
    ship_to = None

    items = []
    quantities = []
    
    # 标志位，指示是否在 Item 和 Qty 部分
    is_item_section = False
    is_qty_section = False

    lines = text.split("\n")
    for i in range(len(lines)):
        line = lines[i].strip()
        # print(f"Line: {line}")
                        
        if "SO" in line:
            match = re.search(r"SO\s*[:]*\s*([\d/]+)", line)
            if match:
                so_no = match.group(1)

        if "Customer PO #" in line and i + 1 < len(lines):
            po_no = lines[i + 1].strip()

        if "Order Date" in line and i + 1 < len(lines):
            order_date_str = lines[i + 1].strip()  # Get the next line
            order_date = convert_to_yyyy_mm_dd(order_date_str)

        if "Date Expected" in line and i + 1 < len(lines):
            pickup_date_str = lines[i + 1].strip()  # Get the next line
            pickup_date = convert_to_yyyy_mm_dd(pickup_date_str)

        if "Bill To" in line:
            bill_to_lines = []
            for j in range(1, 5):  # Get the next four lines
                if i + j < len(lines):
                    bill_to_lines.append(lines[i + j].strip())
            bill_to = "\n".join(bill_to_lines) 

        if "Ship To" in line:
            ship_to_lines = []
            for j in range(1, 5):  # Get the next four lines
                if i + j < len(lines):
                    ship_to_lines.append(lines[i + j].strip())
            ship_to = "\n".join(ship_to_lines)

        # 检查是否是 Item Number / Name 部分
        if "Item Number / Name" in line:
            is_item_section = True
            continue  # 跳过标题行
        
        # 检查是否是 Qty 部分
        if "Qty" in line:
            is_qty_section = True
            continue  # 跳过标题行
        
        # 如果在 Item 部分，提取 Item
        if is_item_section and not is_qty_section:
            # 使用正则表达式提取 Item 名称
            item_match = re.match(r"(.+?)\s*[-]*$", line)  # 匹配 Item 名称
            if item_match:
                items.append(item_match.group(1).strip())
        
        # 如果在 Qty 部分，提取数量
        if is_qty_section:
            qty_match = re.match(r"(\d+)", line)  # 匹配数量
            if qty_match:
                quantities.append(int(qty_match.group(1).strip())) 

    return so_no, order_date, po_no, pickup_date, bill_to, ship_to, items, quantities

# 提取订单条目
def extract_items_from_pdf(text):
    # 1️⃣ Extract product lines between "Item Number / Name" and "Qty"
    pattern = re.compile(r'Item Number / Name(.*?)Qty(.*?)Unit', re.S)
    match = pattern.search(text)

    if match:
        items_part = match.group(1).strip()
        qty_part = match.group(2).strip()

    # 2️⃣ Combine item names that span multiple lines
    items = []
    current_item = ""

    for line in items_part.split("\n"):
        line = line.strip()
        # 判断是否是新的一行（以数字、CAN、KLT、T 开头）
        if re.match(r'^\d+', line) or re.match(r'^(CAN|KLT|T)(\s|-|$)', line):
            if current_item:
                items.append(current_item)
            current_item = line # 开始新的产品名称
        else:  # If it's the second line, add it to previous item
            current_item += " " + line # 追加到上一行

    # Add the last item
    if current_item:
        items.append(current_item)

    # 3️⃣ Extract qtys
    # qtys = qty_part.split("\n")
    qtys = [q.strip() for q in qty_part.split("\n")]

    # 4️⃣ Combine item with qty
    product_qty_list = list(zip(items, qtys))

    # ✅ Output the result
    for item, qty in product_qty_list:
        print(item.strip(), "-->", qty.strip())
    
    return product_qty_list

# 转换日期
def convert_to_yyyy_mm_dd(date_str):
    # 尝试解析日期字符串并转换为 YYYY-MM-DD 格式
    # print("--------convert_to_yyyy_mm_dd-------",date_str)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):  # 添加您需要支持的日期格式
        try:
            date_obj = datetime.strptime(date_str, fmt)
            # print("--------convert_to_yyyy_mm_dd-------",date_obj.strftime("%Y-%m-%d"))
            return date_obj.strftime("%Y-%m-%d")  # 转换为 YYYY-MM-DD 格式
        except ValueError:
            continue  # 如果格式不匹配，继续尝试下一个格式
    return None  # 如果没有匹配的格式，返回 None