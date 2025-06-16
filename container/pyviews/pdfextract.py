import re
from datetime import datetime
from ..models import RMOrder,Container,RMInventory,RMProduct,ContainerItem,OrderItem
from . import inventory_count


# 提取订单信息
def extract_order_info(text):
    so_no = None
    order_date = None
    po_no = None
    pickup_date = None
    bill_to = None
    ship_to = None

    items = []
    quantities = []
    
    # 标志位，指示是否在 Item 和 Qty 部分
    is_item_section = False
    is_qty_section = False

    lines = text.split("\n")
    for i in range(len(lines)):
        line = lines[i].strip()
        # print(f"Line: {line}")
                        
        if "SO" in line:
            match = re.search(r"SO\s*[:]*\s*([\d/]+)", line)
            if match:
                so_no = match.group(1)

        if "Customer PO #" in line and i + 1 < len(lines):
            po_no = lines[i + 1].strip()

        if "Order Date" in line and i + 1 < len(lines):
            order_date_str = lines[i + 1].strip()  # Get the next line
            order_date = convert_to_yyyy_mm_dd(order_date_str)

        if "Date Expected" in line and i + 1 < len(lines):
            pickup_date_str = lines[i + 1].strip()  # Get the next line
            pickup_date = convert_to_yyyy_mm_dd(pickup_date_str)

        if "Bill To" in line:
            bill_to_lines = []
            for j in range(1, 5):  # Get the next four lines
                if i + j < len(lines):
                    bill_to_lines.append(lines[i + j].strip())
            bill_to = "\n".join(bill_to_lines) 

        if "Ship To" in line:
            ship_to_lines = []
            for j in range(1, 5):  # Get the next four lines
                if i + j < len(lines):
                    ship_to_lines.append(lines[i + j].strip())
            ship_to = "\n".join(ship_to_lines)

        # 检查是否是 Item Number / Name 部分
        if "Item Number / Name" in line:
            is_item_section = True
            continue  # 跳过标题行
        
        # 检查是否是 Qty 部分
        if "Qty" in line:
            is_qty_section = True
            continue  # 跳过标题行
        
        # 如果在 Item 部分，提取 Item
        if is_item_section and not is_qty_section:
            # 使用正则表达式提取 Item 名称
            item_match = re.match(r"(.+?)\s*[-]*$", line)  # 匹配 Item 名称
            if item_match:
                items.append(item_match.group(1).strip())
        
        # 如果在 Qty 部分，提取数量
        if is_qty_section:
            qty_match = re.match(r"(\d+)", line)  # 匹配数量
            if qty_match:
                quantities.append(int(qty_match.group(1).strip())) 

    return so_no, order_date, po_no, pickup_date, bill_to, ship_to, items, quantities

# 提取订单条目
def extract_items_from_pdf(text):
    # 1️⃣ Extract product lines between "Item Number / Name" and "Qty"
    pattern = re.compile(r'Item Number / Name(.*?)Qty(.*?)Unit', re.S)
    match = pattern.search(text)

    if not match:
        return []
    
    items_part = match.group(1).strip()
    qty_part = match.group(2).strip()

    # 2️⃣ Combine item names that span multiple lines
    items = []
    current_item = ""

    for line in items_part.split("\n"):
        line = line.strip()
        # 判断是否是新的一行（以数字、CAN、KLT、T 开头）
        if re.match(r'^\s*(\d{4,}|CAN|KLT|TC|TCL|TLESIM|PC|LPC|FACE|TLUB|GXL|RPR)(?!x)', line, re.IGNORECASE):
            if current_item:
                items.append(current_item.strip())
            current_item = line # 开始新的产品名称
        else:  # If it's the second line, add it to previous item
            current_item += " " + line # 追加到上一行

    # Add the last item
    if current_item:
        items.append(current_item.strip())

    # 3️⃣ Extract qtys
    qtys_raw = [q.strip() for q in qty_part.split("\n")]
    qtys = []

    for q in qtys_raw:
        # 去掉逗号，把字符串转换为整数
        try:
            qty_int = int(q.replace(",", ""))
            qtys.append(qty_int)
        except ValueError:
            # 如果无法转换为整数，可以跳过或设为 0，按你需要处理
            qtys.append(0)

    # 4️⃣ Combine item with qty
    product_qty_list = list(zip(items, qtys))

    # ✅ Output the result
    for item, qty in product_qty_list:
        print("item: ",item.strip(), "-->", qty)
    
    return product_qty_list

# 转换日期
def convert_to_yyyy_mm_dd(date_str):
    # 尝试解析日期字符串并转换为 YYYY-MM-DD 格式
    # print("--------convert_to_yyyy_mm_dd-------",date_str)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):  # 添加您需要支持的日期格式
        try:
            date_obj = datetime.strptime(date_str, fmt)
            # print("--------convert_to_yyyy_mm_dd-------",date_obj.strftime("%Y-%m-%d"))
            return date_obj.strftime("%Y-%m-%d")  # 转换为 YYYY-MM-DD 格式
        except ValueError:
            continue  # 如果格式不匹配，继续尝试下一个格式
    return None  # 如果没有匹配的格式，返回 None

# 提取Advance发票
def extract_invoice_data(text):
    """从PDF文本中提取 invoice_id, invoice_date, due_date, price"""
    # 提取所有类似日期格式 MM/DD/YYYY 的字符串
    date_matches = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    invoice_date = None
    due_date = None

    if len(date_matches) >= 2:
        invoice_date = datetime.strptime(date_matches[0], "%m/%d/%Y").date()
        due_date = datetime.strptime(date_matches[-1], "%m/%d/%Y").date()

    # 提取 invoice_id：0215083 出现多次，通常第一次就是
    invoice_id_match = re.search(r"\b(\d{7})\b", text)
    invoice_id = invoice_id_match.group(1) if invoice_id_match else None

    # 提取价格（美元格式）
    price_match = re.search(r"\$\s?(\d{1,3}(?:,\d{3})*|\d+)\.\d{2}", text)
    price = price_match.group(0).replace("$", "").replace(",", "") if price_match else None

    return {
        'invoice_id': invoice_id,
        'invoice_date': invoice_date,
        'due_date': due_date,
        'price': price
    }

# 提取Customer发票
def extract_customer_invoice_data(text):
    """从PDF文本中提取 invoice_id, invoice_date, due_date, price"""

    # 去除多余空格
    text = text.strip()
    lines = text.strip().splitlines()
    
    # 提取 invoice_id（假设以 OS 开头）
    invoice_id_match = re.search(r'\b(O[ST]\d{6,})\b', text)
    invoice_id = invoice_id_match.group(1) if invoice_id_match else None

    # 提取所有日期（格式：M/D/YYYY 或 MM/DD/YYYY）
    dates = re.findall(r'\b\d{1,2}/\d{1,2}/\d{4}\b', text)
    invoice_date = dates[0] if len(dates) >= 1 else None
    due_date = dates[1] if len(dates) >= 2 else None

    # 3. 查找 TOTAL 后的下一行金额作为 price
    for i, line in enumerate(lines):
        if 'TOTAL' in line.upper():
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                m = re.search(r'\$?\s?([\d,]+\.\d{2})', next_line)
                if m:
                    price = float(m.group(1).replace(',', ''))
                    break

    return {
        'invoice_id': invoice_id,
        'invoice_date': datetime.strptime(invoice_date, "%m/%d/%Y").date() if invoice_date else None,
        'due_date': datetime.strptime(due_date, "%m/%d/%Y").date() if due_date else None,
        'price': float(price) if price else 0.0
    }

# 补充库存信息
def get_product_qty_with_inventory(product_qty_list):
    result = []
    all_products = RMProduct.objects.all()
    
    for item, qty in product_qty_list:
        item_cleaned = item.strip()
        print(item_cleaned)
        qty_cleaned = qty

        matched_product = None

        for p in all_products:
            if (p.shortname and p.shortname.strip() in item_cleaned) or (p.name in item_cleaned):
                matched_product = p
                print(matched_product)
                break

        if matched_product:
            
            inventory = RMInventory.objects.filter(product=matched_product).first()
            # print("---",inventory.quantity, inventory.quantity_for_neworder, inventory.quantity_to_stock)
            inventory_qty = inventory.quantity_for_neworder if inventory else 0
        else:
            print(f"⚠️ 未找到匹配产品: {item_cleaned}")
            inventory_qty = 0

        print(f"item: {item_cleaned} --> ordered: {qty}, inventory: {inventory_qty}")
        result.append((item_cleaned, qty_cleaned, inventory_qty))

    return result

# 补充库存信息
def get_product_qty_with_inventory_from_order(order_items):

    for item in order_items:
        # 查询库存记录
        inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list = inventory_count.get_quality(item.product)
        inventory = RMInventory.objects.filter(product=item.product).first()
        product = inventory_count.get_product_qty(inventory, inbound_list, outbound_list, outbound_actual_list,outbound_stock_list,inbound_actual_list)

        item.inventory_qty = product.quantity
        item.pallet_qty = item.quantity //product.product.Pallet
        item.case_qty = item.quantity % product.product.Pallet
        if(product.product.shortname == "20HBC"):
            item.weight = item.quantity * 17.5
            print("20HBC: ",item.weight, product.quantity)
        elif(product.product.shortname == "FM003"):
            item.weight = item.quantity * 19
        else:
            item.weight = item.quantity * 14

    return order_items