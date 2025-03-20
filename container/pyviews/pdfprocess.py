from django.conf import settings
import os
from django.http import JsonResponse
from django.core.files.storage import default_storage
import fitz  # PyMuPDF 解析 PDF
from django.shortcuts import render
import re
from ..models import RMCustomer
from datetime import datetime,date
from django.shortcuts import get_object_or_404
from ..models import RMOrder
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

UPLOAD_DIR = "uploads/"
UPLOAD_DIR_order = "orders/"

# 替换文本 & 插入图片
NEW_ADDRESS = """RIMEI INTERNATION INC
1285 101st St
Lemont, IL 60439"""
NEW_TITLE = "Packing Slip"
NEW_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/remei.jpg')

# Label
PAGE_WIDTH, PAGE_HEIGHT = letter  # Letter size (8.5 x 11 inches)
MARGIN_TOP = 25  # Top margin
MARGIN_LEFT = 5  # Left margin
LABEL_WIDTH = (PAGE_WIDTH - MARGIN_LEFT * 2) / 2  # Two labels per row
LABEL_HEIGHT = (PAGE_HEIGHT - MARGIN_TOP * 2) / 5  # Five rows per page

FONT_SIZE = 60  # Larger font size
DRAW_BORDERS = False  # Set to True to draw borders, False to hide them

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
        print("--- ",pdf_file.name)

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
        if re.match(r'^\s*(\d{4,}|CAN|KLT|TC|TCL|TLESIM)(?!x)', line, re.IGNORECASE):
            if current_item:
                items.append(current_item.strip())
            current_item = line # 开始新的产品名称
        else:  # If it's the second line, add it to previous item
            current_item += " " + line # 追加到上一行

    # Add the last item
    if current_item:
        items.append(current_item.strip())

    # 3️⃣ Extract qtys
    # qtys = qty_part.split("\n")
    qtys = [q.strip() for q in qty_part.split("\n")]

    # 4️⃣ Combine item with qty
    product_qty_list = list(zip(items, qtys))

    # ✅ Output the result
    for item, qty in product_qty_list:
        print("item: ",item.strip(), "-->", qty.strip())
    
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
        page.insert_image(fitz.Rect(x, y, x + logo_width, y + logo_height), filename=NEW_LOGO_PATH)

        # 添加新地址
        address_x, address_y = x, y + logo_height + 20  
        page.insert_text((address_x, address_y), NEW_ADDRESS, fontsize=12, color=(0, 0, 0), fontfile="helvB")

        # 修改右上角的 Packing Slip 文字
        page_width = page.rect.width  
        packing_slip_x = page_width - 180  
        packing_slip_y = 50  

        erase_title_width, erase_title_height = 280, 30  
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
    order = get_object_or_404(RMOrder, so_num=so_num)
    label_count = order.plts

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

def print_bol(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    # 实现打印BOL的逻辑
    return HttpResponse("打印BOL")