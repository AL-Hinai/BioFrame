from django.urls import path
from . import views

app_name = 'workflows'

urlpatterns = [
    path('', views.workflow_list, name='workflow_list'),
    path('create/', views.create_workflow, name='create_workflow'),
    path('<str:workflow_id>/', views.workflow_detail, name='workflow_detail'),
]
