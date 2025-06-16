from django.shortcuts import render, redirect
from .models import Container, RMOrder,RMCustomer,RMInventory,AlineOrderRecord
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import UserAndPermission
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F
from django.template.loader import get_template
from django.http import HttpResponse
from weasyprint import HTML
import tempfile
from datetime import datetime
from django.utils import timezone

@login_required
def home(request):
    return render(request, "container/login/login.html")

@login_required
def index(request):
    template = "container/base.html"  
    user_permissions = get_user_permissions(request.user)
    return render(request, template,{'user_permissions': user_permissions})

def invoice_view(request):
    template = "container/invoice.html"

    containers = Container.objects.exclude(
        Q(ispay=True, customer_ispay=True) |
        Q(customer = 3, ispay=True)
    ).exclude(
        logistics=2
    ).order_by('-due_date')
    
    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

def invoice_finished(request):
    template = "container/invoice.html"

    containers = Container.objects.filter(
        Q(ispay=True, customer_ispay=True) |
        Q(customer = 3, ispay=True)
    ).exclude(
        logistics=2
    ).order_by('-due_date')

    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

def invoice_unpaid(request):
    template = "container/invoice.html"
    containers = Container.objects.filter(
        Q(ispay=False, customer_ispay=True) |
        Q(customer = 3, ispay=False, invoice_id__isnull=False) |
        Q(customer = 12, ispay=False, invoice_id__isnull=False)
    ).order_by('-due_date')
    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

def generate_selected_invoices(request):
    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_ids')
        containers = Container.objects.filter(id__in=selected_ids)
        total_price = sum([c.price for c in containers if c.price])
        return render(request, "container/invoiceManager/generated_invoice_preview.html", {
            "containers": containers, 
            "total_price": total_price,
            "current_date": datetime.now().strftime("%m/%d/%Y"),},)
    return redirect("invoice_unpaid")

def paid_invoice(request):
    ids = request.POST.getlist('all_ids')
    date_str = request.POST.get('payment_date')
    payment_date = timezone.now().date()  # 默认今天

    if date_str:
        try:
            payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # 如果解析失败就用默认

    Container.objects.filter(id__in=ids).update(
        ispay=True,
        payment_date=payment_date
    )
    template = "container/invoice.html"
    return render(request, template)

def paid_invoice_customer(request):
    ids = request.POST.getlist('all_ids')
    date_str = request.POST.get('payment_date')
    customer_payment_date = timezone.now().date()

    if date_str:
        try:
            customer_payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    Container.objects.filter(id__in=ids).update(
        customer_ispay=True,
        customer_payment_date=customer_payment_date
    )
    template = "container/invoice.html"
    return render(request, template)

def payment_view(request):
    template = "container/payment.html"  
    user_permissions = get_user_permissions(request.user)  
    return render(request, template,{'user_permissions': user_permissions})

def aline_payment_view(request):
    template = "container/payment_aline.html"  
    alineOrders = AlineOrderRecord.objects.all().order_by('due_date')
    user_permissions = get_user_permissions(request.user)  
    return render(request, template,{'orders':alineOrders, 'user_permissions': user_permissions})

def container_view(request):
    template = "container/container.html"
    containers = Container.objects.all()
    user_permissions = get_user_permissions(request.user) 
    unfinished_containers = containers.filter(
         is_updateInventory=False, 
    )    
    print("unfinished_containers, ",len(unfinished_containers))

    return render(request, template, {'containers': unfinished_containers,'user_permissions': user_permissions})

def container_view_finished(request):
    template = "container/container.html"
    containers = Container.objects.all().order_by('-delivery_date')
    user_permissions = get_user_permissions(request.user) 
    finished_containers = containers.exclude(
        is_updateInventory=False, 
    )
    print("finished_containers, ",len(finished_containers))

    return render(request, template, {'containers': finished_containers,'user_permissions': user_permissions})

def rimeiorder_view(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.exclude(customer_name='4').annotate(image_count=Count('images')).order_by('pickup_date')
    user_permissions = get_user_permissions(request.user) 
    unfinished_orders = orders.filter(
        is_updateInventory=False, 
        is_canceled=False
    )
    print("unfinished_orders, ",len(unfinished_orders))

    return render(request, template, {
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions
        })

def rimeiorder_view_finished(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.all().annotate(image_count=Count('images')).order_by('-pickup_date')
    user_permissions = get_user_permissions(request.user) 
    finished_orders = orders.exclude(
        is_updateInventory=False, 
        is_canceled=False
    )
    print("finished_orders, ",len(finished_orders))

    return render(request, template, {
        'rimeiorders': finished_orders,
        'user_permissions': user_permissions
        })

def rimeiorder_officedepot(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.filter(customer_name='4').annotate(image_count=Count('images')).order_by('pickup_date')
    user_permissions = get_user_permissions(request.user) 
    finished_orders = orders.filter(
        is_updateInventory=False, 
        is_canceled=False
    )
    print("finished_orders, ",len(finished_orders))

    return render(request, template, {
        'rimeiorders': finished_orders,
        'user_permissions': user_permissions
        })

def rimeiorder_cancel(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.filter(is_canceled=True).annotate(image_count=Count('images')).order_by('pickup_date')
    user_permissions = get_user_permissions(request.user) 
    finished_orders = orders.exclude(
        is_updateInventory=False, 
        is_canceled=False
    )
    print("finished_orders, ",len(finished_orders))

    return render(request, template, {
        'rimeiorders': finished_orders,
        'user_permissions': user_permissions
        })

@login_required
def inventory_view(request):
    inventory_items = RMInventory.objects.all()  # 获取所有库存信息
    user_permissions = get_user_permissions(request.user)
    return render(request, "container/inventory.html", {"inventory_items": inventory_items,'user_permissions': user_permissions})

def inventory_diff_view(request):
    inventory_items = RMInventory.objects.filter(
        ~Q(quantity=F('quantity_for_neworder'))
    ).order_by('quantity_for_neworder')
    user_permissions = get_user_permissions(request.user)
    return render(request, "container/inventory.html", {"inventory_items": inventory_items,'user_permissions': user_permissions})

def permission_view(request):
    # 查询所有用户及其权限
    users_with_permissions = []
    users = User.objects.all()  # 获取所有用户

    for user in users:
        permissions = user.userandpermission_set.all()  # 获取用户的所有权限
        user_permissions = {
            'username': user.username,
            'permissions': [permission.permissionIndex.name for permission in permissions]  # 获取权限名称
        }
        users_with_permissions.append(user_permissions)

    template = "container/permission.html"
    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'users_with_permissions': users_with_permissions,'user_permissions': user_permissions})

def temporary_view(request):
    template = "container/temporary.html"
    user_permissions = get_user_permissions(request.user)

    years = [2025]
    months = list(range(1, 13))  # 1 到 12 月
    return render(request, template,{'user_permissions': user_permissions,'years':years,'months':months})

def get_user_permissions(user):
    # Use permissionIndex__name to get the name of the permission related to the UserAndPermission instance
    permissions = UserAndPermission.objects.filter(username=user).values_list('permissionIndex__name', flat=True)
    
    # Print the length of the permissions list (or log it)
    print("permissions: ", len(permissions))
    
    return permissions