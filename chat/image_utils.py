# Django imports
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

# Python imports
import os
import logging

# Third party imports
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from imagekit import ImageSpec
from imagekit.processors import ResizeToFit, Transpose
from PIL import Image

# Local imports
from .models import Message, Chat

# Constants
User = get_user_model()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_SIZE = 2 * 1024 * 1024
MAX_DIMENSION = 1000

ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
ALLOWED_DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'}


class CompressedImage(ImageSpec):
    processors = [Transpose(), ResizeToFit(MAX_DIMENSION, MAX_DIMENSION)]
    format = 'WEBP'
    options = {'quality': 85}


class HighCompressedImage(ImageSpec):
    processors = [Transpose(), ResizeToFit(MAX_DIMENSION, MAX_DIMENSION)]
    format = 'WEBP'
    options = {'quality': 70}


def validate_file_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ALLOWED_IMAGE_EXTS:
        try:
            with Image.open(file_path) as im:
                im.verify()
            return 'image', ext
        except Exception:
            return None, ext
    
    return ('document', ext) if ext in ALLOWED_DOC_EXTS else (None, ext)


def compress_image(file_path, target_size=MAX_IMAGE_SIZE):
    with open(file_path, 'rb') as f:
        source = ContentFile(f.read())
    
    compressed = CompressedImage(source=source).generate().read()
    
    if len(compressed) <= target_size:
        return compressed
    
    compressed = HighCompressedImage(source=source).generate().read()
    
    return compressed if len(compressed) <= MAX_FILE_SIZE else None


def notify_websocket(chat_id, event_type, data):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"chat_{chat_id}", {'type': event_type, **data})


def format_message_data(message, sender, request=None):
    file_path = str(message.file_path.name if hasattr(message.file_path, 'name') else message.file_path)
    media_url = (settings.MEDIA_URL or '/media/').rstrip('/')
    path = file_path if file_path.startswith('/') else f"/{file_path}"
    
    # Convert ImageFieldFile to URL string
    profile_picture = None
    if sender.profile_picture:
        profile_picture = sender.get_profile_picture(request)
    
    return {
        'id': message.id,
        'sender': {
            'id': sender.id,
            'phone_number': str(sender.phone_number),
            'full_name': sender.get_full_name(),
            'profile_picture': profile_picture,
        },
        'content': message.content or '',
        'message_type': message.message_type,
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_url': f"{media_url}{path}" if not path.startswith(media_url) else path,
        'celery_task_id': message.celery_task_id,
        'created_at': message.created_at.isoformat() if message.created_at else None,
        'read_by': message.read_by_id,
        'read_at': message.read_at.isoformat() if message.read_at else None,
    }


def cleanup(path):
    full_path = os.path.join(settings.MEDIA_ROOT, path) if not os.path.isabs(path) else path
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


def validate_and_process_file(chat_id, sender_id, file_path, content, task_id):
    logger.info(f"Processing: chat={chat_id}, file={file_path}")
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if not os.path.exists(full_path):
        notify_websocket(chat_id, 'upload_failed', {'reason': 'file_not_found'})
        return {'success': False, 'reason': 'file_not_found'}
    
    file_type, ext = validate_file_type(full_path)
    
    if not file_type:
        cleanup(full_path)
        notify_websocket(chat_id, 'upload_failed', {'reason': 'unsupported_type'})
        return {'success': False, 'reason': 'unsupported_type'}
    
    file_size = os.path.getsize(full_path) if os.path.exists(full_path) else 0
    
    if file_size > MAX_FILE_SIZE:
        if file_type == 'document':
            cleanup(full_path)
            notify_websocket(chat_id, 'upload_failed', {'reason': 'file_too_large'})
            return {'success': False, 'reason': 'file_too_large'}
    
    processed_path = file_path
    
    if file_type == 'image' and (file_size > MAX_IMAGE_SIZE or ext != '.webp'):
        try:
            compressed = compress_image(full_path, MAX_IMAGE_SIZE)
            
            if not compressed:
                cleanup(full_path)
                notify_websocket(chat_id, 'upload_failed', {'reason': 'file_too_large'})
                return {'success': False, 'reason': 'file_too_large'}
            
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            processed_path = f"messages/{base_name}.webp"
            new_full_path = os.path.join(settings.MEDIA_ROOT, processed_path)
            
            with open(new_full_path, 'wb') as f:
                f.write(compressed)
            
            if full_path != new_full_path:
                cleanup(full_path)
            
            logger.info(f"Compressed: {len(compressed)} bytes")
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            cleanup(full_path)
            notify_websocket(chat_id, 'upload_failed', {'reason': 'image_unprocessable'})
            return {'success': False, 'reason': 'image_unprocessable'}
    
    try:
        chat = Chat.objects.get(id=chat_id)
        sender = User.objects.get(id=sender_id)
        
        message = Message.objects.create(
            chat=chat,
            sender=sender,
            content=content,
            message_type='file',
            file_path=processed_path,
            celery_task_id=task_id
        )
        
        notify_websocket(chat_id, 'chat_message', {'message': format_message_data(message, sender)})
        logger.info(f"Message created: {message.id}")
        
        return {'success': True, 'message_id': message.id}
        
    except (Chat.DoesNotExist, User.DoesNotExist) as e:
        cleanup(processed_path)
        reason = 'chat_not_found' if isinstance(e, Chat.DoesNotExist) else 'user_not_found'
        notify_websocket(chat_id, 'upload_failed', {'reason': reason})
        return {'success': False, 'reason': reason}
        
    except Exception as e:
        logger.error(f"Database error: {e}", exc_info=True)
        cleanup(processed_path)
        notify_websocket(chat_id, 'upload_failed', {'reason': 'database_error'})
        return {'success': False, 'reason': 'database_error'}
