from django.forms import inlineformset_factory, modelformset_factory
from estoque.models import EntradaEstoque
from django import forms
from .models import *
from produtos.models import Produto


class EntradaEstoqueForm(forms.ModelForm):
    class Meta:
        model = EntradaEstoque
        fields = []  # Removido numero_nota pois será gerado automaticamente

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.data_entrada:
            self.initial['data_entrada'] = self.instance.data_entrada.strftime('%Y-%m-%d')


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'telefone', 'email']

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, disabled=False, **kwargs):
        self.user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if disabled:
            for field in self.fields.values():
                field.widget.attrs['disabled'] = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:  
            if not instance.pk: 
                instance.criado_por = self.user
            instance.modificado_por = self.user 
        if commit:
            instance.save()
        return instance


class ProdutoEntradaForm(forms.ModelForm):
    class Meta:
        model = ProdutoEntrada
        exclude = ['loja', 'entrada', 'venda_unitaria', 'quantidade', 'custo_unitario']

        widgets = {
            'produto': forms.Select(attrs={'class': 'form-control'}),
            'imei': forms.TextInput(attrs={'class': 'form-control'}),
            # 'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
            # 'custo_unitario': forms.TextInput(attrs={'class': 'form-control money'}),
        }

    def __init__(self, *args, **kwargs):
        loja = kwargs.pop('loja', None)
        super().__init__(*args, **kwargs)


class EstoqueImeiForm(forms.ModelForm):
    class Meta:
        model = EstoqueImei
        fields = ['imei', 'vendido', 'produto']
        #deve ser possivel editar a venda?
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vendido'].widget.attrs.update({
            'class': 'form-check-input',  # Classe Bootstrap para o toggle switch
            })
        
class EstoqueImeiEditForm(forms.ModelForm):
    class Meta:
        model = EstoqueImei
        fields = ['imei',]
    
ProdutoEntradaFormSet = modelformset_factory(
    ProdutoEntrada,
    form=ProdutoEntradaForm,
    extra=1,
    max_num=100,
    can_delete=False
)

ProdutoEntradaEditFormSet = modelformset_factory(
    ProdutoEntrada,
    form=ProdutoEntradaForm,
    extra=0,
    max_num=100,
    can_delete=True
)