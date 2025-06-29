
from django.utils import timezone

# 日期
CURRENT_DATE = timezone.now().strftime("%m/%d/%Y")

# 收件人
SIGNATURE_AVA = "Ava"
SIGNATURE_JING = "Jing"
RECIPIENT_OMAR_rosa = "omarorders@omarllc.com;omarwarehouse@rimeius.com"
RECIPIENT_OMAR_rimei ="omarorders@omarllc.com;order@rimeius.com"
RECIPIENT_ADVANCE = "jovana@advance77.com;tijana@advance77.com;raluca@advance77.com;intermodal@advance77.com"

# container_email 的邮件模板（按类型）
INVENTORY_EMAIL_TEMPLATES = {
    "inventory": lambda officedepot_id, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": f"INVENTORY {CURRENT_DATE}",
        "body": f"Hello,\n\nINVENTORY SUMMARY {CURRENT_DATE}. \nPaperwork attached.\n\n{signature}"
    },
    "officedepot": lambda officedepot_id, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": f"OFFICE DEPOT #{officedepot_id} shipped out",
        "body": f"Hello,\n\nOffice Depot# {officedepot_id} has been shipped out. \nPaperwork is attached.\n\nThank you!\n{signature}"
    },
    "default": lambda officedepot_id, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": "Received Order Email",
        "body": f"Well Received.\n\nThank you!\n{signature}"
    }
}

# order_email 的邮件模板（按类型）
ORDER_EMAIL_TEMPLATES = {
    "shippedout": lambda order, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": f"SO# {order.so_num} PO# {order.po_num} shipped out",
        "body": f"Hello,\n\nSO# {order.so_num} PO# {order.po_num} has been shipped out.\nPaperwork is attached.\n\nThank you!\n{signature}"
    }
}

# container_email 的邮件模板（按类型）
CONTAINER_EMAIL_TEMPLATES = {
    "do": lambda container, signature, is_rimei_user: {
        "recipient": RECIPIENT_ADVANCE,
        "subject": f"New **  D/O **  {container.container_id} / OMAR- RIMEI",
        "body": f"Hello,\n\nPlease see new DO for this container going to Lemont.\nContainer: {container.container_id}\nMBL: {container.mbl}\n\nThank you!\n{signature}"
    },
    "received": lambda container, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": f"{container.container_id} RECEIVED IN Notification",
        "body": f"Hello,\n\n{container.container_id} has been received in.\nPaperwork is attached.\n\nThank you!\n{signature}"
    },
    "empty": lambda container, signature, is_rimei_user: {
        "recipient": RECIPIENT_ADVANCE,
        "subject": f"{container.container_id} Empty Container Notification",
        "body": f"Hello,\n\nContainer {container.container_id} is now empty and ready for pickup.\n\nThank you!\n{signature}"
    },
    "default": lambda container, signature, is_rimei_user: {
        "recipient": RECIPIENT_OMAR_rimei if is_rimei_user else RECIPIENT_OMAR_rosa,
        "subject": f"Notification - {container.container_id}",
        "body": f"Hello,\n\nThis is a notification regarding container {container.container_id}.\n\nThank you!\n{signature}"
    }
}