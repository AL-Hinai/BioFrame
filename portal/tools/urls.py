from django.urls import path
from . import views

app_name = 'tools'

urlpatterns = [
    path('', views.tool_list, name='tool_list'),
    path('api/tools/', views.tools_api, name='tools_api'),
    path('<str:tool_name>/', views.tool_detail, name='tool_detail'),
    path('<str:tool_name>/execute/', views.execute_tool, name='execute_tool'),
]
