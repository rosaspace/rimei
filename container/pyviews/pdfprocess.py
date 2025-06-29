import os
import fitz  # PyMuPDF 解析 PDF
import math

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

from datetime import datetime,timedelta
from io import BytesIO

from ..models import RMOrder,OrderItem
from .pdfgenerate import print_pickuplist, print_weekly_pickuplist_on_one_page,print_bol_template
from ..constants import constants_address

# Order
def print_original_order(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)

    if not order.order_pdfname:
        return HttpResponse("❌ 当前记录没有 PDF 文件，请先上传。")

    # 构建PDF文件路径
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order, constants_address.ORDER_FOLDER, order.order_pdfname)
    
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order, constants_address.ORDER_FOLDER, order.order_pdfname)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)
    
    new_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order, constants_address.ORDER_CONVERTED_FOLDER, order.order_pdfname)
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
        page.insert_image(fitz.Rect(x, y, x + logo_width, y + logo_height), filename=constants_address.Rimei_LOGO_PATH)

        # 添加新地址
        address_x, address_y = x, y + logo_height + 20  
        page.insert_text((address_x, address_y), constants_address.NEW_ADDRESS, fontsize=12, color=(0, 0, 0), fontfile="helvB")

        # 修改右上角的 Packing Slip 文字
        page_width = page.rect.width  
        packing_slip_x = page_width - 180  
        packing_slip_y = 50  

        # 遮住右上角名称
        erase_title_width, erase_title_height = 320, 30  
        erase_rect = fitz.Rect(page_width - erase_title_width, 30, page_width, 30 + erase_title_height)
        page.draw_rect(erase_rect, color=(1, 1, 1), fill=(1, 1, 1))

        page.insert_text((packing_slip_x, packing_slip_y), constants_address.NEW_TITLE, fontsize=18, color=(0, 0, 0), fontfile="helvB")

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
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order, constants_address.LABEL_FOLDER)
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    filename = os.path.join(pdf_path, f"{so_num}.pdf")  # Save inside "label" folder
    c = canvas.Canvas(filename, pagesize=letter)

    # Set font
    c.setFont("Helvetica-Bold", constants_address.FONT_SIZE)
    
    y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True
    label_index = 1  # 当前标签序号
    
    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont("Helvetica-Bold", constants_address.FONT_SIZE)  # Reset font on new page
            y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Reset y position
            labels_on_page = 0  # Reset row counter

        first_page = False 
        
        for _ in range(5):  # Max 5 rows per page
            if label_count <= 0:
                break  # Stop when all labels are printed
    
            # Two labels per row, calculate positions
            x_positions = [constants_address.MARGIN_LEFT, constants_address.MARGIN_LEFT + constants_address.LABEL_WIDTH]

            for x in x_positions:
                
                if label_count <= 0:  
                    break  # Stop if all labels are printed
    
                # Center text in each label
                text_x = x + (constants_address.LABEL_WIDTH / 2)
                text_y = y_position  - (constants_address.LABEL_HEIGHT / 2) - 20
                
                # Set font and draw text
                c.setFont("Helvetica-Bold", constants_address.FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if constants_address.DRAW_BORDERS:
                    c.rect(x, y_position - constants_address.LABEL_HEIGHT, constants_address.LABEL_WIDTH, constants_address.LABEL_HEIGHT)

                # Add smaller text for container_id, lot_number, and current date below the label
                c.setFont("Helvetica", constants_address.FONT_SIZE - 30)  # Smaller font size for the new text
                label_number_text = f"{label_index}/{original_label_count}"
                
                c.drawCentredString(text_x, text_y - 30, label_number_text)

                label_index += 1
                label_count -= 1  # Reduce remaining label count

            y_position -= constants_address.LABEL_HEIGHT  # Move to next row
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
        "Ship From": constants_address.rimei_address,
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_order, constants_address.BOL_FOLDER)
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
    if os.path.exists(constants_address.GF_LOGO_PATH):
        p.drawImage(constants_address.GF_LOGO_PATH, 40, y - 60, width=100, height=50, preserveAspectRatio=True, mask='auto')
    p.setFont("Helvetica-Bold", 20)
    p.drawString(220, y, "Packing Slip")
    y -= 80

    # ✅ 公司地址
    p.setFont("Helvetica", 11)
    for line in constants_address.GF_ADDRESS:
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
    for line in constants_address.GF_ADDRESS:
        p.drawString(40, y-220, line)
        y -= 15

    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

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
