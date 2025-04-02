# emailparser/urls.py

from django.urls import path
from . import views # Import views from the current app

app_name = 'emailparser' # Optional: Define an app namespace

urlpatterns = [
    # Map the root URL of this app ('/parser/') to the view
    path('fetch/', views.fetch_and_categorize_expenses, name='fetch_expenses'),

]