from django.db.models import Q
import re
import os
from django.conf import settings
import fitz  # PyMuPDF 解析 PDF
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

from ..models import RMOrder

FONT_SIZE = 60  # Larger font size
# FONT_SIZE = 46  # Larger font size
FONT_SIZE_Lot = 20

# Label
PAGE_WIDTH, PAGE_HEIGHT = letter  # Letter size (8.5 x 11 inches)
MARGIN_TOP = 25  # Top margin
MARGIN_LEFT = 5  # Left margin
LABEL_WIDTH = (PAGE_WIDTH - MARGIN_LEFT * 2) / 2  # Two labels per row
LABEL_HEIGHT = (PAGE_HEIGHT - MARGIN_TOP * 2) / 5  # Five rows per page

DRAW_BORDERS = False  # Set to True to draw borders, False to hide them

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
                c.setFont("Helvetica", FONT_SIZE_Lot)  # Smaller font size for the new text
                text_y_small = text_y - 30  # Position for the smaller text below the main label
                c.drawCentredString(text_x, text_y_small, f"{container_id}    {current_date}")
                c.drawCentredString(text_x, text_y_small - 20, f"Lot: {lot_number}")
    
                label_count -= 1  # Reduce remaining label count

            y_position -= LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row
