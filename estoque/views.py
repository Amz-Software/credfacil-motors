import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView
# from estoque.forms import EntradaForm
from estoque.models import EntradaEstoque, Estoque, EstoqueImei, ProdutoEntrada
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from produtos.models import Produto
from vendas.models import Loja
from .forms import EntradaEstoqueForm, EstoqueImeiForm, ProdutoEntradaForm, ProdutoEntradaFormSet, ProdutoEntradaEditFormSet, EstoqueImeiEditForm
from vendas.views import BaseView
from vendas.models import Venda
from produtos.models import TipoProduto
from .models import Fornecedor
from django.db.models import Sum


class EstoqueListView(BaseView, PermissionRequiredMixin, ListView):
    model = Estoque
    template_name = 'estoque/estoque_list.html'
    context_object_name = 'produtos'
    permission_required = 'estoque.view_estoque'
    paginate_by = 10
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        tipos_produtos = TipoProduto.objects.all()
        context['loja_id'] = loja_id
        context['tipos'] = tipos_produtos
        return context
    
    def get_queryset(self):
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        query = super().get_queryset().filter(loja=loja)
        search = self.request.GET.get('search', None)
        if search:
            query = query.filter(produto__nome__icontains=search)
            
        return query

class EstoqueUpdateView(PermissionRequiredMixin, UpdateView):
    model = Estoque
    fields = ['quantidade_disponivel']
    template_name = 'estoque/estoque_edit.html'
    success_url = reverse_lazy('estoque:estoque_list')
    permission_required = 'estoque.change_estoque'

    def form_valid(self, form):
        estoque = form.save(commit=False)
        estoque.save(user=self.request.user)
        messages.success(self.request, 'Estoque atualizado com sucesso!')
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produto = self.object.produto
        context['produto'] = produto
        return context

class EntradaListView(BaseView, PermissionRequiredMixin, ListView):
    model = EntradaEstoque
    template_name = 'estoque/estoque_entrada_list.html'
    context_object_name = 'entradas'
    permission_required = 'estoque.view_entradaestoque'
    paginate_by = 10
    
    def get_queryset(self):
        query = EntradaEstoque.objects.all()
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        search = self.request.GET.get('search', None)
        liberada = self.request.GET.get('liberada', None)
        
        if liberada:
            if liberada == 'true':
                query = query.filter(venda_liberada=True)
            else:
                query = query.filter(venda_liberada=False)
        
        if not self.request.user.has_perm('estoque.can_view_all_imei'):
            query = query.filter(loja=loja)
            
        if search:
            query = query.filter(Q(numero_nota__icontains=search))
            
        return query.order_by('-criado_em')
    
    
class EntradaDetailView(PermissionRequiredMixin, DetailView):
    model = EntradaEstoque
    template_name = 'estoque/estoque_entrada_detail.html'
    context_object_name = 'entrada'
    permission_required = 'estoque.view_entradaestoque'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    
    
class EntradaUpdateView(PermissionRequiredMixin, UpdateView):
    # levar em consideração que pode ter uma venda e diminuir o estoque
    model = EntradaEstoque
    form_class = EntradaEstoqueForm
    template_name = 'estoque/estoque_form_edit.html'
    success_url = reverse_lazy('estoque:estoque_list')
    permission_required = 'estoque.change_entradaestoque'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        if self.request.POST:
            context['formset'] = ProdutoEntradaEditFormSet(self.request.POST, form_kwargs={'loja': loja_id})
        else:
            context['formset'] = ProdutoEntradaEditFormSet(queryset=ProdutoEntrada.objects.filter(entrada=self.object), form_kwargs={'loja': loja_id})
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        if form.is_valid() and formset.is_valid():
            entrada_estoque = form.save(commit=False)
            produtos = formset.save(commit=False)
            # verificar se excluiu algum produto
            for produto in formset.deleted_objects:
                produto.delete()

            for produto in produtos:
                produto.entrada = entrada_estoque
                produto.loja = loja
                produto.save(user=self.request.user)
                
                # Se o produto for serializado, salve os IMEIs na tabela EstoqueImei
                if produto.imei:  # Presumindo que o IMEI é obrigatório
                    estoque_imei = EstoqueImei.objects.create(
                        produto=produto.produto,
                        imei=produto.imei,
                        produto_entrada=produto,
                        loja=loja
                    )
                    estoque_imei.save(user=self.request.user)

            #verificar se a entrada não esta vazia
            if not entrada_estoque.produtos.all():
                entrada_estoque.delete()
                messages.error(self.request, 'Entrada Excluída, pois não possui produtos.')
                return redirect(self.success_url)

            entrada_estoque.save(user=self.request.user)
            messages.success(self.request, 'Entrada de estoque atualizada com sucesso!')
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)


class AdicionarEntradaEstoqueView(PermissionRequiredMixin, CreateView):
    model = EntradaEstoque
    form_class = EntradaEstoqueForm
    template_name = 'estoque/estoque_form.html'
    success_url = reverse_lazy('estoque:estoque_list')
    permission_required = 'estoque.add_entradaestoque'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        if self.request.POST:
            context['formset'] = ProdutoEntradaFormSet(self.request.POST, form_kwargs={'loja': loja_id})
        else:
            context['formset'] = ProdutoEntradaFormSet(queryset=ProdutoEntrada.objects.none(), form_kwargs={'loja': loja_id})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        if form.is_valid() and formset.is_valid():
            entrada_estoque = form.save(commit=False)
            entrada_estoque.loja = loja
            entrada_estoque.save(user=self.request.user)
            produtos = formset.save(commit=False)

            for produto in produtos:
                produto.entrada = entrada_estoque
                produto.loja = loja
                produto.save(user=self.request.user)
                
                if produto.imei: 
                    estoque_imei = EstoqueImei.objects.create(
                        produto=produto.produto,
                        imei=produto.imei,
                        produto_entrada=produto,
                        loja=loja
                    )
                    estoque_imei.save(user=self.request.user)
            
            messages.success(self.request, 'Entrada de estoque criada com sucesso!')
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)
        


@permission_required('estoque.can_liberar_venda', raise_exception=True)
def liberar_entrada(request, pk):
    entrada = get_object_or_404(EntradaEstoque, pk=pk)

    if entrada.venda_liberada:
        messages.info(request, "Esta Nota de entrada já está liberada para venda.")
    else:
        entrada.venda_liberada = True
        entrada.save(update_fields=['venda_liberada'])
        messages.success(request, "Nota de entrada liberada para venda com sucesso.")

    return redirect('estoque:entrada_detail', pk=pk)


class EstoqueImeiListView(BaseView, PermissionRequiredMixin, ListView):
    model = EstoqueImei
    template_name = 'estoque/estoque_imei_list.html'
    context_object_name = 'produtos'
    permission_required = 'estoque.view_estoqueimei'
    paginate_by = 10
    
    def get_queryset(self):
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        query = super().get_queryset().filter(loja=loja)
        
        search = self.request.GET.get('search', None)
        if search:
            query = query.filter(Q(imei__icontains=search)|Q(produto__nome__icontains=search))
            
        return query
    

class EstoqueImeiUpdateView(PermissionRequiredMixin, UpdateView):
    model = EstoqueImei
    form_class = EstoqueImeiEditForm
    template_name = 'estoque/estoque_imei_form_edit.html'
    success_url = reverse_lazy('estoque:estoque_imei_list')
    permission_required = 'estoque.change_estoqueimei'

    def form_valid(self, form):
        estoque = form.save(commit=False)
        estoque.save(user=self.request.user)
        messages.success(self.request, 'Estoque atualizado com sucesso!')
        return redirect(self.success_url)

class FornecedorListView(PermissionRequiredMixin, ListView):
    model = Fornecedor
    template_name = 'fornecedor/fornecedor_list.html'
    permission_required = 'estoque.view_fornecedor'
    context_object_name = 'items'
    paginate_by = 10

    def get_queryset(self):
        query = super().get_queryset()
        search = self.request.GET.get('search', None)
        if search:
            query = query.filter(nome__icontains=search)
        return query

@login_required
def check_produtos(request, produto_id):
    produto = get_object_or_404(Produto, pk=produto_id)
    if produto.tipo.numero_serial:
        return JsonResponse({'serializado': True})
    else:
        return JsonResponse({'serializado': False})
    
    
class EstoqueImeiSearchView(View):
    def get(self, request, *args, **kwargs):
        term = request.GET.get('term', '')
        user = request.user
        produto_id = request.GET.get('produto_id', None)
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        queryset = EstoqueImei.objects.filter(vendido=False, produto_entrada__entrada__venda_liberada=True).filter(
            Q(imei__icontains=term) | Q(produto__nome__icontains=term) | Q(loja__nome__icontains=term)
        )
        
        if not user.has_perm('estoque.can_view_all_imei'):
            queryset = queryset.filter(loja=loja)
        
        if produto_id:
            queryset = queryset.filter(produto_id=produto_id)
        
        results = []
        for imei in queryset:
            if not user.has_perm('estoque.can_view_all_imei'):
                text = f'{imei.imei} - {imei.produto.nome}'
            else:
                text = f'{imei.imei} - {imei.produto.nome} | {imei.produto.loja.nome}'
            results.append({
                'id': imei.id,
                'text': text
            })
        return JsonResponse({'results': results})
    
class EstoqueImeiSearchEditView(View):
    def get(self, request, *args, **kwargs):
        term = request.GET.get('term', '')
        produto_id = request.GET.get('produto_id', None)
        loja_id = self.request.session.get('loja_id')
        venda_id = self.request.session.get('venda_id')
        loja = get_object_or_404(Loja, pk=loja_id)
        queryset = EstoqueImei.objects.filter(
            Q(imei__icontains=term) | Q(produto__nome__icontains=term)
        ).filter(loja=loja).filter(vendido=False)
        if produto_id:
            queryset = queryset.filter(produto_id=produto_id)
        results = []
        for imei in queryset:
            results.append({
                'id': imei.imei,
                'text': f'{imei.imei} - {imei.produto.nome}'
            })

        if venda_id:
            venda = get_object_or_404(Venda, pk=venda_id)
            for item in venda.itens_venda.all():
                if item.imei:
                    results.append({
                        'id': item.imei,
                        'text': f'{item.imei} - {item.produto.nome}'
                    })
        return JsonResponse({'results': results})
    
def inventario_estoque_pdf (request):
    loja = get_object_or_404(Loja, pk=request.session.get('loja_id'))
    tipo = request.GET.get('tipo', None)
    produtos = Estoque.objects.filter(loja=loja).filter(quantidade_disponivel__gt=0)

    if tipo:
        produtos = produtos.filter(produto__tipo_id=tipo)
    
    quantidade_total = produtos.aggregate(total=Sum('quantidade_disponivel'))['total']
    custo_medio_total = 0
    preco_medio_total = 0

    for produto in produtos:
        preco_medio_total += float(produto.preco_medio()) * produto.quantidade_disponivel
        custo_medio_total  += float(produto.preco_medio_custo()) * produto.quantidade_disponivel

    context = {
        'produtos': produtos,
        'loja': loja,
        'quantidade_total': quantidade_total,
        'custo_medio_total': f'{custo_medio_total:.2f}',
        'preco_medio_total': f'{preco_medio_total:.2f}',
    }

    return render(request, "estoque/folha_estoque.html", context)

def inventario_estoque_imei_pdf (request):
    loja = get_object_or_404(Loja, pk=request.session.get('loja_id'))
    produtos = EstoqueImei.objects.filter(loja=loja).filter(vendido=False)
    
    context = {
        'produtos': produtos,
        'loja': loja,
        'data_hoje': datetime.datetime.now()
    }

    return render(request, "estoque/folha_estoque_imei.html", context)

class FolhaNotaEntradaView(View):
    def get(self, request, *args, **kwargs):
        loja = get_object_or_404(Loja, pk=request.session.get('loja_id'))
        entrada = get_object_or_404(EntradaEstoque, pk=kwargs['pk'])
        produtos = ProdutoEntrada.objects.filter(entrada=entrada)
        
        context = {
            'produtos': produtos,
            'loja': loja,
            'entrada': entrada,
            'data_hoje': datetime.datetime.now()
        }

        return render(request, "estoque/folha_entrada.html", context)
    
def buscar_imei_por_produto(request):
    if request.method == 'GET':
        produto_id = request.GET.get('produto_id')
        imei_antigo = request.GET.get('imei')

        if produto_id:
            imeis = EstoqueImei.objects.filter(produto_id=produto_id, vendido=False).exclude(imei=imei_antigo) if imei_antigo else EstoqueImei.objects.filter(produto_id=produto_id, vendido=False)
            imeis_list = [{'id': imei.id, 'imei': f'{imei.imei} - {imei.produto.nome}'} for imei in imeis]
            return JsonResponse({'imeis': imeis_list})
        
    return JsonResponse({'error': 'Produto não encontrado'}, status=404)