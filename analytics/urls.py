# analytics/urls.py
from django.urls import path
from . import views

app_name = 'analytics' # Define an app namespace

urlpatterns = [
    # Use the new view function name
    path('', views.analytics_dashboard, name='dashboard'),
]