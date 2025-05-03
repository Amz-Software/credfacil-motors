from django.contrib import admin
from financeiro.models import CaixaMensal, GastosAleatorios, GastoFixo, CaixaMensalGastoFixo, CaixaMensalFuncionario, Repasse

class FuncionarioInline(admin.TabularInline):
    model = CaixaMensalFuncionario
    extra = 1
    
class GastoFixoInline(admin.TabularInline):
    model = CaixaMensalGastoFixo
    extra = 1
    fields = ['gasto_fixo', 'valor', 'observacao']
    

class GastosAleatoriosInline(admin.TabularInline):
    model = GastosAleatorios
    extra = 1
    fields = ['descricao', 'valor', 'observacao']
    
@admin.register(CaixaMensal)
class CaixaMensalAdmin(admin.ModelAdmin):
    list_display = ['loja', 'mes', 'valor', 'data_abertura', 'data_fechamento']
    search_fields = ['loja__nome', 'mes']
    list_filter = ['mes', 'loja']
    inlines = [GastoFixoInline, FuncionarioInline, GastosAleatoriosInline]
    

@admin.register(GastoFixo)
class GastoFixoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']


@admin.register(Repasse)
class RepasseAdmin(admin.ModelAdmin):
    list_display = ['loja', 'valor', 'data']
    search_fields = ['loja__nome', 'valor']
    list_filter = ['loja']