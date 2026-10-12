import os
import re
import textwrap
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import pymupdf

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse

from reportlab.lib.pagesizes import letter
from reportlab.platypus import Image, Spacer, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle 
from reportlab.lib.enums import TA_LEFT 
from xml.sax.saxutils import escape

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

    doc = pymupdf.open(full_path)
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
            ).filter(Q(customer_name__classification="Rimei") | Q(is_canceled=True))
            # ).exclude(Q(customer_name="4") | Q(customer_name="19") | Q(is_canceled=True))

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

def print_containerid_lot(c,so_num,container_id,lot_number,current_date,spec,showLot=True,start_index=0,smallFont=False):
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


def converter_customer_invoice(container, amount_items, output_dir, new_filename, isEmptyContainerRelocate, isClassisSplit, isPrepull,isFlip,isDetention,isOverweight,israilstorage):
    
    ensure_dir_exists(output_dir)
    output_path = os.path.join(output_dir, new_filename)
    c, (width, height), inch, ImageReader = create_pdf_canvas(
        file_path=output_path,
        pagesize=letter
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
    invoice_date = container.invoice_date
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
        ["Lift Fee", "", "", ""],
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

    if isFlip == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Flip")
        if relocate_row:
            relocate_units = 1
            relocate_rate = constants_address.Flip_rate
            relocate_charge = relocate_units * relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    if isDetention == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Detention")
        if relocate_row:
            relocate_units = 1
            relocate_rate = constants_address.Detention_rate
            relocate_charge = relocate_units * relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    if isOverweight == "1":
        # 找到对应行
        relocate_row = desc_to_row.get("Overweight")
        if relocate_row:
            relocate_units = 1
            relocate_rate = constants_address.Overweight_rate
            relocate_charge = relocate_units * relocate_rate
            relocate_row[1] = relocate_units
            relocate_row[2] = f"${relocate_rate:,.2f}"
            relocate_row[3] = f"${relocate_charge:,.2f}"
            total += Decimal(str(relocate_charge))

    if israilstorage == "1":
        relocate_row = desc_to_row.get("Rail storage")
        if relocate_row:
            relocate_units = 1
            relocate_rate = constants_address.Railstorage_rate
            relocate_charge = relocate_units * relocate_rate
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
    table.drawOn(c, 40, height - 710 - y_offset)



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

# sub fruction
# Print Order BOL
# Print forklift BOL
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
        text = text.replace("\t", "")
        # c.drawString(x, y, repr(text))
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
    signature_labels = ["Shipper", "Carrier","Consignee"]
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

# sub function
# Print customer shipout BOL
def print_shipout_bol_template(title,filename, contentTitle, container_info, order_details, certification_notes, canvas_obj, pagesize):
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

    table_headers = ["Name", "Description", "Qty",]
    col_widths = [120, 350, 60]
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
            item['ShortName'],
            item['Name'],
            item['Qty'],
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
    signature_labels = ["Shipper", "Carrier","Consignee"]
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

def converter_metal_invoice(container, amount_items, output_dir, new_filename, isInvoice, discount_percent=0, no_tax=False):
    
    ensure_dir_exists(output_dir)

    output_path = os.path.join(output_dir, new_filename)

    c, (width, height), inch, ImageReader = create_pdf_canvas(
        file_path=output_path,
        pagesize=letter
    )

    # ---------------------------------------------------------
    # Basic settings
    # ---------------------------------------------------------

    isJustTableOrder = False

    y = height - 50
    y_offset = 60

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------

    draw_metal_invoice_header(
        c=c,
        container=container,
        isInvoice=isInvoice,
        width=width,
        height=height,
        y=y,
        y_offset=y_offset,
        isJustTableOrder=isJustTableOrder
    )

    # ---------------------------------------------------------
    # Address / Order Information
    # ---------------------------------------------------------

    term_days = container.customer_name.term

    draw_metal_invoice_information(
        c=c,
        container=container,
        isInvoice=isInvoice,
        width=width,
        height=height,
        y_offset=y_offset,
        term_days=term_days,
        isJustTableOrder=isJustTableOrder
    )

    # ---------------------------------------------------------
    # Product Table
    # ---------------------------------------------------------

    table_start_y = get_metal_table_start_y(
        height=height,
        y_offset=y_offset,
        isJustTableOrder=isJustTableOrder
    )

    if isInvoice == 1 or isInvoice == 2:
        draw_packing_table(
            c=c,
            terms=term_days,
            start_y=table_start_y,
            width=width,
            height=height
        )

    table_bottom_y, total = draw_product_table(
        c=c,
        amount_items=amount_items,
        isInvoice=isInvoice,
        table_start_y=table_start_y - 20,
        width=width,
        height=height
    )

    # ---------------------------------------------------------
    # Invoice / Sales Order Summary
    # ---------------------------------------------------------

    if isInvoice in (1, 2):
        draw_metal_invoice_summary(
            c=c,
            container=container,
            table_bottom_y=table_bottom_y,
            total=total,
            discount_percent=discount_percent,
            no_tax=no_tax
        )

    # ---------------------------------------------------------
    # Footer / Payment Information
    # ---------------------------------------------------------

    draw_metal_invoice_footer(
        c=c,
        container=container,
        isInvoice=isInvoice,
        table_bottom_y=table_bottom_y,
        width=width,
        isJustTableOrder=isJustTableOrder
    )

    # ---------------------------------------------------------
    # Finalize
    # ---------------------------------------------------------

    return finalize_pdf_and_response(
        canvas_obj=c,
        file_path=output_path,
        filename=new_filename
    )

def converter_commision_pdf(c, orders, width, height, start_date, end_date):

    if os.path.exists(constants_address.SSA_LOGO_PATH):
        c.drawImage(constants_address.SSA_LOGO_PATH, 40, height - 110, width=140, height=80, preserveAspectRatio=True, mask='auto')

    # c.setFont("Helvetica-Bold", 18)
    # c.drawString(40, height - 40, "Metal Commission Report")

    title_text = "Metal Commission Report" 
    c.setFont(constants_address.font_Helvetica_Bold, 18)
    c.drawCentredString(width / 2, height - 110 + 40, title_text)

    total_customer = Decimal("0")
    total_cost = Decimal("0")
    total_profit_ground = Decimal("0")

    table_data = [[
        "NO",
        "Invoice Date",
        "Invoice",
        "Cus AMT",
        "W/O Tax",
        "Sales AMT",
        "Deli Fee",
        "Comm%",
        "Markup",
        "TotalComm",        
    ]]

    index = 0
    for order in orders:
        index+=1

        customer = order.customer_price or Decimal("0")
        sales = order.total_amount or Decimal("0")
        cost = order.total_cost or Decimal("0")
        profit = order.profit or Decimal("0")
        total_profit = order.total_profit or Decimal("0")
        sub_profit = order.sub_profit or Decimal("0")
        carrier = order.delivery_price or Decimal("0")
        # 如果运费不为0，则设置0，表示已收运费；
        # 如果运费为0，则设为150，需要扣除150
        if carrier == 0:
            carrier = 150
        else:
            carrier = 0

        table_data.append([
            index,
            order.pickup_date.strftime("%m/%d/%Y"),
            order.so_num,            
            f"{customer:,.2f}",
            f"{sales:,.2f}",
            f"{cost:,.2f}",
            f"{carrier:,.2f}",
            f"{profit:,.2f}",
            f"{sub_profit:,.2f}",
            f"{total_profit:,.2f}",
            
        ])

        total_customer += customer
        total_cost += cost
        total_profit_ground += total_profit

    table = Table(
        table_data,
        colWidths=[22,60,95,50, 50, 55,50, 50, 50,55],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # 日期和SO左对齐
        ("ALIGN", (0, 0), (1, -1), "LEFT"),

        # 金额右对齐
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),

        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    table.wrapOn(c, width - 80, height)

    table_top_y = height - 120

    table_bottom_y = draw_commission_table_paginated(
        c=c,
        table=table,
        width=width,
        height=height,
        table_top_y=table_top_y
    )

    # 统计报表时间范围
    if orders:
        # start_date = start_date
        # end_date = end_date
        if start_date and isinstance(start_date, str):
            try:
                start_date = datetime.strptime(
                    start_date,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                start_date = None

        if end_date and isinstance(end_date, str):
            try:
                end_date = datetime.strptime(
                    end_date,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                end_date = None

        period = (
            f"{start_date.strftime('%m/%d/%Y')} - "
            f"{end_date.strftime('%m/%d/%Y')}"
        )
    else:
        period = "N/A"

    y = table_bottom_y - 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Summary")

    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(60, y, f"Report Period : {period}")

    y -= 25
    c.drawString(60, y, f"Monthly Sales : ${total_customer:,.2f}")

    y -= 18
    c.drawString(60, y, f"Total Commission : ${total_profit_ground:,.2f}")

def converter_commision_pdf_2(c, orders, width, height):
    y = height - 40

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, "Metal Commission Report")

    y -= 30

    c.setFont("Helvetica-Bold", 10)

    headers = [
        "SO#",
        "Pickup",
        "Customer AMT",
        "W/O Tax AMT",
        "Sales AMT",
        "Comm%",
        "TotalComm",
        "Carrier"
    ]

    col_widths = [110, 55, 75,75, 55, 50, 60, 50]
    left_margin = 40

    xs = [left_margin]
    for w in col_widths[:-1]:
        xs.append(xs[-1] + w)

    # ===== 表头 =====
    c.setFont("Helvetica-Bold", 10)

    for x, h in zip(xs, headers):
        c.drawString(x, y, h)

    y -= 20

    total_sales = Decimal("0")
    total_cost = Decimal("0")
    total_profit_ground = Decimal("0")

    c.setFont("Helvetica", 10)

    for order in orders:

        invoice = order.invoice_price or Decimal("0")
        customer = order.customer_price or Decimal("0")
        sales = order.total_amount or Decimal("0")
        cost = order.total_cost or Decimal("0")
        profit = order.profit or Decimal("0")
        total_profit = order.total_profit or Decimal("0")
        carrier = order.carrier_price or Decimal("0")

        c.drawString(xs[0], y, order.so_num)
        c.drawString(xs[1], y, order.pickup_date.strftime("%Y-%m-%d"))

        c.drawRightString(xs[2] + col_widths[2] - 5, y, f"{customer:,.2f}")
        c.drawRightString(xs[3] + col_widths[3] - 5, y, f"{sales:,.2f}")
        c.drawRightString(xs[4] + col_widths[4] - 5, y, f"{cost:,.2f}")
        c.drawRightString(xs[5] + col_widths[5] - 5, y, f"{profit:,.2f}")
        c.drawRightString(xs[6] + col_widths[6] - 5, y, f"{total_profit:,.2f}")
        c.drawRightString(xs[7] + col_widths[7] - 5, y, f"{carrier:.2f}")

        total_sales += sales
        total_cost += cost
        total_profit_ground += total_profit

        y -= 18

        if y < 40:
            c.showPage()

            c.setFont("Helvetica-Bold", 10)

            # 新页重新画表头
            for x, h in zip(xs, headers):
                c.drawString(x, height - 40, h)

            c.setFont("Helvetica", 10)
            y = height - 40

    y -= 20

    ground_total_profit = total_profit_ground

    c.setFont("Helvetica-Bold", 12)

    c.drawString(40, y, "Summary")

    y -= 25

    c.drawString(60, y, f"Total Sales : ${total_sales:,.2f}")
    y -= 18
    c.drawString(60, y, f"Total Cost : ${total_cost:,.2f}")
    y -= 18
    c.drawString(60, y, f"Total Profit : ${ground_total_profit:,.2f}")

def draw_commission_table_paginated(c,table,width,height,table_top_y):
    x = 40
    available_width = width - 80

    # 每页底部预留给 Summary 的空间
    bottom_margin = 150

    current_top_y = table_top_y
    table_bottom_y = current_top_y

    # 等待绘制的 Flowable
    pending_tables = [table]

    first_page = True

    while pending_tables:

        current_table = pending_tables.pop(0)

        # 当前页面可以使用的高度
        available_height = current_top_y - bottom_margin

        # 尝试拆分当前 Table
        table_parts = current_table.split(
            available_width,
            available_height
        )

        if not table_parts:
            break

        # 第一部分放在当前页面
        first_table = table_parts[0]

        first_table.wrapOn(
            c,
            available_width,
            available_height
        )

        first_table.drawOn(
            c,
            x,
            current_top_y - first_table._height
        )

        table_bottom_y = (
            current_top_y - first_table._height
        )

        # 如果还有剩余部分
        if len(table_parts) > 1:

            # 剩余部分放回队列
            pending_tables = table_parts[1:] + pending_tables

        # 如果还有内容，需要新页面
        if pending_tables:

            c.showPage()

            draw_commission_header(
                c=c,
                width=width,
                height=height
            )

            current_top_y = height - 120

            first_page = False

    return table_bottom_y

def draw_commission_header(c, width, height):
    if os.path.exists(constants_address.SSA_LOGO_PATH):
        c.drawImage(
            constants_address.SSA_LOGO_PATH,
            40,
            height - 110,
            width=140,
            height=80,
            preserveAspectRatio=True,
            mask='auto'
        )

    title_text = "Metal Commission Report"

    c.setFont(
        constants_address.font_Helvetica_Bold,
        18
    )

    c.drawCentredString(
        width / 2,
        height - 70,
        title_text
    )

def draw_product_table(c, amount_items, isInvoice, table_start_y, width, height):
    total = Decimal("0.00")

    # ==========================================
    # Description style
    # ==========================================

    description_style = ParagraphStyle(
        "ProductDescription",
        fontName=constants_address.font_Helvetica,
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
    )

    # ==========================================
    # Table Header
    # ==========================================

    if isInvoice:
        table_data = [[
            "ITEM",
            "DESCRIPTION",
            "QTY(PC)",
            "Price Per Piece",
            "Total"
        ]]
    else:
        table_data = [[
            "ITEM",
            "DESCRIPTION",
            "QTY"
        ]]

    # ==========================================
    # Data
    # ==========================================

    for item, desc, units, rate, charge in amount_items:

        display_item = str(item) if item else ""

        # Description 使用 Paragraph
        display_desc = escape(str(desc or "")).replace(
            "\n",
            "<br/>"
        )

        description_paragraph = Paragraph(
            display_desc,
            description_style
        )

        display_units = (
            f"{units:.0f}"
            if units
            else ""
        )

        if isInvoice:

            display_rate = (
                f"${rate:,.2f}"
                if rate
                else ""
            )

            display_charge = (
                f"${charge:,.2f}"
                if charge
                else ""
            )

            table_data.append([
                display_item,
                description_paragraph,
                display_units,
                display_rate,
                display_charge
            ])

            total += Decimal(
                str(charge or 0)
            )

        else:

            table_data.append([
                display_item,
                description_paragraph,
                display_units
            ])

    # ==========================================
    # Create Table
    # ==========================================

    if isInvoice:

        table = Table(
            table_data,
            colWidths=[
                80,
                250,
                50,
                80,
                60
            ]
        )

        table.setStyle(TableStyle([

            # Header
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),

            # Border
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.black
            ),

            # Alignment
            (
                "ALIGN",
                (0, 0),
                (0, -1),
                "LEFT"
            ),

            (
                "ALIGN",
                (1, 0),
                (1, -1),
                "LEFT"
            ),

            (
                "ALIGN",
                (2, 0),
                (2, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (3, 1),
                (-1, -1),
                "RIGHT"
            ),

            # Vertical alignment
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            # Font
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                constants_address.font_Helvetica_Bold
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                10
            ),

            # Padding
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
        ]))

    else:

        table = Table(
            table_data,
            colWidths=[
                100,
                360,
                60
            ]
        )

        table.setStyle(TableStyle([

            # Header
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),

            # Border
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.black
            ),

            # Alignment
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "LEFT"
            ),

            # Vertical alignment
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            # Font
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                constants_address.font_Helvetica_Bold
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                10
            ),

            # Padding
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
        ]))

    # ==========================================
    # Draw Table
    # ==========================================

    table.wrapOn(
        c,
        width,
        height
    )

    TABLE_TOP_GAP = -40

    table_top_y = (
        table_start_y +
        TABLE_TOP_GAP
    )

    table_height = table._height

    table.drawOn(
        c,
        40,
        table_top_y - table_height
    )

    table_bottom_y = (
        table_top_y -
        table_height
    )

    return table_bottom_y, total

def draw_packing_table(c, terms, start_y, width, height):
    table_data = [["PURCHASING AGENT", "SHIP VIA", "FOB Point","PAYMENT TERM"],
        ["ADAM C", "FLATBED", "LEMONT, IL", f"{terms} Days" if terms else ""]]

    table = Table(
        table_data,
        colWidths=[120, 80, 180, 140]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),

        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    table.wrapOn(c, width, height)

    table_height = table._height

    table.drawOn(
        c,
        40,
        start_y - table_height
    )

    return start_y - table_height
    

# === Helper function to draw section headers ===
def draw_section_header(c, title, x, y):
    c.setFont(constants_address.font_Helvetica_Bold, 11)
    c.drawString(x, y, title)
    c.setLineWidth(0.5)
    c.line(x, y - 2, x + 210, y - 2)
    c.setFont(constants_address.font_Helvetica, 11)

# 换行的地址格式
def draw_address_block(c, label, address_lines, x, y_start):
    draw_section_header(c, label, x, y_start)

    line_height = 15
    y = y_start - line_height
    for line in address_lines:
        c.drawString(x, y, line)
        y -= line_height

# 字符串的地址格式
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

# 无Header的地址格式
def draw_address_block3(c, address_lines, x, y_start):
    #draw_section_header(c, title, x, y)

    c.setFont(constants_address.font_Helvetica, 10)
    line_height = 15
    y = y_start - line_height
    for line in address_lines:
        c.drawString(x, y, line)
        y -= line_height

# draw_metal_invoice sub section
def draw_metal_invoice_header(
    c,
    container,
    isInvoice,
    width,
    height,
    y,
    y_offset,
    isJustTableOrder=False
):
    # ---------------------------------------------------------
    # Logo
    # ---------------------------------------------------------

    if not isJustTableOrder:
        if os.path.exists(constants_address.Metal_LOGO_PATH):
            c.drawImage(
                constants_address.Metal_LOGO_PATH,
                40,
                y - 85,
                width=180,
                height=120,
                preserveAspectRatio=True,
                mask="auto"
            )

    # ---------------------------------------------------------
    # Title
    # ---------------------------------------------------------

    title_text = {
        0: "Packing List",
        1: "Invoice",
        2: "Sales Order",
    }.get(isInvoice, "Packing List")

    c.setFont(
        constants_address.font_Helvetica_Bold,
        20
    )

    c.drawCentredString(
        width / 2,
        y - 30,
        title_text
    )

def draw_metal_invoice_information(
    c,
    container,
    isInvoice,
    width,
    height,
    y_offset,
    term_days,
    isJustTableOrder=False
):
    if isJustTableOrder:
        return

    y_shipper_diff = 60
    y_diff = 15

    ADDRESS_MAPPING = {
        "SHIPPER": constants_address.SSA_ADDRESS,
        "SHIPPERADAM": constants_address.SSA_ADDRESSADAM,
    }

    invoice_prefix = {
        "Speedier": "OS",
        "Trans Knights": "OT",
    }.get(container.so_num, "")

    full_invoice_no = f"{invoice_prefix}{container.so_num}"

    date_expected = (
        container.pickup_date.strftime("%m/%d/%Y")
        if container.pickup_date
        else "N/A"
    )

    # ---------------------------------------------------------
    # Helper
    # ---------------------------------------------------------

    def draw_label_value(x, y, label, value):
        c.setFont(
            constants_address.font_Helvetica_Bold,
            10
        )
        c.drawString(x, y, label)

        c.setFont(
            constants_address.font_Helvetica,
            10
        )
        c.drawString(x + 90, y, str(value))

    # ---------------------------------------------------------
    # Shipper
    # ---------------------------------------------------------

    if isInvoice == 1:
        draw_address_block(
            c,
            "SHIPPER:",
            ADDRESS_MAPPING["SHIPPER"],
            40,
            height - y_shipper_diff - y_offset
        )

    elif isInvoice == 2:
        draw_address_block(
            c,
            "SHIPPER:",
            ADDRESS_MAPPING["SHIPPERADAM"],
            40,
            height - y_shipper_diff - y_offset
        )

    else:
        draw_address_block3(
            c,
            constants_address.SSA_ADDRESSADAM,
            40,
            height - y_shipper_diff - y_offset + 15
        )

    # ---------------------------------------------------------
    # Invoice / Order Information
    # ---------------------------------------------------------

    invoicenum_x_pos = 350

    if isInvoice == 1:

        draw_section_header(
            c,
            f"INVOICE NO.: {full_invoice_no}",
            invoicenum_x_pos,
            height - y_shipper_diff - y_offset
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff - y_offset,
            "PO#: ",
            container.po_num
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 2 - y_offset,
            "DELIVERY DATE: ",
            date_expected
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 3 - y_offset,
            "INVOICE DATE: ",
            date_expected
        )

        if container.pickup_date:
            due_date = (
                container.pickup_date
                + timedelta(days=term_days)
            )

            due_date_text = due_date.strftime("%m/%d/%Y")
        else:
            due_date_text = "N/A"

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 4 - y_offset,
            "DUE DATE: ",
            due_date_text
        )

    elif isInvoice == 2:

        draw_section_header(
            c,
            "Order:",
            invoicenum_x_pos,
            height - y_shipper_diff - y_offset
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff - y_offset,
            "Date: ",
            container.order_date.strftime("%m/%d/%Y")
            if container.order_date else "N/A"
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 2 - y_offset,
            "Quote#: ",
            container.so_num
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 3 - y_offset,
            "PO#: ",
            container.po_num
        )

        draw_label_value(
            invoicenum_x_pos,
            height - y_shipper_diff - y_diff * 4 - y_offset,
            "Expected Date: ",
            date_expected
        )

    # ---------------------------------------------------------
    # Bill To
    # ---------------------------------------------------------

    y_shipper_interval = 140

    if isInvoice in (1, 2):

        draw_address_block2(
            c,
            "BILL TO:",
            container.bill_to,
            40,
            height - y_shipper_interval - y_offset
        )

    else:

        draw_section_header(
            c,
            "Order:",
            40,
            height - y_shipper_interval - y_offset
        )

        draw_label_value(
            40,
            height - y_shipper_interval - y_diff - y_offset,
            "Date: ",
            container.order_date.strftime("%m/%d/%Y")
            if container.order_date else "N/A"
        )

        draw_label_value(
            40,
            height - y_shipper_interval - y_diff * 2 - y_offset,
            "Order#: ",
            container.so_num
        )

        draw_label_value(
            40,
            height - y_shipper_interval - y_diff * 3 - y_offset,
            "PO#: ",
            container.po_num
        )

        draw_label_value(
            40,
            height - y_shipper_interval - y_diff * 4 - y_offset,
            "Delivery Date: ",
            date_expected
        )

    # ---------------------------------------------------------
    # Ship To
    # ---------------------------------------------------------

    draw_address_block2(
        c,
        "SHIP TO:",
        container.ship_to,
        invoicenum_x_pos,
        height - y_shipper_interval - y_offset
    )

def get_metal_table_start_y(
    height,
    y_offset,
    isJustTableOrder=False
):
    if isJustTableOrder:
        return height - 130

    address_block_height = 100

    return height - 110 - y_offset - address_block_height

def draw_metal_invoice_summary(
    c,
    container,
    table_bottom_y,
    total,
    discount_percent=0,
    no_tax=False
):
    # =========================================================
    # Box Layout
    # =========================================================

    box_top_y = table_bottom_y - 15
    box_bottom_y = box_top_y - 80
    box_height = box_top_y - box_bottom_y

    instructions_x = 40
    instructions_width = 285

    summary_x = 345
    summary_width = 215

    # Border
    c.setLineWidth(0.4)

    # =========================================================
    # Special Instructions
    # =========================================================

    draw_special_instructions_box(
        c=c,
        container=container,
        x=instructions_x,
        top_y=box_top_y,
        width=instructions_width,
        height=box_height
    )

    # =========================================================
    # Calculate Amounts
    # =========================================================

    amounts = calculate_invoice_amounts(
        total=total,
        container=container,
        discount_percent=discount_percent,
        no_tax=no_tax
    )

    # =========================================================
    # Price Summary
    # =========================================================

    draw_price_summary_box(
        c=c,
        amounts=amounts,
        x=summary_x,
        top_y=box_top_y,
        width=summary_width,
        height=box_height
    )

    return box_bottom_y

def calculate_invoice_amounts(
    total,
    container,
    discount_percent=0,
    no_tax=False
):
    discount_rate = (
        Decimal(discount_percent) / Decimal("100")
    )

    discount_amount = (
        total * discount_rate
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    discounted_subtotal = (
        total - discount_amount
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    carrier_amount = container.delivery_price or Decimal("0.00")

    tax_amount = (
        discounted_subtotal
        * constants_address.Tax_rate
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if no_tax:
        tax_amount = Decimal("0.00")

    grand_total = (
        discounted_subtotal
        + tax_amount
        + carrier_amount
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    credit_total = (
        grand_total
        * constants_address.Credit_rate
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    return {
        "subtotal": total,
        "discount_amount": discount_amount,
        "discounted_subtotal": discounted_subtotal,
        "tax_amount": tax_amount,
        "carrier_amount": carrier_amount,
        "grand_total": grand_total,
        "credit_total": credit_total,
    }

def draw_special_instructions_box(
    c,
    container,
    x,
    top_y,
    width,
    height
):
    # Border
    c.setLineWidth(0.4)

    c.rect(
        x,
        top_y - height,
        width,
        height
    )

    # Title
    c.setFont(
        constants_address.font_Helvetica_Bold,
        10
    )

    c.drawString(
        x + 10,
        top_y - 16,
        "Other Special Instructions"
    )

    # Description
    description = container.content or ""

    description_style = ParagraphStyle(
        "OrderDescription",
        fontName=constants_address.font_Helvetica,
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
    )

    description_paragraph = Paragraph(
        str(description).replace("\n", "<br/>"),
        description_style
    )

    description_width = width - 20

    description_paragraph.wrapOn(
        c,
        description_width,
        height - 35
    )

    description_paragraph.drawOn(
        c,
        x + 10,
        top_y - 32 - description_paragraph.height
    )

def draw_price_summary_box(
    c,
    amounts,
    x,
    top_y,
    width,
    height
):
    # ---------------------------------------------------------
    # Box
    # ---------------------------------------------------------

    c.setLineWidth(0.4)

    c.rect(
        x,
        top_y - height,
        width,
        height
    )

    # ---------------------------------------------------------
    # Settings
    # ---------------------------------------------------------

    line_height = 16

    summary_y = top_y - 17
    summary_right = x + width - 10

    c.setFont(
        constants_address.font_Helvetica_Bold,
        10
    )

    # ---------------------------------------------------------
    # Subtotal
    # ---------------------------------------------------------

    c.drawRightString(
        summary_right,
        summary_y,
        f"Subtotal:   ${amounts['subtotal']:,.2f}"
    )

    summary_y -= line_height

    # ---------------------------------------------------------
    # Discount
    # ---------------------------------------------------------

    if amounts["discount_amount"] > 0:

        discount_percent = (
            amounts["discount_amount"]
            / amounts["subtotal"]
            * Decimal("100")
            if amounts["subtotal"]
            else Decimal("0")
        )

        c.drawRightString(
            summary_right,
            summary_y,
            f"Discount ({discount_percent:g}%):  "
            f"-${amounts['discount_amount']:,.2f}"
        )

        summary_y -= line_height

        c.drawRightString(
            summary_right,
            summary_y,
            f"Discounted Subtotal:   "
            f"${amounts['discounted_subtotal']:,.2f}"
        )

        summary_y -= line_height

    # ---------------------------------------------------------
    # Sales Tax
    # ---------------------------------------------------------

    c.drawRightString(
        summary_right,
        summary_y,
        f"Sales Tax:   ${amounts['tax_amount']:,.2f}"
    )

    summary_y -= line_height

    # ---------------------------------------------------------
    # Delivery
    # ---------------------------------------------------------

    c.drawRightString(
        summary_right,
        summary_y,
        f"Delivery:   ${amounts['carrier_amount']:,.2f}"
    )

    summary_y -= line_height

    # ---------------------------------------------------------
    # Grand Total
    # ---------------------------------------------------------

    c.setLineWidth(0.4)

    c.line(
        x + 10,
        summary_y + 7,
        summary_right,
        summary_y + 7
    )

    summary_y -= 3

    c.setFont(
        constants_address.font_Helvetica_Bold,
        11
    )

    c.drawRightString(
        summary_right,
        summary_y,
        f"Grand Total:   "
        f"${amounts['grand_total']:,.2f}"
    )

def draw_metal_invoice_footer(
    c,
    container,
    isInvoice,
    table_bottom_y,
    width,
    isJustTableOrder=False
):
    if isJustTableOrder:
        return

    left_text_y = table_bottom_y - 120
    interval = 15

    c.setFont(
        constants_address.font_Helvetica,
        10
    )

    if isInvoice == 1:
        draw_invoice_footer(
            c,
            left_text_y,
            interval
        )

    elif isInvoice == 2:
        draw_sales_order_footer(
            c,
            width,
            left_text_y,
            interval
        )

    elif isInvoice == 0:
        draw_packing_list_footer(
            c,
            left_text_y,
            interval
        )

def draw_invoice_footer(c, y, interval):

    c.drawString(
        40,
        y,
        "Accepted forms of payment: Check and ACH transfer."
    )

    c.drawString(
        40,
        y - interval,
        "Please send all the checks to:"
    )

    c.drawString(
        40,
        y - interval * 2,
        "Secure Source America LLC"
    )

    c.drawString(
        40,
        y - interval * 3,
        "1215 101st Street"
    )

    c.drawString(
        40,
        y - interval * 4,
        "Lemont, IL 60439"
    )

    # ACH
    c.drawString(
        320,
        y,
        "Bank information for ACH payment:"
    )

    c.drawString(
        320,
        y - interval,
        "BMO Harris Bank"
    )

    c.drawString(
        320,
        y - interval * 2,
        "Routing# 071025661"
    )

    c.drawString(
        320,
        y - interval * 3,
        "Account# 4834963144"
    )

    c.drawString(
        320,
        y - interval * 4,
        "Account Name: Secure Source America LLC"
    )

    # Notes
    c.drawString(
        40,
        y - interval * 6,
        "*Products availability and lead time may change"
    )

    c.drawString(
        40,
        y - interval * 7,
        "*SSA reserve the right to change pricing and terms without notice"
    )

    c.drawString(
        40,
        y - interval * 8,
        "If you have questions concerning this invoice, "
        "contact us at 708-882-1188      info@ssametal.com"
    )

def draw_sales_order_footer(c, width, y, interval):
    c.setFont(constants_address.font_Helvetica, 10)

    c.drawString(
        40,
        y,
        "*Products availability and lead time may change"
    )

    c.drawString(
        40,
        y - interval,
        "*SSA reserve the right to change pricing and terms without notice"
    )

    center_x = width / 2

    c.drawCentredString(
        center_x,
        y - interval * 3,
        "If you have any questions concerning this order"
    )

    c.drawCentredString(
        center_x,
        y - interval * 4,
        "contact us at: 708-888-8810"
    )

    c.drawCentredString(
        center_x,
        y - interval * 5,
        "info@ssametal.com"
    )

def draw_packing_list_footer(c, left_text_y, interval=15):
    c.setFont(constants_address.font_Helvetica, 10)

    c.drawString(
        40,
        left_text_y,
        "Received by:"
    )

    c.drawString(
        40,
        left_text_y - interval * 2,
        "Signature:"
    )

    c.drawString(
        40,
        left_text_y - interval * 4,
        "Date:"
    )

    c.drawString(
        100,
        left_text_y,
        "_____________________________________________________"
    )

    c.drawString(
        100,
        left_text_y - interval * 2,
        "_____________________________________________________"
    )

    c.drawString(
        100,
        left_text_y - interval * 4,
        "_____________________________________________________"
    )

    c.drawString(
        400,
        left_text_y,
        "(Please print)"
    )

    c.drawString(
        400,
        left_text_y - interval * 2,
        "(Quality verified for all items above)"
    )

    c.drawString(
        400,
        left_text_y - interval * 4,
        "(mm/dd/yyyy)"
    )


# 生成多个container的DO
def generate_delivery_order_pdf(containers, mbl_no=None, pickup_location=None, filename=None):
    """
    通用 Delivery Order PDF 生成方法。

    containers: Container 对象列表
    filename: 可选的 PDF 文件名
    """

    if not containers:
        raise ValueError("At least one container is required.")

    #----------------------------------------------------------------------
    first_item = containers[0]

    # 兼容数据库 Container 对象和临时提取的字典
    if isinstance(first_item, dict):
        container_infos = [
            {
                "container_id": item.get("container_no", ""),
                "size_type": item.get("size_type", "40HQ"),
                "weight": item.get("weight", ""),
                "seal_number": item.get("seal_no", ""),
                "Remarks": item.get("Remarks", item.get("remarks", "")),
                "commodity": item.get("commodity", "Metal"),
                "vessel": item.get("vessel", ""),
                "voyage": item.get("voyage", ""),
                "ssl": item.get("ssl", ""),
                "ref_no": item.get("ref_no", ""),
                "mbl": item.get("mbl", ""),
                "pickup_location": item.get("pickup_location", ""),
                "pickup_date": item.get("pickup_date", "Pending"),
                "delivery_location": item.get("delivery_location", ""),
                "delivery_date": item.get("delivery_date", "Pending"),
            }
            for item in containers
        ]
    else:
        container_infos = [
            build_container_info(container)
            for container in containers
        ]

    containerInfo = container_infos[0]

    # 优先使用调用方传入的公共信息
    if mbl_no is not None:
        containerInfo["mbl"] = mbl_no

    if pickup_location is not None:
        containerInfo["pickup_location"] = pickup_location
    #----------------------------------------------------------------------

    # 默认使用第一个 Container 的公共信息
    containerInfo = container_infos[0]

    # PDF 路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_solar,
        constants_address.SOLAR_DO
    )
    ensure_dir_exists(pdf_path)

    
    # file name
    if not filename:
        if isinstance(containers[0], dict):
            container_names = [
                item.get("container_no", "")
                for item in containers
            ]
        else:
            container_names = [
                item.container_id
                for item in containers
            ]

        filename = "-".join(
            str(name).strip()
            for name in container_names
            if name and str(name).strip()
        ) + ".pdf"

    c, pagesize, inch, ImageReader = create_pdf_canvas(filename)
    width, height = pagesize

    # 样式
    left_margin = 0.5 * inch
    line_height = 18
    font_size = 10
    font_size_small = 8

    bold_font = constants_address.font_Helvetica_Bold
    regular_font = constants_address.font_Helvetica

    def draw_text(x, y, text, font=regular_font, size=font_size):
        c.setFont(font, size)
        c.drawString(x, y, str(text or ""))

    # --------------------------------------------------
    # Logo 和标题
    # --------------------------------------------------
    logo_width, logo_height = 80, 80
    logo_x = 0.5 * inch
    logo_y = height - logo_height - 40

    c.drawImage(
        ImageReader(constants_address.SSA_LOGO_PATH),
        logo_x,
        logo_y,
        width=logo_width,
        height=logo_height
    )

    y = height - 75
    c.setFont(bold_font, 18)
    c.drawCentredString(width / 2, y, "DELIVERY ORDER")

    # --------------------------------------------------
    # US Headquarter
    # --------------------------------------------------
    y = height - 140

    draw_text(left_margin, y, "US Headquarter:", bold_font)

    for line in constants_address.Only_ADDRESS:
        draw_text(left_margin + 120, y, line)
        y -= line_height

    y += line_height

    # --------------------------------------------------
    # 右上角信息
    # --------------------------------------------------
    right_x = width - 240

    y += line_height

    draw_text(
        right_x, y,
        f"DATE: {datetime.now().strftime('%m/%d/%Y')}"
    )
    y -= line_height

    draw_text(right_x, y, f"REF. NO: {containerInfo['ref_no']}")
    y -= line_height

    draw_text(right_x, y, f"MBL: {containerInfo['mbl']}")

    # --------------------------------------------------
    # Pickup Location
    # --------------------------------------------------
    y -= line_height * 2

    pickup_lines = containerInfo["pickup_location"].splitlines()
    pickup_y = y

    draw_text(left_margin, pickup_y, "Pickup Location:", bold_font)

    for line in pickup_lines:
        draw_text(left_margin + 120, pickup_y, line, bold_font)
        pickup_y -= line_height

    draw_text(
        right_x, y,
        f"Pickup Date:    {containerInfo['pickup_date']}"
    )

    # --------------------------------------------------
    # Delivery Location
    # --------------------------------------------------
    y = pickup_y - line_height

    delivery_lines = containerInfo["delivery_location"].splitlines()
    delivery_y = y

    draw_text(left_margin, delivery_y, "Delivery Location:", bold_font)

    for line in delivery_lines:
        draw_text(left_margin + 120, delivery_y, line, bold_font)
        delivery_y -= line_height

    draw_text(
        right_x, y,
        f"Delivery Date:    {containerInfo['delivery_date']}"
    )

    y = delivery_y

    # --------------------------------------------------
    # 联系信息
    # --------------------------------------------------
    y -= 20

    c.setFont(regular_font, font_size_small)

    for line in constants_address.DO_CONTACT_LINES:
        c.drawString(left_margin + 120, y, line)
        y -= line_height

    y -= 2

    # --------------------------------------------------
    # Container 表格
    # --------------------------------------------------
    table_headers = [
        "Container#",
        "Container Size/Type",
        "Weight",
        "Seal#",
        "Remarks",
    ]

    col_widths = [120, 150, 100, 100, 100]

    def draw_table_header(y):
        """绘制表头及上下横线"""

        c.setLineWidth(1)

        c.line(
            left_margin,
            y + line_height - 2,
            width - left_margin,
            y + line_height - 2
        )

        x = left_margin

        for header, col_width in zip(table_headers, col_widths):
            draw_text(x, y, header, bold_font)
            x += col_width

        c.line(
            left_margin,
            y - 4,
            width - left_margin,
            y - 4
        )

        return y - line_height

    y -= 20
    y = draw_table_header(y)

    # 一个 Container 对应一行
    for info in container_infos:

        # 如果剩余空间不足，换页并重新绘制表头
        if y < 80:
            c.showPage()
            y = height - 70
            y = draw_table_header(y)

        row_values = [
            info["container_id"],
            info["size_type"],
            info["weight"],
            info["seal_number"],
            info["Remarks"],
        ]

        x = left_margin

        for value, col_width in zip(row_values, col_widths):
            draw_text(x, y, value)
            x += col_width

        c.setLineWidth(1)
        c.line(
            left_margin,
            y - 4,
            width - left_margin,
            y - 4
        )

        y -= line_height

    # --------------------------------------------------
    # Footer
    # --------------------------------------------------
    y -= 20

    c.setFont(regular_font, font_size_small)

    for line in constants_address.DO_FOOTER_LINES_TEMPLATE:
        c.drawString(
            left_margin + 120,
            y,
            line.format(**containerInfo)
        )
        y -= line_height

    # --------------------------------------------------
    # 签名区
    # --------------------------------------------------
    y -= 60

    for line in constants_address.DO_SIGNATURE_LINES:
        draw_text(width / 2, y, line)
        y -= line_height

    return finalize_pdf_and_response(c, filename)
# 构建Container信息
def build_container_info(container):
    """将单个 Container 转换为 DO 所需的数据"""

    railway_station = container.railwayStation
    carrier = container.Carrier

    pickup_location = ""
    if railway_station:
        address = (railway_station.address or "").replace("\\n", "\n")
        pickup_location = f"{railway_station.name}\n{address}"

    delivery_location = ""
    if carrier:
        address = (carrier.address or "").replace("\\n", "\n")
        delivery_location = f"{carrier.name}\n{address}"

    return {
        "container_id": container.container_id,
        "size_type": "40HQ",
        "weight": f"{container.weight} LBS",
        "seal_number": "",
        "Remarks": (
            "Overweight"
            if container.customer_id in [12, 3]
            else ""
        ),
        "commodity": (
            "Metal"
            if container.customer_id == 12
            else "Plastic Bag"
        ),
        "vessel": "",
        "voyage": "",
        "ssl": "",
        "pickup_location": pickup_location,
        "pickup_date": "Pending",
        "delivery_location": delivery_location,
        "delivery_date": "Pending",
        "ref_no": container.refnumber or "",
        "mbl": container.mbl or "",
    }
