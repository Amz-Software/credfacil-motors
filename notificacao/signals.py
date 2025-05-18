from django.db.models.signals import post_save
from django.dispatch import receiver
from vendas.models import AnaliseCreditoCliente, Cliente
from django.contrib.auth import get_user_model
from notifications.signals import notify
from notificacao.utils import enviar_ws_para_usuario

User = get_user_model()

@receiver(post_save, sender=AnaliseCreditoCliente)
def notificar_status_analise_credito(sender, instance, created, **kwargs):
    if created:
        return

    if instance.status_aplicativo == 'C':
        print("Status de análise de crédito foi alterado para 'C' (Confirmado).")
        cliente_nome = instance.cliente.nome if instance.cliente else "Cliente"
        verb = f'Instalação do cliente {cliente_nome.capitalize()} está aguardando confirmação.'
        description = f'Imei {instance.imei.imei} da loja {instance.loja.nome.capitalize()}.'

        # Admins + analista que criou
        usuarios_para_notificar = list(
            User.objects.filter(groups__name__in=['ADMINISTRADOR', 'ANALISTA']).exclude(id=instance.criado_por_id)
        )

        if instance.criado_por:
            usuarios_para_notificar.append(instance.criado_por)

        for user in usuarios_para_notificar:
            notify.send(
                instance,
                recipient=user,
                verb=verb,
                description=description,
                target=instance.cliente,
            )

            # WebSocket
            ultima_notificacao = user.notifications.unread().order_by('-timestamp').first()
            if ultima_notificacao:
                enviar_ws_para_usuario(
                    usuario=user,
                    instance=instance,
                    notification_id=ultima_notificacao.id,
                    verb=verb,
                    description=description,
                    target_url=instance.cliente.get_absolute_url()
                )
