import os
import fitz  # PyMuPDF 解析 PDF
import textwrap

from django.conf import settings
from django.db.models import Q

from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from datetime import timedelta
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Image
from reportlab.lib import colors
from decimal import Decimal
from datetime import datetime, timedelta

from ..models import RMOrder
from ..constants import constants_address

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
    # if target_date.weekday() == 0:  # Monday
    #     pickup_numbers.append("Office Depot")

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

def print_weekly_pickuplist_on_one_page(start_date):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="weekday_pickup_report.pdf"'

    c = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    # 配置
    left_margin = 1 * inch
    top_margin = height - 1 * inch
    line_height = 26
    title_font_size = 24
    item_font_size = 16

    # 标题
    c.setFont("Helvetica-Bold", title_font_size + 10)
    c.drawCentredString(width / 2, height - 1 * inch, "WEEKDAY PICKUP LIST")

    # 当前绘制位置
    y = top_margin - 0.7 * inch

    # 仅打印周一至周五
    current_date = start_date
    printed_days = 0
    while printed_days < 5:
        
        weekday = current_date.weekday()
        if weekday < 5:  # 周一到周五
            weekday_str = current_date.strftime('%A')[:3].upper()
            date_str = current_date.strftime('%m/%d')
            header_text = f"{weekday_str} {date_str}"

            c.setFont("Helvetica-Bold", title_font_size)
            c.drawString(left_margin, y, header_text)
            y -= line_height

            pickup_orders = RMOrder.objects.filter(
                pickup_date=current_date.date()
            ).exclude(Q(customer_name="4") | Q(customer_name="19") | Q(is_canceled=True))

            if pickup_orders.exists():
                pickup_list = [f"{o.so_num} / {o.plts} plts / {o.customer_name}" for o in pickup_orders]
            else:
                pickup_list = ["N/A"]
            if current_date.weekday() == 0:
                pickup_list.append("Office Depot")

            # 编号列表
            c.setFont("Helvetica", item_font_size)
            for entry in pickup_list:
                if y < 1 * inch:
                    c.showPage()
                    y = top_margin
                    c.setFont("Helvetica", item_font_size)
                c.drawString(left_margin + 10, y, f"- {entry}")
                y -= line_height

            y -= line_height  # 每天之间多留一行间隔
            printed_days += 1

        current_date += timedelta(days=1)

    c.save()
    return response

def print_weekly_pickuplist(start_date):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="weekly_pickup_report.pdf"'

    c = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    left_margin = 1 * inch

    for i in range(7):  # 接下来 7 天
        target_date = start_date + timedelta(days=i)
        weekday_str = target_date.strftime('%A').upper()
        date_str = target_date.strftime('%m/%d')

        pickup_orders = RMOrder.objects.filter(
            pickup_date=target_date.date()
        ).exclude(Q(customer_name="4") | Q(is_canceled=True))

        pickup_numbers = [str(order.so_num) for order in pickup_orders]
        if not pickup_numbers:
            pickup_numbers = ["N/A"]
        if target_date.weekday() == 0:
            pickup_numbers.append("Office Depot")

        # 页面起始 Y 坐标
        y = height - 2 * inch

        # 日期标题
        c.setFont("Helvetica-Bold", 48)
        date_text = f"{weekday_str}   {date_str}"
        c.drawString(left_margin, y, date_text)

        text_width = c.stringWidth(date_text, "Helvetica-Bold", 48)
        underline_y = y - 5
        c.setLineWidth(3)
        c.line(left_margin, underline_y, left_margin + text_width, underline_y)

        # Pickup 标签
        y -= 60
        c.setFont("Helvetica", 30)
        c.drawString(left_margin, y, "PICKUPS:")

        # 列表
        y -= 50
        for num in pickup_numbers:
            if y < 1.5 * inch:  # 页面到底了，加新页
                c.showPage()
                y = height - 2 * inch
                c.setFont("Helvetica-Bold", 48)
                c.drawString(left_margin, y, f"{weekday_str}   {date_str}")
                y -= 110  # 留出 Pickup 标签空间
                c.setFont("Helvetica", 30)
            c.drawString(left_margin, y, num)
            y -= 50

        c.showPage()  # 每天单独一页

    c.save()
    return response

def print_containerid_lot(c, so_num, label_count, container_id, lot_number, current_date):
    try:
        label_count = int(label_count) if label_count is not None else 0
    except ValueError:
        label_count = 10  # Handle invalid input gracefully

    # Set font
    c.setFont("Helvetica-Bold", constants_address.FONT_SIZE)
    
    y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

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
                text_y = y_position  - (constants_address.LABEL_HEIGHT / 2) - 0
                
                # Set font and draw text
                c.setFont("Helvetica-Bold", constants_address.FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if constants_address.DRAW_BORDERS:
                    c.rect(x, y_position - constants_address.LABEL_HEIGHT, constants_address.LABEL_WIDTH, constants_address.LABEL_HEIGHT)

                # Add smaller text for container_id, lot_number, and current date below the label
                c.setFont("Helvetica", constants_address.FONT_SIZE_Lot)  # Smaller font size for the new text
                text_y_small = text_y - 30  # Position for the smaller text below the main label
                c.drawCentredString(text_x, text_y_small, f"{container_id}    {current_date}")
                c.drawCentredString(text_x, text_y_small - 20, f"Lot: {lot_number}")
    
                label_count -= 1  # Reduce remaining label count

            y_position -= constants_address.LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

def converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate):
    # 构建新的PDF文件（使用 reportlab）
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4    

    y = height - 80
    y_offset = 30  # ✅ 向下移动整体内容高度

    # ✅ Logo 和标题
    if os.path.exists(constants_address.SSA_LOGO_PATH):
        c.drawImage(constants_address.SSA_LOGO_PATH, 40, y - 60, width=140, height=80, preserveAspectRatio=True, mask='auto')
    
    # c.setFont("Helvetica-Bold", 20)
    # c.drawString(220, y, "Packing Slip")
    # y -= 80
    # c.setFont("Helvetica", 12)

    # === Helper function to draw section headers ===
    def draw_section_header(title, x, y):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, title)
        c.setLineWidth(0.5)
        c.line(x, y - 2, x + 150, y - 2)
        c.setFont("Helvetica", 11)

    def draw_address_block(c, label, address_lines, x, y_start):
        draw_section_header(label, x, y_start)
        line_height = 15
        y = y_start - line_height
        for line in address_lines:
            c.drawString(x, y, line)
            y -= line_height

    ADDRESS_MAPPING = {
        "SHIPPER": constants_address.SSA_ADDRESS,
        "CONSIGNEE": constants_address.CONSIGNEE
    }

    invoice_prefix = {
        "Speedier": "OS",
        "Trans Knights": "OT"
    }.get(container.customer.name, "")  # 默认为空字符串
    full_invoice_no = f"{invoice_prefix}{container.invoice_id}"

    # --- Shipper Info ---
    draw_address_block(c, "SHIPPER:", ADDRESS_MAPPING["SHIPPER"], 40, height - 130 - y_offset)

    # --- Invoice Box ---
    # c.rect(350, height - 160 - y_offset, 160, 70)
    invoice_date = datetime.today()
    due_date = invoice_date + timedelta(days=30)
    draw_section_header("INVOICE:", 360, height - 75 - y_offset)
    c.drawString(360, height - 90 - y_offset, f"INVOICE NO.: {full_invoice_no}")
    c.drawString(360, height - 105 - y_offset, f"INVOICE DATE: {invoice_date.strftime('%m/%d/%Y')}")
    c.drawString(360, height - 120 - y_offset, f"DUE DATE: {due_date.strftime('%m/%d/%Y')}")

    # --- Ship Info ---
    draw_section_header("SHIP INFO:", 360, height - 145 - y_offset)
    c.drawString(360, height - 160 - y_offset, f"SHIP DATE: {container.delivery_date.strftime('%m/%d/%Y')}")
    c.drawString(360, height - 175 - y_offset, f"BILL OF LADING: {container.container_id}")
    c.drawString(360, height - 190 - y_offset, f"REFERENCE NO: {container.refnumber}")

    # --- Bill To ---
    bill_to_type = container.customer.name
    bill_to_address = constants_address.address_mapping.get(bill_to_type, ["Unknown Address"])
    draw_address_block(c, "BILL TO:", bill_to_address, 40, height - 220 - y_offset)

    # --- Consignee ---
    draw_address_block(c, "CONSIGNEE:", ADDRESS_MAPPING["CONSIGNEE"], 360, height - 220 - y_offset)

    # --- Table Data ---
    # 初始化总金额
    total = Decimal("0.00")

    # 表格初始结构
    data = [
        ["DESCRIPTION", "UNITS", "RATE", "CHARGES"],
        ["Drayage (FSC all included)", "", "", ""],
        ["Chassis", "", "", ""],
        ["Chassis split", "", "", ""],
        ["OW TICKET", "", "", ""],
        ["Pre-pull", "", "", ""],
        ["Yard storage", "", "", ""],
        ["Empty container relocate/SOC", "", "", ""],
        ["Flip", "", "", ""],
        ["Rail storage", "", "", ""],
        ["Detention", "", "", ""],
        ["Drop Off", "", "", ""],
        ["Dry Run", "", "", ""],
        ["", "", "TOTAL", ""]
    ]    

    # 建立描述到行的映射，方便更新
    desc_to_row = {row[0]: row for row in data[1:-1]}  # 跳过表头和TOTAL

    # 遍历金额项目并填入表格
    for raw_desc, units, rate, charge in amount_items:
        mapped_desc = constants_address.description_mapping.get(raw_desc, raw_desc)
        row = desc_to_row.get(mapped_desc)
        if not row:
            continue

        # 默认处理
        display_units = f"{float(units):.1f}" if units else ""
        display_rate = f"${rate:,.2f}" if rate else ""
        display_charge = f"${charge:,.2f}" if charge else ""

        # 自定义逻辑
        if mapped_desc == "Drayage (FSC all included)":
            charge += 30
            new_rate = charge
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Chassis":
            orig_units = float(units or 0)
            new_units = orig_units if orig_units > 2 else 2
            new_rate = 40
            charge = new_units * new_rate
            display_units = f"{new_units:.1f}"
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Chassis split":
            orig_units = float(units or 0)
            new_units = orig_units if orig_units > 2 else 2
            new_rate = 70
            charge = new_units * new_rate
            display_units = f"{new_units:.1f}"
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Pre-pull":
            orig_units = float(units or 0)
            new_rate = 150
            charge = orig_units * new_rate
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Yard storage":
            orig_units = float(units or 0)
            new_rate = 45
            charge = orig_units * new_rate
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"
    

        # 写入表格
        row[1] = display_units
        row[2] = display_rate
        row[3] = display_charge

        total += Decimal(str(charge))

    print("isEmptyContainerRelocate: ", isEmptyContainerRelocate)
    if isEmptyContainerRelocate == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Empty container relocate/SOC")
        if relocate_row:
            relocate_units = "1.0"
            relocate_rate = 150
            relocate_charge = relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    # 填入总金额
    data[-1][-1] = f"${total:,.2f}"

    # 创建表格
    table = Table(data, colWidths=[220, 80, 80, 120])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),   # 表头背景色
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),       # 表格线
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEADING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),              # 增加下边距
        ("TOPPADDING", (0, 0), (-1, -1), 6),                 # 增加上边距
        ("BACKGROUND", (-2, -1), (-1, -1), colors.lightgrey),  # 总计背景色
    ]))

    # 绘制表格
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, height - 650 - y_offset)

    # 关闭 canvas 并写入 buffer
    c.save()
    buffer.seek(0)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, new_filename)

    # 写入 PDF 文件
    with open(output_path, "wb") as f:
        f.write(buffer.read())

def print_checklist_template(title,filename, contentTitle, container_info,can_liner_details, note_lines, issign = False):
  
    # 创建 PDF 文件
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(title)
    width, height = letter

    # 设置标题居中
    c.setFont("Helvetica-Bold", 16)
    title = contentTitle
    c.drawCentredString(width / 2, height - 40, title)

    # 内容起始位置
    x_label = 60         # 标签起始 x
    x_line_start = 180   # 填空线起始 x
    line_length = 340    # 下划线长度
    y = height - 80     # 初始 y 坐标
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
            for i, note in enumerate(constants_address.note_lines):
                wrapped_lines = textwrap.wrap(note, width=constants_address.max_line_width)
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
        wrapped_lines = textwrap.wrap(note, width=constants_address.max_line_width)
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

