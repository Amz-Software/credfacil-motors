from django.db.models.signals import post_save
from django.dispatch import receiver
from vendas.models import AnaliseCreditoCliente, Cliente
from django.contrib.auth import get_user_model
from notifications.signals import notify
from notificacao.utils import enviar_ws_para_usuario
from estoque.models import EntradaEstoque

User = get_user_model()

@receiver(post_save, sender=AnaliseCreditoCliente)
def notificar_status_analise_credito(sender, instance, created, **kwargs):
    cliente_nome = instance.cliente.nome if instance.cliente else "Cliente"
    if created:
        verb = f'Nova análise de crédito criada para o cliente {cliente_nome.capitalize()}.'
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
                    target_url=instance.cliente.get_absolute_url(),
                    type_notification='analise_credito_cliente',
                )

    if instance.status_aplicativo == 'C':
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
                    target_url=instance.cliente.get_absolute_url(),
                    type_notification='analise_credito_cliente',
                )

# @receiver(post_save, sender=EntradaEstoque)
# def notificar_entrada_estoque(sender, instance, created, **kwargs):
#     if created:
#         verb = f'Nova entrada de estoque registrada.'
#         description = f'Entrada Estoque'

#         # Notificar administradores e analistas
#         usuarios_para_notificar = list(
#             User.objects.filter(groups__name__in=['ADMINISTRADOR', 'ANALISTA']).exclude(id=instance.criado_por_id)
#         )

#         if instance.criado_por:
#             usuarios_para_notificar.append(instance.criado_por)

#         for user in usuarios_para_notificar:
#             notify.send(
#                 instance,
#                 recipient=user,
#                 verb=verb, 
#                 description=description,
#                 target=instance,
#             )

#             # WebSocket
#             ultima_notificacao = user.notifications.unread().order_by('-timestamp').first()
#             if ultima_notificacao:
#                 enviar_ws_para_usuario(
#                     usuario=user,
#                     instance=instance,
#                     notification_id=ultima_notificacao.id,
#                     verb=verb,
#                     description=description,
#                     target_url=instance.get_absolute_url(),
#                     type_notification='entrada_estoque',
#                 )


                
@receiver(post_save, sender=EntradaEstoque)
def notificar_administradores_entrada(sender, instance, created, **kwargs):
    if created:
        loja_nome = instance.loja.nome.capitalize()
        criado_por = instance.criado_por.get_full_name()
        criado_por = criado_por.capitalize() if criado_por else instance.criado_por.username.capitalize()
        admins = User.objects.filter(groups__name__icontains="ADMINISTRADOR").exclude(id=instance.criado_por_id)
        for admin in admins:
            notificacoes = notify.send(
                instance,
                recipient=admin,
                verb=f'Nova entrada de estoque registrada na {loja_nome.capitalize()} por {criado_por.capitalize()}',
                description=f'Entrada {instance.numero_nota}',
                target=instance,
            )

            # Extrai a notificação criada
            notification = admin.notifications.unread().order_by('-timestamp').first()

            if notification:
                enviar_ws_para_usuario(admin, instance, notification.id, 
                verb=f'Nova entrada de estoque registrada na {loja_nome.capitalize()} por {criado_por.capitalize()}', 
                description=f'Entrada {instance.numero_nota}',
                target_url=instance.get_absolute_url(),
                type_notification='entrada_estoque',
                )