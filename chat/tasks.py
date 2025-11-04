from celery import shared_task
import logging
from .image_utils import validate_and_process_file, notify_websocket

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_and_save_file_task(self, chat_id, sender_id, file_path, content=''):
    try:
        result = validate_and_process_file(chat_id, sender_id, file_path, content, self.request.id)
        logger.info(f"Task {'completed' if result['success'] else 'failed'}: {result.get('reason', 'N/A')}")
        return result
    except Exception as exc:
        logger.error(f"Task error: {exc}", exc_info=True)
        notify_websocket(chat_id, 'upload_failed', {'reason': 'processing_error'})
        raise self.retry(exc=exc)

