from django.urls import path
from . import views

urlpatterns = [
    path('notificacoes/', views.NotificacaoListView.as_view(), name='notificacao_list'),
    path('marcar-como-lida/<int:pk>/', views.MarcarNotificacaoComoLidaView.as_view(), name='notificacao_marcar_lida'),
    path('ler-todas/', views.marcar_todas_como_lidas, name='notificacao_ler_todas'),
    path('notificacao/lida/<int:pk>/', views.MarcarNotificacaoComoLidaRedirectView.as_view(), name='notificacao_marcar_lida'),

]
