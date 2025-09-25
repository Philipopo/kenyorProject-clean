from django.urls import path, re_path
from . import views, consumers

app_name = 'chat'  # Prevents ImproperlyConfigured error

urlpatterns = [
    path('users/search/', views.UserSearchViewSet.as_view({'get': 'search'}), name='user-search'),
    path('conversations/', views.ConversationViewSet.as_view({'get': 'list', 'post': 'create'}), name='conversation-list'),
    path('conversations/<int:pk>/', views.ConversationViewSet.as_view({'get': 'retrieve'}), name='conversation-detail'),
    path('conversations/<int:pk>/messages/', views.ConversationViewSet.as_view({'get': 'messages', 'post': 'send_message'}), name='conversation-messages'),
    path('conversations/<int:pk>/mark_as_read/', views.ConversationViewSet.as_view({'post': 'mark_as_read'}), name='conversation-mark-as-read'),  # Added this line
]

websocket_urlpatterns = [
    re_path(r'^ws/chat/$', consumers.ChatConsumer.as_asgi()),
]