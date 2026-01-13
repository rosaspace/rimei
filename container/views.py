import tempfile

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F
from django.template.loader import get_template
from django.http import HttpResponse

from weasyprint import HTML
from datetime import datetime, date, timedelta
from django.utils import timezone
from collections import defaultdict

from .models import Container, RMOrder,RMCustomer,AlineOrderRecord,ContainerStatement
from .models import RMProduct, InvoicePaidCustomer,Carrier,InvoiceAPRecord,InvoiceARRecord
from .pyviews.getPermission import get_user_permissions
from .constants import constants_view

# home
@login_required
def home(request):
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_login, {'user_permissions': user_permissions})

@login_required
def index(request):
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_base, {'user_permissions': user_permissions})

# invoice
@login_required(login_url='/login/')
def invoice_view(request):
    containers = Container.objects.all().exclude(
        logistics=2
    ).order_by('-delivery_date')
    
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_invoice, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_unpaid_customer(request):
    containers = Container.objects.filter(
        Q(ispay=False, customer_ispay=False) & ~Q(price=0) & (~Q(customer = 3) & ~Q(customer = 12) )
    ).exclude(
        logistics=2
    ).order_by('-due_date')
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_invoice, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_unpaid(request):
    containers = Container.objects.filter(
        Q(ispay=False, customer_ispay=True) |
        Q(customer = 3, ispay=False, invoice_id__isnull=False) |
        Q(customer = 12, ispay=False, invoice_id__isnull=False)
    ).order_by('-due_date')
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_invoice, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def invoice_pallet_labor(request):
    years = [2025]
    months = list(range(1, 13))  # 1 到 12 月

    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_generete_monthLabor, {
        'user_permissions': user_permissions,
        'years':years,'months':months
    })  

@login_required(login_url='/login/')
def statement_selected_invoices(request):

    # ==================================================
    # GET：查看已有 Statement
    # ==================================================
    if request.method == "GET":
        statement_number = request.GET.get("statement_number")

        if not statement_number:
            return redirect("invoice_unpaid")

        container_statements = ContainerStatement.objects.filter(
            statement_number=statement_number
        ).select_related("container")

        containers = [cs.container for cs in container_statements]
        total_price = sum(c.price or 0 for c in containers)

        return render(
            request,
            constants_view.template_statement_invoice_preview,
            {
                "containers": containers,
                "total_price": total_price,
                "current_date": datetime.now(),
                "statement_number": statement_number,
            }
        )

    # ==================================================
    # POST：新建 Statement
    # ==================================================
    if request.method == "POST":
        is_select_all = request.POST.get('isselectall') == 'true'
        search_keyword = request.GET.get("q", "")
        print("---search word:", search_keyword)

        selected_ids = request.POST.getlist('selected_ids')
        page_container_ids = request.POST.getlist("page_container_ids")  # 搜索结果
        search_ids = request.POST.getlist('search_container_ids')
        
        if is_select_all:
            if not page_container_ids:
                return redirect("invoice_unpaid")
            containers = Container.objects.filter(container_id__in=page_container_ids)
            print("---all: ", len(page_container_ids))
        elif search_keyword:
            containers = Container.objects.filter(container_id__icontains=search_keyword)
            print("---search: ", len(search_ids))
        else:
            if not selected_ids:
                return redirect("invoice_unpaid")
            containers = Container.objects.filter(container_id__in=selected_ids)
            print("---select: ", len(selected_ids))
        
        total_price = sum([c.price for c in containers if c.price])
        statement_number = "STM" + datetime.now().strftime("%Y%m%d")

        for container in containers:
            ContainerStatement.objects.get_or_create(
                container=container,
                statement_number=statement_number,
                defaults={
                    "statement_date": datetime.now().date(),
                    "created_at": timezone.now(),
                    "created_user": request.user,
                }
            )

        return render(request, constants_view.template_statement_invoice_preview, {
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
def paid_invoice_advance(request):
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

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_statement, {"statements":merged_statements,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def aline_payment_view(request):
    alineOrders = AlineOrderRecord.objects.all().order_by('due_date')
    user_permissions = get_user_permissions(request.user)  
    return render(request, constants_view.template_payment_aline,{'orders':alineOrders, 'user_permissions': user_permissions})

def invoice_ap_view(request):

    apRecord = InvoiceAPRecord.objects.all()    
    user_permissions = get_user_permissions(request.user)    

    return render(request, constants_view.template_ap_invoice,{'user_permissions': user_permissions,
    'apRecord':apRecord
    })

def invoice_ar_view(request):
    
    arRecord = InvoiceARRecord.objects.all()
    user_permissions = get_user_permissions(request.user)  

    return render(request, constants_view.template_ar_invoice,{'user_permissions': user_permissions,
    'arRecord':arRecord
    })

# container
@login_required(login_url='/login/')
def container_advance77(request):
    containers = Container.objects.filter(Q(logistics = 1) | Q(logistics = 3)).order_by('-delivery_date') # logistics: 非Customer
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_container, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def container_omar(request):
    containers = Container.objects.filter(Q(logistics = 2)).exclude(Q(customer = 3) | Q(customer = 12)).order_by('-delivery_date') # logistics: Customer, 排除Mcdonalds和Metal
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_container, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def container_mcd(request):
    containers = Container.objects.filter(Q(customer = 3)).order_by('-delivery_date') # customer: Mcdonalds
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_container, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def container_metal(request):
    containers = Container.objects.filter(Q(customer = 12)).order_by('-delivery_date') # customer: Metal
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_container, {'containers': containers,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def simplified_container_view(request):
    containers = Container.objects.filter(Q(is_updateInventory = False)).order_by('delivery_date')
    user_permissions = get_user_permissions(request.user) 
    return render(request, constants_view.template_simplified_container, {'containers': containers,'user_permissions': user_permissions})

# order
@login_required(login_url='/login/')
def rimeiorder_view(request):
    orders = RMOrder.objects.exclude(Q(customer_name='4') | Q(customer_name='19')).annotate(image_count=Count('images')).order_by('-pickup_date')
    user_permissions = get_user_permissions(request.user) 
    unfinished_orders = orders.filter(
        is_canceled=False
    )
    print("unfinished_orders, ",len(unfinished_orders))

    today = date.today()
    # 计算本周的周一和周日
    start_of_week = today - timedelta(days=today.weekday())   # 本周一
    end_of_week = start_of_week + timedelta(days=6)           # 本周日
    # 下周的时间范围
    next_start_of_week = start_of_week + timedelta(days=7)
    next_end_of_week = next_start_of_week + timedelta(days=6)
    # 下下周
    next2_start_of_week = start_of_week + timedelta(days=14)
    next2_end_of_week = next2_start_of_week + timedelta(days=6)

    return render(request, constants_view.template_rmorder, {
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        "next_start_of_week": next_start_of_week,
        "next_end_of_week": next_end_of_week,
        "next2_start_of_week":next2_start_of_week,
        "next2_end_of_week":next2_end_of_week
        })

@login_required(login_url='/login/')
def rimeiorder_metal(request):
    orders = RMOrder.objects.filter(customer_name='19').annotate(image_count=Count('images')).order_by('-pickup_date')
    user_permissions = get_user_permissions(request.user) 
    unfinished_orders = orders.filter(
        is_canceled=False
    )

    return render(request, constants_view.template_rmorder, {
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions
        })

@login_required(login_url='/login/')
def rimeiorder_mcdonalds(request):
    orders = RMOrder.objects.filter(customer_name='10').annotate(image_count=Count('images')).order_by('-pickup_date')
    user_permissions = get_user_permissions(request.user) 
    unfinished_orders = orders.filter(
        is_canceled=False
    )
    print("unfinished_orders, ",len(unfinished_orders))

    return render(request, constants_view.template_rmorder, {
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions
        })

@login_required(login_url='/login/')
def rimeiorder_officedepot(request):
    orders = RMOrder.objects.filter(customer_name='4').annotate(image_count=Count('images')).order_by('-pickup_date')
    user_permissions = get_user_permissions(request.user) 
    finished_orders = orders.filter(
        is_canceled=False
    )
    print("finished_orders, ",len(finished_orders))

    return render(request, constants_view.template_rmorder, {
        'rimeiorders': finished_orders,
        'user_permissions': user_permissions
        })

@login_required(login_url='/login/')
def rimeiorder_cancel(request):
    orders = RMOrder.objects.filter(is_canceled=True).annotate(image_count=Count('images')).order_by('pickup_date')
    user_permissions = get_user_permissions(request.user) 
    finished_orders = orders.exclude(
        is_updateInventory=False, 
        is_canceled=False
    )
    print("finished_orders, ",len(finished_orders))

    return render(request, constants_view.template_rmorder, {
        'rimeiorders': finished_orders,
        'user_permissions': user_permissions
        })

@login_required(login_url='/login/')
def simplified_view(request):
    orders = RMOrder.objects.exclude(Q(customer_name='4') | Q(customer_name='19')).annotate(image_count=Count('images')).order_by('pickup_date')
    unfinished_orders = orders.filter(
        Q(is_canceled=False) &
        Q(is_updateInventory=False)
    )

    today = date.today()
    # 计算本周的周一和周日
    start_of_week = today - timedelta(days=today.weekday())   # 本周一
    end_of_week = start_of_week + timedelta(days=6)           # 本周日
    # 下周的时间范围
    next_start_of_week = start_of_week + timedelta(days=7)
    next_end_of_week = next_start_of_week + timedelta(days=6)
    # 下下周
    next2_start_of_week = start_of_week + timedelta(days=14)
    next2_end_of_week = next2_start_of_week + timedelta(days=6)

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_simplified_order,{
        'rimeiorders': unfinished_orders,
        'user_permissions': user_permissions,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        "next_start_of_week": next_start_of_week,
        "next_end_of_week": next_end_of_week,
        "next2_start_of_week":next2_start_of_week,
        "next2_end_of_week":next2_end_of_week
        })

# general
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

    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_permission, {'users_with_permissions': users_with_permissions,'user_permissions': user_permissions})

@login_required(login_url='/login/')
def temporary_view(request):
    user_permissions = get_user_permissions(request.user)

    years = [2025]
    months = list(range(1, 13))  # 1 到 12 月
    return render(request, constants_view.template_temporary,{'user_permissions': user_permissions,'years':years,'months':months})