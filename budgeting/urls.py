# budgeting/urls.py - Simplified without namespace for now
from django.urls import path
from . import views

urlpatterns = [
    path('', views.budget_page, name='budget_page'),
    path('update/', views.update_budget, name='update_budget'),
]