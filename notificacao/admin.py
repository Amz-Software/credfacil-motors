from django.contrib import admin
from notifications.models import Notification
from notifications.admin import NotificationAdmin as DefaultNotificationAdmin

# Desregistra o admin original
admin.site.unregister(Notification)

# Define e registra o seu próprio admin
@admin.register(Notification)
class CustomNotificationAdmin(DefaultNotificationAdmin):
    list_display = ('recipient', 'verb', 'description', 'unread', 'timestamp')
    list_filter = ('unread', 'timestamp')
    search_fields = ('verb', 'description', 'recipient__username')
    ordering = ('-timestamp',)
