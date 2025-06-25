from django.shortcuts import render, redirect
from .models import Container, RMOrder,RMCustomer,AlineOrderRecord,ContainerStatement
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
from collections import defaultdict

@login_required
def home(request):
    return render(request, "container/user/login.html")

@login_required
def index(request):
    template = "container/base.html"  
    user_permissions = get_user_permissions(request.user)
    return render(request, template,{'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_view(request):
    template = "container/invoice.html"

    containers = Container.objects.exclude(
        Q(ispay=True, customer_ispay=True) |
        Q(customer = 3, ispay=True) | 
        Q(customer = 12, ispay=True)
    ).exclude(
        logistics=2
    ).order_by('-due_date')
    
    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_finished(request):
    template = "container/invoice.html"

    containers = Container.objects.filter(
        Q(ispay=True, customer_ispay=True) |
        Q(customer = 3, ispay=True) |
        Q(customer = 12, ispay=True)
    ).exclude(
        logistics=2
    ).order_by('-due_date')

    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_unpaid(request):
    template = "container/invoice.html"
    containers = Container.objects.filter(
        Q(ispay=False, customer_ispay=True) |
        Q(customer = 3, ispay=False, invoice_id__isnull=False) |
        Q(customer = 12, ispay=False, invoice_id__isnull=False)
    ).order_by('-due_date')
    user_permissions = get_user_permissions(request.user)
    return render(request, template, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def statement_selected_invoices(request):
    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_ids')
        statement_number = request.POST.get("statement_number")
        
        for item in selected_ids:
            print('item: ', item)

        # ✅ 如果是查看现有 Statement（通过 statement_number）
        if statement_number and not selected_ids:
            container_statements = ContainerStatement.objects.filter(statement_number=statement_number)
            containers = [cs.container for cs in container_statements]
            total_price = sum([c.price for c in containers if c.price])

            return render(request, "container/invoiceManager/statement_invoice_preview.html", {
                "containers": containers,
                "total_price": total_price,
                "current_date": datetime.now(),
                "statement_number": statement_number,
            })
        # ✅ 如果是新建 Statement（通过 selected_ids）
        elif selected_ids:
            containers = Container.objects.filter(container_id__in=selected_ids)
            total_price = sum([c.price for c in containers if c.price])
            statement_number = "STM" + datetime.now().strftime("%Y%m%d")

            for container in containers:
                print('container_id: ', container.container_id)
                exists = ContainerStatement.objects.filter(
                    container__container_id=container.container_id,
                    statement_number=statement_number
                ).exists()
                if not exists:
                    ContainerStatement.objects.create(
                        container=container,
                        statement_number=statement_number,
                        statement_date=datetime.now().date(),
                        created_at=timezone.now(),
                        created_user=request.user,  # ✅ 保存创建人
                )

            return render(request, "container/invoiceManager/statement_invoice_preview.html", {
                "containers": containers, 
                "total_price": total_price,
                "current_date": datetime.now(),
                "statement_number" : statement_number,
                },)
    return redirect("invoice_unpaid")

@login_required(login_url='/login/')
def delete_statement(request):
    print("---------delete_statement---------")
    statement_number = request.POST.get("statement_number")
    print("statement_number: ",statement_number)
    if statement_number:
        ContainerStatement.objects.filter(statement_number=statement_number).delete()
        return redirect("invoice_statement")
    return JsonResponse({"success": False, "error": "No statement number provided"})

@login_required(login_url='/login/')
def paid_invoice(request):
    print("POST data:", request.POST)  # 🔍 打印全部 POST 数据
    ids = request.POST.getlist('all_ids')
    date_str = request.POST.get('payment_date')
    payment_date = timezone.now().date()  # 默认今天

    print("Received container_ids:", ids)  # 检查你是否收到了 container_id 列表

    if date_str:
        try:
            payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # 如果解析失败就用默认

    Container.objects.filter(id__in=ids).update(
        ispay=True,
        payment_date=payment_date
    )

    return redirect("invoice_statement")

@login_required(login_url='/login/')
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
    return redirect("invoice_statement")

@login_required(login_url='/login/')
def invoice_statement(request):
    statements = ContainerStatement.objects.all().order_by('statement_date')
    container_ids = [stmt.container_id_str for stmt in statements if stmt.container_id_str]
    containers_map = {
        c.container_id: c for c in Container.objects.filter(container_id__in=container_ids)
    }

    # 使用 defaultdict 按日期分组
    grouped = defaultdict(list)
    for statement in statements:
        container = containers_map.get(statement.container_id_str)  # 用 container_id 找对应 Container 实例
        if container:
            grouped[(statement.statement_date, statement.statement_number)].append((container,statement))
            print("group:", container.container_id)

    # 构建合并后的结构，每个日期只显示一条
    merged_statements = []
    for (date, statement_number), container_statement_pairs  in grouped.items():
        containers = [c for c, _ in container_statement_pairs]
        total_amount = sum(c.price for c in containers )

        # ✅ 判断是否全部已付款
        all_paid = all(c.ispay for c in containers)
        paid_status = "Paid" if all_paid else "Unpaid"

        # 从任意一个 statement 获取 created_user
        _, sample_statement = container_statement_pairs[0]
        operator = sample_statement.created_user

        merged_entry = {
            "statement_number": statement_number,
            "statement_date": date,
            "container_count": len(containers),
            "total_amount": total_amount,
            "paid_status": paid_status,  # 如果需要动态取，可额外查询或改逻辑
            "operator" : operator,
            "containers": containers,
        }
        merged_statements.append(merged_entry)

    # 按日期排序（可选，因 defaultdict 顺序可能不是稳定的）
    merged_statements.sort(key=lambda x: x["statement_date"])

    template = "container/invoiceManager/statement.html"
    user_permissions = get_user_permissions(request.user)
    return render(request, template,{"statements":merged_statements,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def aline_payment_view(request):
    template = "container/payment_aline.html"  
    alineOrders = AlineOrderRecord.objects.all().order_by('due_date')
    user_permissions = get_user_permissions(request.user)  
    return render(request, template,{'orders':alineOrders, 'user_permissions': user_permissions})

@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
def rimeiorder_view(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.exclude(Q(customer_name='4') | Q(customer_name='19')).annotate(image_count=Count('images')).order_by('pickup_date')
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

@login_required(login_url='/login/')
def metalorder(request):
    template = "container/rmorder2.html"
    orders = RMOrder.objects.filter(customer_name='19').annotate(image_count=Count('images')).order_by('pickup_date')
    user_permissions = get_user_permissions(request.user) 
    unfinished_orders = orders.filter(
        is_updateInventory=False, 
        is_canceled=False
    )

    return render(request, template, {
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions
        })

@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
def inventory_view(request):
    inventory_items = RMProduct.objects.all()  # 获取所有库存信息
    user_permissions = get_user_permissions(request.user)
    return render(request, "container/inventory.html", {"inventory_items": inventory_items,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def inventory_diff_view(request):
    inventory_items = RMProduct.objects.filter(
        ~Q(quantity=F('quantity_for_neworder'))
    ).order_by('quantity_for_neworder')
    user_permissions = get_user_permissions(request.user)
    return render(request, "container/inventory.html", {"inventory_items": inventory_items,'user_permissions': user_permissions})

@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
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