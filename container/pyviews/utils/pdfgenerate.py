import os
import re
import textwrap
from datetime import datetime, timedelta
from decimal import Decimal

import fitz  # PyMuPDF 解析 PDF

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.platypus import Image, Spacer, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import inch

from container.models import RMOrder, Container
from container.constants import constants_address
from container.constants.constants_address import font_Helvetica, font_Helvetica_Bold

from .pdf_utils import create_pdf_canvas, finalize_pdf_and_response
from .file_utils import get_media_path, ensure_dir_exists

# PDF 解析函数
def extract_text_from_pdf(full_path):
    """ 解析 PDF 并提取文本 """
    # full_path = get_media_path(pdf_path)
    # print("edit_invoice_file extract_text_from_pdf: ",full_path)

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
    title_font_size = 20

    # 查询 RMOrder 表中的 Pickup No.
    pickup_orders = RMOrder.objects.filter(
        pickup_date=target_date.date()
    ).exclude(Q(customer_name="4") | Q(customer_name="19")| Q(is_canceled=True))
    pickup_numbers = [f"{o.so_num} / {o.plts} plts / {o.customer_name}" for o in pickup_orders]

    delivery_container = Container.objects.filter(delivery_date=target_date.date())
    delivery_numbers = [f"{o.container_id} / {o.plts} plts" for o in delivery_container]

    # 如果没有数据，显示占位
    if not pickup_numbers:
        pickup_numbers = ["N/A"]
    if not delivery_numbers:
        delivery_numbers = ["N/A"]

    # PDF 文件路径（临时文件）
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        f"pickup_today_{target_date.strftime('%Y%m%d')}.pdf"
    )
    ensure_dir_exists(os.path.dirname(pdf_path))

    # 生成 PDF
    c, pagesize, inch, ImageReader = create_pdf_canvas(pdf_path)
    width, height = pagesize

    left_margin = 1 * inch
    y = height - 2 * inch

    # 日期行样式
    c.setFont(constants_address.font_Helvetica_Bold, 48)
    date_text = f"{weekday_str}   {date_str}"
    c.drawString(left_margin, y, date_text)
    text_width = c.stringWidth(date_text, constants_address.font_Helvetica_Bold, 48)
    underline_y = y - 5  # 稍微低一点以贴近文字底部
    c.setLineWidth(3)
    c.line(left_margin, underline_y, left_margin + text_width, underline_y)

    # Pickup 标签
    y -= 60
    c.setFont(constants_address.font_Helvetica, 30)
    c.drawString(left_margin, y, "PICKUPS:")
    y -= 30
    c.setFont(constants_address.font_Helvetica, title_font_size)
    for num in pickup_numbers:
        c.drawString(left_margin, y, num)
        y -= 30

    # Delivery 标签
    if not delivery_numbers:
        delivery_numbers = ["N/A"]
    y -= 30
    c.setFont(constants_address.font_Helvetica, 30)
    c.drawString(left_margin, y, "Delivery:")
    y -= 30
    c.setFont(constants_address.font_Helvetica, title_font_size)
    for num in delivery_numbers:
        c.drawString(left_margin, y, num)
        y -= 30

    return finalize_pdf_and_response(c, pdf_path)

def print_weekly_pickuplist_on_one_page(start_date):
    # PDF 文件路径（临时文件）
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        f"pickup_week_{start_date.strftime('%Y%m%d')}.pdf"
    )
    ensure_dir_exists(os.path.dirname(pdf_path))

    c, pagesize, inch, ImageReader = create_pdf_canvas(pdf_path)
    width, height = pagesize

    # 配置
    left_margin = 1 * inch
    top_margin = height - 1 * inch
    line_height = 24
    title_font_size = 24
    item_font_size = 16

    # 标题
    c.setFont(constants_address.font_Helvetica_Bold, title_font_size + 10)
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

            c.setFont(constants_address.font_Helvetica_Bold, title_font_size)
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
            c.setFont(constants_address.font_Helvetica, item_font_size)
            for entry in pickup_list:
                if y < 1 * inch:
                    c.showPage()
                    y = top_margin
                    c.setFont(constants_address.font_Helvetica, item_font_size)
                c.drawString(left_margin + 10, y, f"- {entry}")
                y -= line_height

            y -= line_height  # 每天之间多留一行间隔
            printed_days += 1

        current_date += timedelta(days=1)

    return finalize_pdf_and_response(c, pdf_path)

def print_weekly_droplist_on_one_page(start_date):
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        f"droplist_week_{start_date.strftime('%Y%m%d')}.pdf"
    )
    ensure_dir_exists(os.path.dirname(pdf_path))

    containers = Container.objects.filter(Q(is_updateInventory = False)).order_by('delivery_date')

    c, pagesize, inch, ImageReader = create_pdf_canvas(pdf_path)
    width, height = pagesize

    # 配置
    left_margin = 1 * inch
    top_margin = height - 1 * inch
    line_height = 24
    title_font_size = 24
    item_font_size = 16

    # 标题
    c.setFont(constants_address.font_Helvetica_Bold, title_font_size + 10)
    c.drawCentredString(width / 2, height - 1 * inch, "WEEKDAY DROP LIST")

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

            c.setFont(constants_address.font_Helvetica_Bold, title_font_size)
            c.drawString(left_margin, y, header_text)
            y -= line_height

            pickup_orders = containers.filter(
                delivery_date=current_date.date()
            )

            if pickup_orders.exists():
                pickup_list = [f"{o.container_id} / {o.plts} plts / {o.customer.name} / {o.inboundCategory.Type}" for o in pickup_orders]
            else:
                pickup_list = ["N/A"]

            # 编号列表
            c.setFont(constants_address.font_Helvetica, item_font_size)
            for entry in pickup_list:
                if y < 1 * inch:
                    c.showPage()
                    y = top_margin
                    c.setFont(constants_address.font_Helvetica, item_font_size)
                c.drawString(left_margin + 10, y, f"- {entry}")
                y -= line_height

            y -= line_height  # 每天之间多留一行间隔
            printed_days += 1

        current_date += timedelta(days=1)

    return finalize_pdf_and_response(c, pdf_path)

def print_containerid_lot(
    c,
    so_num,
    container_id,
    lot_number,
    current_date,
    spec,
    showLot=True,
    start_index=0,
    smallFont=False,
):
    font_size = (
        constants_address.FONT_SIZE_SMALL
        if smallFont
        else constants_address.FONT_SIZE
    )

    c.setFont(constants_address.font_Helvetica_Bold, font_size)

    # ⭐ 全局顺序 → 当前页位置
    pos = start_index % 10
    row = pos // 2
    col = pos % 2

    x = constants_address.MARGIN_LEFT + col * constants_address.LABEL_WIDTH
    y_top = (
        constants_address.PAGE_HEIGHT
        - constants_address.MARGIN_TOP
        - row * constants_address.LABEL_HEIGHT
    )

    text_x = x + constants_address.LABEL_WIDTH / 2
    text_y = y_top - constants_address.LABEL_HEIGHT / 2

    # 主标题
    c.setFont(constants_address.font_Helvetica_Bold, font_size)
    c.drawCentredString(text_x, text_y, so_num)

    if constants_address.DRAW_BORDERS:
        c.rect(
            x,
            y_top - constants_address.LABEL_HEIGHT,
            constants_address.LABEL_WIDTH,
            constants_address.LABEL_HEIGHT,
        )

    # 底部信息
    c.setFont(constants_address.font_Helvetica, constants_address.FONT_SIZE_Lot)
    c.drawCentredString(
        text_x,
        text_y - 30,
        f"{container_id}    {current_date}",
    )

    if showLot:
        c.drawCentredString(
            text_x,
            text_y - 50,
            f"Lot: {lot_number}   Qty: {spec}",
        )


def converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate, isClassisSplit, isPrepull):
    
    ensure_dir_exists(output_dir)
    output_path = os.path.join(output_dir, new_filename)
    c, (width, height), inch, ImageReader = create_pdf_canvas(
        file_path=output_path,
        pagesize=A4
    )

    y = height - 80
    y_offset = 30  # ✅ 向下移动整体内容高度

    # ✅ Logo 和标题
    if os.path.exists(constants_address.SSA_LOGO_PATH):
        c.drawImage(constants_address.SSA_LOGO_PATH, 40, y - 60, width=140, height=80, preserveAspectRatio=True, mask='auto')
    
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
    draw_section_header(c, "INVOICE:", 360, height - 75 - y_offset)
    c.drawString(360, height - 90 - y_offset, f"INVOICE NO.: {full_invoice_no}")
    c.drawString(360, height - 105 - y_offset, f"INVOICE DATE: {invoice_date.strftime('%m/%d/%Y')}")
    c.drawString(360, height - 120 - y_offset, f"DUE DATE: {due_date.strftime('%m/%d/%Y')}")

    # --- Ship Info ---
    draw_section_header(c, "SHIP INFO:", 360, height - 145 - y_offset)
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
        ["Overweight", "", "", ""],
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
        # print('decp: ',raw_desc)
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
            base_charge = Decimal(str(charge or 0))
            fsc = Decimal("30.00")
            final_charge = base_charge + fsc

            display_units = "1.0"      
            display_rate = f"${final_charge:,.2f}"
            display_charge = f"${final_charge:,.2f}"
            charge = final_charge

        elif mapped_desc == "Chassis":
            orig_units = float(units or 0)
            new_units = orig_units if orig_units > 2 else 2
            new_rate = constants_address.Chassis_rate
            charge = new_units * new_rate
            display_units = f"{new_units:.1f}"
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Chassis split":
            orig_units = float(units or 0)
            new_units = orig_units if orig_units > 2 else 2
            new_rate = constants_address.ClassisSplit_rate
            charge = new_units * new_rate
            display_units = f"{new_units:.1f}"
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Pre-pull":
            orig_units = float(units or 0)
            new_rate = constants_address.Pre_pull_rate
            charge = orig_units * new_rate
            display_rate = f"${new_rate:,.2f}"
            display_charge = f"${charge:,.2f}"

        elif mapped_desc == "Yard storage":
            orig_units = float(units or 0)
            new_rate = constants_address.Yard_storage_rate
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
            relocate_rate = constants_address.EmptyContainerRelocate_rate
            relocate_charge = relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    print("isClassisSplit: ", isClassisSplit)
    if isClassisSplit == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Chassis split")
        if relocate_row:
            relocate_units = 2
            relocate_rate = constants_address.ClassisSplit_rate
            relocate_charge = relocate_units * relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    print("isPrepull: ", isPrepull)
    if isPrepull == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Pre-pull")
        if relocate_row:
            relocate_units = 1
            relocate_rate = constants_address.Pre_pull_rate
            relocate_charge = relocate_units * relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

        extra_row = desc_to_row.get("Yard storage") 
        if extra_row:
            extra_units = 1
            extra_rate = constants_address.Yard_storage_rate
            extra_charge = extra_units * extra_rate
            extra_row[1] = extra_units
            extra_row[2] = f"${extra_rate:,.2f}"
            extra_row[3] = f"${extra_charge:,.2f}"

            total += Decimal(str(extra_charge))

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
    table.drawOn(c, 40, height - 690 - y_offset)



    # ✅ 统一交给 finalize_pdf_and_response
    return finalize_pdf_and_response(
        canvas_obj=c,
        file_path=output_path,
        filename=new_filename
    )

def print_checklist_template(c,pagesize, title,filename, contentTitle, container_info,can_liner_details, note_lines, issign = False):
  
    # 创建 PDF 文件
    c.setTitle(title)
    width, height = pagesize

    # 设置标题居中
    c.setFont(constants_address.font_Helvetica_Bold, 16)
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
    c.setFont(constants_address.font_Helvetica, 12)

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

        x_line_1 = 80
        x_line_2 = 210
        x_line_3 = 290
        x_line_4 = 370

        if key == "Total Pallets":
            # 插入子表头
            c.setFont(constants_address.font_Helvetica_Bold, 11)
            c.drawString(x_sub_table + 0, y, "Size")
            c.drawString(x_sub_table + x_line_1 + 10, y, "Name")
            c.drawString(x_sub_table + x_line_2, y, "CTNS")
            c.drawString(x_sub_table + x_line_3, y, "PLTS")
            c.drawString(x_sub_table + x_line_4, y, "Case")
            y -= 20

            c.setFont(constants_address.font_Helvetica, 11)
            for item in can_liner_details:
                if y < 100:   # 👈 页面安全底线
                    c.showPage()
                    c.setFont(constants_address.font_Helvetica, 11)
                    y = height - 80

                c.drawString(x_sub_table, y, item["Size"])

                c.drawString(x_sub_table + x_line_1 + 10, y, item["Name"])
                c.line(x_sub_table + x_line_1 - 10, y - 2, x_sub_table + x_line_1 + 100, y - 2)  # Name 下划线

                c.drawString(x_sub_table + x_line_2 + 10, y, item["Qty"])
                c.line(x_sub_table + x_line_2 - 10, y - 2, x_sub_table + x_line_2 + 50, y - 2)  # QTY 下划线

                c.drawString(x_sub_table + x_line_3 + 10, y, item["PLTS"])
                c.line(x_sub_table + x_line_3 - 10, y - 2, x_sub_table + x_line_3 + 50, y - 2)  # QTY 下划线

                c.drawString(x_sub_table + x_line_4 + 10, y, item["Case"])
                c.line(x_sub_table + x_line_4 - 10, y - 2, x_sub_table + x_line_4 + 50, y - 2)  # Case 下划线

                y -= 20

            # 在子表格之后添加三组文字和空行
            y -= 10
            line_spacing_extra = 35  # 每组行距
            

            c.setFont(constants_address.font_Helvetica, 12)
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

                c.setFont(constants_address.font_Helvetica, 12)
                for i, label in enumerate(signature_labels):
                    x_pos = signature_x_start + i * signature_spacing
                    c.drawString(x_pos, signature_y, f"{label}:")
                    c.line(x_pos + 60, signature_y, x_pos + 150, signature_y)  # 签名字下划线

                    c.drawString(x_pos, signature_y - 30, "Date:")
                    c.line(x_pos + 60, signature_y - 30, x_pos + 150, signature_y - 30)  # 日期下划线

def print_mcd_template(c, x, y, width, table_data):

    table = Table(
        table_data,
        colWidths=[100, 300, 100],
        rowHeights=50
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), constants_address.font_Helvetica_Bold),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
    ]))

    table.wrapOn(c, width, 800)
    table.drawOn(c, x, y)


def print_bol_template(title,filename, contentTitle, container_info, order_details, certification_notes, canvas_obj, pagesize):
    # 创建 PDF 文件
    # 使用传入的 canvas 或创建新的
    c = canvas_obj
    c.setTitle(title)
    width, height = pagesize

    # 设置标题居中
    c.setFont(constants_address.font_Helvetica_Bold, 16)
    title = contentTitle
    c.drawCentredString(width / 2, height - 80, title)

    # 内容起始位置
    x_label = 60         # 标签起始 x
    line_length = 210    # 下划线长度
    y = height - 120     # 初始 y 坐标
    line_spacing = 30
    x_sub_table = 100   #子表起始点

    # 设置正文字体
    c.setFont(constants_address.font_Helvetica, 12)

    regular_font = constants_address.font_Helvetica
    bold_font = constants_address.font_Helvetica_Bold
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
                    y -= 18
                    items_Y = y
                else:
                    y -= 14  # 多行地址行间距
        # 右侧其他Number
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

    c.setFont(constants_address.font_Helvetica, 12)
    for i, label in enumerate(signature_labels):
        x_pos = signature_x_start + i * signature_spacing
        c.drawString(x_pos, signature_y, f"{label}:")
        c.line(x_pos + 60, signature_y, x_pos + 150, signature_y)  # 签名字下划线

        c.drawString(x_pos, signature_y - 30, "Date:")
        c.line(x_pos + 60, signature_y - 30, x_pos + 150, signature_y - 30)  # 日期下划线

def converter_metal_invoice(container, amount_items, output_dir, new_filename, isInvoice, discount_percent=0):
    
    ensure_dir_exists(output_dir)
    output_path = os.path.join(output_dir, new_filename)
    c, (width, height), inch, ImageReader = create_pdf_canvas(
        file_path=output_path,
        pagesize=A4
    )

    y = height - 80
    y_offset = 30  # ✅ 向下移动整体内容高度

    isJustTableOrder = False # True, just print order table

    # ✅ Logo 和标题
    if not isJustTableOrder:
        if os.path.exists(constants_address.SSA_LOGO_PATH):
            c.drawImage(constants_address.SSA_LOGO_PATH, 40, y - 60, width=140, height=80, preserveAspectRatio=True, mask='auto')

    # ---- Center Title (Invoice / Order) ----
    title_text = "Invoice" if isInvoice == 1 else "Order"

    c.setFont(constants_address.font_Helvetica_Bold, 20)
    c.drawCentredString(width / 2, height - 101, title_text)

    ADDRESS_MAPPING = {
        "SHIPPER": constants_address.SSA_ADDRESS,
        "CONSIGNEE": constants_address.CONSIGNEE
    }

    invoice_prefix = {
        "Speedier": "OS",
        "Trans Knights": "OT"
    }.get(container.so_num, "")  # 默认为空字符串
    full_invoice_no = f"{invoice_prefix}{container.so_num}"

    if not isJustTableOrder:
        # --- Shipper Info ---
        draw_address_block(c, "SHIPPER:", ADDRESS_MAPPING["SHIPPER"], 40, height - 130 - y_offset)

        # --- Invoice Box ---
        invoice_date = datetime.today()
        due_date = invoice_date + timedelta(days=30)

        invoicenum_x_pos = 390
        draw_section_header(c, "INVOICE:", invoicenum_x_pos, height - 130 - y_offset)        
        c.drawString(invoicenum_x_pos, height - 145 - y_offset, f"INVOICE NO.: {full_invoice_no}")
        c.drawString(invoicenum_x_pos, height - 160 - y_offset, f"INVOICE DATE: {invoice_date.strftime('%m/%d/%Y')}")
        c.drawString(invoicenum_x_pos, height - 175 - y_offset, f"DUE DATE: {due_date.strftime('%m/%d/%Y')}")

        # --- Bill To ---
        bill_to_address = container.bill_to
        draw_address_block2(c, "BILL TO:", container.bill_to, 40, height - 220 - y_offset)

        # --- Consignee ---
        draw_address_block2(c, "SHIP TO:", container.ship_to, invoicenum_x_pos, height - 220 - y_offset)

    # 预估地址块高度（每行约 14，高度预留更安全）
    address_block_height = 100
    if isJustTableOrder:
        # ✅ Order：没有地址块，直接靠近标题
        table_start_y = height - 140
    else:
        # Invoice：有地址块，稍微往下
        table_start_y = height - 160 - y_offset - address_block_height

    # --- Table Data ---
    # 初始化总金额
    total = Decimal("0.00")

    # --- Table Data (Dynamic Version) ---
    # table_data = [["ITEM", "DESCRIPTION", "QTY", "Unit Cost", "CHARGES"]]
    if isInvoice == 1:
        table_data = [["ITEM", "DESCRIPTION", "QTY", "Unit Cost", "CHARGES"]]
    else:
        table_data = [["ITEM", "DESCRIPTION", "QTY", "Price"]]
    total = Decimal("0.00")

    for item, desc, units, rate, charge in amount_items:
        display_item = str(item) if item else ""
        display_desc = desc
        display_units = f"{units:.0f}" if units else ""
        
        if isInvoice == 1:
            display_rate = f"${rate:,.2f}" if rate else ""
            display_charge = f"${charge:,.2f}" if charge else ""

            table_data.append([
                display_item,
                display_desc,
                display_units,
                display_rate,
                display_charge
            ])

            total += Decimal(str(charge or 0))
        else:
            # ✅ Order：Price 列存在，但永远空
            table_data.append([
                display_item,
                display_desc,
                display_units,
                ""
            ])


    # --- Build Table ---
    if isInvoice == 1:
        table = Table(table_data, colWidths=[80, 290, 35, 55, 60])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),

            # ✅ 行高关键
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
    else:
        
        table = Table(table_data, colWidths=[100, 300, 60, 60])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),  # 显示边框
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),

            # ✅ 行高关键
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

    table.wrapOn(c, width, height)

    TABLE_TOP_GAP = -10 # 值越大，越靠上
    table_top_y = table_start_y + TABLE_TOP_GAP   # 表头位置固定
    table_height = table._height  # 表格真实高度
    table.drawOn(c, 40, table_top_y - table_height)
    table_bottom_y = table_top_y  - table_height

    # Amount summary block
    if isInvoice == 1:
        summary_x = 360   # 靠右
        line_height = 16
        
        summary_y = table_bottom_y - 20

        c.setFont(constants_address.font_Helvetica_Bold, 11)

        # discount
        discount_rate = Decimal(discount_percent) / Decimal("100")
        discount_amount = (total * discount_rate).quantize(Decimal("0.01"))
        discounted_subtotal = (total - discount_amount).quantize(Decimal("0.01"))

        # 准备数值
        tax_amount = (discounted_subtotal  * constants_address.Tax_rate).quantize(Decimal("0.01"))
        grand_total = (discounted_subtotal  + tax_amount).quantize(Decimal("0.01"))
        credit_total = (grand_total * constants_address.Credit_rate).quantize(Decimal("0.01"))

        # Subtotal
        subtotal_x_pos = 200
        c.drawRightString(summary_x + subtotal_x_pos, summary_y, f"Subtotal:   ${total:,.2f}")
        summary_y -= line_height

        # Discount（只有有折扣才显示）
        if discount_percent > 0:
            c.drawRightString(
                summary_x + subtotal_x_pos,
                summary_y,
                f"Discount ({discount_percent}%):  -${discount_amount:,.2f}"
            )
            summary_y -= line_height

            c.drawRightString(
                summary_x + subtotal_x_pos,
                summary_y,
                f"Discounted Subtotal:   ${discounted_subtotal:,.2f}"
            )
            summary_y -= line_height * 1.3

        # Tax
        c.drawRightString(summary_x + subtotal_x_pos, summary_y, f"Tax (8.25%):   ${tax_amount:,.2f}")
        summary_y -= line_height* 1.3

        # Total
        c.drawRightString(summary_x + subtotal_x_pos, summary_y, f"Total:   ${grand_total:,.2f}")
        summary_y -= line_height

        # Credit card total 3%
        c.drawRightString(summary_x + subtotal_x_pos, summary_y, f"Credit Card (3%):   ${credit_total:,.2f}")
        summary_y -= line_height

    # --- 在表格之后插入说明文字 ---
    # y_text = 180   # 根据表格位置调整，越大越靠上
    # ===== 表格底部基准 =====
    left_text_y = table_bottom_y - 20

    if not isJustTableOrder:
        # 2 行：靠左显示
        c.setFont(constants_address.font_Helvetica, 10)
        c.drawString(40, left_text_y, "*Products availability and lead time may change")
        c.drawString(40, left_text_y - 15, "*SSA reserve the right to change pricing and terms without notice")

        # 3 行：靠左显示（电话、邮箱、公司名）
        c.drawString(40, left_text_y - 45, "If you have questions concerning this invoice, contact us")
        c.drawString(40, left_text_y - 60, "Phone: (708) 882-1188")
        c.drawString(40, left_text_y - 75, "Email: info@securesourceamerica.com")

        # 3 行：居中显示（电话、邮箱、公司名）
        # center_x = width / 2
        # c.drawCentredString(center_x, y_text - 45, "If you have questions concerning this invoice, contact us")
        # c.drawCentredString(center_x, y_text - 60, "Phone: (708) 882-1188")
        # c.drawCentredString(center_x, y_text - 75, "Email: info@securesourceamerica.com")


    # ✅ 统一交给 finalize_pdf_and_response
    return finalize_pdf_and_response(
        canvas_obj=c,
        file_path=output_path,
        filename=new_filename
    )

# === Helper function to draw section headers ===
def draw_section_header(c, title, x, y):
    c.setFont(constants_address.font_Helvetica_Bold, 11)
    c.drawString(x, y, title)
    c.setLineWidth(0.5)
    c.line(x, y - 2, x + 150, y - 2)
    c.setFont(constants_address.font_Helvetica, 11)

def draw_address_block(c, label, address_lines, x, y_start):
    draw_section_header(c, label, x, y_start)

    line_height = 15
    y = y_start - line_height
    for line in address_lines:
        c.drawString(x, y, line)
        y -= line_height

def draw_address_block2(c, title, text, x, y):
    draw_section_header(c, title, x, y)

    c.setFont(constants_address.font_Helvetica, 10)

    # ---- 清洗不可见 / 非法换行字符 ----
    clean_text = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u2028", "\n")
        .replace("\u2029", "\n")
    )

    # 移除其他不可打印字符（保留正常文字）
    clean_text = re.sub(r"[^\x20-\x7E\n]", "", clean_text)

    # 处理多行地址
    lines = clean_text.split("\n")

    offset = 15
    for line in lines:
        c.drawString(x, y - offset, line)
        offset += 15