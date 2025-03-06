from django import forms
from django.contrib.auth.models import User
from .models import Permission, UserAndPermission

class UserPermissionForm(forms.ModelForm):
    class Meta:
        model = UserAndPermission
        fields = ['username', 'permissionIndex']

class UserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'password', 'email']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])  # 设置密码
        if commit:
            user.save()
        return user