# Django imports
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.db.models import Q

# Third Party Packages
from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField

# Local imports
from .models import Chat, Message

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information in chat."""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'phone_number', 'full_name', 'first_name', 'last_name', 'profile_picture')
        read_only_fields = ('id', 'phone_number', 'full_name', 'first_name', 'last_name', 'profile_picture')

class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""
    sender = UserSerializer(read_only=True)
    sender_id = serializers.IntegerField(write_only=True, required=False)
    chat_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Message
        fields = (
            'id', 'chat', 'chat_id', 'sender', 'sender_id', 
            'content', 'message_type', 'file_path',
            'read_by', 'read_at', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'chat', 'sender', 'read_by', 'read_at', 'created_at', 'updated_at')
        
    def create(self, validated_data):
        """Create message with current user as sender."""
        validated_data.pop('sender_id', None)
        validated_data.pop('chat_id', None)
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)

class ChatSerializer(serializers.ModelSerializer):
    """Serializer for Chat model."""
    user1 = UserSerializer(read_only=True)
    user2 = UserSerializer(read_only=True)
    user2_id = serializers.IntegerField(write_only=True, required=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = (
            'id', 'user1', 'user2', 'user2_id',
            'last_message', 'unread_count',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user1', 'user2', 'created_at', 'updated_at')
    
    def get_last_message(self, obj):
        """Get last message in chat."""
        last_msg = obj.messages.first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None
    
    def get_unread_count(self, obj):
        """Get unread message count for current user."""
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.messages.filter(
                ~Q(sender=user),
                read_by__isnull=True
            ).count()
        return 0
    
    def create(self, validated_data):
        """Create chat with current user as user1."""
        user2_id = validated_data.pop('user2_id')
        user2 = User.objects.get(id=user2_id)
        user1 = self.context['request'].user
        
        # Check if chat already exists
        chat = Chat.objects.filter(
            user1=user1, user2=user2
        ).first()
        
        if not chat:
            chat = Chat.objects.filter(
                user1=user2, user2=user1
            ).first()
        
        if chat:
            return chat
        
        # Create new chat
        validated_data['user1'] = user1
        validated_data['user2'] = user2
        return super().create(validated_data)

class ChatListSerializer(serializers.ModelSerializer):
    """Serializer for Chat list (simplified)."""
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = (
            'id', 'other_user', 'last_message', 'unread_count',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'other_user', 'last_message', 'unread_count', 'created_at', 'updated_at')
    
    def get_other_user(self, obj):
        """Get the other user in chat."""
        user = self.context['request'].user
        other_user = obj.user2 if obj.user1 == user else obj.user1
        return UserSerializer(other_user).data
    
    def get_last_message(self, obj):
        """Get last message in chat."""
        last_msg = obj.messages.first()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content,
                'message_type': last_msg.message_type,
                'sender_id': last_msg.sender.id,
                'created_at': last_msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        """Get unread message count for current user."""
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.messages.filter(
                ~Q(sender=user),
                read_by__isnull=True
            ).count()
        return 0
