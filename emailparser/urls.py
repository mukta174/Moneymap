# emailparser/urls.py

from django.urls import path
from . import views # Import views from the current app

app_name = 'emailparser' # Optional: Define an app namespace

urlpatterns = [
    # Map the root URL of this app ('/parser/') to the view
    path('', views.fetch_expenses_view, name='fetch_page'),
]