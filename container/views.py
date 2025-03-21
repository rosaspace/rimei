from django.shortcuts import render, redirect
from .models import Container, RMOrder,RMCustomer
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import UserAndPermission
from django.db.models import Count
from django.utils import timezone

# Create your views here.
def index(request):
    template = "container/base.html"
    return render(request, template)

def container_view(request):
    template = "container/container.html"
    containers = Container.objects.all()
    return render(request, template, {'containers': containers})

def invoice_view(request):
    template = "container/invoice.html"
    containers = Container.objects.all()
    return render(request, template, {'containers': containers})

def payment_view(request):
    template = "container/payment.html"    
    return render(request, template)

def rimeiorder_view(request):
    template = "container/rmorder2.html"
    # orders = RMOrder.objects.all()
    orders = RMOrder.objects.all().annotate(image_count=Count('images'))
    customers = RMCustomer.objects.all()

    # 创建年份和月份的选项
    years = [str(year) for year in range(2024, 2026)] 
    months = [f"{month:02d}" for month in range(1, 13)]  # 01到12月

    return render(request, template, {
        'rimeiorders': orders,
        'customers': customers,
        'years': years,
        'months': months
        })

def temporary_view(request):
    template = "container/temporary.html"
    return render(request, template)

def preview_email(request, number, so_number=None, po_number=None, container_id=None, officedepot_id=None):
    template = "container/temporary.html"
    recipient = "omarorders@omarllc.com,omarwarehouse@rimeius.com"
    current_date = timezone.now().strftime("%m/%d/%Y")
    if number == 1:
        context = {
            "recipient": recipient,
            "subject": f"INVENTORY {current_date}",
            "body": f"Hello,\n\nINVENTORY SUMMARY {current_date}. Paperwork attached.\n\nJing"
        }
    elif number == 2:
        context = {
            "recipient": recipient,
            "subject": "Shipped out Email",
            "body": f"Hello,\n\nSO #{so_number} PO #{po_number}  has been shipped out. Paperwork is attached.\n\nThank you!\nJing"
        }
    elif number == 3:
        context = {
            "recipient": recipient,
            "subject": f"{container_id} RECEIVED IN",
            "body": f"Hello,\n\n{container_id}  has received in. Paperwork is attached.\n\nThank you!\nJing"
        }
    elif number == 4:
        context = {
            "recipient": recipient,
            "subject": f"OFFICE DEPOT #{officedepot_id}",
            "body": f"Hello,\n\nOffice Depot order #{officedepot_id} shipped out. Paperwork is attached.\n\nThank you!\nJing"
        }
    else:
        context = {
            "recipient": recipient,
            "subject": "Received Order Email",
            "body": "Well Received.\n\nThank you!\nJing"
        }
    return render(request, template, context)

