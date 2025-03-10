from django import template
from ..models import RMInventory

register = template.Library()

@register.filter
def get_item(inventory_items, product_id):
    """根据产品 ID 获取库存项"""
    for item in inventory_items:
        if item.product.id == product_id:
            return item
    return None