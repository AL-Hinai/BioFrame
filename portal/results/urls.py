from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    path('', views.results_list, name='results_list'),
]
