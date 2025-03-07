from django.shortcuts import render, redirect
from django.contrib import messages
from ..models import RMOrder, RMCustomer
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def create_rmorder(request):
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