from django.urls import path
from . import views

urlpatterns = [
    path('notificacoes/', views.NotificacaoListView.as_view(), name='notificacao_list'),
    path('marcar-como-lida/<int:pk>/', views.MarcarNotificacaoComoLidaView.as_view(), name='notificacao_marcar_lida'),
    path('ler-todas/', views.marcar_todas_como_lidas, name='notificacao_ler_todas'),
    path('notificacao/marcar-todas/', views.ler_todas, name='notificacao_marcar_todas_lidas'),
    path(
        'notificacao/lida/<int:pk>/',
        views.MarcarNotificacaoComoLidaRedirectView.as_view(),
        name='notificacao_marcar_lida'
    ),
    path('notificacao/ler-todas/', views.ler_todas, name='ler_todas'),
    path('notificacao/selecionadas/', views.marcar_selecionadas, name='marcar_selecionadas'),

]
