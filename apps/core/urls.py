from .views import DocumentationView
from django.urls import path

urlpatterns = [
    path('docs/', DocumentationView.as_view(), name='documentation'),
]
