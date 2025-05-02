from django.shortcuts import render, redirect
from ..models import RMProduct, RMInventory
from django.http import JsonResponse
import json

def add_stock_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # 解析 JSON 数据
            items = data.get("items", [])

            for item in items:
                product_id = item.get("product_id")
                quantity = item.get("quantity")

                # if quantity <= 0:
                #     return JsonResponse({"message": "Invalid quantity for product ID: {}".format(product_id)}, status=400)

                # 查找产品并更新库存
                product = RMProduct.objects.get(id=product_id)
                inventory_item, created = RMInventory.objects.get_or_create(product=product)
                inventory_item.quantity += quantity
                inventory_item.save()

            return JsonResponse({"message": "Stock updated successfully!"})

        except Exception as e:
            return JsonResponse({"message": str(e)}, status=400)

    products = RMProduct.objects.all()  # 获取所有产品
    return render(request, "container/rmorder/add_stock.html", {"products": products})

def remove_stock_view(request):
    print("-------remove_stock_view---------")
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # 解析 JSON 数据
            items = data.get("items", [])

            for item in items:
                product_id = item.get("product_id")
                quantity = item.get("quantity")

                # if quantity <= 0:
                #     return JsonResponse({"message": "Invalid quantity for product ID: {}".format(product_id)}, status=400)

                # 查找产品并更新库存
                product = RMProduct.objects.get(id=product_id)
                inventory_item = RMInventory.objects.get(id=product)
                inventory_item.quantity -= quantity
                inventory_item.save()
            
            return JsonResponse({"message": "Stock updated successfully!"})
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=400)

    products = RMProduct.objects.all()  # 获取所有产品
    return render(request, "container/rmorder/remove_stock.html", {"products": products})