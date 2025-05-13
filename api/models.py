import uuid
from django.db import models

class ConversationHistory(models.Model):
    conversation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Conversation {self.conversation_id}"

    class Meta:
        verbose_name_plural = "Conversation Histories"

