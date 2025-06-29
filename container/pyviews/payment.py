from django.shortcuts import render, redirect, get_object_or_404
from ..models import AlineOrderRecord
from ..constants import constants_view

def edit_aline(request, order_number):
    alineOrder = get_object_or_404(AlineOrderRecord, order_number=order_number)

    if request.method == 'GET':
        return render(request, constants_view.template_edit_aline,{'order': alineOrder})
    elif request.method == 'POST':
        alineOrder.ispay = request.POST.get('is_pay') == 'on'                                         
        alineOrder.save()
        
        return redirect('aline_payment')
    
def aline_ispay(request, order_number):
    alineOrder = get_object_or_404(AlineOrderRecord, order_number=order_number)
    alineOrder.ispay = not alineOrder.ispay
    alineOrder.save()
    
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)