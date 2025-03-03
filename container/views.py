from django.shortcuts import render

# Create your views here.
def index(request):
    template = "container/base.html"
    return render(request, template)

def container_view(request):
    template = "container/container.html"
    return render(request, template)

def invoice_view(request):
    template = "container/invoice.html"
    return render(request, template)

def payment_view(request):
    template = "container/payment.html"
    return render(request, template)