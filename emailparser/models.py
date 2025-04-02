from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class StoredTransaction(models.Model):
    """
    Model to store fetched transactions for each user
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_id = models.CharField(max_length=255)  # Unique identifier for the transaction
    transaction_data = models.JSONField()  # Store the full transaction data as JSON
    fetched_date = models.DateTimeField(default=timezone.now)
    is_processed = models.BooleanField(default=False)  # For monthly report tracking
    
    class Meta:
        unique_together = ('user', 'transaction_id')  # Prevent duplicate transactions
        indexes = [
            models.Index(fields=['user', 'fetched_date']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        # Get description and amount from transaction_data for display
        try:
            description = self.transaction_data.get('party_name', 'Unknown')
            amount = self.transaction_data.get('amount', '0.00')
            return f"{description}: {amount}"
        except (AttributeError, json.JSONDecodeError):
            return f"Transaction {self.id}"