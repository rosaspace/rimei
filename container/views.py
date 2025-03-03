from django.shortcuts import render
from .models import Container

# Create your views here.
def index(request):
    template = "container/base.html"
    return render(request, template)

def container_view(request):
    template = "container/container.html"
    return render(request, template)

def invoice_view(request):
    template = "container/invoice.html"
    containers = Container.objects.all()
    return render(request, template,{'containers': containers})

def payment_view(request):
    template = "container/payment.html"
    return render(request, template)