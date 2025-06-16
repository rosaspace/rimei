from django.conf import settings
import os
from django.http import JsonResponse
from django.core.files.storage import default_storage
import fitz  # PyMuPDF 解析 PDF
import math
import textwrap
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..models import RMCustomer
from datetime import datetime,date
from ..models import RMOrder,Container,ContainerItem,OrderItem
from .pdfextract import extract_invoice_data, extract_customer_invoice_data, extract_order_info, extract_items_from_pdf,get_product_qty_with_inventory
from .pdfgenerate import extract_text_from_pdf, print_pickuplist, print_weekly_pickuplist, containerid_lot, print_weekly_pickuplist_on_one_page,generate_customer_invoice
from django.http import HttpResponse

from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.utils import ImageReader

from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal
import re
import io
from reportlab.platypus  import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
from reportlab.lib.styles import ParagraphStyle

UPLOAD_DIR = "uploads/"
UPLOAD_DIR_order = "orders/"
UPLOAD_DIR_container = "containers/"
UPLOAD_DIR_invoice = "invoices/"
UPLOAD_DIR_temp = "temp/"

# Order
BOL_FOLDER = "BOL/"
ORDER_FOLDER = "ORDER/"
ORDER_CONVERTED_FOLDER = "CONVERTED/"
LABEL_FOLDER = "label"
# Container
CHECKLIST_FOLDER = "checklist/"
DO_FOLDER = "DO/"
# INVOICE
INVOICE_FOUDER = "INVOICE"
CUSTOMER_INVOICE_FOLDER = "CustomerInvoice"
ORIGINAL_DO_FOUDER = "original"

# 替换文本 & 插入图片
NEW_ADDRESS = """RIMEI INTERNATION INC
1285 101st St
Lemont, IL 60439"""
NEW_TITLE = "Packing Slip"

# logo
Rimei_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/remei.jpg')
SSA_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/ssa.jpg')
GF_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static/icon/goldenfeather.jpg')

# Label
PAGE_WIDTH, PAGE_HEIGHT = letter  # Letter size (8.5 x 11 inches)
MARGIN_TOP = 25  # Top margin
MARGIN_LEFT = 5  # Left margin
LABEL_WIDTH = (PAGE_WIDTH - MARGIN_LEFT * 2) / 2  # Two labels per row
LABEL_HEIGHT = (PAGE_HEIGHT - MARGIN_TOP * 2) / 5  # Five rows per page

FONT_SIZE = 60  # Larger font size
# FONT_SIZE = 46  # Larger font size
FONT_SIZE_Lot = 20
FONT_SIZE_Container = 36  # Larger font size
LINE_SPACING = 40
DRAW_BORDERS = False  # Set to True to draw borders, False to hide the

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors


# 一行的文字长度
max_line_width = 96  # 根据页面宽度大致估算字符数


os.makedirs(LABEL_FOLDER, exist_ok=True)

# Order pdf
def upload_orderpdf(request):
    print("------upload_orderpdf--------\n")
    if request.method == "POST" and request.FILES.get("pdf_file"):
        pdf_file = request.FILES["pdf_file"]

        upload_dir = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order)  # 确保路径在 MEDIA_ROOT 目录下

        # ✅ 如果目录不存在，则创建
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(UPLOAD_DIR_order, ORDER_FOLDER, pdf_file.name)

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

# Order
def print_original_order(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)

    if not order.order_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, ORDER_FOLDER, order.order_pdfname)
    
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

    if not order.order_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, ORDER_FOLDER, order.order_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    new_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, ORDER_CONVERTED_FOLDER, order.order_pdfname)
    base_name, ext = os.path.splitext(new_path)
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

def print_order_label(request, so_num):
    print("----------print_order_label----------",so_num)
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
                text_y = y_position  - (LABEL_HEIGHT / 2) - 20
                
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

def print_order_bol(request, so_num):
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_order, BOL_FOLDER)
    filename = os.path.join(pdf_path, f"{container_info['SO Number']}.pdf")
    title = f"Order - {container_info['SO Number']}"
    contentTitle =  f"Bill Of Lading - {order.so_num}"

    print_bol_template(title,filename, contentTitle, container_info, order_details, certification_notes)

    # 返回 PDF 响应
    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response

def print_order_mcd(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    order_items = OrderItem.objects.filter(order=order)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 80

    LOT_MAPPING = {
        "07604-034": "GF041124-S",
        "07605-039": "GF100524-M",
        "07606-039": "GF100524-L",
        "07607-024": "GF100524-XL",
        "07326-024": "GF072124B",
        # Add more mappings if needed
    }

    # ✅ Logo 和标题
    if os.path.exists(GF_LOGO_PATH):
        p.drawImage(GF_LOGO_PATH, 40, y - 60, width=100, height=50, preserveAspectRatio=True, mask='auto')
    p.setFont("Helvetica-Bold", 20)
    p.drawString(220, y, "Packing Slip")
    y -= 80

    # ✅ 公司地址
    p.setFont("Helvetica", 11)
    company_info = [
        "Golden Feather Supplies LLC",
        "1285 101st St",
        "Lemont, IL 60439"
    ]
    for line in company_info:
        p.drawString(40, y, line)
        y -= 15

    # ✅ 订单信息框
    offset = 50
    p.rect(370, height - 120 - offset, 160, 50)
    p.drawString(375, height - 85 - offset, "Order Date")
    p.drawString(445, height - 85 - offset, order.order_date.strftime("%m/%d/%Y"))
    p.drawString(375, height - 100 - offset, "Omar SO#")
    p.drawString(445, height - 100 - offset, str(order.so_num))
    p.drawString(375, height - 115 - offset, "PO#")
    p.drawString(445, height - 115 - offset, order.po_num or "")

    # 收货地址框
    box_x = 40
    box_top_y = y  # 顶部 y 坐标
    line_height = 16
    ship_lines = (order.ship_to or "").split('\n')
    row_count = len(ship_lines) + 1  # 地址行数 + 标题行
    box_height = line_height * row_count + 10  # 每行 12，高度留出 10 点 padding

    # 绘制框
    p.rect(box_x, box_top_y - box_height, 300, box_height)

    # 绘制标题行 “Ship to:”
    p.setFont("Helvetica-Bold", 11)
    p.drawString(box_x + 5, box_top_y - line_height, "Ship to:")

    # 写入文字（从 top_y - line_height 开始写入）
    p.setFont("Helvetica", 11)
    text_y = box_top_y - (2 * line_height)
    for line in ship_lines:
        p.drawString(box_x + 5, text_y, line.strip())  # 加点 padding
        text_y -= line_height

    # 更新 y 位置，为后面内容留空间
    y = box_top_y - box_height - 200

    # ✅ 表格头和数据
    table_data = [["Item code", "Description", "Quantities(case)"]]
    total_qty = 0
    for item in order_items:
        lot_number = LOT_MAPPING.get(item.product.shortname, "LOT-UNKNOWN")
        description = f"{item.product.name} 200PC/BOX\nBATCH# {lot_number}"
        table_data.append([item.product.shortname, description, item.quantity])
        total_qty += item.quantity

    table_data.append(["", "Total", total_qty])

    table = Table(table_data, colWidths=[100, 300, 100], rowHeights=50)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'), 
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
    ]))

    table.wrapOn(p, width, height)
    table.drawOn(p, 40, y - (20 * len(table_data)))

    # ✅ 底部公司名
    p.drawString(40, 145, "Golden Feather Supplies LLC")
    p.drawString(40, 130, "1285 101st St")
    p.drawString(40, 115, "Lemont, IL 60439")

    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')
 
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
    col_widths = [60, 80, 270, 60, 60]
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

# Container
def print_container_label(request, container_num):
    container = get_object_or_404(Container, container_id=container_num)
    label_count = 10

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, LABEL_FOLDER)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    today_date = datetime.today().strftime("%m/%d/%Y").replace("/0", "/")  # Fix for Windows
    filename = os.path.join(pdf_path, f"{container_num}_old.pdf")  # Save inside "label" folder
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, LABEL_FOLDER)
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
# Delivery Order
def print_container_delivery_order(request, container_num):
    print("------------print_container_delivery_order------------")
    container = get_object_or_404(Container, container_id=container_num)

    containerInfo = {
        "container_id": container.container_id,              # 集装箱编号
        "size_type": "40HQ",                        # 集装箱尺寸/类型
        "weight": f"{container.weight} LBS",                       # 重量
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, DO_FOLDER)
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_temp, LABEL_FOLDER)
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_temp, LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container_id}_lot.pdf")

    c = canvas.Canvas(filename, pagesize=letter)
    containerid_lot(c, so_num, label_count, container_id, lot_number, current_date)
    c.save()

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response
  
# pick up list
def pickup_fourth(request):
    target_date = datetime.today()
    target_date += timedelta(days=3)
    response = print_pickuplist(target_date)
    return response

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

def pickup_week(request):
    target_date = datetime.today()
    # target_date += timedelta(days=7)
    response = print_weekly_pickuplist_on_one_page(target_date)
    return response

# Invoice
def print_original_do(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if not container.container_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_container, ORIGINAL_DO_FOUDER, container.container_pdfname)
    
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_invoice, INVOICE_FOUDER, container.invoice_pdfname)
    
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_invoice, ORDER_CONVERTED_FOLDER, container.customer_invoice_pdfname)
    
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
    input_pdf_path  = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_invoice, INVOICE_FOUDER, container.invoice_pdfname)    
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
    output_dir = os.path.join(settings.MEDIA_ROOT, UPLOAD_DIR_invoice, CUSTOMER_INVOICE_FOLDER)
    output_file_path = os.path.join(output_dir, new_filename)  # ✅ 拼接完整路径
    generate_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate)
    
    # 打开并读取PDF文件
    with open(output_file_path , 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{new_filename}"'
        return response

def generate_invoice_pdf(request):
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_ids")
        containers = Container.objects.filter(id__in=selected_ids)
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


def generate_invoice_pdf_old(request):
    print("generate_invoice_pdf")
    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_ids')
        containers = Container.objects.filter(id__in=selected_ids)
        total_price = sum([c.price for c in containers if c.price])
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # 标题
        elements.append(Paragraph("Invoice Statement", styles["Title"]))
        elements.append(Spacer(1, 12))

        # 表格数据
        data = [["ID", "Container#", "Customer", "Invoice#", "Price", "Invoice Date", "Due Date"]]

        for c in containers:
            data.append([
                c.id,
                c.container_id,
                c.customer.name,
                c.invoice_id,
                f"${c.price or 0:.2f}",
                c.invoice_date.strftime("%m/%d/%Y") if c.invoice_date else "",
                c.due_date.strftime("%m/%d/%Y") if c.due_date else "",
            ])

        # 合计
        data.append(["", "", "", "Total", f"${total_price:.2f}", "", ""])

        # 创建表格
        table = Table(data, colWidths=[50, 100, 80, 60, 60, 70, 70])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(table)

        # 生成 PDF
        doc.build(elements)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="invoice_statement.pdf"'
        response.write(pdf)
        return response

    return HttpResponse("Invalid Request", status=400)

def edit_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if request.method == "GET":
        return render(request, 'container/invoiceManager/edit_invoice.html', {
            'container': container,
        })

    elif request.method == 'POST':
        invoice_file = request.FILES.get('invoice_file')
        is_pay = 'is_pay' in request.POST

        if invoice_file:
            container.invoice_pdfname = invoice_file.name
            file_path = os.path.join(UPLOAD_DIR_invoice, INVOICE_FOUDER, invoice_file.name) 
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
                    'error': f"解析失败：{e}"
                })

        container.ispay = is_pay
        container.payment_date = request.POST.get('pay_date') or None
        container.save()

        return render(request, 'container/invoiceManager/edit_invoice.html', {
            'container': container,
        })

def edit_customer_invoice(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)

    if request.method == 'POST':
        invoice_file = request.FILES.get('invoice_file')
        is_pay = 'is_pay' in request.POST

        if invoice_file:
            container.customer_invoice_pdfname = invoice_file.name
            file_path = os.path.join(UPLOAD_DIR_invoice, ORDER_CONVERTED_FOLDER, invoice_file.name) 
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

            # 保存文件
            with open(full_path, 'wb+') as destination:
                for chunk in invoice_file.chunks():
                    destination.write(chunk)

            # 解析 PDF 内容
            try:
                text = extract_text_from_pdf(file_path)
                print("---:",text)
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
                    print(container.customer_price)
            except Exception as e:
                return render(request, 'container/invoiceManager/edit_invoice.html', {
                    'container': container,
                    'container_id': container_id,
                    'error': f"解析失败：{e}"
                })

        container.customer_ispay = is_pay
        container.customer_payment_date = request.POST.get('pay_date') or None
        container.save()

        return render(request, 'container/invoiceManager/edit_invoice.html', {
            'container': container,
            'container_id': container_id
        })

        return redirect('invoice')

    return render(request, 'container/invoiceManager/edit_invoice.html', {
        'container': container,
        'container_id': container_id,
    })
 
