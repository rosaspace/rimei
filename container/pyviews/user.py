# container/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse

from ..models import Permission, UserAndPermission
from ..constants import constants_address,constants_view

def add_user_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')

        # 检查密码是否一致
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, constants_view.template_add_user)

        # 创建新用户
        try:
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            messages.success(request, "User created successfully!")
            return redirect('permission')  # 重定向到添加用户页面
        except Exception as e:
            messages.error(request, f"Error creating user: {e}")

    return render(request, constants_view.template_add_user)

def assign_permission_view(request):
    users = User.objects.all()  # 获取所有用户
    permissions = Permission.objects.all()  # 获取所有权限
    return render(request, constants_view.template_assign_permission, {'users': users, 'permissions': permissions})

def update_user_permissions(request, user_id): 
    if request.method == 'POST':
        permission_ids = request.POST.getlist('permission_ids')  # 获取多选权限
        user = User.objects.get(username=user_id)  # 获取用户
        # 清除用户已有的权限
        UserAndPermission.objects.filter(username=user.id).delete()
        # 为用户分配新权限
        for permission_id in permission_ids:
            permission = Permission.objects.get(index=permission_id)
            UserAndPermission.objects.create(username=user, permissionIndex=permission)
        
        messages.success(request, f"Permissions updated for user '{user.username}' successfully!")
        return redirect('permission')  # 重定向到权限分配页面

    # 如果不是 POST 请求，返回权限分配页面
    users = User.objects.all()  # 获取所有用户
    permissions = Permission.objects.all()  # 获取所有权限
    return render(request, constants_view.template_assign_permission, {'users': users, 'permissions': permissions})

