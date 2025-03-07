# container/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from ..models import Permission, UserAndPermission
from django.http import JsonResponse

def add_user_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')

        # 检查密码是否一致
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'container/user/add_user.html')

        # 创建新用户
        try:
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            messages.success(request, "User created successfully!")
            return redirect('add_user')  # 重定向到添加用户页面
        except Exception as e:
            messages.error(request, f"Error creating user: {e}")

    return render(request, 'container/user/add_user.html')

def assign_permission_view(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        permission_ids = request.POST.getlist('permission_ids')  # 获取多选权限

        # 获取用户
        user = User.objects.get(id=user_id)

        # 清除用户已有的权限
        UserAndPermission.objects.filter(userId=user).delete()

        # 为用户分配新权限
        for permission_id in permission_ids:
            permission = Permission.objects.get(id=permission_id)
            UserAndPermission.objects.create(userId=user, permissionIndex=permission)
        
        messages.success(request, f"Permissions assigned to user '{user.username}' successfully!")
        return redirect('assign_permission')  # 重定向到权限分配页面

    users = User.objects.all()  # 获取所有用户
    permissions = Permission.objects.all()  # 获取所有权限
    return render(request, 'container/user/assign_permission.html', {'users': users, 'permissions': permissions})

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
        return redirect('assign_permission')  # 重定向到权限分配页面

    # 如果不是 POST 请求，返回权限分配页面
    users = User.objects.all()  # 获取所有用户
    permissions = Permission.objects.all()  # 获取所有权限
    return render(request, 'container/user/assign_permission.html', {'users': users, 'permissions': permissions})

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
    return render(request, template, {'users_with_permissions': users_with_permissions})
