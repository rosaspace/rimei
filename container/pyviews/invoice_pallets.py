import math

from datetime import datetime, date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect

from reportlab.platypus import Image, Spacer, Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import inch

from ..constants import constants_address, constants_view
from ..models import RMProduct

from .inventory_count import get_month_pallet_number, get_quality, get_product_qty
from .utils.getPermission import get_user_permissions
from .utils.pdf_temp_utils import create_temp_pdf, cleanup_temp_file


@login_required(login_url='/login/')
def invoice_pallet_labor(request):
    years = [date.today().year]
    months = list(range(1, 13))  # 1 到 12 月

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_generete_monthLabor, {
        'user_permissions': user_permissions,
        'years':years,'months':months
    })  

# show container and pallet number
def show_pallet_number(request):
    # 获取请求中的月份和年份
    select_month = request.GET.get('month')
    select_year = request.GET.get('year')

    # 当月剩余托盘数
    inventory_items = RMProduct.objects.filter(type = "Rimei")
    total_storage_pallets = 0
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)
        total_storage_pallets += math.ceil(product.quantity / product.Pallet) # 数量，向上取整

    # ✅ 出入库托盘数
    total_container,total_in_plts,total_out_plts, gloves_in_data,container_in_orders = get_month_pallet_number(select_month, select_year)
    total_plts = total_in_plts + total_out_plts

    # ✅ 总价格
    total_price = total_container * 450 + total_in_plts * 4 + total_out_plts * 4+total_plts * 12 + total_storage_pallets * 6

    # 成本统计表格
    cost_table = [{
        'type': 'Container Unload Fee', 'pallets': total_container, 'unit': 450, 'value': total_container * 450
    }, {
        'type': 'Pallet Fee', 'pallets': total_plts, 'unit': 12, 'value': total_plts * 12
    }, {
        'type': 'Pallet Storage Per Month', 'pallets': total_storage_pallets, 'unit': 6, 'value': total_storage_pallets * 6
    }, {
        'type': 'Pallet Inbound Labor Fee', 'pallets': total_in_plts, 'unit': 4, 'value': total_in_plts * 4
    }, {
        'type': 'Pallet Outbound Labor Fee', 'pallets': total_out_plts, 'unit': 4, 'value': total_out_plts * 4

    }]    

    years = [date.today().year]
    months = list(range(1, 13))  # 1 到 12 月
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_generete_monthLabor, {
        'gloves_in_data':gloves_in_data,
        'user_permissions': user_permissions,
        'total_in_plts': total_in_plts,
        'total_out_plts': total_out_plts,
        'cost_table': cost_table,
        'total_plts': total_plts,
        'total_container': total_container,
        'total_pallets' : total_storage_pallets,
        'total_price': total_price,
        'years':years,'months':months,
        'selectYear':select_year,'selectMonth':select_month,
    }) 

# export pallet and labor invoice monthly
def export_pallet_invoice(request):
    # 获取请求中的月份和年份
    select_month = request.GET.get('month')
    select_year = request.GET.get('year')
    inboundNumber_str = request.GET.get('inboundNumber')
    outboundNumber_str = request.GET.get('outboundNumber')
    palletstoragenumber_str = request.GET.get('palletstoragenumber')

    try:
        inboundNumber = int(inboundNumber_str)
        outboundNumber = int(outboundNumber_str)
        palletstoragenumber = int(palletstoragenumber_str)
    except (TypeError, ValueError):
        inboundNumber = 0  # 或根据你的需求设为其他默认值
        outboundNumber = 0
        palletstoragenumber = 0

    # 当月剩余托盘数
    inventory_items = RMProduct.objects.filter(type = "Rimei")
    total_storage_pallets = 0
    for product in inventory_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = get_quality(product)
        productTemp = get_product_qty(product, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)
        total_storage_pallets += math.ceil(product.quantity / product.Pallet) # 数量，向上取整

    # ✅ 出入库托盘数
    total_container,total_in_plts,total_out_plts, gloves_in_data,container_in_orders = get_month_pallet_number(select_month, select_year)

    if inboundNumber > total_in_plts :
        total_in_plts = inboundNumber
    if outboundNumber > total_out_plts :
        total_out_plts = outboundNumber
    if palletstoragenumber > total_storage_pallets :
        total_storage_pallets = palletstoragenumber
    total_plts = total_in_plts + total_out_plts

    # ✅ 总价格
    total_price = total_container * 450 + total_in_plts * 4 + total_out_plts * 4 + total_plts * 12 + total_storage_pallets * 6

    # ✅ 拼接 container 名字（每行 3~4 个）
    container_list = list(container_in_orders.values_list('container_id', flat=True))
    wrapped_container = ""
    for i in range(0, len(container_list), 3):  # 每行3个
        wrapped_container += "  ".join(container_list[i:i+3]) + "\n"
    print(wrapped_container)
    
    title = 'Payment Invoice Report'
    temp_path = invoice_template(title,wrapped_container,total_container, total_in_plts, total_out_plts, total_plts, total_storage_pallets, total_price)

    # ✅ 读取 PDF 文件并返回
    new_filename = "invoice_month_warehouse.pdf"
    with open(temp_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{new_filename}"'

    cleanup_temp_file(temp_path)
    return response

# Template -- export pallet and labor invoice monthly
def invoice_template(title,wrapped_container, total_container, total_in_plts,total_out_plts,total_plts,total_pallets,total_price):
    # 组织Table
    elements = []

    # 样式
    normal = ParagraphStyle(name='Normal', fontSize=10, leading=12)
    bold = ParagraphStyle(name='Bold', parent=normal, fontName='Helvetica-Bold')
    invoice_title_style = ParagraphStyle(
        name="InvoiceTitle",
        fontSize=20,
        leading=24,
        alignment=TA_RIGHT,
        textColor=colors.black,
        spaceAfter=6,
        fontName=constants_address.font_Helvetica_Bold,
    )
    invoice_cell_style = ParagraphStyle(
        name="InvoiceCell",
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
    )

    # ✅ Logo 和标题
    logo = Image(constants_address.Rimei_LOGO_PATH, width=2 * inch, height=0.7 * inch)
    rm_address_str = "<br/>".join(constants_address.RM_ADDRESS)
    company_info = Paragraph(rm_address_str, normal)

    # ✅ 用 Table 将 logo 和公司地址垂直排列在一列，左对齐
    left_column = Table(
        [[logo], [company_info]],
        colWidths=[3.2 * inch],  # 可微调宽度
        hAlign='LEFT'
    )
    left_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # 发票信息
    today_str = datetime.today().strftime("%m%d%Y")
    today_display = datetime.today().strftime("%-m/%-d/%Y")
    invoice_title = Paragraph("INVOICE", invoice_title_style)
    invoice_spacer = Spacer(1, 10)  # 加一个高度为6的空行
    invoice_data = [
        [Paragraph("<b>Invoice#</b>", invoice_cell_style), Paragraph(f"RM{today_str}", invoice_cell_style)],
        [Paragraph("<b>Date</b>", invoice_cell_style), Paragraph(today_display, invoice_cell_style)],
    ]
    invoice_table = Table(invoice_data, colWidths=[60, 100], hAlign='RIGHT')
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # ✅ 将标题和表格垂直堆叠
    right_column = Table([[invoice_title], [invoice_spacer], [invoice_table]], hAlign='RIGHT')
    right_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ✅ 主布局：左右两列
    header_table = Table(
        [[left_column, right_column]],
        colWidths=[4.0 * inch, 3.2 * inch]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    #region Bill To
    # 收款人地址, Bill To
    elements.extend(add_section_header("Bill to:", bold, 40))
    elements.append(Paragraph(
        'Omar supplies Inc.<br/>400 E. Randolph St.<br/>Suite 705<br/>Chicago IL 60601<br/>United States',
        normal
    ))
    elements.append(Spacer(1, 12))
    #endregion

    #region 表格
    # 项目表格
    data = [
        ["Item", "Description", "Qty", "Unit Price", "Total Price"],
        ["Container Unload Fee", wrapped_container.strip(), total_container, "$450.00", f'${total_container * 450:.2f}'],
        ["Pallet Fee", "", total_plts, "$12.00", f'${total_plts * 12:.2f}'],
        ["Pallet Storage Per Month", "", total_pallets, "$6.00", f'${total_pallets * 6:.2f}'],
        ["Pallet Inbound Labor Fee", "", total_in_plts, "$4.00", f'${total_in_plts * 4:.2f}'],
        ["Pallet Outbound Labor Fee", "", total_out_plts, "$4.00", f'${total_out_plts * 4:.2f}'],
        ["Omar Labor cost", "", "0", "$0.25", "$0.00"]
    ]
    table = Table(data, colWidths=[130, 230, 40, 50, 55])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # 右对齐的 TOTAL 小计行
    right_align_style = ParagraphStyle(
        name='RightAlign',
        fontSize=14,
        textColor=colors.black,
        alignment=TA_RIGHT
    )

    # 添加右对齐的 TOTAL 段落
    elements.append(Paragraph(f'<b>TOTAL: ${total_price:.2f}</b>', right_align_style))
    elements.append(Spacer(1, 20))
    #endregion

    #region 汇款信息
    # 汇款信息标题部分，左右对齐
    left_title = add_section_header("Please remit all payments to:", bold, 160)[0]
    right_title = add_section_header("Bank information for payment:", bold, 160)[0]

    left_para = Paragraph(constants_address.labor_left_text, normal)
    right_para = Paragraph(constants_address.labor_right_text, normal)

    # 拼接标题 + 正文的表格（两行两列）
    info_table = Table(
        [
            [left_title, right_title],
            [left_para, right_para],
        ],
        colWidths=[4.0 * inch, 4.0 * inch],
        hAlign='LEFT',
    )

    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(info_table)
    #endregion

    # ✅ 创建临时文件
    temp_path = create_temp_pdf(elements)

    return temp_path

# Template -- add title with underline
def add_section_header(title, style, width):
    """使用表格边框生成段落标题和下划线，左侧对齐。"""
    table = Table(
        [[Paragraph(f'<b>{title}</b>', style)]],  # 只有一行一列
        colWidths=[width],
        hAlign='LEFT'
    )
    table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # 在第一行下方画一条线
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return [table, Spacer(1, 6)]

