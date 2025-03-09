
from django.shortcuts import render, redirect
from .models import Container, RMOrder,RMCustomer
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import UserAndPermission
from django.db.models import Count

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
    context = {
        "recipient": "someone@example.com",
        "subject": "Invoice Details",
        "body": "Hello,\n\nPlease find the invoice details attached.\n\nBest regards."
    }
    return render(request, template, context)

def rimeiorder_view(request):
    template = "container/rmorder.html"
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


