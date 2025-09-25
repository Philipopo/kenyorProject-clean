from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'content', 'timestamp', 'is_read')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    inlines = [MessageInline]
    ordering = ['-created_at']  # Match your model's Meta ordering

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'content', 'timestamp', 'is_read')
    list_filter = ('conversation', 'sender', 'timestamp', 'is_read')
    search_fields = ('content',)
    ordering = ['timestamp']  # Match your model's Meta ordering