from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from notifications.models import Notification
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator

class NotificacaoListView(ListView):
    model = Notification
    template_name = 'notificacao/lista.html'

    def get_queryset(self):
        return self.request.user.notifications.unread()

@login_required
def marcar_como_lida(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.mark_as_read()
    return redirect(notif.target.get_absolute_url() if notif.target else '/')


@login_required
def marcar_todas_como_lidas(request):
    request.user.notifications.mark_all_as_read()
    return redirect('vendas:index')


@method_decorator(login_required, name='dispatch')
class MarcarNotificacaoComoLidaView(View):
    def post(self, request, pk):
        notificacao = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notificacao.mark_as_read()
        return JsonResponse({'status': 'ok'})