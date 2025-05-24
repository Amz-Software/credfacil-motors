from django.urls import path
from .views import *
from .models import *
from utils.gerador_views import generate_views
from .forms import *


app_name = 'estoque'

forneViews = generate_views(Fornecedor, FornecedorForm, 10, 'fornecedor')

urlpatterns = [
    path('estoque/', EstoqueListView.as_view(), name='estoque_list'),
    path('estoque/editar/<int:pk>/', EstoqueUpdateView.as_view(), name='estoque_update'),
    path('estoque/entrada/criar', AdicionarEntradaEstoqueView.as_view() , name='estoque_entrada'),
    path('estoque/entrada/', EntradaListView.as_view(), name='entrada_list'),
    path('estoque/entrada/<int:pk>/', EntradaDetailView.as_view(), name='entrada_detail'),
    path('estoque/entrada/editar/<int:pk>/', EntradaUpdateView.as_view(), name='entrada_update'),
    path('estoque/inventario', inventario_estoque_pdf, name='inventario_pdf'),
    path('estoque/folha-entrada/<int:pk>/', FolhaNotaEntradaView.as_view(), name='folha_entrada'),
    
    path('estoque_imei/', EstoqueImeiListView.as_view(), name='estoque_imei_list'),
    path('estoque_imei/editar/<int:pk>/', EstoqueImeiUpdateView.as_view(), name='estoque_imei_update'),
    path('estoque_imei/inventario', inventario_estoque_imei_pdf, name='inventario_imei_pdf'),
    
    #api
    path('produto/details/<int:produto_id>/', check_produtos, name='produto_details'),

    #fornecedor
    path('fornecedor/', FornecedorListView.as_view(), name='fornecedores'),
    path('fornecedor/novo/', forneViews['create_view'].as_view(), name='fornecedor_create'),
    path('fornecedor/detalhe/<int:pk>/', forneViews['detail_view'].as_view(), name='fornecedor_detail'),
    path('fornecedor/editar/<int:pk>/', forneViews['update_view'].as_view(), name='fornecedor_update'),
    path('fornecedor/deletar/<int:pk>/', forneViews['delete_view'].as_view(), name='fornecedor_delete'),
    
    path('estoque-imei-search/', EstoqueImeiSearchView.as_view(), name='estoque-imei-search'),
    path('estoque-imei-search-edit/', EstoqueImeiSearchEditView.as_view(), name='estoque-imei-search-edit'),
    
    path('estoque/entrada/liberar/<int:pk>/', liberar_entrada, name='liberar_entrada'),

]