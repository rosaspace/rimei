
from django.shortcuts import render, redirect
from .models import Container, RMOrder
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import UserAndPermission

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

def rimeiorder(request):
    template = "container/rmorder.html"
    orders = RMOrder.objects.all()
    return render(request, template, {'rimeiorders': orders})


