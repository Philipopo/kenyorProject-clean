from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer, UserSearchSerializer
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class UserSearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '').strip().lower()
        logger.info(f'[UserSearchViewSet] Searching users with query: "{query}", user: {request.user.email}')
        if not query:
            logger.debug('[UserSearchViewSet] No query provided, returning empty results')
            return Response({'results': []})
        try:
            users = User.objects.filter(
                Q(full_name__icontains=query) |
                Q(name__icontains=query) |
                Q(email__icontains=query)
            ).exclude(id=request.user.id).select_related('profile')
            logger.info(f'[UserSearchViewSet] Found {users.count()} users matching query: {query}')
            if not users.exists():
                logger.warning(f'[UserSearchViewSet] No users found for query: {query}')
            serializer = UserSearchSerializer(users, many=True)
            return Response({'results': serializer.data})
        except Exception as e:
            logger.error(f'[UserSearchViewSet] Error: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        logger.info(f'[ConversationViewSet] Fetching conversations for user: {self.request.user.email}')
        return Conversation.objects.filter(participants=self.request.user).order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'request': self.request})
        return context

    def create(self, request):
        participant_id = request.data.get('participant_id')
        logger.info(f'[ConversationViewSet] Creating conversation with participant_id: {participant_id}')
        if not participant_id:
            logger.error('[ConversationViewSet] Participant ID is required')
            return Response({'error': 'Participant ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            participant = get_object_or_404(User, id=participant_id)
            if participant.id == request.user.id:
                logger.error('[ConversationViewSet] Cannot create conversation with self')
                return Response({'error': 'Cannot chat with yourself'}, status=status.HTTP_400_BAD_REQUEST)
            conversation = Conversation.objects.filter(participants=participant).filter(participants=request.user).first()
            if not conversation:
                conversation = Conversation.objects.create()
                conversation.participants.add(request.user, participant)
                logger.info(f'[ConversationViewSet] Created new conversation: {conversation.id}')
            serializer = self.get_serializer(conversation, context={'request': self.request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'[ConversationViewSet] Error: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        try:
            conversation = self.get_object()
            messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
            logger.info(f'[ConversationViewSet] Fetched {messages.count()} messages for conversation: {conversation.id}')
            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f'[ConversationViewSet] Messages Error: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        try:
            conversation = self.get_object()
            if conversation.participants.filter(id=request.user.id).exists():
                content = request.data.get('content')
                if not content:
                    logger.error('[ConversationViewSet] No content provided')
                    return Response({'error': 'Message content is required'}, status=status.HTTP_400_BAD_REQUEST)
                message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=content,
                    is_read=False
                )
                logger.info(f'[ConversationViewSet] Message sent to conversation: {conversation.id}')
                serializer = MessageSerializer(message)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            logger.error(f'[ConversationViewSet] Not authorized for conversation: {conversation.id}')
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f'[ConversationViewSet] Send Message Error: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        try:
            conversation = self.get_object()
            # Mark all unread messages as read for this user
            updated = conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
            logger.info(f'[ConversationViewSet] Marked {updated} messages as read in conversation {conversation.id}')
            return Response({
                "status": "ok",
                "conversation_id": conversation.id,
                "updated": updated
            })
        except Exception as e:
            logger.error(f'[ConversationViewSet] mark_as_read Error: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)