# accounts/urls.py
from django.urls import path, include
from . import views

# No app_name needed here if included with namespace in main urls.py

urlpatterns = [
    path('signup/', views.sign_up_view, name='signup'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),
    ]