from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

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
    return render(request, 'container/login/login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'container/login/register.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))
