from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # Add default auth URLs
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='bioframe/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('create-workflow/', views.create_workflow, name='create_workflow'),
    path('workflow-list/', views.workflow_list, name='workflow_list'),
    path('workflow/<str:workflow_id>/', views.workflow_detail, name='workflow_detail'),
    path('create-workflow-for-run/<str:run_id>/', views.create_workflow_for_run, name='create_workflow_for_run'),
    path('initialize-workflow/<str:template_id>/', views.initialize_workflow_run, name='initialize_workflow_run'),
    path('tools/', include('tools.urls')),
    path('workflows/', include('workflows.urls')),
    path('results/', include('results.urls')),
]
