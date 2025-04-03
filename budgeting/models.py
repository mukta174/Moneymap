# budgeting/models.py - Add a correct app_label if needed
from django.db import models
from django.contrib.auth.models import User

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'budgeting'  # Explicitly define app_label
        unique_together = ['user', 'month', 'year']
        
    def __str__(self):
        return f"{self.user.username}'s budget for {self.month}/{self.year}: ₹{self.amount}"

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'budgeting'  # Explicitly define app_label
    
    def __str__(self):
        return f"{self.user.username} - {self.description}: ₹{self.amount}"