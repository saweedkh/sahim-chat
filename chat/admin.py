from django.contrib import admin
from .models import Chat, Message

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'user1', 'user2', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user1__phone_number', 'user2__phone_number')
    ordering = ('-created_at',)
    save_on_top = True

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'sender', 'content', 'message_type', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')