from django.db import migrations


def criar_status_pagamentos(apps, schema_editor):
    StatusPagamento = apps.get_model('vendas', 'StatusPagamento')
    
    status_list = [
        {'nome': 'BO', 'cor_hex': '#dc3545'},  # vermelho
        {'nome': 'Atrasado', 'cor_hex': '#fd7e14'},  # laranja
        {'nome': 'Sem conexão', 'cor_hex': '#6c757d'},  # cinza
        {'nome': 'Roubo', 'cor_hex': '#000000'},  # preto
    ]
    
    for status_data in status_list:
        StatusPagamento.objects.get_or_create(
            nome=status_data['nome'],
            defaults={'cor_hex': status_data['cor_hex']}
        )


def reverter_status_pagamentos(apps, schema_editor):
    StatusPagamento = apps.get_model('vendas', 'StatusPagamento')
    StatusPagamento.objects.filter(
        nome__in=['BO', 'Atrasado', 'Sem conexão', 'Roubo']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0126_loja_porcentagem_desconto_16_pagamento_bo_and_more'),
    ]

    operations = [
        migrations.RunPython(criar_status_pagamentos, reverter_status_pagamentos),
    ]

