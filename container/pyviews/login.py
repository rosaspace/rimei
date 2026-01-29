from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse

from ..constants import constants_view
from .utils.getPermission import get_user_permissions

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            print("Authenticated username:", form.cleaned_data.get('username'))  # ✅ 打印用户名
            auth_login(request, user)
            return redirect('index')  # 登录后跳转
    else:
        form = AuthenticationForm()
    return render(request, constants_view.template_login, {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, constants_view.template_register, {'form': form})

# home
@login_required
def home(request):
    return redirect("index")

@login_required
def index(request):
    user_permissions = get_user_permissions(request.user)
    return render(request, constants_view.template_base, {'user_permissions': user_permissions})

@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))
