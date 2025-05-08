from django.conf import settings
import os
from django.http import JsonResponse
from django.core.files.storage import default_storage
import fitz  # PyMuPDF 解析 PDF
import re
from ..models import RMCustomer
from datetime import datetime,date
from ..models import RMOrder,Container,RMInventory,RMProduct,ContainerItem,OrderItem
from .pdfextract import extract_invoice_data
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta
import math
import textwrap
from io import BytesIO
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal

UPLOAD_DIR = "uploads/"
UPLOAD_DIR_order = "orders/"
UPLOAD_DIR_container = "containers/"
CHECKLIST_FOLDER = "checklist/"

# 替换文本 & 插入图片
NEW_ADDRESS = """RIMEI INTERNATION INC
1285 101st St
Lemont, IL 60439"""
NEW_TITLE = "Packing Slip"
Rimei_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/remei.jpg')
SSA_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/ssa.jpg')

# Label
PAGE_WIDTH, PAGE_HEIGHT = letter  # Letter size (8.5 x 11 inches)
MARGIN_TOP = 25  # Top margin
MARGIN_LEFT = 5  # Left margin
LABEL_WIDTH = (PAGE_WIDTH - MARGIN_LEFT * 2) / 2  # Two labels per row
LABEL_HEIGHT = (PAGE_HEIGHT - MARGIN_TOP * 2) / 5  # Five rows per page

FONT_SIZE = 60  # Larger font size
FONT_SIZE_Container = 36  # Larger font size
LINE_SPACING = 40
DRAW_BORDERS = False  # Set to True to draw borders, False to hide them

# 一行的文字长度
max_line_width = 110  # 根据页面宽度大致估算字符数

LABEL_FOLDER = "label"
os.makedirs(LABEL_FOLDER, exist_ok=True)

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
        orderitems_new = get_product_qty_with_inventory(orderitems)

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
            "orderitems":orderitems_new,
            'customers': RMCustomer.objects.all(),
            'order_pdfname': pdf_file.name
        }        
        
        return render(request, 'container/rmorder/add_order.html',context)

    return render(request, 'container/rmorder.html')

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

    if not match:
        return []
    
    items_part = match.group(1).strip()
    qty_part = match.group(2).strip()

    # 2️⃣ Combine item names that span multiple lines
    items = []
    current_item = ""

    for line in items_part.split("\n"):
        line = line.strip()
        # 判断是否是新的一行（以数字、CAN、KLT、T 开头）
        if re.match(r'^\s*(\d{4,}|CAN|KLT|TC|TCL|TLESIM|PC|LPC|FACE)(?!x)', line, re.IGNORECASE):
            if current_item:
                items.append(current_item.strip())
            current_item = line # 开始新的产品名称
        else:  # If it's the second line, add it to previous item
            current_item += " " + line # 追加到上一行

    # Add the last item
    if current_item:
        items.append(current_item.strip())

    # 3️⃣ Extract qtys
    qtys_raw = [q.strip() for q in qty_part.split("\n")]
    qtys = []

    for q in qtys_raw:
        # 去掉逗号，把字符串转换为整数
        try:
            qty_int = int(q.replace(",", ""))
            qtys.append(qty_int)
        except ValueError:
            # 如果无法转换为整数，可以跳过或设为 0，按你需要处理
            qtys.append(0)

    # 4️⃣ Combine item with qty
    product_qty_list = list(zip(items, qtys))

    # ✅ Output the result
    for item, qty in product_qty_list:
        print("item: ",item.strip(), "-->", qty)
    
    return product_qty_list

# 补充库存信息
def get_product_qty_with_inventory(product_qty_list):
    result = []
    all_products = RMProduct.objects.all()
    
    for item, qty in product_qty_list:
        item_cleaned = item.strip()
        print(item_cleaned)
        qty_cleaned = qty

        matched_product = None

        for p in all_products:
            if (p.shortname and p.shortname.strip() in item_cleaned) or (p.name in item_cleaned):
                matched_product = p
                print(matched_product)
                break

        if matched_product:
            
            inventory = RMInventory.objects.filter(product=matched_product).first()
            # print("---",inventory.quantity, inventory.quantity_for_neworder, inventory.quantity_to_stock)
            inventory_qty = inventory.quantity_for_neworder if inventory else 0
        else:
            print(f"⚠️ 未找到匹配产品: {item_cleaned}")
            inventory_qty = 0

        print(f"item: {item_cleaned} --> ordered: {qty}, inventory: {inventory_qty}")
        result.append((item_cleaned, qty_cleaned, inventory_qty))

    return result

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

# Order
def print_original_order(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, order.order_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    # 打开并读取PDF文件
    with open(pdf_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{order.order_pdfname}"'
        return response

def print_converted_order(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, order.order_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    base_name, ext = os.path.splitext(pdf_path)
    updated_pdf = f"{base_name}_updated.pdf"
    doc = fitz.open(pdf_path)

    for page in doc:
        x, y = 40, 28  
        erase_width, erase_height = 250, 150  
        rect = fitz.Rect(x, y, x + erase_width, y + erase_height)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))  

        # 添加新 LOGO
        logo_width, logo_height = 130, 65  
        page.insert_image(fitz.Rect(x, y, x + logo_width, y + logo_height), filename=Rimei_LOGO_PATH)

        # 添加新地址
        address_x, address_y = x, y + logo_height + 20  
        page.insert_text((address_x, address_y), NEW_ADDRESS, fontsize=12, color=(0, 0, 0), fontfile="helvB")

        # 修改右上角的 Packing Slip 文字
        page_width = page.rect.width  
        packing_slip_x = page_width - 180  
        packing_slip_y = 50  

        # 遮住右上角名称
        erase_title_width, erase_title_height = 320, 30  
        erase_rect = fitz.Rect(page_width - erase_title_width, 30, page_width, 30 + erase_title_height)
        page.draw_rect(erase_rect, color=(1, 1, 1), fill=(1, 1, 1))

        page.insert_text((packing_slip_x, packing_slip_y), NEW_TITLE, fontsize=18, color=(0, 0, 0), fontfile="helvB")

    doc.save(updated_pdf)
    doc.close()
    
    with open(updated_pdf, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(updated_pdf)}"'
            return response

def print_label(request, so_num):
    print("----------print_label----------",so_num)
    order = get_object_or_404(RMOrder, so_num=so_num)
    label_count = order.plts
    original_label_count = label_count  # 用于总数显示

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    filename = os.path.join(pdf_path, f"{so_num}.pdf")  # Save inside "label" folder
    c = canvas.Canvas(filename, pagesize=letter)

    # Set font
    c.setFont("Helvetica-Bold", FONT_SIZE)
    
    y_position = PAGE_HEIGHT - MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True
    label_index = 1  # 当前标签序号

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", FONT_SIZE)  # Reset font on new page
            y_position = PAGE_HEIGHT - MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 

        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [MARGIN_LEFT, MARGIN_LEFT + LABEL_WIDTH]

            for x in x_positions:
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (LABEL_WIDTH / 2)
                text_y = y_position  - (LABEL_HEIGHT / 2) - 0
                
                # Set font and draw text
                c.setFont("Helvetica-Bold", FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if DRAW_BORDERS:
                    c.rect(x, y_position - LABEL_HEIGHT, LABEL_WIDTH, LABEL_HEIGHT)

                # Add smaller text for container_id, lot_number, and current date below the label
                c.setFont("Helvetica", FONT_SIZE - 30)  # Smaller font size for the new text
                label_number_text = f"{label_index}/{original_label_count}"
                c.drawCentredString(text_x, text_y - 30, label_number_text)

                label_index += 1
                label_count -= 1  # Reduce remaining label count

            y_position -= LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

    c.save()
    
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_bol(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    orderItems = OrderItem.objects.filter(order=order)

    # 列表
    order_details = []
    total_plts = 0

    for item in orderItems:
        pallet_qty = item.product.Pallet or 1  # 避免除以0
        plts = math.ceil(item.quantity / pallet_qty)
        total_plts += plts  # 累加托盘总数
        order_details.append({
            "Size": item.product.size if hasattr(item.product, 'size') else "N/A",
            "ShortName": item.product.shortname,
            "Name": item.product.name,
            "Qty": str(item.quantity),
            "PLTS": str(plts)
        })

    # 基本信息
    container_info = {
        "Ship From": 'Rimei INTERNATION INC\n1285 101st St\nLemont, IL 60439',
        "Ship To": order.ship_to,
        "Bill To": order.bill_to,
        "SO Number": order.so_num,
        "PO Number": order.po_num,
        "Ship Date": order.pickup_date.strftime("%m/%d/%Y"),
        "Total LBS": str(total_plts * 1250),
        "Total Pallets": str(total_plts),
    }

    # 注意事项
    # 添加附加说明
    certification_notes = [
        "NOTE: Liability Limitation for loss or damage in this shipment may be applicable. See 49 U.S.C. - 14706(c)(1)(A) and (B).",
        "Checker: All pallets are in good condition, with no visible damage.",
        "Shipper: Materials are properly classified, packaged, and labeled per DOT regulations, and in good condition for transport.",
        "Carrier: Receipt of goods and placards; emergency info provided or accessible. Goods received in apparent good order unless noted.",
    ]

    # 保存路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, CHECKLIST_FOLDER)
    filename = os.path.join(pdf_path, f"{container_info['SO Number']}.pdf")
    title = f"Order - {container_info['SO Number']}"
    contentTitle =  f"Bill Of Lading - {order.so_num}"

    print_bol_template(title,filename, contentTitle, container_info, order_details, certification_notes)

    # 返回 PDF 响应
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

# Container
def print_container_label(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    label_count = 10

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    today_date = datetime.today().strftime("%m/%d/%Y").replace("/0", "/")  # Fix for Windows
    filename = os.path.join(pdf_path, f"{container_num}.pdf")  # Save inside "label" folder
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(f"Label - {container.container_id}")

    # Set font
    c.setFont("Helvetica-Bold", FONT_SIZE_Container)
    
    y_position = PAGE_HEIGHT - MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", FONT_SIZE_Container)  # Reset font on new page
            y_position = PAGE_HEIGHT - MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 

        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [MARGIN_LEFT, MARGIN_LEFT + LABEL_WIDTH]

            for x in x_positions:
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (LABEL_WIDTH / 2)
                text_y = y_position  - (LABEL_HEIGHT / 2) - 10
                
                # Print first line (custom text) and second line (today's date)
                c.drawCentredString(text_x, text_y + (LINE_SPACING / 2), container_num)  # First line (higher)
                c.drawCentredString(text_x, text_y - (LINE_SPACING / 2), today_date)  # Second line (lower)
    
                # Draw label borders (for testing)
                if DRAW_BORDERS:
                    c.rect(x, y_position - LABEL_HEIGHT, LABEL_WIDTH, LABEL_HEIGHT)
    
                label_count -= 1  # Reduce remaining label count

            y_position -= LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

    c.save()
    
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_container_color_label(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    containerItems = ContainerItem.objects.filter(container=container)

    # 统计每个 so_num 的数量
    so_label_map = {}
    for item in containerItems:
        pallet_qty = item.product.Pallet or 1  # 避免除以0
        plts = math.ceil(item.quantity / pallet_qty)
        try:
            order = item.product
            if order and order.shortname:
                so_num = order.shortname
                so_label_map[so_num] = so_label_map.get(so_num, 0) + plts
        except AttributeError:
            continue

    if not so_label_map:
        return HttpResponse("找不到相关的订单号", status=400)

    # 通用信息
    container_id = container.container_id
    lot_number = container.lot
    current_date = datetime.now().strftime('%m/%d/%Y')

    # PDF 路径设置
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container.container_id}.pdf")

    # 使用内存文件构建 PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for so_num, total_count in so_label_map.items():
        pages = (total_count + 9) // 10  # 计算需要的总页数，每页最多 10 个

        for page in range(pages):
            # 计算当前页应打印的 label 数量
            page_label_count = min(10, total_count - page * 10)
            try:
                containerid_lot(c, so_num, page_label_count, container_id, lot_number, current_date)
                c.showPage()
            except Exception as e:
                print(f"生成标签出错：{e}")
                return HttpResponse(f"生成标签时出错：{e}", status=500)

    c.save()
    buffer.seek(0)

    # 保存到文件
    with open(filename, 'wb') as f:
        f.write(buffer.read())

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_container_detail(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    containerItems = ContainerItem.objects.filter(container=container)

    # 列表
    can_liner_details = []
    total_plts = 0

    for item in containerItems:
        pallet_qty = item.product.Pallet or 1  # 避免除以0
        plts = math.ceil(item.quantity / pallet_qty)
        total_plts += plts  # 累加托盘总数
        can_liner_details.append({
            "Size": item.product.size if hasattr(item.product, 'size') else "N/A",
            "Name": item.product.shortname,
            "Qty": str(item.quantity),
            "PLTS": str(plts)
        })

    # 基本信息
    container_info = {
        "Manufacturer": container.inboundCategory.Manufacturer,
        "Container Number": container.container_id,
        "Carrier": container.inboundCategory.Carrier.name,
        "LOT#": container.lot,
        "Date": datetime.now().strftime("%m/%d/%Y"),
        "Product Validity": "",
        "Name": "OMAR",
        "Commodity": container.inboundCategory.Name,
        # "Can liner Size": '',
        "Total Pallets": str(total_plts),
    }
    # 注意事项
    note_lines = [
                "Remove 1 case of each size performing physical examinations on the box as well as a detailed examination of a glove in each.",
                "Check for black spots, tears, discoloration, and dampness, etc. ",
                "Briefly check elasticity ensuring the glove doesn’t easily rip.", 
                "Check the accuracy of the packaging does the external Bo match up with the internal boxes pertaining to weight, size, and the product number?",
                "Check the external box of individual boxes for spelling and print accuracy. ",
            ]

    # 保存路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, CHECKLIST_FOLDER)
    filename = os.path.join(pdf_path, f"container.container_id.pdf")
    title = f"Container - {container.container_id}"
    contentType = container.inboundCategory.Type
    contentTitle = f"Inbound Container {contentType} Quality Checklist"

    print_checklist_template(title,filename, contentTitle,container_info,can_liner_details, note_lines)

    # 返回 PDF 响应
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_bol_template(title,filename, contentTitle, container_info, order_details, certification_notes):
    # 创建 PDF 文件
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(title)
    width, height = letter

    # 设置标题居中
    c.setFont("Helvetica-Bold", 16)
    title = contentTitle
    c.drawCentredString(width / 2, height - 80, title)

    # 内容起始位置
    x_label = 60         # 标签起始 x
    line_length = 210    # 下划线长度
    y = height - 120     # 初始 y 坐标
    line_spacing = 30
    x_sub_table = 100   #子表起始点

    # 设置正文字体
    c.setFont("Helvetica", 12)

    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    font_size = 10
    left_margin = 0.8 * inch
    line_height = 18

    def draw_text(x, y, text, font=regular_font, size=font_size):
        c.setFont(font, size)
        c.drawString(x, y, text)

    part1_Y = y
    items_Y = 0
    for key, value in container_info.items():
        # 左上角多行地址
        if key in ["Ship To", "Bill To", "Ship From"] and isinstance(value, str):
            draw_text(x_label, y, f"{key}:")
            address_lines = value.splitlines()
            for i, line in enumerate(address_lines):
                draw_text(x_label + 60, y, line)
                if i == len(address_lines) - 1:
                    # c.line(x_label + 60, y - 2, x_label + line_length, y - 2)  # 只画最后一行的下划线
                    y -= 18
                    items_Y = y
                else:
                    y -= 14  # 多行地址行间距
        else:
            # 右上角信息
            right_x = width - 280
            draw_text(right_x, part1_Y, f"{key}:")            
            draw_text(right_x + 80, part1_Y, str(value))
            # c.line(right_x + 60, part1_Y - 2, right_x + line_length, part1_Y - 2)
            part1_Y -= line_spacing

    # 产品条目表头
    y = items_Y - line_height

    # 添加表头上方横线
    c.setLineWidth(1)
    c.line(left_margin, y + line_height -2, width - left_margin, y + line_height -2)

    table_headers = ["Size", "ShortName", "Name", "Qty", "PLTS"]
    col_widths = [40, 60, 320, 50, 60]
    x = left_margin
    for header, w in zip(table_headers, col_widths):
        draw_text(x, y, header, bold_font)
        x += w

    # 添加表头下方横线
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)
    
    # 产品条目
    y -= line_height 
    for item in order_details:
        row_values = [
            item['Size'],
            item['ShortName'],
            item['Name'],
            item['Qty'],
            item['PLTS'],
        ]
        x = left_margin  # 每行开始时重置 x 坐标
        for value, w in zip(row_values, col_widths):
            draw_text(x, y, str(value))
            x += w
        y -= line_height  # 向下移一行

    # 添加数据行下方横线
    y += line_height
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)

    # 提示信息
    y -= line_height * 2
    for note in certification_notes:
        wrapped_lines = textwrap.wrap(note, width=max_line_width)
        for line in wrapped_lines:
            draw_text(x_label, y, line)
            y -= 16
        y -= 6  # 每段间距

    # 添加签名和日期区域
    y -= line_height  # 签名上方稍作间隔
    signature_labels = ["Checker", "Shipper","Carrier"]
    signature_spacing = 160  # 每组签名之间的水平间距
    signature_y = y     # 签名区开始的 Y 坐标
    signature_x_start = x_label

    c.setFont("Helvetica", 12)
    for i, label in enumerate(signature_labels):
        x_pos = signature_x_start + i * signature_spacing
        c.drawString(x_pos, signature_y, f"{label}:")
        c.line(x_pos + 60, signature_y, x_pos + 150, signature_y)  # 签名字下划线

        c.drawString(x_pos, signature_y - 30, "Date:")
        c.line(x_pos + 60, signature_y - 30, x_pos + 150, signature_y - 30)  # 日期下划线

    # 保存 PDF
    c.save()

def print_checklist_template(title,filename, contentTitle, container_info,can_liner_details, note_lines, issign = False):
  
    # 创建 PDF 文件
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(title)
    width, height = letter

    # 设置标题居中
    c.setFont("Helvetica-Bold", 16)
    title = contentTitle
    c.drawCentredString(width / 2, height - 80, title)

    # 内容起始位置
    x_label = 60         # 标签起始 x
    x_line_start = 180   # 填空线起始 x
    line_length = 340    # 下划线长度
    y = height - 120     # 初始 y 坐标
    line_spacing = 30
    x_sub_table = 100   #子表起始点

    # 设置正文字体
    c.setFont("Helvetica", 12)

    for key, value in container_info.items():
        # 写字段标签
        c.drawString(x_label, y, f"{key}:")
        # c.line(x_line_start, y - 2, x_line_start + line_length, y - 2)

        # 处理多行地址
        if key in ["Ship To", "Bill To", "Ship From"] and isinstance(value, str):
            address_lines = value.splitlines()
            for i, line in enumerate(address_lines):
                c.drawString(x_line_start + 20, y, line)
                if i == len(address_lines) - 1:
                    c.line(x_line_start, y - 2, x_line_start + line_length, y - 2)  # 只画最后一行的下划线
                    y -= 26
                else:
                    y -= 18  # 多行地址行间距
        else:
            # 单行字段值
            c.drawString(x_line_start + 20, y, str(value))
            c.line(x_line_start, y - 2, x_line_start + line_length, y - 2)
            y -= line_spacing

        if key == "Total Pallets":
            # 插入子表头
            c.setFont("Helvetica-Bold", 11)
            c.drawString(x_sub_table + 0, y, "Size")
            c.drawString(x_sub_table + 100, y, "Name")
            c.drawString(x_sub_table + 220, y, "CTNS")
            # c.drawString(x_sub_table + 280, y, "CTNS")
            c.drawString(x_sub_table + 340, y, "PLTS")
            y -= 20

            c.setFont("Helvetica", 11)
            for item in can_liner_details:
                c.drawString(x_sub_table, y, item["Size"])

                c.drawString(x_sub_table + 100, y, item["Name"])
                c.line(x_sub_table + 80, y - 2, x_sub_table + 180, y - 2)  # Name 下划线

                c.drawString(x_sub_table + 220, y, item["Qty"])
                c.line(x_sub_table + 200, y - 2, x_sub_table + 300, y - 2)  # QTY 下划线

                # c.drawString(x_sub_table + 280, y, "CTNS")

                c.drawString(x_sub_table + 340, y, item["PLTS"])
                c.line(x_sub_table + 320, y - 2, x_sub_table + 400, y - 2)  # QTY 下划线

                y -= 20

            # 在子表格之后添加三组文字和空行
            y -= 10
            line_spacing_extra = 35  # 每组行距
            

            c.setFont("Helvetica", 12)
            for i, note in enumerate(note_lines):
                wrapped_lines = textwrap.wrap(note, width=max_line_width)
                for line in wrapped_lines:
                    c.drawString(x_label, y, line)
                    y -= 18  # 行间距适当紧凑一点

                # 如果是第2段开始，加下划线和额外间距
                if i >= 1:
                    c.line(x_label, y, x_label + 490, y)
                    y -= line_spacing_extra
                else:
                    y -= 10  # 如果不画线就只空一点行距
            
            if issign :
                # 添加附加说明
                certification_notes = [
                    "Checker: All pallets are in good condition, with no visible damage.",
                    "Shipper: Materials are properly classified, packaged, and labeled per DOT regulations, and in good condition for transport.",
                    "Carrier: Receipt of goods and placards; emergency info provided or accessible. Goods received in apparent good order unless noted.",
                ]

                for note in certification_notes:
                    wrapped_lines = textwrap.wrap(note, width=90)
                    for line in wrapped_lines:
                        c.drawString(x_label, y, line)
                        y -= 16
                    y -= 6  # 每段间距

                # 添加签名和日期区域
                y -= 10  # 签名上方稍作间隔
                signature_labels = ["Checker", "Shipper","Carrier"]
                signature_spacing = 160  # 每组签名之间的水平间距
                signature_y = y     # 签名区开始的 Y 坐标
                signature_x_start = x_label

                c.setFont("Helvetica", 12)
                for i, label in enumerate(signature_labels):
                    x_pos = signature_x_start + i * signature_spacing
                    c.drawString(x_pos, signature_y, f"{label}:")
                    c.line(x_pos + 60, signature_y, x_pos + 150, signature_y)  # 签名字下划线

                    c.drawString(x_pos, signature_y - 30, "Date:")
                    c.line(x_pos + 60, signature_y - 30, x_pos + 150, signature_y - 30)  # 日期下划线

    # 保存 PDF
    c.save()

# Temp
def print_label_only(request):
    print("----------print_label_only----------")
    so_num = request.POST.get('so_number')
    label_count = request.POST.get('quantity')
    
    try:
        label_count = int(label_count) if label_count is not None else 0
    except ValueError:
        label_count = 10  # Handle invalid input gracefully

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    print("pdf_path: ", pdf_path)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    filename = os.path.join(pdf_path, f"{so_num}.pdf")  # Save inside "label" folder
    c = canvas.Canvas(filename, pagesize=letter)

    # Set font
    c.setFont("Helvetica-Bold", FONT_SIZE)
    
    y_position = PAGE_HEIGHT - MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", FONT_SIZE)  # Reset font on new page
            y_position = PAGE_HEIGHT - MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 

        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [MARGIN_LEFT, MARGIN_LEFT + LABEL_WIDTH]

            for x in x_positions:
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (LABEL_WIDTH / 2)
                text_y = y_position  - (LABEL_HEIGHT / 2) - 20
                
                # Set font and draw text
                c.setFont("Helvetica-Bold", FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if DRAW_BORDERS:
                    c.rect(x, y_position - LABEL_HEIGHT, LABEL_WIDTH, LABEL_HEIGHT)
    
                label_count -= 1  # Reduce remaining label count

            y_position -= LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

    c.save()
    
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_label_containerid_lot(request):
    print("----------print_label_containerid_lot----------")
    so_num = request.POST.get('so_number')
    label_count = request.POST.get('quantity')
    container_id = request.POST.get('containerid')
    lot_number = request.POST.get('lot_number')
    current_date = datetime.now().strftime('%m/%d/%Y')

    # PDF 路径设置
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container_id}.pdf")

    c = canvas.Canvas(filename, pagesize=letter)
    containerid_lot(c, so_num, label_count, container_id, lot_number, current_date)
    c.save()

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def containerid_lot(c, so_num, label_count, container_id, lot_number, current_date):
    try:
        label_count = int(label_count) if label_count is not None else 0
    except ValueError:
        label_count = 10  # Handle invalid input gracefully

    # Set font
    c.setFont("Helvetica-Bold", FONT_SIZE)
    
    y_position = PAGE_HEIGHT - MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", FONT_SIZE)  # Reset font on new page
            y_position = PAGE_HEIGHT - MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 

        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [MARGIN_LEFT, MARGIN_LEFT + LABEL_WIDTH]

            for x in x_positions:
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (LABEL_WIDTH / 2)
                text_y = y_position  - (LABEL_HEIGHT / 2) - 0
                
                # Set font and draw text
                c.setFont("Helvetica-Bold", FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if DRAW_BORDERS:
                    c.rect(x, y_position - LABEL_HEIGHT, LABEL_WIDTH, LABEL_HEIGHT)

                # Add smaller text for container_id, lot_number, and current date below the label
                c.setFont("Helvetica", FONT_SIZE -40)  # Smaller font size for the new text
                text_y_small = text_y - 30  # Position for the smaller text below the main label
                c.drawCentredString(text_x, text_y_small, f"{container_id}    {current_date}")
                c.drawCentredString(text_x, text_y_small - 20, f"Lot: {lot_number}")
    
                label_count -= 1  # Reduce remaining label count

            y_position -= LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

# Delivery Order
def print_container_delivery_order(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)

    containerInfo = {
        "container_id": container.container_id,              # 集装箱编号
        "size_type": "40HQ",                        # 集装箱尺寸/类型
        "weight": "56658.80LBS",                       # 重量
        "seal_number": "",                # 封条号
        "commodity": "Plastic Bag",                 # 商品描述
        "vessel": "",               # 船名
        "voyage": "",                          # 航次
        "ssl": "",                          # 船公司（Shipping Line）

        "pickup_location": f"{container.railwayStation.name}\n{container.railwayStation.address}".replace("\\n", "\n").replace("\r\n", "\n"),
        "pickup_date": "Pending",                   # 提货日期
        "delivery_location": f"{container.Carrier.name}\n{container.Carrier.address}".replace("\\n", "\n").replace("\r\n", "\n"),
        "delivery_date": "Pending",                 # 送货日期

        "ref_no": container.refnumber,                 # 参考编号
        "mbl": container.mbl                   # 提单号
    }

    # PDF 路径设置
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container.container_id}.pdf")

    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # 插入 logo
    logo_width, logo_height = 80, 80  
    logo_x = 0.5 * inch  # left_margin
    logo_y = height - logo_height - 40  # 顶部边距 10
    c.drawImage(ImageReader(SSA_LOGO_PATH), logo_x, logo_y, width=logo_width, height=logo_height)

    # 样式设置
    left_margin = 0.5 * inch
    line_height = 18
    font_size = 10
    font_size_small = 8
    bold_font = "Helvetica-Bold"
    regular_font = "Helvetica"

    def draw_text(x, y, text, font=regular_font, size=font_size):
        c.setFont(font, size)
        c.drawString(x, y, text)

    y = height - 75

    # 标题
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2 , y, "DELIVERY ORDER")

    # US Headquarter
    y = height - 140
    draw_text(left_margin, y, "US Headquarter:", bold_font)
    draw_text(left_margin + 120, y, "1285 101st Street")
    y -= line_height
    draw_text(left_margin + 120, y, "Lemont, Illinois 60439")

    # 右上角信息
    right_x = width - 240
    y += line_height
    draw_text(right_x, y, f"DATE: {datetime.now().strftime('%m/%d/%Y')}")
    y -= line_height
    draw_text(right_x, y, f"REF. NO: {containerInfo['ref_no']}")
    y -= line_height
    draw_text(right_x, y, f"MBL: {containerInfo['mbl']}")

    # Pickup / Delivery 信息
    # y -= 40
    y = y - line_height * 2  # 空一行

    # Pickup Location
    pickup_lines = containerInfo['pickup_location'].split('\n')
    pickup_y = y  # 记录起始高度
    draw_text(left_margin, pickup_y, "Pickup Location:", bold_font)
    for line in pickup_lines:
        draw_text(left_margin + 120, pickup_y, line, bold_font)
        pickup_y -= line_height
    # Pickup Date 与 Pickup Location 的首行对齐
    draw_text(right_x, y, f"Pickup Date:    {containerInfo['pickup_date']}")

    # Delivery Location
    y = pickup_y - line_height  # 空一行
    delivery_lines = containerInfo['delivery_location'].split('\n')
    delivery_y = y
    draw_text(left_margin, delivery_y, "Delivery Location:", bold_font)
    for line in delivery_lines:
        draw_text(left_margin + 120, delivery_y, line, bold_font)
        delivery_y -= line_height
    # Delivery Date 与 Delivery Location 的首行对齐
    draw_text(right_x, y, f"Delivery Date:    {containerInfo['delivery_date']}")
    y = delivery_y  # 更新 y 供后续使用

    # 提示
    y -= 20
    c.setFont(regular_font, font_size_small)
    c.drawString(left_margin + 120, y, "FOR DELIVERY AND APPOINTMENT INSTRUCTIONS, CONTACT TEL:+1 630-909-9888")
    y -= line_height
    c.drawString(left_margin + 120, y, "BEFORE ATTEMPTING PICK-UP OR DELIVERY OF CARGO")

    # 表头
    y -= 20

    # 添加表头上方横线
    c.setLineWidth(1)
    c.line(left_margin, y + line_height -2, width - left_margin, y + line_height -2)

    table_headers = ["Container#", "Container Size/Type", "Weight", "Seal#", "Remarks"]
    col_widths = [120, 150, 100, 100, 100]
    x = left_margin
    for header, w in zip(table_headers, col_widths):
        draw_text(x, y, header, bold_font)
        x += w

    # 添加表头下方横线
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)

    # 数据行
    y -= line_height
    x = left_margin
    row_values = [
        containerInfo['container_id'],
        containerInfo['size_type'],
        containerInfo['weight'],
        containerInfo['seal_number'],
        ""
    ]
    for value, w in zip(row_values, col_widths):
        draw_text(x, y, str(value))
        x += w

    # 添加数据行下方横线
    c.setLineWidth(1)
    c.line(left_margin, y - 4, width - left_margin, y - 4)

    # Footer
    y -= 20
    c.setFont(regular_font, font_size_small)
    c.drawString(left_margin + 120, y, f"Total Containers: 1")
    y -= line_height
    c.drawString(left_margin + 120, y, f"Commodity: {containerInfo['commodity']}")
    y -= line_height
    c.drawString(left_margin + 120, y, f"Vessel: {containerInfo['vessel']}")
    y -= line_height
    c.drawString(left_margin + 120, y, f"Voyage: {containerInfo['voyage']}")
    y -= line_height
    c.drawString(left_margin + 120, y, f"SSL: {containerInfo['ssl']}")

    # 签名区
    y -= 60
    draw_text(width / 2, y, "Received in Good Order")
    y -= line_height * 2
    draw_text(width / 2, y, "By: _____________________________")
    y -= line_height
    draw_text(width / 2, y, "Date:                                 Time:")

    c.save()

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response
    
# pick up list
def pickup_tomorrow(request):
    # 获取今天或明天
    target_date = datetime.today()
    target_date += timedelta(days=1)
    response = print_pickuplist(target_date)
    return response

def pickup_third(request):
    target_date = datetime.today()
    target_date += timedelta(days=2)
    response = print_pickuplist(target_date)
    return response

def pickup_today(request):
    # 获取今天或明天
    target_date = datetime.today()
    response = print_pickuplist(target_date)
    return response

def print_pickuplist(target_date):
    # 格式化日期文本：TUESDAY 04/10
    weekday_str = target_date.strftime('%A').upper()
    date_str = target_date.strftime('%m/%d')

    # 查询 RMOrder 表中的 Pickup No.
    pickup_orders = RMOrder.objects.filter(pickup_date=target_date.date()).exclude(Q(customer_name="4") | Q(is_canceled=True))
    pickup_numbers = [str(order.so_num) for order in pickup_orders]

    # 如果没有数据，显示占位
    if not pickup_numbers:
        pickup_numbers = ["N/A"]
    if target_date.weekday() == 0:  # Monday
        pickup_numbers.append("Office Depot")

    # 生成 PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="pickup_report.pdf"'

    c = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    left_margin = 1 * inch
    y = height - 2 * inch

    # 日期行样式
    c.setFont("Helvetica-Bold", 48)
    # 日期文字
    date_text = f"{weekday_str}   {date_str}"
    c.drawString(left_margin, y, date_text)

    # 计算文字宽度以便画下划线
    text_width = c.stringWidth(date_text, "Helvetica-Bold", 48)
    underline_y = y - 5  # 稍微低一点以贴近文字底部

    # 画下划线
    c.setLineWidth(3)
    c.line(left_margin, underline_y, left_margin + text_width, underline_y)

    # Pickup 标签
    y -= 60
    c.setFont("Helvetica", 30)
    c.drawString(left_margin, y, "PICKUPS:")

    # Pickup 编号列表
    y -= 50
    c.setFont("Helvetica", 30)
    for num in pickup_numbers:
        c.drawString(left_margin, y, num)
        y -= 50

    c.save()
    return response

# Invoice
def edit_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    extracted_price = None

    if request.method == 'POST':
        invoice_file = request.FILES.get('invoice_file')
        is_pay = 'is_pay' in request.POST

        if invoice_file:
            container.invoice_pdfname = invoice_file.name
            file_path = os.path.join('invoices', invoice_file.name)  # 假设保存在 MEDIA_ROOT/invoices/
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

            # 保存文件
            with open(full_path, 'wb+') as destination:
                for chunk in invoice_file.chunks():
                    destination.write(chunk)

            # 解析 PDF 内容
            try:
                text = extract_text_from_pdf(file_path)
                data = extract_invoice_data(text)

                # 更新模型字段
                if data['invoice_id']:
                    container.invoice_id = data['invoice_id']
                if data['invoice_date']:
                    container.invoice_date = data['invoice_date']
                if data['due_date']:
                    container.due_date = data['due_date']
                if data['price']:
                    container.price = Decimal(data['price'])
            except Exception as e:
                return render(request, 'container/invoiceManager/edit_invoice.html', {
                    'container': container,
                    'container_id': container_id,
                    'error': f"解析失败：{e}"
                })

        container.ispay = is_pay
        container.save()

        if extracted_price:
            return render(request, 'container/invoiceManager/edit_invoice.html', {
                'container': container,
                'container_id': container_id,
                'extracted_price': extracted_price
            })

        return redirect('invoice')

    return render(request, 'container/invoiceManager/edit_invoice.html', {
        'container': container,
        'container_id': container_id,
    })