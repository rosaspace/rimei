from django.shortcuts import render, redirect
from django.contrib import messages
from ..models import RMOrder, RMCustomer, OrderImage
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import JsonResponse
from django.db.models import Count

@require_http_methods(["GET", "POST"])
def add_order(request):
    if request.method == "POST":
        try:
            # 检查SO号是否已存在
            so_num = request.POST.get('so_num')
            if RMOrder.objects.filter(so_num=so_num).exists():
                messages.error(request, f'创建订单失败：SO号 {so_num} 已存在')
                customers = RMCustomer.objects.all()
                return render(request, 'container/rmorder/add_order.html', {
                    'customers': customers,
                    'order': {
                        'so_num': request.POST.get('so_num'),
                        'po_num': request.POST.get('po_num'),
                        'plts': request.POST.get('plts'),
                        'pickup_date': request.POST.get('pickup_date'),
                        'outbound_date': request.POST.get('outbound_date'),
                        'customer_name': RMCustomer.objects.get(id=request.POST.get('customer_name')),
                        'is_sendemail': request.POST.get('is_sendemail') == 'on',
                        'is_updateInventory': request.POST.get('is_updateInventory') == 'on'
                    }
                })

            customer = RMCustomer.objects.get(id=request.POST.get('customer_name'))
            order = RMOrder(
                so_num=request.POST.get('so_num'),
                po_num=request.POST.get('po_num'),
                plts=request.POST.get('plts'),
                customer_name=customer,
                pickup_date=request.POST.get('pickup_date') or None,
                outbound_date=request.POST.get('outbound_date') or None,
                is_sendemail=request.POST.get('is_sendemail') == 'on',
                is_updateInventory=request.POST.get('is_updateInventory') == 'on'
            )
            order.save()
            messages.success(request, '订单创建成功！')
            return redirect('rimeiorder')
        except Exception as e:
            messages.error(request, f'创建订单失败：{str(e)}')
    
    customers = RMCustomer.objects.all()
    return render(request, 'container/rmorder/add_order.html', {'customers': customers})

@require_http_methods(["GET", "POST"])
def edit_order(request, so_num):
    try:
        order = RMOrder.objects.get(so_num=so_num)
        if request.method == "POST":
            try:
                new_so_num = request.POST.get('so_num')
                if new_so_num != so_num and RMOrder.objects.filter(so_num=new_so_num).exists():
                    messages.error(request, f'更新订单失败：SO号 {new_so_num} 已存在')
                    customers = RMCustomer.objects.all()
                    return render(request, 'container/rmorder/add_order.html', {
                        'order': order,
                        'customers': customers
                    })

                customer = RMCustomer.objects.get(id=request.POST.get('customer_name'))
                order.so_num = new_so_num
                order.po_num = request.POST.get('po_num')
                order.plts = request.POST.get('plts')
                order.customer_name = customer
                order.pickup_date = request.POST.get('pickup_date') or None
                order.outbound_date = request.POST.get('outbound_date') or None
                order.is_sendemail = request.POST.get('is_sendemail') == 'on'
                order.is_updateInventory = request.POST.get('is_updateInventory') == 'on'                
                order.save()
                messages.success(request, '订单更新成功！')
                return redirect('rimeiorder')
            except Exception as e:
                messages.error(request, f'更新订单失败：{str(e)}')
        
        customers = RMCustomer.objects.all()
        return render(request, 'container/rmorder/add_order.html', {
            'order': order,
            'customers': customers
        })
    except RMOrder.DoesNotExist:
        messages.error(request, '订单不存在')
        return redirect('rmorder')
    
def search_order(request):
    print("--------------search_order-----------------")
    
    # 获取搜索参数
    search_so = request.GET.get('search_so', '')
    search_po = request.GET.get('search_po', '')
    search_customer = request.GET.get('search_customer', '')
    search_pickup_date = request.GET.get('search_pickup_date', '')

    # 构建查询条件
    filters = Q()
    if search_so:
        filters &= Q(so_num=search_so)
    if search_po:
        filters &= Q(po_num=search_po)
    if search_customer:
        filters &= Q(customer_name__id=search_customer)  # 使用客户 ID 进行过滤
    if search_pickup_date:
        filters &= Q(pickup_date=search_pickup_date)

    # 根据过滤条件获取订单，并计算每个订单的图片数量
    rimeiorders = RMOrder.objects.filter(filters).annotate(image_count=Count('images'))

    # 打印每个订单的图片数量
    # for order in rimeiorders:
    #     print(f"Order ID: {order.id}, Image Count: {order.image_count}")

    # 获取所有客户
    customers = RMCustomer.objects.all()

    return render(request, 'container/rmorder.html', {
        'rimeiorders': rimeiorders,
        'customers': customers,  # 将客户列表传递给模板
    })

@require_http_methods(["POST"])
def upload_images(request, order_id):
    try:
        order = RMOrder.objects.get(id=order_id)
        images = request.FILES.getlist('images')  # 获取上传的图片

        for image in images:
            OrderImage.objects.create(order=order, image=image)  # 保存图片与订单的关联

        return JsonResponse({"success": True})
    except RMOrder.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order does not exist."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)