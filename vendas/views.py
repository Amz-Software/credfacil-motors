import logging
from datetime import datetime
import json
from typing import Any
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, DetailView, CreateView, DeleteView, UpdateView, View, FormView
from django.utils.timezone import localtime, now
from estoque.models import Estoque, EstoqueImei
from financeiro.forms import RepasseForm
from financeiro.models import Repasse
from produtos.models import Produto
from vendas.forms import AnaliseCreditoClienteForm, ClienteConsultaForm, ClienteForm, ComprovantesClienteForm, ContatoAdicionalForm, FormaPagamentoEditFormSet, InformacaoPessoalForm, LojaForm, ProdutoVendaEditFormSet, RelatorioVendasForm, VendaForm, ProdutoVendaFormSet, FormaPagamentoFormSet, LancamentoForm, LancamentoCaixaTotalForm
from .models import AnaliseCreditoCliente, Caixa, Cliente, Loja, Pagamento, Parcela, ProdutoVenda, TipoPagamento, Venda, LancamentoCaixa, LancamentoCaixaTotal
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils import timezone
from django.db import transaction
from django_select2.views import AutoResponseView
from django.db.models import Sum
from django.contrib.auth.decorators import permission_required
from django.db.models import Count
from datetime import date, timedelta
from django.core.paginator import Paginator
import base64
from django.http import HttpResponse
from pixqrcode import PixQrCode
from io import BytesIO
import qrcode
from dateutil.relativedelta import relativedelta
import calendar
from datetime import date
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
import re, sys, io, base64
import base64
from io import BytesIO
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
import qrcode
from pixqrcodegen import Payload
from vendas.models import Pagamento, Loja


logger = logging.getLogger(__name__)

class BaseView(View):
    def get_loja(self):
        loja_id = self.request.session.get('loja_id')
        if loja_id:
            return get_object_or_404(Loja, id=loja_id)
        return None

    def get_queryset(self):
        loja = self.get_loja()
        if loja:
            return super().get_queryset().filter(loja=loja)
        
        if not loja:
            raise Http404("Loja não encontrada para o usuário.")

        return super().get_queryset()


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        loja = Loja.objects.get(id=self.request.session.get('loja_id'))
        caixa_diario_loja = Caixa.objects.filter(loja=loja).order_by('-data_abertura').first()
        caixa_total = Caixa.objects.all().filter(loja=loja)

        valor_caixa_total = 0
        for caixa in caixa_total:
            valor_caixa_total += caixa.saldo_total_dinheiro
            valor_caixa_total += caixa.entradas
            valor_caixa_total -= caixa.saidas

        caixa_diario_lucro = 0
        if caixa_diario_loja:
            caixa_diario_lucro = (caixa_diario_loja.saldo_total_dinheiro + caixa_diario_loja.entradas) - caixa_diario_loja.saidas

        entrada_caixa_total = LancamentoCaixaTotal.objects.filter(tipo_lancamento='1', loja=loja)
        saida_caixa_total = LancamentoCaixaTotal.objects.filter(tipo_lancamento='2', loja=loja)

        for entrada in entrada_caixa_total:
            valor_caixa_total += entrada.valor

        for saida in saida_caixa_total:
            valor_caixa_total -= saida.valor


        context['loja'] = loja
        context['caixa_diario'] = caixa_diario_loja
        context['caixa_diario_lucro'] = caixa_diario_lucro
        context['caixa_total'] = valor_caixa_total

        return context
    

from django.http import JsonResponse
from django.views import View

class CaixaKpiCountsView(View):
    def get(self, request, *args, **kwargs):
        if request.user.has_perm('vendas.view_all_analise_credito'):
            qs = AnaliseCreditoCliente.objects.all()
        else:
            loja_id = request.session.get('loja_id')
            qs = AnaliseCreditoCliente.objects.filter(loja_id=loja_id)

        status_counts = (
            qs.values('status')
              .annotate(total=Count('id'))
        )
        data = {item['status']: item['total'] for item in status_counts}
        # garantia de zeros
        for code, _ in AnaliseCreditoCliente.STATUS_CHOICES:
            data.setdefault(code, 0)
        return JsonResponse(data)


    

class CaixaListView(BaseView, PermissionRequiredMixin, ListView):
    model = Caixa
    template_name = 'caixa/caixa_list.html'
    context_object_name = 'caixas'
    permission_required = 'vendas.view_caixa'
    
    def get_queryset(self):
        query = super().get_queryset()
        data_filter = self.request.GET.get('search')
        if data_filter:
            return query.filter(data_abertura=data_filter)
        
        return query.order_by('-criado_em')
    
    def post(self, request, *args, **kwargs):
        criar_caixa = request.POST.get('criar_caixa')

        if criar_caixa:
            today = timezone.localtime(timezone.now()).date()

            if not Caixa.caixa_aberto(today, Loja.objects.get(id=request.session.get('loja_id'))):
                Caixa.objects.create(
                    data_abertura=today,
                    criado_por=request.user,
                    modificado_por=request.user,
                    loja=Loja.objects.get(id=request.session.get('loja_id'))
                    )
                messages.success(request, 'Caixa aberto com sucesso')
                return redirect('vendas:caixa_list')
            else:
                messages.warning(request, 'Já existe um caixa aberto para hoje')
                return redirect('vendas:caixa_list')
            
        
        fechar_caixa = request.POST.get('fechar_caixa')
        if fechar_caixa:
            today = timezone.localtime(timezone.now()).date()
            try:
                caixa = Caixa.objects.get(id=fechar_caixa, loja=request.session.get('loja_id'))
                caixa.data_fechamento = today
                caixa.save(user=request.user)
                messages.success(request, 'Caixa fechado com sucesso')
                return redirect('vendas:caixa_list')
            except:
                messages.warning(request, 'Não existe caixa aberto para hoje')
                return redirect('vendas:caixa_list')
        
        return self.get(request, *args, **kwargs)



class CaixaDetailView(PermissionRequiredMixin, DetailView):
    model = Caixa
    template_name = 'caixa/caixa_detail.html'
    permission_required = 'vendas.view_caixa'
    
    def get_context_data(self, **kwargs):
        loja_id = self.request.session.get('loja_id')
        loja = get_object_or_404(Loja, id=loja_id)
        context = super().get_context_data(**kwargs)
        context['vendas'] = self.object.vendas.filter(is_deleted=False).filter(loja=loja)
        context['form_lancamento'] = LancamentoForm()
        context['lancamentos'] = LancamentoCaixa.objects.filter(caixa=self.object)
        return context

    def post(self, request, *args, **kwargs):
        # Pegue o ID do caixa diretamente de kwargs
        caixa_id = kwargs.get('pk')  # O parâmetro é chamado 'pk' na URL

        try:
            # Busque o objeto Caixa
            caixa = Caixa.objects.get(id=caixa_id)
        except Caixa.DoesNotExist:
            messages.error(request, 'Erro: Caixa não existe.')
            return redirect('vendas:caixa_list')  # Ajuste conforme sua necessidade

        # Instancie o formulário com os dados do POST
        form = LancamentoForm(request.POST, user=request.user)

        if form.is_valid():
            # Salve o formulário e associe ao caixa
            lancamento = form.save(commit=False)
            lancamento.caixa = caixa
            lancamento.save()
            messages.success(request, 'Lançamento realizado com sucesso')
            return redirect('vendas:caixa_detail', pk=caixa_id)

        # Caso o formulário seja inválido
        messages.error(request, 'Erro ao realizar lançamento')
        return self.get(request, *args, **kwargs)
    

def lancamento_delete_view(request, pk):
    lancamento = get_object_or_404(LancamentoCaixa, id=pk)
    caixa_id = lancamento.caixa.id
    lancamento.delete()
    messages.success(request, 'Lançamento excluído com sucesso')
    return redirect('vendas:caixa_detail', pk=caixa_id)

def lancamento_total_delete_view(request, pk):
    lancamento = get_object_or_404(LancamentoCaixaTotal, id=pk)
    loja_id = lancamento.loja.id
    lancamento.delete()
    messages.success(request, 'Lançamento excluído com sucesso')
    return redirect('vendas:caixa_total')
    

class ClienteListView(BaseView, PermissionRequiredMixin, ListView):
    model = Cliente
    template_name = 'cliente/cliente_list.html'
    context_object_name = 'items'
    paginate_by = 10
    permission_required = 'vendas.view_cliente'
    

    def get_queryset(self):
        qs = Cliente.objects.all()
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(nome__icontains=search)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(analise_credito__status=status).distinct()
            
        if not self.request.user.has_perm('vendas.view_all_analise_credito'):
            loja_id = self.request.session.get('loja_id')
            qs = qs.filter(loja_id=loja_id)
        
        return qs.order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # monta os KPIs conforme permissão
        if self.request.user.has_perm('vendas.view_all_analise_credito'):
            analises = AnaliseCreditoCliente.objects.all()
        else:
            loja_id = self.request.session.get('loja_id')
            analises = AnaliseCreditoCliente.objects.filter(loja_id=loja_id)

        counts = analises.values('status').annotate(total=Count('id'))
        kpis = {item['status']: item['total'] for item in counts}
        for code, _ in AnaliseCreditoCliente.STATUS_CHOICES:
            kpis.setdefault(code, 0)

        context['kpis'] = kpis
        context['status_choices'] = AnaliseCreditoCliente.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context
    
    # def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
    #     context = super().get_context_data(**kwargs)
    #     context['form_cliente'] = ClienteForm()
    #     context['form_adicional'] = ContatoAdicionalForm() 
    #     context['form_comprovantes'] = ComprovantesClienteForm()
    #     return context
    
    # def post(self, request, *args, **kwargs):
    #     cliente_id = request.POST.get('cliente_id')  # Verifique se há um cliente_id
        
    #     if cliente_id:  # Se cliente_id existe, é uma edição
    #         cliente = Cliente.objects.get(id=cliente_id)
    #         form_cliente = ClienteForm(request.POST, instance=cliente)
            
    #         # Usamos as instâncias existentes de contato e comprovantes para evitar duplicação
    #         form_adicional = ContatoAdicionalForm(request.POST, instance=cliente.contato_adicional)
    #         form_comprovantes = ComprovantesClienteForm(request.POST, request.FILES, instance=cliente.comprovantes)
    #     else:  # Se não, é um novo cadastro
    #         form_cliente = ClienteForm(request.POST)
    #         form_adicional = ContatoAdicionalForm(request.POST)
    #         form_comprovantes = ComprovantesClienteForm(request.POST, request.FILES)
        
    #     if form_cliente.is_valid() and form_adicional.is_valid() and form_comprovantes.is_valid():
    #         cliente = form_cliente.save(commit=False)
    #         endereco = form_adicional.save(commit=False)  # Salve o contato sem commit para associá-lo
    #         comprovantes = form_comprovantes.save(commit=False)  # Salve comprovantes sem commit
    #         loja = Loja.objects.get(id=request.session.get('loja_id'))
    #         cliente.criado_por = request.user
    #         cliente.modificado_por = request.user
    #         cliente.loja = loja
    #         endereco.criado_por = request.user
    #         endereco.modificado_por = request.user
    #         endereco.loja = loja
    #         comprovantes.criado_por = request.user
    #         comprovantes.modificado_por = request.user
    #         comprovantes.loja = loja
            
    #         # Associa as instâncias e depois salva tudo
    #         cliente.contato_adicional = endereco
    #         cliente.comprovantes = comprovantes
            
    #         endereco.save()  # Salva as instâncias associadas
    #         comprovantes.save()
    #         cliente.save()

    #         # Mensagem de sucesso baseada em ação de edição ou criação
    #         if cliente_id:
    #             messages.success(request, 'Cliente atualizado com sucesso')
    #         else:
    #             messages.success(request, 'Cliente cadastrado com sucesso')
                    
    #         return redirect('vendas:cliente_list')
        
    #     # Mensagem de erro e retorno do formulário em caso de falha na validação
    #     messages.error(request, 'Erro ao cadastrar cliente')
    #     return self.get(request, *args, **kwargs)
    

class ClienteCreateView(PermissionRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'cliente/form_cliente.html'
    success_url = reverse_lazy('vendas:cliente_list')
    permission_required = 'vendas.add_cliente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['form_cliente'] = kwargs.get('form_cliente', ClienteForm(user=self.request.user))
        context['form_adicional'] = kwargs.get('form_adicional', ContatoAdicionalForm(user=self.request.user))
        context['form_informacao'] = kwargs.get('form_informacao', InformacaoPessoalForm(user=self.request.user))
        context['form_comprovantes'] = kwargs.get('form_comprovantes', ComprovantesClienteForm(user=self.request.user))
        context['form_analise_credito'] = kwargs.get('form_analise_credito', AnaliseCreditoClienteForm(user=self.request.user))
        
        produtos = Produto.objects.all().values('id', 'nome', 'valor_4_vezes', 'valor_6_vezes')
        produtos_list = [
            {
                'id': p['id'],
                'nome': p['nome'],
                'valor4': float(p['valor_4_vezes']),
                'valor6': float(p['valor_6_vezes']),
            }
            for p in produtos
        ]
        context['produtos_json'] = json.dumps(produtos_list)

        return context

    def post(self, request, *args, **kwargs):
        self.object = None

        # Passando o user para os formulários
        form_cliente = ClienteForm(request.POST, user=request.user)
        form_adicional = ContatoAdicionalForm(request.POST, user=request.user)
        form_informacao = InformacaoPessoalForm(request.POST, user=request.user)
        form_comprovantes = ComprovantesClienteForm(request.POST, request.FILES, user=request.user)
        form_analise_credito = AnaliseCreditoClienteForm(request.POST, user=request.user)

        if all([
            form_cliente.is_valid(),
            form_adicional.is_valid(),
            form_informacao.is_valid(),
            form_comprovantes.is_valid(),
            form_analise_credito.is_valid()
        ]):

            # Primeiro salva os comprovantes
            comprovantes = form_comprovantes.save()
            contato_adicional = form_adicional.save()
            informacao = form_informacao.save()
            loja_id = request.session.get('loja_id')

            # Atribui os comprovantes ao form_cliente antes de salvar
            cliente = form_cliente.save(commit=False)
            cliente.criado_por = request.user
            cliente.modificado_por = request.user
            cliente.loja = Loja.objects.get(id=loja_id)
            
            cliente.contato_adicional = contato_adicional
            cliente.informacao_pessoal = informacao
            cliente.comprovantes = comprovantes
            cliente.save()

            try:
                loja = Loja.objects.get(id=loja_id)
            except Loja.DoesNotExist:
                print(f"❌ Loja com ID {loja_id} não encontrada")
                return self.form_invalid(form_cliente)

            analise = form_analise_credito.save(commit=False)
            analise.cliente = cliente
            analise.loja = loja
            analise.criado_por = request.user
            analise.modificado_por = request.user
            analise.save()
            print("✅ Análise de crédito salva")

            messages.success(request, "✅ Soliticitação cadastrado com sucesso")
            return redirect(self.success_url)

        else:
            print("❌ Um ou mais formulários são inválidos:")
            print("form_cliente errors:", form_cliente.errors)
            print("form_adicional errors:", form_adicional.errors)
            print("form_informacao errors:", form_informacao.errors)
            print("form_comprovantes errors:", form_comprovantes.errors)
            print("form_analise_credito errors:", form_analise_credito.errors)
            
            messages.error(request, "❌ Erro ao cadastrar Soliticitação. Verifique os dados e tente novamente.")

        # Renderiza novamente com os erros
        context = self.get_context_data(
            form_cliente=form_cliente,
            form_adicional=form_adicional,
            form_informacao=form_informacao,
            form_comprovantes=form_comprovantes,
            form_analise_credito=form_analise_credito,
        )
        return self.render_to_response(context)

class ClienteUpdateView(PermissionRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'cliente/form_cliente.html'
    success_url = reverse_lazy('vendas:cliente_list')
    permission_required = 'vendas.change_cliente'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()

        context['form_cliente'] = kwargs.get('form_cliente', ClienteForm(instance=cliente, user=self.request.user))  # Alteração aqui
        context['form_adicional'] = kwargs.get('form_adicional', ContatoAdicionalForm(instance=cliente.contato_adicional, user=self.request.user))
        context['form_informacao'] = kwargs.get('form_informacao', InformacaoPessoalForm(instance=cliente.informacao_pessoal, user=self.request.user))
        context['form_comprovantes'] = kwargs.get('form_comprovantes', ComprovantesClienteForm(instance=cliente.comprovantes, user=self.request.user))
        context['form_analise_credito'] = kwargs.get('form_analise_credito', AnaliseCreditoClienteForm(instance=cliente.analise_credito, user=self.request.user))
        context['cliente_id'] = cliente.id

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = request.user

        if not user.has_perm('vendas.can_edit_finished_sale') and not self.object.analise_credito.status == 'EA':
            messages.warning(request, "❌ Somente Soliticitação em análise de crédito em andamento podem ser editados.")
            return redirect(self.success_url)

        form_cliente = ClienteForm(request.POST, instance=self.object, user=user)
        form_adicional = ContatoAdicionalForm(request.POST, instance=self.object.contato_adicional, user=user)
        form_informacao = InformacaoPessoalForm(request.POST, instance=self.object.informacao_pessoal, user=user)
        form_comprovantes = ComprovantesClienteForm(request.POST, request.FILES, instance=self.object.comprovantes, user=user)
        form_analise_credito = AnaliseCreditoClienteForm(request.POST, instance=self.object.analise_credito, user=request.user)

        if all([
            form_cliente.is_valid(),
            form_adicional.is_valid(),
            form_informacao.is_valid(),
            form_comprovantes.is_valid(),
            form_analise_credito.is_valid()
        ]):
            contato_adicional = form_adicional.save()
            informacao = form_informacao.save()
            comprovantes = form_comprovantes.save()
            analise_credito = form_analise_credito.save()

            cliente = form_cliente.save(commit=False)
            cliente.contato_adicional = contato_adicional
            cliente.comprovantes = comprovantes
            cliente.save()
            messages.success(request, "✅ Soliticitação atualizada com sucesso")
            return redirect(self.success_url)
        else:
            print("❌ Formulários inválidos")
            print("form_cliente errors:", form_cliente.errors)
            print("form_adicional errors:", form_adicional.errors)
            print("form_comprovantes errors:", form_comprovantes.errors)
            print("form_analise_credito errors:", form_analise_credito.errors)
            messages.error(request, "❌ Erro ao atualizar Soliticitação. Verifique os dados e tente novamente.")

        context = self.get_context_data(
            form_cliente=form_cliente,
            form_adicional=form_adicional,
            form_comprovantes=form_comprovantes,
            form_analise_credito=form_analise_credito,
        )
        return self.render_to_response(context)




def calcular_data_primeira_parcela(data_pagamento_str):
    """
    Sempre joga a 1ª parcela pro próximo mês no dia escolhido.
    """
    hoje = timezone.now().date()
    dia = int(data_pagamento_str)

    # próximo mês
    ano = hoje.year + (hoje.month // 12)
    mes = hoje.month % 12 + 1
    ultimo = calendar.monthrange(ano, mes)[1]
    dia = min(dia, ultimo)
    return date(ano, mes, dia)


def criar_parcelas(pagamento, loja):
    """
    Gera cada vencimento mantendo o dia fixo (ou último do mês se faltar).
    """
    Parcela.objects.filter(pagamento=pagamento).delete()
    dia = pagamento.data_primeira_parcela.day

    for n in range(1, pagamento.parcelas + 1):
        # calcula ano/mes de cada parcela
        month_offset = pagamento.data_primeira_parcela.month - 1 + (n - 1)
        ano = pagamento.data_primeira_parcela.year + month_offset // 12
        mes = month_offset % 12 + 1

        ultimo = calendar.monthrange(ano, mes)[1]
        venc_dia = min(dia, ultimo)
        data_venc = date(ano, mes, venc_dia)

        Parcela.objects.create(
            loja=loja,
            pagamento=pagamento,
            numero_parcela=n,
            valor=pagamento.valor_parcela,
            data_vencimento=data_venc,
            criado_por=pagamento.criado_por,
            modificado_por=pagamento.modificado_por
        )
        

@transaction.atomic
@permission_required('vendas.add_venda', raise_exception=True)
def gerar_venda(request, cliente_id):
    if request.method != 'POST':
        return redirect('vendas:cliente_list')

    cliente = get_object_or_404(Cliente, id=cliente_id)
    loja = get_object_or_404(Loja, id=request.session.get('loja_id'))

    # Verifica caixa aberto
    caixa = Caixa.objects.filter(
        loja=loja,
        data_abertura=timezone.now().date(),
        data_fechamento__isnull=True
    ).first()
    if not caixa:
        messages.error(request, "❌ Nenhum caixa aberto encontrado para hoje.")
        return redirect('vendas:cliente_list')

    # Valida análise de crédito
    analise = cliente.analise_credito
    if not analise or analise.status != 'A':
        messages.error(request, "❌ Análise de crédito não aprovada para o cliente.")
        return redirect('vendas:cliente_list')
    if not analise.imei:
        messages.error(request, "❌ Nenhum IMEI associado à análise de crédito.")
        return redirect('vendas:cliente_list')
    if analise.venda:
        messages.error(request, "❌ Essa solicitação já foi convertida em venda.")
        return redirect('vendas:cliente_list')

    produto = analise.produto
    imei = analise.imei
    if imei.vendido:
        messages.error(request, "❌ IMEI já vendido. Altere o IMEI para continuar.")
        return redirect('vendas:cliente_list')

    estoque = Estoque.objects.filter(produto=produto, loja=loja).first()
    if not estoque or estoque.quantidade_disponivel <= 0:
        messages.error(request, f"❌ Estoque insuficiente para o produto {produto.nome}.")
        return redirect('vendas:cliente_list')

    # Cria venda
    venda = Venda.objects.create(
        loja=loja,
        cliente=cliente,
        vendedor=request.user,
        caixa=caixa,
        repasse_logista=produto.valor_repasse_logista,
        observacao=analise.observacao,
        criado_por=request.user,
        modificado_por=request.user,
        criado_em=timezone.now(),
        modificado_em=timezone.now()
    )
    analise.venda = venda
    analise.save()

    # Define valores e número de parcelas
    if analise.numero_parcelas == '4':
        valor_credfacil = produto.valor_4_vezes
        parcelas = 4
    else:
        valor_credfacil = produto.valor_6_vezes
        parcelas = 6

    # Cria ProdutoVenda
    ProdutoVenda.objects.create(
        loja=loja,
        venda=venda,
        produto=produto,
        imei=imei.imei,
        valor_unitario=valor_credfacil,
        quantidade=1,
        valor_desconto=0
    )

    # Atualiza IMEI e estoque
    imei.vendido = True
    imei.data_venda = timezone.now()
    imei.save()
    estoque.remover_estoque(1)

    # Pagamentos
    tipo_entrada = TipoPagamento.objects.get(nome__iexact='ENTRADA')
    tipo_credfacil = TipoPagamento.objects.get(nome__iexact='CREDFACIL')

    pagamento_entrada = Pagamento.objects.create(
        loja=loja,
        venda=venda,
        tipo_pagamento=tipo_entrada,
        valor=produto.entrada_cliente,
        parcelas=1,
        data_primeira_parcela=timezone.now().date()
    )

    data1 = calcular_data_primeira_parcela(analise.data_pagamento)
    pagamento_credfacil = Pagamento.objects.create(
        loja=loja,
        venda=venda,
        tipo_pagamento=tipo_credfacil,
        valor=valor_credfacil,
        parcelas=parcelas,
        data_primeira_parcela=data1
    )

    criar_parcelas(pagamento_entrada, loja)
    criar_parcelas(pagamento_credfacil, loja)

    messages.success(request, f"✅ Venda criada para o cliente {cliente.nome}!")
    return redirect('vendas:cliente_list')


@permission_required('vendas.change_status_analise', raise_exception=True)
def aprovar_analise_credito(request, id):
    user = request.user
    try:
        analise = AnaliseCreditoCliente.objects.get(id=id)
        if not analise.status == 'EA' and user.has_perm('vendas.can_edit_finished_sale'):
            messages.error(request, 'Somente soliticitações em análise podem ser aprovadas')
            return redirect('vendas:cliente_list')
        analise.aprovar(user=request.user)
        analise.modificado_por = request.user
        analise.modificado_em = timezone.now()
        analise.save()
        messages.success(request, 'Análise de crédito aprovada com sucesso')
    except AnaliseCreditoCliente.DoesNotExist:
        messages.error(request, 'Análise de crédito não encontrada')

    return redirect('vendas:cliente_list')


@permission_required('vendas.change_analisecreditocliente', raise_exception=True)
def cancelar_analise_credito(request, id):
    user = request.user
    try:
        analise = AnaliseCreditoCliente.objects.get(id=id)
        if not analise.status == 'EA' and user.has_perm('vendas.can_edit_finished_sale'):
            messages.error(request, 'Somente solicitações em análise podem ser canceladas')
            return redirect('vendas:cliente_list')
        analise.cancelar()
        analise.modificado_por = request.user
        analise.modificado_em = timezone.now()
        analise.save()
        messages.success(request, 'Análise de crédito cancelada com sucesso')
    except AnaliseCreditoCliente.DoesNotExist:
        messages.error(request, 'Análise de crédito não encontrada')

    return redirect('vendas:cliente_list')

@permission_required('vendas.change_status_analise', raise_exception=True)
def reprovar_analise_credito(request, id):
    user = request.user
    try:
        analise = AnaliseCreditoCliente.objects.get(id=id)
        if not analise.status == 'EA' and user.has_perm('vendas.can_edit_finished_sale'):
            messages.error(request, 'Somente solicitações em análise podem ser reprovadas')
            return redirect('vendas:cliente_list')
        analise.reprovar()
        analise.modificado_por = request.user
        analise.modificado_em = timezone.now()
        analise.save()
        messages.success(request, 'Análise de crédito reprovada com sucesso')
    except AnaliseCreditoCliente.DoesNotExist:
        messages.error(request, 'Análise de crédito não encontrada')

    return redirect('vendas:cliente_list')
    

def cliente_editar_view(request):
    cliente_id = request.GET.get('cliente_id')
    cliente = get_object_or_404(Cliente, id=cliente_id)
    cliente.nascimento = cliente.nascimento.strftime('%Y-%m-%d')
    form_cliente = ClienteForm(instance=cliente, user=request.user)
    form_adicional = ContatoAdicionalForm(instance=cliente.contato_adicional)
    form_comprovantes = ComprovantesClienteForm(instance=cliente.comprovantes, user=request.user)
    
    return render(request, 'cliente/form_cliente.html', {
        'form_cliente': form_cliente,
        'form_adicional': form_adicional,
        'form_comprovantes': form_comprovantes,
        'cliente_id': cliente_id,
    })

class VendaListView(BaseView, PermissionRequiredMixin, ListView):
    model = Venda
    template_name = 'venda/venda_list.html'
    context_object_name = 'vendas'
    paginate_by = 10
    permission_required = 'vendas.view_venda'
    
    def get_queryset(self):
        query = Venda.objects.all()
        data_filter = self.request.GET.get('search')
        loja = self.request.GET.get('loja_id')
        
        if loja:
            query = query.filter(loja__id=loja)
        if data_filter:
            return query.filter(data_venda=data_filter)
        
        if not self.request.user.has_perm('vendas.can_view_all_sales'):
            loja_id = self.request.session.get('loja_id')
            query = query.filter(loja_id=loja_id)
        
        return query.order_by('-criado_em')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        context['lojas'] = Loja.objects.all()
        context['loja_selecionada'] = loja_id
        return context

class VendaCreateView(PermissionRequiredMixin, CreateView):
    model = Venda
    form_class = VendaForm
    template_name = 'venda/venda_create.html'
    success_url = reverse_lazy('vendas:venda_list')
    permission_required = 'vendas.add_venda'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loja'] = self.request.session.get('loja_id')
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        if self.request.POST:
            context['produto_venda_formset'] = ProdutoVendaFormSet(self.request.POST, form_kwargs={'loja': loja_id})
            context['pagamento_formset'] = FormaPagamentoFormSet(self.request.POST, form_kwargs={'loja': loja_id})
        else:
            context['produto_venda_formset'] = ProdutoVendaFormSet(form_kwargs={'loja': loja_id})
            context['pagamento_formset'] = FormaPagamentoFormSet(form_kwargs={'loja': loja_id})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        produto_venda_formset = context['produto_venda_formset']
        pagamento_formset = context['pagamento_formset']
        loja = Loja.objects.get(id=self.request.session.get('loja_id'))

        if not (produto_venda_formset.is_valid() and pagamento_formset.is_valid() and form.is_valid()):
            return self.form_invalid(form)

        if not Caixa.caixa_aberto(localtime(now()).date(), loja):
            messages.warning(self.request, 'Não é possível realizar vendas com o caixa fechado')
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                self._salvar_venda(form, loja)
                self._processar_produtos(produto_venda_formset, loja)
                self._processar_pagamentos(pagamento_formset, loja)
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Erro ao processar a venda: {str(e)}")
            return self.form_invalid(form)

    def _salvar_venda(self, form, loja):
        form.instance.loja = loja
        form.instance.criado_por = self.request.user
        form.instance.modificado_por = self.request.user
        form.instance.caixa = Caixa.objects.filter(data_abertura=localtime(now()).date(), loja=loja).order_by('-criado_em').first()
        form.instance.data_venda = localtime(now())
        self.object = form.save()

    def _processar_produtos(self, formset, loja):
        for produto_venda in formset.save(commit=False):
            produto = produto_venda.produto
            quantidade = produto_venda.quantidade
            imei = produto_venda.imei

            self._validar_estoque(produto, quantidade, loja)
            if produto.tipo.numero_serial:
                self._validar_imei(produto, imei)
            self._atualizar_estoque(produto, quantidade, loja)

            produto_venda.venda = self.object
            produto_venda.loja = loja
            produto_venda.save()

    def _validar_estoque(self, produto, quantidade, loja):
        estoque = Estoque.objects.filter(produto=produto, loja=loja).first()
        if not estoque or quantidade > estoque.quantidade_disponivel:
            raise ValueError(f"Quantidade indisponível para o produto {produto}")

    def _validar_imei(self, produto, imei):
        try:
            produto_imei = EstoqueImei.objects.get(imei=imei, produto=produto)
            if produto_imei.vendido:
                raise ValueError(f"IMEI {imei} já vendido")
            produto_imei.vendido = True
            produto_imei.save()
        except EstoqueImei.DoesNotExist:
            raise ValueError(f"IMEI {imei} não encontrado")

    def _atualizar_estoque(self, produto, quantidade, loja):
        estoque = Estoque.objects.filter(produto=produto, loja=loja).first()
        if estoque:
            estoque.remover_estoque(quantidade)
            estoque.save()

    def _processar_pagamentos(self, formset, loja):
        for pagamento in formset.save(commit=False):
            pagamento.venda = self.object
            pagamento.loja = loja
            pagamento.save()


class VendaUpdateView(PermissionRequiredMixin, UpdateView):
    model = Venda
    form_class = VendaForm
    template_name = 'venda/venda_edit.html'
    permission_required = 'vendas.change_venda'
    
    def get_success_url(self):
        return reverse_lazy('vendas:venda_update', kwargs={'pk': self.object.id})

    def get_form_kwargs(self):
        """Passa a loja para o form."""
        kwargs = super().get_form_kwargs()
        loja_id = self.request.session.get('loja_id')
        kwargs['loja'] = loja_id
        return kwargs

    def get_context_data(self, **kwargs):
        """Carrega os formsets de produtos e pagamentos."""
        context = super().get_context_data(**kwargs)
        loja_id = self.request.session.get('loja_id')
        self.request.session['venda_id'] = self.object.id # Guarda o ID da venda na sessão

        if self.request.POST:
            context['produto_venda_formset'] = ProdutoVendaEditFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'loja': loja_id}
            )
            context['pagamento_formset'] = FormaPagamentoEditFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'loja': loja_id}
            )
        else:
            context['produto_venda_formset'] = ProdutoVendaEditFormSet(
                instance=self.object,
                form_kwargs={'loja': loja_id}
            )
            context['pagamento_formset'] = FormaPagamentoEditFormSet(
                instance=self.object,
                form_kwargs={'loja': loja_id}
            )
        return context

    def form_valid(self, form):
        """Valida os formsets e chama processamento das regras."""
        context = self.get_context_data()
        produto_venda_formset = context['produto_venda_formset']
        pagamento_formset = context['pagamento_formset']
        loja_id = self.request.session.get('loja_id')

        # Verifica se a loja existe
        try:
            loja = Loja.objects.get(id=loja_id)
        except Loja.DoesNotExist:
            messages.error(self.request, "Loja não encontrada")
            logger.error("Loja com id %s não encontrada", loja_id)
            return self.form_invalid(form)

        # Verifica se o caixa está aberto
        if not Caixa.caixa_aberto(localtime(now()).date(), loja):
            messages.warning(self.request, 'Não é possível editar vendas com o caixa fechado')
            logger.warning("Tentativa de editar venda com caixa fechado para a loja %s", loja)
            return self.form_invalid(form)

        # Verifica a validade do formulário e dos formsets
        if not form.is_valid():
            logger.error("Formulário principal com erros: %s", form.errors)
        if not produto_venda_formset.is_valid():
            logger.error("ProdutoVendaFormSet com erros: %s", produto_venda_formset.errors)
        if not pagamento_formset.is_valid():
            logger.error("FormaPagamentoFormSet com erros: %s", pagamento_formset.errors)

        if not (form.is_valid() and produto_venda_formset.is_valid() and pagamento_formset.is_valid()):
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                # Atualiza dados básicos da venda
                self._atualizar_venda(form, loja)
                # Processa produtos (incluindo estoque e IMEI)
                self._processar_produtos(produto_venda_formset, loja)
                # Processa pagamentos
                self._processar_pagamentos(pagamento_formset, loja)
                messages.success(self.request, 'Venda atualizada com sucesso')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Erro ao processar a venda: {str(e)}")
            logger.exception("Erro ao processar a venda: %s", e)
            return self.form_invalid(form)

    def _atualizar_venda(self, form, loja):
        """Salva a instância da venda com possíveis alterações."""
        form.instance.loja = loja
        form.instance.modificado_por = self.request.user
        self.object = form.save()

    def _processar_produtos(self, formset, loja):
        """Cria/atualiza/remove itens de venda, validando e atualizando estoques."""
        produtos_modificados = formset.save(commit=False)

        # 1) Deletar itens marcados para exclusão
        for deletado in formset.deleted_objects:
            logger.debug("Deletando produto venda: %s", deletado)
            if deletado.produto.tipo.numero_serial and deletado.imei:
                self._restaurar_imei(deletado.produto, deletado.imei)
            deletado.delete()

        # 2) Salvar/atualizar itens (novos ou já existentes)
        for produto_venda in produtos_modificados:
            produto = produto_venda.produto
            quantidade = produto_venda.quantidade
            imei = produto_venda.imei

            self._validar_estoque(produto, quantidade, loja)
            if produto.tipo.numero_serial:
                print(produto, imei)
                # self._validar_imei(produto, imei)
                
            #LÓGICA DE ATUALIZAR ESTOQUE ESTÁ NOS SIGNALS

            produto_venda.venda = self.object
            produto_venda.loja = loja
            produto_venda.save()

        formset.save_m2m()

    def _processar_pagamentos(self, formset, loja):
        """Processa pagamentos do formset, incluindo exclusão e criação/atualização."""
        pagamentos_modificados = formset.save(commit=False)

        # Remover pagamentos excluídos
        for deletado in formset.deleted_objects:
            deletado.delete()

        # Salvar/atualizar pagamentos
        for pagamento in pagamentos_modificados:
            pagamento.venda = self.object
            pagamento.loja = loja
            pagamento.save()

        formset.save_m2m()

    # Métodos auxiliares de estoque e IMEI
    def _validar_estoque(self, produto, quantidade, loja):
        estoque = Estoque.objects.filter(produto=produto, loja=loja).first()
        if not estoque or quantidade > estoque.quantidade_disponivel:
            error_message = f"Quantidade indisponível para o produto {produto}"
            logger.error(
                "Estoque insuficiente para o produto %s: solicitado %s, disponível %s",
                produto, quantidade, estoque.quantidade_disponivel if estoque else 0
            )
            raise ValueError(error_message)
        
    def _validar_imei(self, produto, imei):
        try:
            produto_imei = EstoqueImei.objects.get(imei=imei)
            novo_imei = EstoqueImei.objects.filter(imei=imei, produto=produto).first()
            imei_antigo = ProdutoVenda.objects.filter(imei=imei).first()
            if novo_imei and novo_imei != imei_antigo:
                if produto_imei.vendido:
                    error_message = f"IMEI {imei} já vendido"
                    logger.error("IMEI já vendido para o produto %s: %s", produto, imei)
                    raise ValueError(error_message)
                produto_imei.vendido = True
                produto_imei.save()
        except EstoqueImei.DoesNotExist:
            error_message = f"IMEI {imei} não encontrado"
            logger.error("IMEI não encontrado para o produto %s: %s", produto, imei)
            raise ValueError(error_message)

    def _restaurar_estoque(self, produto, quantidade, loja):
        """Restaura a quantidade do estoque se o item for removido."""
        estoque = Estoque.objects.filter(produto=produto, loja=loja).first()
        if estoque:
            estoque.adicionar_estoque(quantidade)
            estoque.save()

    def _restaurar_imei(self, produto, imei):
        """Reverte o status do IMEI se o item for removido."""
        try:
            produto_imei = EstoqueImei.objects.get(imei=imei, produto=produto)
            produto_imei.vendido = False
            produto_imei.save()
        except EstoqueImei.DoesNotExist:
            logger.warning("Tentativa de restaurar IMEI inexistente %s para o produto %s", imei, produto)
            
            
class VendaDetailView(PermissionRequiredMixin, DetailView):
    model = Venda
    template_name = 'venda/venda_detail.html'
    permission_required = 'vendas.view_venda'
    

def cancelar_venda(request, id):
    venda = get_object_or_404(Venda, id=id)
    data_atual = localtime(now()).date()

    if venda.is_deleted:
        messages.warning(request, 'Venda já cancelada')
        return redirect('vendas:venda_list')
    
    if not Caixa.caixa_aberto(localtime(now()).date(), Loja.objects.get(id=request.session.get('loja_id'))):
        messages.warning(request, 'Não é possível cancelar vendas com o caixa fechado')
        return redirect('vendas:venda_list')
    
    venda.is_deleted = True
    venda.save(user=request.user)
    messages.success(request, 'Venda cancelada com sucesso')
    return redirect('vendas:venda_list')

    
class CaixaTotalView(PermissionRequiredMixin, TemplateView):
    template_name = 'caixa/caixa_total.html'
    permission_required = 'vendas.view_caixa'
    
    def get_context_data(self, **kwargs):
        loja_id = self.request.session.get('loja_id')
        loja = Loja.objects.get(id=loja_id)

        caixas = Loja.objects.get(id=loja_id).caixa_loja.all().order_by('-data_abertura').filter(data_fechamento__isnull=False)
        vendas_caixa = []
        entradas_caixa = []
        saidas_caixa = []
        total_entrada = 0
        total_saida = 0
        total_venda =0

        for caixa in caixas:
            vendas = caixa.vendas.filter(is_deleted=False, pagamentos__tipo_pagamento__caixa=True)
            entradas = caixa.lancamentos_caixa.filter(tipo_lancamento='1')
            saidas = caixa.lancamentos_caixa.filter(tipo_lancamento='2')
            if vendas:
                vendas_caixa.append(vendas)

            if entradas:
                entradas_caixa.append(entradas)

            if saidas:
                saidas_caixa.append(saidas)
            
            total_entrada += caixa.entradas
            total_saida += caixa.saidas
            total_venda += caixa.saldo_total_dinheiro

        entradas_caixa_total = LancamentoCaixaTotal.objects.filter(tipo_lancamento='1', loja=loja)
        saidas_caixa_total = LancamentoCaixaTotal.objects.filter(tipo_lancamento='2', loja=loja)

        for entrada in entradas_caixa_total:
            total_entrada += entrada.valor

        for saida in saidas_caixa_total:
            total_saida += saida.valor

        entradas_caixa.append(entradas_caixa_total)
        saidas_caixa.append(saidas_caixa_total)

            
        total = (total_entrada + total_venda) - total_saida

        context = super().get_context_data(**kwargs)
        context['caixas'] = Caixa.objects.all()
        context['loja'] = Loja.objects.get(id=loja_id)
        context['vendas'] = vendas_caixa
        context['entradas'] = entradas_caixa
        context['saidas'] = saidas_caixa
        context['total_entrada'] = total_entrada
        context['total_saida'] = total_saida
        context['total_venda'] = total_venda
        context['total'] = total
        context['form_lancamento'] = LancamentoCaixaTotalForm()
        context['lancamentos'] = LancamentoCaixaTotal.objects.filter(loja=loja)
        
        return context
    
    def post(self, request, *args, **kwargs):
        loja_id = request.session.get('loja_id')
        loja = Loja.objects.get(id=loja_id)
        form = LancamentoCaixaTotalForm(request.POST)
        
        if form.is_valid():
            form.instance.loja = loja
            form.instance.criado_por = request.user
            form.save()
            messages.success(request, 'Lançamento realizado com sucesso')
            return redirect('vendas:caixa_total')
        
        messages.error(request, 'Erro ao realizar lançamento')
        return self.get(request, *args, **kwargs)
    

class LojaListView(BaseView, PermissionRequiredMixin, ListView):
    model = Loja
    template_name = 'loja/loja_list.html'
    context_object_name = 'lojas'
    permission_required = 'vendas.view_loja'

    def get_queryset(self):
        user = self.request.user
        query = Loja.objects.all()
        loja_id = self.request.session.get('loja_id')
        search = self.request.GET.get('search')
        filter_type = self.request.GET.get('filter')
        
        if not user.has_perm('vendas.can_view_all_stores'):
            query = query.filter(id=loja_id)

        if search:
            query = query.filter(nome__icontains=search)
        
        if filter_type == 'pendente':
            query = query.com_repasse_pendente()
        elif filter_type == 'sem_pendente':
            query = query.sem_repasse_pendente()
        
        return query.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Adiciona as informações de repasses para cada loja no contexto
        for loja in context['lojas']:
            repasses, atrasados = loja.get_repasses_status()
            loja.repasses_info = {
                'repasses': repasses,
                'atrasados': atrasados
            }
        context['filter'] = self.request.GET.get('filter', '')  # Passa o filtro para o template
        return context


class LojaCreateView(PermissionRequiredMixin, CreateView):
    model = Loja
    form_class = LojaForm
    template_name = 'loja/loja_form.html'
    permission_required = 'vendas.add_loja'
    
    def form_valid(self, form):
        messages.success(self.request, 'Loja cadastrada com sucesso')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('vendas:loja_detail', kwargs={'pk': self.object.id})
    

class LojaUpdateView(PermissionRequiredMixin, UpdateView):
    model = Loja
    form_class = LojaForm
    template_name = 'loja/loja_form.html'
    permission_required = 'vendas.change_loja'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user_loja'] = self.request.session.get('loja_id')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Loja atualizada com sucesso')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('vendas:loja_detail', kwargs={'pk': self.object.id})

    
from django.db.models import Count, Sum
from django.utils.dateparse import parse_date

class LojaDetailView(PermissionRequiredMixin, DetailView):
    model = Loja
    template_name = 'loja/loja_detail.html'
    permission_required = 'vendas.view_loja'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loja = self.object

        contrato = loja.contrato
        context['contrato'] = json.dumps(contrato) if contrato else None

        repasses_qs    = Repasse.objects.filter(loja=loja).select_related('criado_por')
        repasse_paginator = Paginator(repasses_qs, 10)
        context['repasses'] = repasse_paginator.get_page(self.request.GET.get('repasse_page'))

        vendas_qs = Venda.objects.filter(loja=loja, is_deleted=False).select_related('cliente')
        data_inicio = self.request.GET.get('data_inicio')
        data_fim    = self.request.GET.get('data_fim')
        if data_inicio:
            di = parse_date(data_inicio)
            vendas_qs = vendas_qs.filter(data_venda__date__gte=di)
        if data_fim:
            df = parse_date(data_fim)
            vendas_qs = vendas_qs.filter(data_venda__date__lte=df)

        total_vendas = vendas_qs.aggregate(qtd=Count('id'))['qtd'] or 0
        valor_total  = vendas_qs.aggregate(val=Sum('pagamentos__valor'))['val'] or 0

        venda_paginator = Paginator(vendas_qs.order_by('-data_venda'), 10)
        context['vendas']      = venda_paginator.get_page(self.request.GET.get('venda_page'))
        context['data_inicio'] = data_inicio
        context['data_fim']    = data_fim

        status_list, atrasados = loja.get_repasses_status(meses_atras=1)
        if data_inicio:
            status_list = [r for r in status_list if r['data'] >= parse_date(data_inicio)]
        if data_fim:
            status_list = [r for r in status_list if r['data'] <= parse_date(data_fim)]
        context['repasse_status_list'] = status_list
        context['repasse_atrasados']   = sum(1 for r in status_list if not r['feito'] and r['data'] < date.today())
        context['today'] = date.today()

        di = parse_date(data_inicio) if data_inicio else None
        df = parse_date(data_fim)    if data_fim    else None
        context['kpi_valor_repasse'] = loja.calcular_valor_repasse(di, df)

        context['repasse_form'] = RepasseForm(initial={'loja': loja})

        context['kpi'] = {
            'qtd_vendas':    total_vendas,
            'valor_total':   valor_total,
            'valor_repasse': context['kpi_valor_repasse'],
        }

        return context



def product_information(request):
    product_id = request.GET.get('product_id')
    imei = request.GET.get('imei')
    product = get_object_or_404(Produto, id=product_id) if product_id else None
    imei_id = request.GET.get('imei_id')
    loja = get_object_or_404(Loja, id=request.session.get('loja_id'))
    
    if imei_id:
        product_imei = EstoqueImei.objects.get(id=imei_id, loja=loja)
        if product_imei.vendido:
            return JsonResponse({'status': 'error', 'message': 'IMEI já vendido'}, status=400)
        else:
            return JsonResponse({'status': 'success', 'product': product_imei.produto.nome, 'price': product_imei.produto_entrada.venda_unitaria})
    
    if imei and product:    
        try:
            product_imei = EstoqueImei.objects.filter(id=imei, produto=product, loja=loja).first()
            if product_imei.vendido:
                return JsonResponse({'status': 'error', 'message': 'IMEI já vendido'}, status=400)
            else:
                return JsonResponse({'status': 'success', 'product': product.nome, 'price': product_imei.produto_entrada.venda_unitaria})
        except EstoqueImei.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'IMEI não encontrado'}, status=404)
    elif product and not imei:
        estoque = Estoque.objects.filter(produto=product, loja=loja).first()
        if not estoque:
            return JsonResponse({'status': 'error', 'message': 'Estoque não encontrado'}, status=404)
        return JsonResponse({'status': 'success', 'product': product.nome, 'price': estoque.preco_medio()})

    

def get_payment_method(request):
    payment_id = request.GET.get('payment_id')
    payment = get_object_or_404(TipoPagamento, id=payment_id)
    
    if payment:
        return JsonResponse({
            'status': 'success',
            'parcela': payment.parcelas,
            'financeira': payment.financeira,
            'caixa': payment.caixa,
            'carne': payment.carne,
        })


class ProdutoAutoComplete(AutoResponseView):
    def get_queryset(self):
        return Produto.objects.all()
    
    
def get_produtos(request):
    loja_id = request.session.get('loja_id')
    term = request.GET.get('term')
    loja = get_object_or_404(Loja, id=loja_id)
    
    if term:
        produtos = Produto.objects.filter(estoque_atual__loja_id=loja_id, estoque_atual__quantidade_disponivel__gt=0, loja=loja).distinct().filter(nome__icontains=term)
    else:
        produtos = Produto.objects.filter(estoque_atual__loja_id=loja_id, estoque_atual__quantidade_disponivel__gt=0, loja=loja).distinct()

    produtos_data = [{'id': produto.id, 'text': produto.nome} for produto in produtos]
    return JsonResponse({'results': produtos_data})

class VendaPDFView(PermissionRequiredMixin, View):
    permission_required = 'vendas.view_venda'
    
    def get(self, request, pk):
        venda = get_object_or_404(Venda, id=pk)
        context = {
            'venda': venda,
            'produtos': venda.itens_venda.all(),
            'pagamentos': venda.pagamentos.all(),
        }
        return render(request, 'venda/venda_pdf.html', context)
    
    
class FolhaCaixaPDFView(PermissionRequiredMixin, View):
    permission_required = 'vendas.view_venda'
    
    def get(self, request, pk):
        caixa = get_object_or_404(Caixa, id=pk)
        vendas = caixa.vendas.filter(is_deleted=False)
        lancamentos = caixa.lancamentos_caixa.all()

        entrada_total = 0
        saida_total = 0

        for lancamento in lancamentos:
            if lancamento.tipo_lancamento == '1':
                entrada_total += lancamento.valor
            else:
                saida_total += lancamento.valor

        valor_venda_por_tipo_pagamento = {}

        for venda in vendas:
            for pagamento in venda.pagamentos.all():
                if not pagamento.tipo_pagamento.nao_contabilizar:
                    if pagamento.tipo_pagamento.nome not in valor_venda_por_tipo_pagamento:
                        valor_venda_por_tipo_pagamento[pagamento.tipo_pagamento.nome] = 0
                    valor_venda_por_tipo_pagamento[pagamento.tipo_pagamento.nome] += pagamento.valor

        caixa_valor_final = (caixa.saldo_total_dinheiro + caixa.entradas) - caixa.saidas
        valor_por_tipo_pagamento_total = sum(valor_venda_por_tipo_pagamento.values())

        entrada_total += valor_por_tipo_pagamento_total
        valor_final = entrada_total - saida_total
        saldo_total = entrada_total

        context = {
            'caixa': caixa,
            'data': localtime(now()).date(),
            'vendas': vendas,
            'lancamentos': lancamentos,
            'entrada_total': entrada_total,
            'saida_total': saida_total,
            'valor_por_tipo_pagamento_total': valor_por_tipo_pagamento_total,
            'saldo_total': saldo_total,
            'valor_venda_por_tipo_pagamento': valor_venda_por_tipo_pagamento.items(),
            'caixa_valor_final': caixa_valor_final,
            'valor_final': valor_final
        }
        return render(request, 'caixa/folha_caixa.html', context)

    
class FolhaProdutoPDFView(PermissionRequiredMixin, View):
    permission_required = 'vendas.view_venda'

    def get(self, request, pk):
        caixa = get_object_or_404(Caixa, id=pk)

        # Otimiza a query trazendo os relacionamentos necessários
        vendas = caixa.vendas.filter(is_deleted=False).prefetch_related(
            'itens_venda__produto', 'pagamentos'
        )

        produtos_info = []
        total_produtos = 0
        valor_total = 0

        for venda in vendas:
            # Captura todas as formas de pagamento únicas
            pagamentos = venda.pagamentos.all()
            formas_pagamento = ', '.join(set(p.tipo_pagamento.nome for p in pagamentos))
            valor_total += venda.pagamentos_valor_total
            total_custos = 0
            total_lucro = 0

            for produto in venda.itens_venda.all():
                if produto.produto and produto.produto.nome:
                    produtos_info.append({
                        'id_venda': venda.id,
                        'id_produto': produto.produto.id,
                        'produto': produto.produto.nome,
                        'tipo_produto': produto.produto.tipo.nome,
                        'vendedor': venda.vendedor.get_full_name(),
                        'preco': produto.valor_unitario,
                        'quantidade': produto.quantidade,
                        'custo': produto.custo(),
                        'total': venda.pagamentos_valor_total,
                        'lucro': produto.lucro(),
                        'formas_pagamento': formas_pagamento
                    })
                    total_produtos += produto.quantidade

        total_lucro = sum(produto['lucro'] for produto in produtos_info)
        total_custos = sum(produto['custo'] for produto in produtos_info)

        context = {
            'caixa': caixa,
            'data': localtime(now()).date(),
            'produtos': produtos_info,
            'total_produtos': total_produtos,
            'valor_total': valor_total,
            'total_custos': total_custos,
            'total_lucro': total_lucro
        }

        return render(request, 'caixa/folha_produtos.html', context)



import re
import sys
import io
import base64

from io import BytesIO
from dateutil.relativedelta import relativedelta

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

import qrcode
from qrcode import QRCode
from qrcode.constants import ERROR_CORRECT_M
from pixqrcodegen import Payload

from vendas.models import Venda, Pagamento, Loja


def folha_carne_view(request, pk, tipo):
    # 1) Busca a venda e o pagamento em carnê/promissória
    venda = get_object_or_404(Venda, pk=pk)
    pagamento_carne = Pagamento.objects.filter(
        venda=venda,
        tipo_pagamento__carne=True
    ).first()
    if not pagamento_carne:
        messages.error(request, 'Venda não possui pagamento em carnê ou promissória')
        return redirect('vendas:venda_list')

    # 2) Dados iniciais
    quantidade_parcelas = pagamento_carne.parcelas
    nome_cliente       = venda.cliente.nome.title()
    tipo_pagamento     = 'Carnê' if tipo == 'carne' else 'Promissória'
    endereco_cliente   = venda.cliente.endereco
    cpf                = venda.cliente.cpf
    loja               = get_object_or_404(Loja, nome__icontains="CredFácil")

    # 3) Sanitiza chave Pix
    raw_chave     = loja.chave_pix or ""
    chave_digits  = re.sub(r'\D', '', raw_chave)
    is_celular    = bool(re.fullmatch(r'(?:\+?55)?\d{11}', raw_chave))

    parcelas_info = []
    for i in range(quantidade_parcelas):
        # vencimento e valor
        data_venc   = pagamento_carne.data_primeira_parcela + relativedelta(months=i)
        valor_parc  = f"{pagamento_carne.valor_parcela:.2f}"
        txid        = f"{pagamento_carne.pk:04d}{i+1:02d}"

        if is_celular:
            # fluxo antigo
            pix_qrcode = PixQrCode(
                name=loja.nome,
                key=raw_chave,
                city=loja.endereco or '',
                amount=valor_parc
            )
            qr_string = pix_qrcode.generate_code()
            img = qrcode.make(qr_string)

        else:
            payload = Payload(loja.nome, chave_digits, valor_parc, loja.endereco or '', txid)

            buf_out    = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout  = buf_out
            payload.gerarPayload()
            sys.stdout  = old_stdout
            emv        = buf_out.getvalue().strip()

            qr = QRCode(
                version=None,
                error_correction=ERROR_CORRECT_M,
                box_size=10,
                border=4
            )
            qr.add_data(emv)
            qr.make(fit=True)
            img = qr.make_image()

        # converte a imagem em base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        parcelas_info.append({
            'parcela': i + 1,
            'valor_parcela': valor_parc,
            'data_vencimento': data_venc.strftime('%d/%m/%Y'),
            'qr_code_base64': qr_base64,
            'chave_pix': raw_chave,
        })

    context = {
        'venda': venda,
        'valor_total': venda.pagamentos_valor_total,
        'tipo_pagamento': tipo_pagamento,
        'quantidade_parcelas': quantidade_parcelas,
        'nome_cliente': nome_cliente,
        'endereco_cliente': endereco_cliente,
        'data_atual': localtime(now()).date(),
        'cpf': cpf,
        'parcelas_info': parcelas_info,
        'loja': loja,
    }
    return render(request, "venda/folha_carne.html", context)

class RelatorioVendasView(PermissionRequiredMixin, FormView):
    template_name = 'relatorios/relatorio_vendas.html'
    form_class = RelatorioVendasForm
    permission_required = 'vendas.can_generate_report_sale'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loja'] = self.request.session.get('loja_id')
        return kwargs


from datetime import datetime, timedelta

class FolhaRelatorioVendasView(PermissionRequiredMixin, TemplateView):
    template_name = 'relatorios/folha_relatorio_vendas.html'
    permission_required = 'vendas.can_generate_report_sale'

    def get_context_data(self, **kwargs):
        data_inicial = self.request.GET.get('data_inicial')
        data_final = self.request.GET.get('data_final')
        produtos = self.request.GET.get('produtos')
        vendedores = self.request.GET.get('vendedores')
        loja = self.request.GET.get('lojas')
        tipos_venda = self.request.GET.get('tipos_venda')

        filtros = {}

        # Adiciona filtros para datas, se informadas
        if data_inicial and data_final:
            data_final = datetime.strptime(data_final, '%Y-%m-%d')
            data_inicial = datetime.strptime(data_inicial, '%Y-%m-%d')
            
            data_final = data_final + timedelta(days=1)
            filtros['data_venda__range'] = [data_inicial, data_final]
        elif data_inicial:
            filtros['data_venda__gte'] = data_inicial
        elif data_final:
            data_final = datetime.strptime(data_final, '%Y-%m-%d')  # Converte data_final para datetime
            filtros['data_venda__lte'] = data_final
        
        if vendedores:
            filtros['vendedor__in'] = vendedores

        if produtos:
            filtros['produtos__in'] = produtos
            
        if tipos_venda:
            filtros['pagamentos__tipo_pagamento__in'] = tipos_venda

        if loja:
            filtros['loja__id'] = loja
            loja = Loja.objects.filter(id=loja).first()

        vendas = Venda.objects.filter(**filtros).distinct()
        
        if not vendas:
            messages.warning(self.request, 'Nenhuma venda encontrada com os filtros informados')
            return redirect('vendas:venda_relatorio')

        total_vendas = vendas.count()
        total_valor = 0
        total_lucro = 0
        
        if tipos_venda:
            for venda in vendas:
                    for pagamento in venda.pagamentos.filter(tipo_pagamento__in=tipos_venda):
                        if not pagamento.tipo_pagamento.nao_contabilizar:
                            total_valor += pagamento.valor
                            total_lucro += venda.lucro_total()
        else:
            total_valor = sum(venda.pagamentos_valor_total for venda in vendas)
            total_lucro = sum(venda.lucro_total() for venda in vendas)

        if data_final:
            data_final = data_final - timedelta(days=1)  # Subtrai o timedelta apenas se data_final for datetime

        context = super().get_context_data(**kwargs)

        context['vendas'] = vendas
        context['total_vendas'] = total_vendas
        context['total_valor'] = total_valor
        context['data_inicial'] = f'{data_inicial.strftime("%d/%m/%Y")}' if data_inicial else None
        context['data_final'] = f'{data_final.strftime("%d/%m/%Y")}' if data_final else None
        context['lojas'] = loja
        context['lucro'] = total_lucro

        return context

        
class ProdutoVendidoListView(PermissionRequiredMixin, ListView):
    model = ProdutoVenda
    template_name = 'produto_vendido/produto_vendido_list.html'
    context_object_name = 'produtos_vendidos'
    permission_required = 'vendas.view_produtovenda'
    paginate_by = 10
    
    def get_queryset(self):
        query = super().get_queryset()
        user = self.request.user
        nome = self.request.GET.get('nome')
        imei = self.request.GET.get('imei')
        data = self.request.GET.get('data')
        data_fim = self.request.GET.get('data_fim')
        loja = self.request.GET.get('loja')
        
        if loja and user.has_perm('vendas.can_view_all_products_sold'):
            loja_id = loja
        elif user.has_perm('vendas.can_view_all_products_sold'):
            loja_id = None
        else:
            loja_id = self.request.session.get('loja_id')
            
        if loja_id:
            loja = Loja.objects.get(id=loja_id)

        if nome:
            query = query.filter(produto__nome__icontains=nome)
        if imei:
            query = query.filter(imei__icontains=imei)
        if data and data_fim:
            query = query.filter(venda__data_venda__range=[data, data_fim])
        if loja:
            query = query.filter(venda__loja=loja)
        
        return query.order_by('-venda__data_venda')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nome'] = self.request.GET.get('nome')
        context['imei'] = self.request.GET.get('imei')
        context['data'] = self.request.GET.get('data')
        context['data_fim'] = self.request.GET.get('data_fim')
        context['loja'] = self.request.GET.get('loja')
        
        context['lojas'] = Loja.objects.all()
        return context


from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from pixqrcode import PixQrCode
from io import BytesIO
import qrcode
from .models import Loja

def gerar_qrcode_pix(request, loja_id):
    # Obter a loja pelo ID
    loja = get_object_or_404(Loja, id=loja_id)

    # Verificar se a chave Pix está presente
    if not loja.chave_pix:
        return HttpResponse("Chave Pix não encontrada para esta loja.", status=400)

    # Definir o valor fixo para o QR Code (R$10,00)
    valor = 10.00

    # Definindo a chave Pix da loja
    chave_pix = loja.chave_pix
    nome_loja = loja.nome
    cidade_loja = loja.endereco or "Cidade não especificada"

    # Criando a instância da classe PixQrCode
    pix_qrcode = PixQrCode(
        name=nome_loja, 
        key=chave_pix, 
        city=cidade_loja, 
        amount=str(valor)  # O valor precisa ser passado como string
    )

    # Gerar o código QR Pix
    qr_code_data = pix_qrcode.generate_code()

    # Gerar a imagem do QR Code
    qr = qrcode.make(qr_code_data)

    # Salvar o QR Code em memória usando BytesIO
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    # Criar a resposta HTTP com o QR Code gerado
    response = HttpResponse(buffer, content_type="image/png")
    response['Content-Disposition'] = 'inline; filename="qrcode_pix.png"'

    return response


def contrato_view(request, pk):
    
    # Busca a venda
    venda = Venda.objects.get(pk=pk)
    valor_total = venda.pagamentos_valor_total
    pagamento_carne = Pagamento.objects.filter(venda=venda, tipo_pagamento__carne=True).first()
    aparelho = venda.itens_venda.first()
    imei = aparelho.imei if aparelho else None
    loja = Loja.objects.get(id=request.session.get('loja_id'))
    cliente = venda.cliente
    contrato = loja.contrato
    contrato = json.dumps(contrato)
    primeira_parcela = pagamento_carne.data_primeira_parcela if pagamento_carne else None
    parcelas = pagamento_carne.parcelas if pagamento_carne else 0
    parcelas_meses = []

    for i in range(parcelas):
        # somar 1 meses a data de vencimento
        mes = primeira_parcela.month + i
        ano = primeira_parcela.year
        if mes > 12:
            mes -= 12
            ano += 1
        data_vencimento = primeira_parcela.replace(month=mes, year=ano)
        parcelas_meses.append(data_vencimento.strftime('%d/%m/%Y'))

    ultima_parcela = parcelas_meses[-1] if parcelas_meses else None

    context = {
        'venda': venda,
        'valor_total': valor_total,
        'tipo_pagamento': 'Carnê' if pagamento_carne else 'À vista',
        'cliente': cliente,
        'data_atual': localtime(now()).date(),
        'loja': loja,
        'contrato': contrato,
        'aparelho': aparelho,
        'imei': imei,
        'valor_parcela': pagamento_carne.valor_parcela if pagamento_carne else None,
        'quantidade_parcelas': parcelas,
        'parcelas_meses': parcelas_meses,
        'primeira_parcela': primeira_parcela.strftime('%d/%m/%Y') if primeira_parcela else None,
        'ultima_parcela': ultima_parcela,

    }

    return render(request, "venda/contrato.html", context)



@login_required
@permission_required('vendas.change_pagamento', raise_exception=True)
def toggle_bloqueio_pagamento(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    pagamento.bloqueado = not pagamento.bloqueado
    pagamento.save()
    return redirect(reverse('financeiro:contas_a_receber_update', args=[pagamento.pk]))


class ConsultaPagamentosView(FormView):
    template_name = "publico/consulta_pagamentos.html"
    form_class = ClienteConsultaForm

    def form_valid(self, form):
        cpf = form.cleaned_data['cpf']
        dob = form.cleaned_data['date_of_birth']
        pagamentos = (
            Pagamento.objects
            .with_status_flags()     # já inclui with_parcelas_info() internamente
            .filter(
                venda__cliente__cpf=cpf,
                venda__cliente__nascimento=dob
            )
        )
        return self.render_to_response(
            self.get_context_data(form=form, pagamentos=pagamentos)
        )
        

class PagamentoDetailView(DetailView):
    model = Pagamento
    template_name = 'publico/pagamento_detail.html'
    context_object_name = 'pagamento'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        ctx       = super().get_context_data(**kwargs)
        pagamento = ctx['pagamento']

        # busca loja e limpa só os dígitos da chave (telefone ou CPF/CNPJ)
        loja    = get_object_or_404(Loja, nome__iexact='CredFácil')
        chave   = re.sub(r'\D', '', loja.chave_pix)
        nome    = loja.nome
        cidade  = 'belem'

        qr_items = []
        for parcela in pagamento.parcelas_pagamento.all().order_by('numero_parcela'):
            txid   = f"{pagamento.pk:04d}{parcela.numero_parcela:02d}"
            amount = f"{parcela.valor:.2f}"

            payload = Payload(nome, chave, amount, cidade, txid)

            buf_out = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf_out
            payload.gerarPayload()
            sys.stdout = old_stdout
            emv = buf_out.getvalue().strip()

            img = qrcode.make(emv)
            img_buf = BytesIO()
            img.save(img_buf, format='PNG')
            b64 = base64.b64encode(img_buf.getvalue()).decode()

            qr_items.append({'parcela': parcela, 'qr_b64': b64})

        ctx['qr_items'] = qr_items
        return ctx



class InformarPagamentoView(View):
    def post(self, request, pk):
        parcela = get_object_or_404(Parcela, pk=pk)
        parcela.pagamento_efetuado = True
        parcela.pagamento_efetuado_em = timezone.now()
        parcela.data_pagamento = timezone.now().date()
        parcela.save(update_fields=['pagamento_efetuado', 'data_pagamento'])
        messages.success(request, "Pagamento informado e está em confirmação.")
        return redirect('vendas:pagamento_detail', pk=parcela.pagamento.pk)
