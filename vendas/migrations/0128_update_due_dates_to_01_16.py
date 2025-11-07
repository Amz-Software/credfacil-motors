from django.db import migrations


def atualizar_datas_pagamento(apps, schema_editor):
    AnaliseCreditoCliente = apps.get_model('vendas', 'AnaliseCreditoCliente')
    
    # Atualiza dia 5 para dia 1
    AnaliseCreditoCliente.objects.filter(data_pagamento='5').update(data_pagamento='1')
    
    # Atualiza dia 15 para dia 16
    AnaliseCreditoCliente.objects.filter(data_pagamento='15').update(data_pagamento='16')


def reverter_datas_pagamento(apps, schema_editor):
    AnaliseCreditoCliente = apps.get_model('vendas', 'AnaliseCreditoCliente')
    
    # Reverte dia 1 para dia 5
    AnaliseCreditoCliente.objects.filter(data_pagamento='1').update(data_pagamento='5')
    
    # Reverte dia 16 para dia 15
    AnaliseCreditoCliente.objects.filter(data_pagamento='16').update(data_pagamento='15')


class Migration(migrations.Migration):

    dependencies = [
        ('vendas', '0127_seed_status_pagamento'),
    ]

    operations = [
        migrations.RunPython(atualizar_datas_pagamento, reverter_datas_pagamento),
    ]

