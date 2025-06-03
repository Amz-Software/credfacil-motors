from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Pagamento, Parcela
from datetime import timedelta
from notifications.signals import notify
from .models import Parcela
from notificacao.utils import enviar_ws_para_usuario
from django.contrib.auth import get_user_model
User = get_user_model()

@receiver(post_save, sender=Pagamento)
def criar_ou_atualizar_parcelas(sender, instance, created, **kwargs):
    if created: 
        for numero in range(1, instance.parcelas + 1):
            Parcela.objects.create(
                pagamento=instance,
                numero_parcela=numero,
                valor=instance.valor_parcela,
                data_vencimento=calcular_data_vencimento(instance.data_primeira_parcela, numero),
                criado_por=instance.criado_por,
                modificado_por=instance.modificado_por
            )
    else:
        # Só recria as parcelas se algum campo relevante mudou (exceto 'bloqueado')
        update_fields = kwargs.get('update_fields', None)
        
        if update_fields is not None and update_fields == {'bloqueado'}:
            return

        Parcela.objects.filter(pagamento=instance).delete()

        for numero in range(1, instance.parcelas + 1):
            Parcela.objects.create(
                pagamento=instance,
                numero_parcela=numero,
                valor=instance.valor_parcela,
                data_vencimento=calcular_data_vencimento(instance.data_primeira_parcela, numero),
                criado_por=instance.criado_por,
                modificado_por=instance.modificado_por
            )

def calcular_data_vencimento(data_primeira_parcela, numero_parcela):
    return data_primeira_parcela + timedelta(days=30 * (numero_parcela - 1))



@receiver(post_save, sender=Parcela)
def notificar_pagamento_parcela(sender, instance, created, **kwargs):
    if created:
        return

    if instance.pagamento_efetuado_em and not instance.pago:
        print("🧾 Mudou pagamento e ainda não está marcado como pago.")
        
        admins = User.objects.filter(groups__name__in=["ADMINISTRADOR", "ANALISTA"]).exclude(id=instance.criado_por_id)
        pagamento = instance.pagamento
        cliente = pagamento.venda.cliente if hasattr(pagamento.venda, 'cliente') else "Cliente"
        
        descricao = f'Parcela {instance.numero_parcela} no valor de R$ {instance.valor} foi informada como paga em {instance.pagamento_efetuado_em.strftime("%d/%m às %H:%M")} e está pendente de análise.'

        for admin in admins:
            ja_existe = admin.notifications.unread().filter(
                verb__icontains="Pagamento informado",
                description=descricao,
                target_object_id=pagamento.id,
                target_content_type__model=pagamento._meta.model_name
            ).exists()

            if ja_existe:
                continue

            print(f"✅ Enviando notificação ao admin {admin.username}")
            notify.send(
                instance,
                recipient=admin,
                verb=f'Pagamento informado por {cliente.nome.capitalize()}',
                description=descricao,
                target=pagamento,
            )

            notification_obj = admin.notifications.unread().order_by('-timestamp').first()
            if notification_obj:
                enviar_ws_para_usuario(
                    admin,
                    instance=pagamento,
                    notification_id=notification_obj.id,
                    verb=f'Pagamento informado por {cliente.nome.capitalize()}',
                    description=descricao,
                    target_url=pagamento.get_absolute_url()
                )
