
from django.utils import timezone

# 日期
CURRENT_DATE = timezone.now().strftime("%m/%d/%Y")

# 收件人
RECIPIENT_OMAR = "omarorders@omarllc.com;omarwarehouse@rimeius.com"
RECIPIENT_ADVANCE = "jovana@advance77.com;tijana@advance77.com;raluca@advance77.com;intermodal@advance77.com"

def get_preview_email_template(email_type, signature, recipient, officedepot_id=None):
    if email_type == 1:
        return {
            "recipient": recipient,
            "subject": f"INVENTORY {CURRENT_DATE}",
            "body": f"Hello,\n\nINVENTORY SUMMARY {CURRENT_DATE}. \nPaperwork attached.\n\n{signature}"
        }
    elif email_type == 4 and officedepot_id:
        return {
            "recipient": recipient,
            "subject": f"OFFICE DEPOT #{officedepot_id} shipped out",
            "body": f"Hello,\n\nOffice Depot# {officedepot_id} has been shipped out. \nPaperwork is attached.\n\nThank you!\n{signature}"
        }
    elif email_type == 5:
        return {
            "recipient": recipient,
            "subject": "Received Order Email",
            "body": f"Well Received.\n\nThank you!\n{signature}"
        }
    else:
        return {
            "recipient": recipient,
            "subject": "Received Order Email",
            "body": f"Well Received.\n\nThank you!\n{signature}"
        }

# order_email 的邮件模板（按类型）
ORDER_EMAIL_TEMPLATES = {
    "shippedout": lambda order, signature: {
        "recipient": RECIPIENT_OMAR,
        "subject": f"SO# {order.so_num} PO# {order.po_num} shipped out",
        "body": f"Hello,\n\nSO# {order.so_num} PO# {order.po_num} has been shipped out.\nPaperwork is attached.\n\nThank you!\n{signature}"
    }
}

# container_email 的邮件模板（按类型）
CONTAINER_EMAIL_TEMPLATES = {
    "do": lambda container, signature: {
        "recipient": RECIPIENT_ADVANCE,
        "subject": f"New **  D/O **  {container.container_id} / OMAR- RIMEI",
        "body": f"Hello,\n\nPlease see new DO for these containers going to Lemont.\n\nContainer: {container.container_id}\nMBL: {container.mbl}\n\nThank you!\n{signature}"
    },
    "received": lambda container, signature: {
        "recipient": RECIPIENT_OMAR,
        "subject": f"{container.container_id} RECEIVED IN Notification",
        "body": f"Hello,\n\n{container.container_id} has been received in.\nPaperwork is attached.\n\nThank you!\n{signature}"
    },
    "empty": lambda container, signature: {
        "recipient": RECIPIENT_ADVANCE,
        "subject": f"{container.container_id} Empty Container Notification",
        "body": f"Hello,\n\nContainer {container.container_id} is now empty and ready for pickup.\n\nThank you!\n{signature}"
    },
    "default": lambda container, signature: {
        "recipient": RECIPIENT_OMAR,
        "subject": f"Notification - {container.container_id}",
        "body": f"Hello,\n\nThis is a notification regarding container {container.container_id}.\n\nThank you!\n{signature}"
    }
}