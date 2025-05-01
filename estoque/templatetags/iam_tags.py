from django import template
from produtos.models import Produto

register = template.Library()

@register.filter
def has_perm(user, perm):
    return user.has_perm(perm)

register.filter('has_perm', has_perm)


@register.filter
def total_vendas(produto, loja_id):
    if loja_id:
        return produto.produto.total_vendas(loja_id=loja_id)
    return 0

@register.filter
def get_item(dict_, key):
    return dict_.get(key, 0)
