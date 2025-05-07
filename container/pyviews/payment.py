from django.shortcuts import render, redirect, get_object_or_404
from ..models import AlineOrderRecord

def edit_aline(request, order_number):
    alineOrder = get_object_or_404(AlineOrderRecord, order_number=order_number)

    if request.method == 'GET':
        return render(request, 'container/payment/edit_aline.html',{'order': alineOrder})
    elif request.method == 'POST':
        alineOrder.ispay = request.POST.get('is_pay') == 'on'                                         
        alineOrder.save()
        
        return redirect('aline_payment')