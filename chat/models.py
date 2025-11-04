# Django imports
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Local imports
from utils.models import TimeStampedModel

class Chat(TimeStampedModel):
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats_as_user1',
        db_index=True,
        verbose_name=_('کاربر 1'),
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats_as_user2',
        db_index=True,
        verbose_name=_('کاربر 2'),
    )

    class Meta:
        verbose_name = _('چت')
        verbose_name_plural = _('چت ها')
        indexes = [
            models.Index(fields=['user1'], name='idx_chat_user1'),
            models.Index(fields=['user2'], name='idx_chat_user2'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F('user2_id')),
                name='check_user1_lt_user2'
            ),
            models.UniqueConstraint(
                fields=['user1', 'user2'],
                name='unique_user_pair'
            ),
        ]

    def __str__(self):
        user1_name = self.user1.username or self.user1.phone_number
        user2_name = self.user2.username or self.user2.phone_number
        return f"چت بین {user1_name} و {user2_name}"

    def save(self, *args, **kwargs):
        if self.user1 and self.user2 and self.user1.id > self.user2.id:
            self.user1, self.user2 = self.user2, self.user1
        super().save(*args, **kwargs)


class Message(TimeStampedModel):
    MESSAGE_TYPE_CHOICES = [
        ('text', _('متن')),
        ('image', _('تصویر')),
        ('file', _('فایل')),
    ]

    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True,
        verbose_name=_('چت'),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        db_index=True,
        verbose_name=_('ارسال کننده'),
    )
    content = models.TextField(blank=True, null=True, verbose_name=_('محتوا'))
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text', verbose_name=_('نوع پیام'))
    file_path = models.FileField(upload_to='messages/', max_length=255, blank=True, null=True, verbose_name=_('فایل'))
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='read_messages',
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('خوانده شده توسط'),
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_('زمان خواندن'))
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('شناسه تسک'))
    
    class Meta:
        verbose_name = _('پیام')
        verbose_name_plural = _('پیام ها')
        indexes = [
            models.Index(fields=['chat'], name='idx_message_chat'),
            models.Index(fields=['sender'], name='idx_message_sender'),
            models.Index(fields=['created_at'], name='idx_message_created_at'),
            models.Index(fields=['read_by'], name='idx_message_read_by'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        sender_name = self.sender.username or self.sender.phone_number
        return f"پیام از {sender_name} در چت {self.chat.id}"
