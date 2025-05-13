import re
from datetime import datetime

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