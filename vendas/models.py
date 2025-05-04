from django.db import models
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.utils.functional import cached_property
from django.db.models import Count, Q, Case, When, Value, IntegerField
from datetime import date, timedelta

class Base(models.Model):
    loja = models.ForeignKey('vendas.Loja', on_delete=models.PROTECT, related_name='%(class)s_loja', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True,editable=False)
    modificado_em = models.DateTimeField(auto_now=True,editable=False)
    criado_por = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='%(class)s_criadas',editable=False, null=True, blank=True)
    modificado_por = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='%(class)s_modificadas',editable=False, null=True, blank=True)
    
    def save(self, *args, user=None, **kwargs):
        if user:
            if not self.pk: 
                self.criado_por = user
            self.modificado_por = user
        super().save(*args, **kwargs)
        
    class Meta:
        abstract = True


class Caixa(Base):
    data_abertura = models.DateField(default=timezone.now)
    data_fechamento = models.DateField(null=True, blank=True)
    
    @property
    def saldo_total(self):
        return sum(venda.pagamentos_valor_total for venda in self.vendas.filter(is_deleted=False).filter(loja=self.loja).filter(caixa=self))
    
    @property
    def saldo_total_dinheiro(self):
        total = sum(venda.pagamentos_valor_total_dinheiro for venda in self.vendas.filter(is_deleted=False, pagamentos__tipo_pagamento__caixa=True).filter(loja=self.loja).filter(caixa=self))
        return total if total else 0
    
    def saldo_final(self):
        return (self.saldo_total_dinheiro + self.entradas) - self.saidas

    @property
    def saidas(self):
        return sum(lancamento.valor for lancamento in self.lancamentos_caixa.filter(tipo_lancamento='2'))
    
    @property
    def entradas(self):
        return sum(lancamento.valor for lancamento in self.lancamentos_caixa.filter(tipo_lancamento='1'))
    
    @property
    def quantidade_vendas(self):
        return self.vendas.filter(is_deleted=False).filter(loja=self.loja).filter(caixa=self).count()
    
    @property
    def caixa_fechado(self):
        if self.data_fechamento:
            return True
        return False
        
    
    @classmethod
    def caixa_aberto(cls, data, loja):
        return cls.objects.filter(data_abertura=data, data_fechamento__isnull=True, loja=loja).exists()

    def __str__(self):
        return f"Caixa do dia {self.data_abertura} - {self.loja}"

    class Meta:
        verbose_name_plural = 'Caixas'

class LancamentoCaixaTotal(Base):
    tipo_lancamento_opcoes = (
        ('1', 'Crédito'),
        ('2', 'Débito'),
    )

    motivo = models.CharField(max_length=100)
    tipo_lancamento = models.CharField(max_length=1, choices=tipo_lancamento_opcoes)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.tipo_lancamento} - R$ {self.valor}"
    
    class Meta:
        verbose_name_plural = 'Lancamentos Caixa Total'

class LancamentoCaixa(Base):
    tipo_lancamento_opcoes = (
        ('1', 'Crédito'),
        ('2', 'Débito'),
    )

    caixa = models.ForeignKey('vendas.Caixa', on_delete=models.PROTECT, related_name='lancamentos_caixa')
    motivo = models.CharField(max_length=100)
    tipo_lancamento = models.CharField(max_length=1, choices=tipo_lancamento_opcoes)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.tipo_lancamento} - R$ {self.valor}"
    
    class Meta:
        verbose_name_plural = 'Lancamentos Caixa'


from django.db.models import Count, Case, When, Value, IntegerField
from datetime import date

class LojaQuerySet(models.QuerySet):
    def com_repasse_pendente(self):
        hoje = date.today()
        return self.annotate(
            repasses_pendentes=Count(
                Case(
                    When(
                        repasse__status='pendente',  # Apenas repasses com status 'pendente'
                        repasse__data__lte=hoje,  # E com data do repasse até hoje
                        then=Value(1)
                    ),
                    default=Value(0),
                    output_field=IntegerField()
                )
            )
        ).filter(repasses_pendentes__gt=0)  # Apenas lojas com repasses pendentes

    def sem_repasse_pendente(self):
        hoje = date.today()
        return self.annotate(
            repasses_pendentes=Count(
                Case(
                    When(
                        repasse__status='pendente',  # Apenas repasses com status 'pendente'
                        repasse__data__lte=hoje,  # E com data do repasse até hoje
                        then=Value(1)
                    ),
                    default=Value(0),
                    output_field=IntegerField()
                )
            )
        ).filter(repasses_pendentes=0)  # Apenas lojas sem repasses pendentes


class Loja(Base):
    nome = models.CharField(max_length=100)
    cnpj = models.CharField(max_length=14, null=True, blank=True)
    inscricao_estadual = models.CharField(max_length=20, null=True, blank=True)
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    meta_vendas_diaria = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    meta_vendas_mensal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    entrada_caixa_diaria = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    logo_loja = models.ImageField(upload_to='logos_lojas/', null=True, blank=True)
    mensagem_garantia = models.TextField(null=True, blank=True)
    contrato = models.JSONField(null=True, blank=True, default=dict)
    usuarios = models.ManyToManyField('accounts.User', related_name='lojas')
    gerentes = models.ManyToManyField('accounts.User', related_name='lojas_gerenciadas')
    chave_pix = models.CharField(max_length=100, null=True, blank=True)
    objects = LojaQuerySet.as_manager()


    REPASSES_DIAS = (1, 10, 20)

    def get_repasses_status(self, meses_atras=0, limite_meses=6):
        hoje = date.today()
        resultados = []

        # Limita quantos meses olhar para trás
        meses_atras = min(meses_atras, limite_meses)

        # Queryset base de Vendas
        vendas_qs = self.venda_loja.all()

        for delta in range(meses_atras, -1, -1):
            ano = hoje.year
            mes = hoje.month - delta
            while mes <= 0:
                mes += 12
                ano -= 1

            for idx, dia in enumerate(self.REPASSES_DIAS):
                # Data do repasse atual
                try:
                    dt_atual = date(ano, mes, dia)
                except ValueError:
                    continue

                # Data do repasse anterior
                if idx == 0:
                    prev_mes, prev_ano = (mes-1, ano)
                    if prev_mes == 0:
                        prev_mes, prev_ano = 12, ano-1
                    dia_prev = self.REPASSES_DIAS[-1]
                    dt_prev = date(prev_ano, prev_mes, dia_prev)
                else:
                    dt_prev = date(ano, mes, self.REPASSES_DIAS[idx-1])

                # Intervalo de vendas (exclusive dt_prev, inclusive dt_atual)
                inicio = dt_prev + timedelta(days=1)
                fim    = dt_atual

                vendas_periodo = vendas_qs.filter(
                    data_venda__date__gte=inicio,
                    data_venda__date__lte=fim,
                    is_deleted=False
                )

                qtd = vendas_periodo.count()
                if qtd == 0:
                    continue

                # Soma de valor_repasse_logista de cada venda
                valor = Decimal('0.00')
                for venda in vendas_periodo:
                    valor_repasse = venda.repasse_logista or sum(
                        produto.produto.valor_repasse_logista * produto.quantidade
                        for produto in ProdutoVenda.objects.filter(venda=venda)
                    )
                    valor += valor_repasse

                feito = self.repasse.filter(data__date=dt_atual).exists()

                # Verifica se o valor do repasse é menor que o calculado
                if feito:
                    repasses = self.repasse.filter(data__date=dt_atual)
                    for repasse in repasses:
                        if repasse.valor < valor:
                            # Se o valor do repasse for menor que o calculado, marca como parcial
                            repasse.status = 'parcial'
                            repasse.save()

                resultados.append({
                    'data': dt_atual,
                    'inicio_periodo': inicio,
                    'fim_periodo': fim,
                    'qtd_vendas': qtd,
                    'valor_total_repasse': valor,
                    'feito': feito,
                })

        atrasados = sum(1 for rep in resultados if not rep['feito'] and rep['data'] < hoje)
        return resultados, atrasados

        
    def calcular_valor_repasse(self, data_inicio, data_fim):
        if data_inicio and data_fim:
            vendas = self.venda_loja.filter(data_venda__date__gte=data_inicio, data_venda__date__lte=data_fim, is_deleted=False)
            valor_repasse = sum(
                venda.repasse_logista if venda.repasse_logista else sum(
                    produto.produto.valor_repasse_logista * produto.quantidade
                    for produto in ProdutoVenda.objects.filter(venda=venda)
                )
                for venda in vendas
            )
            return valor_repasse

        elif data_inicio:
            vendas = self.venda_loja.filter(data_venda__date__gte=data_inicio, is_deleted=False)
            valor_repasse = sum(
                venda.repasse_logista if venda.repasse_logista else sum(
                    produto.produto.valor_repasse_logista * produto.quantidade
                    for produto in ProdutoVenda.objects.filter(venda=venda)
                )
                for venda in vendas
            )
            return valor_repasse

        elif data_fim:
            vendas = self.venda_loja.filter(data_venda__date__lte=data_fim, is_deleted=False)
            valor_repasse = sum(
                venda.repasse_logista if venda.repasse_logista else sum(
                    produto.produto.valor_repasse_logista * produto.quantidade
                    for produto in ProdutoVenda.objects.filter(venda=venda)
                )
                for venda in vendas
            )
            return valor_repasse

        else:
            vendas = self.venda_loja.filter(is_deleted=False)
            valor_repasse = sum(
                venda.repasse_logista if venda.repasse_logista else sum(
                    produto.produto.valor_repasse_logista * produto.quantidade
                    for produto in ProdutoVenda.objects.filter(venda=venda)
                )
                for venda in vendas
            )
            return valor_repasse

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = 'Lojas'


class Cliente(Base):
    nome = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20)
    cpf = models.CharField(max_length=14)
    nascimento = models.DateField()
    rg = models.CharField(max_length=20)
    cep = models.CharField(max_length=8)
    endereco = models.CharField(max_length=200)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    comprovantes = models.ForeignKey('vendas.ComprovantesCliente', on_delete=models.PROTECT, related_name='clientes')
    contato_adicional = models.ForeignKey('vendas.ContatoAdicional', on_delete=models.PROTECT, related_name='clientes', null=True, blank=True)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = 'Clientes'
        


class Venda(Base):
    data_venda = models.DateTimeField(auto_now_add=True)
    cliente = models.ForeignKey('vendas.cliente', on_delete=models.CASCADE, related_name='vendas')
    vendedor = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='vendas_realizadas')
    produtos = models.ManyToManyField('produtos.Produto', through='ProdutoVenda', related_name='vendas')
    caixa = models.ForeignKey('vendas.Caixa', on_delete=models.PROTECT, related_name='vendas')
    observacao = models.TextField(null=True, blank=True)
    repasse_logista = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    @property
    def pagamentos_valor_total(self):
        return sum(pagamento.valor for pagamento in self.pagamentos.all().filter(tipo_pagamento__nao_contabilizar=False))
    
    @property
    def pagamentos_valor_total_dinheiro(self):
        return sum(pagamento.valor for pagamento in self.pagamentos.all() if pagamento.tipo_pagamento.caixa)
    
    
    def calcular_valor_total(self):
        return sum(produto.calcular_valor_total() for produto in self.itens_venda.all())
    
    def custo_total(self):
        return sum(produto.custo() for produto in self.itens_venda.all())
    
    def lucro_total(self):
        return sum(produto.lucro() for produto in self.itens_venda.all())
    
    @cached_property
    def valor_repasse(self):
        return sum(produto.produto.valor_repasse_logista * produto.quantidade for produto in self.itens_venda.all())
    
    def __str__(self):
        return f"{self.cliente} - {self.data_venda.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name_plural = 'Vendas'
        permissions = (
            ('can_more_desconto', 'Pode dar mais desconto'),
            ('can_generate_report_sale', 'Pode gerar relatório de vendas'),
            ('change_status_analise', 'Pode alterar status de análise'),
            ('can_view_all_sales', 'Pode ver todas as vendas'),
            ('can_view_produtos_vendidos', 'Pode ver aba produtos vendidos'),
            ('can_edit_finished_sale', 'Pode editar venda finalizada'),
        )


class AnaliseCreditoCliente(Base):
    STATUS_CHOICES = [
        ('EA', 'Em análise'),
        ('A', 'Aprovado'),
        ('R', 'Reprovado'),
        ('C', 'Cancelado'),   
    ]
    cliente = models.OneToOneField('vendas.Cliente', on_delete=models.PROTECT, related_name='analise_credito')
    data_analise = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_reprovacao = models.DateTimeField(null=True, blank=True)
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    aprovado_por = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='analises_credito_aprovadas', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='EA')
    data_pagamento = models.CharField(max_length=20, null=True, blank=True, choices=(
        ('1', 'Dia 1'),
        ('10', 'Dia 10'),
        ('20', 'Dia 20'),
    ), verbose_name='Data de pagamento')
    numero_parcelas = models.CharField(max_length=20, choices=(
        ('4', '4x'),
        ('6', '6x'),
    ))
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT, related_name='analises_credito')
    imei = models.ForeignKey('estoque.EstoqueImei', on_delete=models.PROTECT, related_name='analises_credito_imei', null=True, blank=True)
    venda = models.ForeignKey('vendas.Venda', on_delete=models.PROTECT, related_name='analises_credito_venda', null=True, blank=True)
    observacao = models.TextField(null=True, blank=True)
    
    def venda_gerada(self):
        if self.venda:
            return True
        return False
    
    
    def aprovar(self, user):
        self.status = 'A'
        self.data_aprovacao = timezone.now()
        self.aprovado_por = user
        self.save()
        return self.status
    
    def reprovar(self):
        self.status = 'R'
        self.data_reprovacao = timezone.now()
        self.save()
        return self.status
    
    def cancelar(self):
        self.status = 'C'
        self.save()
        return self.status
    
    def __str__(self):
        return f"Análise de crédito para {self.cliente} - {self.data_analise.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name_plural = 'Análises de Crédito'
        permissions = (
            ('can_approve_credit_analysis', 'Pode aprovar análise de crédito'),
            ('can_reject_credit_analysis', 'Pode reprovar análise de crédito'),
            ('can_cancel_credit_analysis', 'Pode cancelar análise de crédito'),
            ('view_all_analise_credito', 'Pode ver todos as análise de crédito')
        )
    
    

class ContatoAdicional(Base):
    nome_adicional = models.CharField(max_length=100, null=True, blank=True)
    contato = models.CharField(max_length=20, null=True, blank=True)
    endereco_adicional = models.CharField(max_length=200, null=True, blank=True)

class Endereco(Base):
    cep = models.CharField(max_length=8)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    endereco = models.CharField(max_length=200)
    numero = models.CharField(max_length=10)
    complemento = models.CharField(max_length=100)
    
    def __str__(self):
        return self.endereco
    
    class Meta:
        verbose_name_plural = 'Informacoes Clientes'

class ComprovantesCliente(Base):
    documento_identificacao_frente = models.ImageField(upload_to='comprovantes_clientes')
    documento_identificacao_frente_analise = models.BooleanField(default=False)
    documento_identificacao_verso = models.ImageField(upload_to='comprovantes_clientes')
    documento_identificacao_verso_analise = models.BooleanField(default=False)
    comprovante_residencia = models.ImageField(upload_to='comprovantes_clientes')
    comprovante_residencia_analise = models.BooleanField(default=False)
    consulta_serasa = models.ImageField(upload_to='comprovantes_clientes', null=True, blank=True)
    consulta_serasa_analise = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = 'Comprovantes Clientes'

class ProdutoVenda(Base):
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT, related_name='produto_vendas')
    imei = models.CharField(max_length=100, null=True, blank=True)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField()
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    venda = models.ForeignKey('vendas.Venda', on_delete=models.PROTECT, related_name='itens_venda')
    

    def calcular_valor_total(self):
        return (self.valor_unitario * self.quantidade) - self.valor_desconto
    
    def lucro(self):
        from estoque.models import ProdutoEntrada
        return (self.valor_unitario - ProdutoEntrada.objects.filter(produto=self.produto).last().custo_unitario) * self.quantidade
    
    def custo(self):
        from estoque.models import ProdutoEntrada
        return ProdutoEntrada.objects.filter(produto=self.produto).last().custo_unitario * self.quantidade
    
    def __str__(self):
        return f"{self.produto.nome} x {self.quantidade} (R$ {self.valor_unitario})"
    
    class Meta:
        verbose_name_plural = 'Produtos Vendas'
        ordering = ['-id']
        permissions = (
            ('can_view_all_products_sold', 'Pode ver todos os produtos vendidos'),
        )
        

class Pagamento(Base):
    venda = models.ForeignKey('vendas.Venda', on_delete=models.PROTECT, related_name='pagamentos')
    tipo_pagamento = models.ForeignKey('vendas.TipoPagamento', on_delete=models.PROTECT, related_name='pagamentos_tipo')
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    parcelas = models.PositiveIntegerField(default=1, null=True, blank=True)
    # valor_parcela = models.DecimalField(max_digits=10, decimal_places=2)
    data_primeira_parcela = models.DateField()
    
    @property
    def valor_parcela(self):
        return self.valor / self.parcelas
    
    def __str__(self):
        return f"Pagamento de R$ {self.valor} via {self.tipo_pagamento.nome}"
    
    class Meta:
        verbose_name_plural = 'Pagamentos'
        permissions = (
            ('can_view_all_payments', 'Pode ver todos os pagamentos'),
        )
    

class TipoPagamento(Base):
    nome = models.CharField(max_length=100)
    caixa = models.BooleanField(default=False)
    parcelas = models.BooleanField(default=False)
    financeira = models.BooleanField(default=False)
    carne = models.BooleanField(default=False)
    nao_contabilizar = models.BooleanField(default=False)
    
    def __str__(self):
        return self.nome
    
    class  Meta:
        verbose_name_plural = 'Tipos de Pagamentos'
        

class Parcela(Base):
    pagamento = models.ForeignKey('vendas.Pagamento', on_delete=models.PROTECT, related_name='parcelas_pagamento')
    numero_parcela = models.PositiveIntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    tipo_pagamento = models.ForeignKey('vendas.TipoPagamento', on_delete=models.PROTECT, related_name='parcelas_tipo_pagamento', null=True, blank=True)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField()
    pago = models.BooleanField(default=False)

    @property
    def valor_restante(self):
        valor_pago = self.valor_pago or 0
        desconto = self.desconto or 0
        return (self.valor - desconto) - valor_pago

    def __str__(self):
        return f"Parcela {self.numero_parcela} de {self.pagamento}"
        