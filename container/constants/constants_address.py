import os
from django.conf import settings
from reportlab.lib.pagesizes import letter

# 替换文本 & 插入图片
NEW_ADDRESS = """RIMEI INTERNATION INC
1285 101st St
Lemont, IL 60439"""
NEW_TITLE = "Packing Slip" 

rimei_address = 'Rimei INTERNATION INC\n1285 101st St\nLemont, IL 60439'

Only_ADDRESS = [
    "1285 101st St",
    "Lemont, IL 60439"
]

RM_ADDRESS = [
    "RIMEI INTERNATION INC",
    "1285 101st Street",
    "Lemont, IL 60439"
]

GF_ADDRESS = [
    "Golden Feather Supplies LLC",
    "1285 101st St",
    "Lemont, IL 60439"
]

SSA_ADDRESS = [
    "Secure Source America LLC",
    "1285 101 st Street, Lemont, IL 60439",
    "TEL: 708-882-1188",
    "accounting@securesourceamerica.com"
]

CONSIGNEE = [
    "OMAR",
    "1285 101st",
    "LEMONT, IL 60439"
]

address_mapping = {
    "Speedier": [
        "SPEEDIER LOGISTIC INC.",
        "175-01 Rockaway Blvd. Ste. 305",
        "Jamaica, NY 11434",
        "Tel: 7183735400"
    ],
    "Trans Knights": [
        "TRANS KNIGHTS INC",
        "18030 CORTNEY CT",
        "CITY OF INDUSTRY, CA 91748"
    ]
}

labor_left_text = """
Rimei International Inc<br/>
1285 101st Street, <br/>
Lemont, IL 60439"""

labor_right_text = """
Citi Bank<br/>
Routing# 271070801<br/>
Account# 801776329<br/>
Account Name: Rimei International Inc"""

# Invoice
Chassis_rate = 40
EmptyContainerRelocate_rate = 150
ClassisSplit_rate = 70 
Pre_pull_rate = 150
Yard_storage_rate = 45

# 描述映射：原始 → 表格描述
description_mapping = {
    "INTERM1": "Drayage (FSC all included)",
    "Chassis use": "Chassis",
    "Chassis split": "Chassis split", 
    "Storage": "Yard storage",
    "Prepull": "Pre-pull",
    "Rail storage + fee": "Rail storage",
    "Rail storage + 20% fee": "Rail storage",
    "OW citation":"OW TICKET",
    "OW Citation":"OW TICKET",
    "OW ticket - citation":"OW",
    "OW":"Overweight",
    "flip":"Flip",
    "Dry run":"Dry Run",
    "Drop Off":"Drop Off",
    # 可继续扩展其他映射项
}

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

# Font size
# FONT_SIZE = 60  # Larger font size
FONT_SIZE =  50  # Larger font size
# FONT_SIZE = 30  # Larger font size
FONT_SIZE_Lot = 20
FONT_SIZE_Container = 36  # Larger font size
LINE_SPACING = 40
DRAW_BORDERS = False  # Set to True to draw borders, False to hide the

font_Helvetica = "Helvetica"
font_Helvetica_Bold = "Helvetica-Bold"

# 一行的文字长度
max_line_width = 96  # 根据页面宽度大致估算字符数

# 注意事项
note_lines = [
    "Remove 1 case of each size performing physical examinations on the box as well as a detailed examination of a glove in each.",
    "Check for black spots, tears, discoloration, and dampness, etc. ",
    "Briefly check elasticity ensuring the glove doesn’t easily rip.", 
    "Check the accuracy of the packaging does the external Bo match up with the internal boxes pertaining to weight, size, and the product number?",
    "Check the external box of individual boxes for spelling and print accuracy. ",
]
DO_CONTACT_LINES = [
    "FOR DELIVERY AND APPOINTMENT INSTRUCTIONS, CONTACT TEL:+1 630-909-9888",
    "BEFORE ATTEMPTING PICK-UP OR DELIVERY OF CARGO"
]

DO_FOOTER_LINES_TEMPLATE = [
    "Total Containers: 1",
    "Commodity: {commodity}",
    "Vessel: {vessel}",
    "Voyage: {voyage}",
    "SSL: {ssl}",
]
DO_SIGNATURE_LINES = [
    "Received in Good Order",
    "By: _____________________________",
    "Date:                                 Time:"
]