from django.db import models
from vendas.models import Base

class Produto(Base):
    codigo = models.IntegerField(unique=True, blank=True, null=True)
    nome = models.CharField(max_length=100)
    valor_repasse_logista = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    entrada_cliente = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_14_vezes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_12_vezes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_10_vezes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tipo = models.ForeignKey('produtos.TipoProduto', on_delete=models.PROTECT, related_name='produtos_tipo', null=True, blank=True)
    
    def gerar_codigo(self):
        last_product = Produto.objects.all().order_by('codigo').last()
        if not last_product:
            self.codigo = 1
        else:
            self.codigo = last_product.codigo + 1

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.gerar_codigo()
        super(Produto, self).save(*args, **kwargs)
        
    
    def total_vendas(self, loja_id=None):
        if loja_id:
            return self.produto_vendas.filter(venda__loja_id=loja_id, venda__is_deleted=False).count()
        return None
    
    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class TipoProduto(Base):
    nome = models.CharField(max_length=100)
    numero_serial = models.BooleanField(default=False)
    assistencia = models.BooleanField(default=False)

    def __str__(self):
        return self.nome

class CorProduto(Base):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class Fabricante(Base):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class MemoriaProduto(Base):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class EstadoProduto(Base):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome
