import os
import pandas as pd

from datetime import datetime, date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect

from ..constants import constants_address, constants_view
from ..constants import email_constants
from ..models import (
    Container, RMProduct, AlineOrderRecord, RMOrder,
    InvoiceAPRecord, InvoiceVendor, Carrier, InvoicePurposeFor,
    CabinetProductType
)

from .utils.pdfgenerate import print_containerid_lot
from .utils.getPermission import get_user_permissions
from .utils.pdf_utils import create_pdf_canvas, finalize_pdf_and_response
from .utils.date_utils import parse_date
from .utils.file_utils import get_media_path, ensure_dir_exists, save_uploaded_file
from .utils.excel_utils import format_worksheet

# Temp
@login_required(login_url='/login/')
def temporary_view(request):
    user_permissions = get_user_permissions(request.user)

    years = [date.today().year]
    months = list(range(1, 13))  # 1 到 12 月
    return render(request, constants_view.template_temporary, {
        'user_permissions': user_permissions,
        'years': years,
        'months': months
    })


def print_label_only(request):
    print("----------print_label_only----------")
    so_num = request.POST.get('so_number')
    label_count = request.POST.get('quantity')
    
    try:
        label_count = int(label_count) if label_count is not None else 0
    except ValueError:
        label_count = 10  # Handle invalid input gracefully

    # 构建PDF文件路径
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        constants_address.LABEL_FOLDER
    )
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return HttpResponse("PDF文件未找到", status=404)

    filename = os.path.join(pdf_path, f"{so_num}.pdf")  # Save inside "label" folder
    c, pagesize, inch, ImageReader = create_pdf_canvas(filename)

    # Set font
    c.setFont(constants_address.font_Helvetica_Bold, constants_address.FONT_SIZE)
    
    y_position = constants_address.PAGE_HEIGHT - constants_address.MARGIN_TOP  # Start from the top of the page
    labels_on_page = 0  # Track labels per page
    first_page = True

    while label_count > 0:
        if not first_page:  
            c.showPage()  # Create a new page *only if necessary*
            c.setFont(constants_address.font_Helvetica_Bold, constants_address.FONT_SIZE)  # Reset font on new page
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
                c.setFont(constants_address.font_Helvetica_Bold, constants_address.FONT_SIZE)
                c.drawCentredString(text_x, text_y, so_num)
    
                # Draw label borders (for testing)
                if constants_address.DRAW_BORDERS:
                    c.rect(x, y_position - constants_address.LABEL_HEIGHT, constants_address.LABEL_WIDTH, constants_address.LABEL_HEIGHT)
    
                label_count -= 1  # Reduce remaining label count

            y_position -= constants_address.LABEL_HEIGHT  # Move to next row
            labels_on_page += 2  # Two labels per row

    return finalize_pdf_and_response(c, filename)

def print_label_containerid_lot(request):
    print("----------print_label_containerid_lot----------")
    so_num = request.POST.get('so_number')
    label_count = request.POST.get('quantity')
    container_id = request.POST.get('containerid')
    lot_number = request.POST.get('lot_number')
    current_date = datetime.now().strftime('%m/%d/%Y')

    # PDF 路径设置
    pdf_path = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        constants_address.LABEL_FOLDER
    )
    ensure_dir_exists(pdf_path)
    filename = os.path.join(pdf_path, f"{container_id}_lot.pdf")

    c, pagesize, inch, ImageReader = create_pdf_canvas(filename)
    start_index = 0
    for _ in range(int(label_count)):
        print_containerid_lot(c, so_num, container_id, lot_number, current_date, 84, True, start_index)
        start_index += 1
        if start_index % 10 == 0:
            c.showPage()
    return finalize_pdf_and_response(c, filename)

def print_mcd_label(request):
    print("----------print_mcd_label----------")

    lotnum = request.POST.get("lot_number", "").strip()
    startdate = request.POST.get("start_date", "").strip()
    expireddate = request.POST.get("expired_date", "").strip()

    if not lotnum:
        return HttpResponse("LOT number is required", status=400)

    # === PDF 路径 ===
    pdf_dir = get_media_path(
        constants_address.UPLOAD_DIR_temp,
        constants_address.MCD_FOLDER_Temp
    )
    ensure_dir_exists(pdf_dir)

    filename = os.path.join(pdf_dir, f"LOT_{lotnum}.pdf")

    # === 页面设置 ===    
    c, pagesize, inch, ImageReader = create_pdf_canvas(filename)
    PAGE_WIDTH, PAGE_HEIGHT = pagesize

    # === Label 布局 ===
    COLS = 5
    ROWS = 10
    ROW_GAP = 20
    COL_GAP = 10
    TOTAL_LABELS = 50

    MARGIN_LEFT = 5
    MARGIN_TOP = 30
    MARGIN_RIGHT = 5
    MARGIN_BOTTOM = 20

    usable_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - COL_GAP * (COLS - 1)
    # usable_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    usable_height = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM - ROW_GAP * (ROWS - 1)

    LABEL_WIDTH = usable_width / COLS
    LABEL_HEIGHT = usable_height / ROWS

    FONT_SIZE_TITLE = 16
    FONT_SIZE_TEXT = 14
    line_gap = 22    
    

    # === 开始画 labels ===
    for i in range(50):
        row = i // COLS
        col = i % COLS

        x = MARGIN_LEFT + col * (LABEL_WIDTH + COL_GAP)
        y = PAGE_HEIGHT - MARGIN_TOP - row * (LABEL_HEIGHT + ROW_GAP)

        # ===== Label center =====
        center_x = x + LABEL_WIDTH / 2
        label_center_y = y - LABEL_HEIGHT / 2

        # ===== Text block center =====
        text_block_height = line_gap * 2
        base_y = label_center_y + text_block_height / 2

        # ===== Draw text =====
        c.setFont(constants_address.font_Helvetica_Bold, FONT_SIZE_TITLE)
        c.drawCentredString(center_x, base_y,                f"{lotnum}")
        c.setFont(constants_address.font_Helvetica, FONT_SIZE_TEXT)
        c.drawCentredString(center_x, base_y - line_gap,     f"{startdate}")
        c.drawCentredString(center_x, base_y - line_gap * 2, f"{expireddate}")

    return finalize_pdf_and_response(c, filename)


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
                shortname=row["Short Name"],
                size=row["Size"],
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

def import_accounting(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read the Excel file into a DataFrame
        df = pd.read_excel(excel_file, engine='openpyxl')

        # ✅ 固定选项对象
        fixed_vendor = InvoiceVendor.objects.get(id=1)
        fixed_company = Carrier.objects.get(id=1)
        fixed_purpose = InvoicePurposeFor.objects.get(id=2)

        # Ensure column names match the model fields
        for index, row in df.iterrows():
            # 处理日期字段 - 使用工具函数
            due_date = parse_date(row["Due Date"]) if pd.notna(row.get("Due Date", None)) else None
            givetoboss_date = parse_date(row["Give to BOSS Date"]) if pd.notna(row.get("Give to BOSS Date", None)) else None
            payment_date = parse_date(row["Paid Date"]) if pd.notna(row.get("Paid Date", None)) else None

            # Create RMProduct instance
            product = InvoiceAPRecord.objects.create(
                vendor=fixed_vendor,
                invoice_id=row["Invoice No."],
                invoice_price=row["Amount"],
                company=fixed_company,
                due_date=due_date,
                givetoboss_date=givetoboss_date,
                payment_date=payment_date,
                purposefor=fixed_purpose,
                note=row["Notes"],
            )

        return JsonResponse({"message": "Excel data imported successfully!"})
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

def import_cabinettype(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        # Read the Excel file into a DataFrame
        df = pd.read_excel(excel_file, engine='openpyxl')
        df.columns = df.columns.str.strip()

        required_columns = ["name", "pallet_usage"]
        for col in required_columns:
            if col not in df.columns:
                return JsonResponse(
                    {"error": f"Excel missing column: {col}"},
                    status=400
                )

        created_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            name = str(row["name"]).strip()
            pallet_usage = float(row["pallet_usage"])

            # ⭐ 核心：存在就更新，不存在就创建
            obj, created = CabinetProductType.objects.update_or_create(
                name=name,
                defaults={
                    "pallet_usage": pallet_usage,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return JsonResponse({
            "message": "Excel data imported successfully!",
            "created": created_count,
            "updated": updated_count
        })
    
    return JsonResponse({"error": "No file uploaded"}, status=400)

# export pallets
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

        full_path = get_media_path(
            constants_address.UPLOAD_DIR_temp,
            constants_address.UPLOAD_DIR_orderpallets
        )
        ensure_dir_exists(full_path)
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
    
# Office depot, inventory, order received
def preview_email(request):
    email_type = request.POST.get("action")
    officedepot_id = request.POST.get('officedepot_number')

    username  = request.user.username.lower()
    SIGNATURE_MAP = {
        "rosa": email_constants.SIGNATURE_JING,
        "rimei": email_constants.SIGNATURE_AVA,
        "david": email_constants.SIGNATURE_DAVID,
    }
    signature = SIGNATURE_MAP.get(username, email_constants.SIGNATURE_JING)
    is_rimei_user = username in ["rimei", "david"]

    current_date = datetime.now().strftime("%m/%d/%Y")
    template_func = email_constants.INVENTORY_EMAIL_TEMPLATES.get(email_type, email_constants.INVENTORY_EMAIL_TEMPLATES["default"])
    email_data = template_func(
        officedepot_id=officedepot_id,  # 👈 只有需要的模板才会用
        signature=signature,
        is_rimei_user=is_rimei_user,
        current_date=current_date,
    )

    return render(request, constants_view.template_temporary, email_data)

# order ship out
def order_email(request, so_num):
    order = get_object_or_404(RMOrder, so_num=so_num)
    email_type = request.GET.get("type", "shippeout")  # default to 'do' if not provided
    
    username  = request.user.username.lower()
    SIGNATURE_MAP = {
        "rosa": email_constants.SIGNATURE_JING,
        "rimei": email_constants.SIGNATURE_AVA,
        "david": email_constants.SIGNATURE_DAVID,
    }
    signature = SIGNATURE_MAP.get(username, email_constants.SIGNATURE_JING)
    is_rimei_user = username in ["rimei", "david"]

    # 获取模板（默认为 shippedout）
    template_func = email_constants.ORDER_EMAIL_TEMPLATES.get(email_type, email_constants.ORDER_EMAIL_TEMPLATES["shippedout"])
    email_data = template_func(order, signature, is_rimei_user)

    return render(request, constants_view.template_temporary, email_data)

# container DO, empty, receive in
def container_email(request, container_id):
    container = get_object_or_404(Container, container_id=container_id)
    email_type = request.GET.get("type", "do")  # default to 'do' if not provided

    carrier = 0
    if email_type == "do":
        try:
            do_option = int(request.GET.get("do_option", 1))
        except ValueError:
            do_option = 1

        if do_option == 1:
            # A 逻辑
            carrier = 1
        elif do_option == 2:
            # B 逻辑
            carrier = 2
        elif do_option == 3:
            # C 逻辑
            carrier = 3
        elif do_option == 4:
            # C 逻辑
            carrier = 4

    username  = request.user.username.lower()
    SIGNATURE_MAP = {
        "rosa": email_constants.SIGNATURE_JING,
        "rimei": email_constants.SIGNATURE_AVA,
        "david": email_constants.SIGNATURE_DAVID,
    }
    signature = SIGNATURE_MAP.get(username, email_constants.SIGNATURE_JING)
    is_rimei_user = username in ["rimei", "david"]

    # 获取模板（默认使用 default）
    template_func = email_constants.CONTAINER_EMAIL_TEMPLATES.get(email_type, email_constants.CONTAINER_EMAIL_TEMPLATES["default"])
    email_data = template_func(container, signature, is_rimei_user, carrier)

    return render(request, constants_view.template_temporary, email_data) 
