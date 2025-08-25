import os
import pandas as pd

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db.models import Q, F

from datetime import datetime
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..constants import constants_address,constants_view
from ..constants import email_constants
from .pdfgenerate import print_containerid_lot
from .getPermission import get_user_permissions
from ..models import Container,RMProduct,AlineOrderRecord,RMOrder,InboundCategory,RailwayStation,Carrier

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
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_temp, constants_address.LABEL_FOLDER)
    print("pdf_path: ", pdf_path)
    
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
    
                label_count -= 1  # Reduce remaining label count

            y_position -= constants_address.LABEL_HEIGHT  # Move to next row
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
    pdf_path = os.path.join(settings.MEDIA_ROOT, constants_address.UPLOAD_DIR_temp, constants_address.LABEL_FOLDER)
    os.makedirs(pdf_path, exist_ok=True)
    filename = os.path.join(pdf_path, f"{container_id}_lot.pdf")

    c = canvas.Canvas(filename, pagesize=letter)
    print_containerid_lot(c, so_num, label_count, container_id, lot_number, current_date)
    c.save()

    with open(filename, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
        return response
  
def import_inventory(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read the Excel file into a DataFrame
        df = pd.read_excel(excel_file, engine='openpyxl')

        # Ensure column names match the model fields
        for index, row in df.iterrows():
            # Create RMProduct instance
            product = RMProduct.objects.create(
                name=row["Display Name"],
                shortname = row["Short Name"],
                size = row["Size"],
                description="",  # description 为空
                quantity_init=row["Quantity On Hand"],
            )

        return JsonResponse({"message": "Excel data imported successfully!"})
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

def import_aline(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read only the "Matched Records" sheet
        try:
            df = pd.read_excel(excel_file, sheet_name="Matched Records", engine="openpyxl")
        except ValueError:
            return JsonResponse({"error": "Sheet 'Matched Records' not found in the uploaded file"}, status=400)

        # Loop through each row and save to database
        for _, row in df.iterrows():
            try:
                AlineOrderRecord.objects.create(
                    document_number=row.get("Document Number", ""),  # 文档编号
                    order_number=row.get("Order No", ""),  # 订单编号
                    po_number=row.get("P.O. No.", ""),  # PO编号
                    invoice_date=pd.to_datetime(row.get("Date", None), errors="coerce").date()
                        if pd.notna(row.get("Date", None)) else None,  # 发票日期
                    due_date=pd.to_datetime(row.get("Due Date", None), errors="coerce").date()
                        if pd.notna(row.get("Due Date", None)) else None,  # 截止日期
                    pdf_name=row.get("PDFFileName", ""),  # 文档名称
                    price=row.get("Total", 0) if pd.notna(row.get("Total", 0)) else 0  # 价格
                )
            except Exception as e:
                return JsonResponse({"error": f"Failed to import row {row.to_dict()} - {str(e)}"}, status=400)

        return JsonResponse({"message": "Excel data imported successfully!"})
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

def export_pallet(request):
    # 获取请求中的月份和年份
    month = request.GET.get('month')
    year = request.GET.get('year')

    if month and year:
        # 过滤出指定月份的订单
        start_date = datetime(int(year), int(month), 1)
        if month == '12':
            end_date = datetime(int(year) + 1, 1, 1)  # 下一年1月1日
        else:
            end_date = datetime(int(year), int(month) + 1, 1)  # 下个月的1日

        # 查询 "gloves in" 数据
        gloves_in_orders = Container.objects.filter(
            empty_date__gte=start_date, 
            empty_date__lt=end_date
        ).order_by('empty_date')
        print("golve in : ",len(gloves_in_orders))

        # 创建 "gloves in" DataFrame
        gloves_in_data = {
            'Inbound Date': [order.empty_date for order in gloves_in_orders],  # 假设有 empty_date 字段
            'Container ID': [order.container_id for order in gloves_in_orders],  # 假设有 container_id 字段
            'PLTS': [order.plts for order in gloves_in_orders],
            'Customer': [order.customer for order in gloves_in_orders],
            'Description': [order.content for order in gloves_in_orders],
        }
        gloves_in_df = pd.DataFrame(gloves_in_data)

        # 查询 "gloves out" 数据（根据您的需求进行调整）
        gloves_out_orders = RMOrder.objects.filter(
            outbound_date__gte=start_date, 
            outbound_date__lt=end_date
        ).exclude(Q(customer_name="8") | Q(customer_name="19")).order_by('outbound_date')
        print("golve out : ",len(gloves_out_orders))

        # 创建 "gloves out" DataFrame
        gloves_out_data = {
            'Outbound Date': [order.outbound_date for order in gloves_out_orders],
            'SO': [order.so_num for order in gloves_out_orders],
            'PLTS': [order.plts for order in gloves_out_orders],
            'Customer': [order.customer_name for order in gloves_out_orders],
        }
        gloves_out_df = pd.DataFrame(gloves_out_data) 

        full_path = os.path.join(settings.MEDIA_ROOT, "orderpallets")
        os.makedirs(full_path, exist_ok=True)  # 确保目录存在
        filename = f'Pallets_{year}_{month}.xlsx'
        file_path = os.path.join(full_path, filename)

        # 创建 Excel 文件
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            gloves_in_df.to_excel(writer, sheet_name='gloves in', index=False)
            gloves_out_df.to_excel(writer, sheet_name='gloves out', index=False)

        # 返回 Excel 文件
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            gloves_in_df.to_excel(writer, sheet_name='gloves in', index=False)
            gloves_out_df.to_excel(writer, sheet_name='gloves out', index=False)

            # 获取 workbook 和 worksheet 并设置格式
            workbook = writer.book
            gloves_in_ws = writer.sheets['gloves in']
            gloves_out_ws = writer.sheets['gloves out']

            format_worksheet(gloves_in_ws)
            format_worksheet(gloves_out_ws)

        return response
    else:
        return HttpResponse("Invalid month or year", status=400)
    

# 设置列宽和居中样式
def format_worksheet(ws):
    alignment = Alignment(horizontal='center', vertical='center')
    for col in ws.columns:
        max_length = 0
        column_letter = get_column_letter(col[0].column)
        for cell in col:
            cell.alignment = alignment
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        adjusted_width = max(max_length + 2, 12)  # 设置最小宽度为12
        ws.column_dimensions[column_letter].width = adjusted_width

# 邮件  
def preview_email(request):
    email_type = request.GET.get("type", "inventory")
    officedepot_id = request.POST.get('officedepot_number')
    print("officedepot_id: ",officedepot_id)

    is_rimei_user = request.user.username.lower() == "rimei"
    recipient = email_constants.RECIPIENT_OMAR_rimei if is_rimei_user else email_constants.RECIPIENT_OMAR_rosa
    signature = email_constants.SIGNATURE_AVA if is_rimei_user else email_constants.SIGNATURE_JING

    template_func = email_constants.INVENTORY_EMAIL_TEMPLATES.get(email_type, email_constants.INVENTORY_EMAIL_TEMPLATES["default"])
    email_data = template_func(officedepot_id, signature, is_rimei_user)

    return render(request, constants_view.template_temporary, email_data)

def order_email(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    email_type = request.GET.get("type", "shippeout")  # default to 'do' if not provided

    is_rimei_user = request.user.username.lower() == "rimei"
    recipient = email_constants.RECIPIENT_OMAR_rimei if is_rimei_user else email_constants.RECIPIENT_OMAR_rosa
    signature = email_constants.SIGNATURE_AVA if is_rimei_user else email_constants.SIGNATURE_JING

    # 获取模板（默认为 shippedout）
    template_func = email_constants.ORDER_EMAIL_TEMPLATES.get(email_type, email_constants.ORDER_EMAIL_TEMPLATES["shippedout"])
    email_data = template_func(order, signature, is_rimei_user)

    return render(request, constants_view.template_temporary, email_data)

def container_email(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    email_type = request.GET.get("type", "do")  # default to 'do' if not provided

    is_rimei_user = request.user.username.lower() == "rimei"
    recipient = email_constants.RECIPIENT_OMAR_rimei if is_rimei_user else email_constants.RECIPIENT_OMAR_rosa
    signature = email_constants.SIGNATURE_AVA if is_rimei_user else email_constants.SIGNATURE_JING

    # 获取模板（默认使用 default）
    template_func = email_constants.CONTAINER_EMAIL_TEMPLATES.get(email_type, email_constants.CONTAINER_EMAIL_TEMPLATES["default"])
    email_data = template_func(container, signature, is_rimei_user)

    return render(request, constants_view.template_temporary, email_data) 
