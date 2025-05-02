from django import forms
from django.contrib.auth.forms import AuthenticationForm
from accounts.models import User
from vendas.models import Loja
from django.contrib.auth.models import Permission, Group
from django_select2.forms import Select2MultipleWidget

class LoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']


class MyProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'password': forms.PasswordInput()
        }

class ResetPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={'placeholder': 'Nova senha', 'class': 'form-control'}
        ), label='Nova senha')
    password_confirm = forms.CharField(widget=forms.PasswordInput(
        attrs={'placeholder': 'Nova senha', 'class': 'form-control'}
    ), label='Confirme a senha')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('As senhas não conferem.')
        return cleaned_data

    
class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username','first_name', 'last_name', 'email', 'password', 'user_permissions', 'groups']
        widgets = {
            'password': forms.PasswordInput(),
            'user_permissions': Select2MultipleWidget(),
            'groups': Select2MultipleWidget()
        }
        
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
            'password': 'Senha',
            'user_permissions': 'Permissões',
            'groups': 'Grupos'
        }

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        if first_name and last_name:
            username = f"{first_name.lower()}.{last_name.lower()}"
            cleaned_data['username'] = username
        return cleaned_data
    
    #salvar usuário 
    def save(self, commit=True):
        user = super().save(commit=False)

        # Configuração da senha
        if not self.cleaned_data['password']:
            if user.pk: 
                current_password = User.objects.get(pk=user.pk).password
                user.password = current_password
            else:
                user.set_password('123456')
        else:
            user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

        if commit:
            groups = self.cleaned_data.get('groups')
            user.groups.set(groups)

            permissions = self.cleaned_data.get('user_permissions')
            user.user_permissions.set(permissions)

        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'permissions': Select2MultipleWidget()
        }