from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Remove the default auth URLs that are causing the redirect issue
    # path('accounts/', include('django.contrib.auth.urls')),  # Commented out to fix redirect
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='bioframe/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='bioframe/logout.html'), name='logout'),
    path('create-workflow/', views.create_workflow, name='create_workflow'),
    path('workflow-list/', views.workflow_list, name='workflow_list'),
    path('workflow/<str:workflow_id>/', views.workflow_detail, name='workflow_detail'),
    path('workflow/<str:workflow_id>/status/', views.workflow_status_api, name='workflow_status_api'),
    path('workflow/<str:workflow_id>/view-file/', views.view_workflow_file, name='view_workflow_file'),
    path('workflow/<str:workflow_id>/download-file/', views.download_workflow_file, name='download_workflow_file'),
    path('workflow/<str:workflow_id>/rerun/', views.rerun_workflow, name='rerun_workflow'),
    path('workflow/<str:workflow_id>/rerun/<int:step_number>/', views.rerun_workflow_from_step, name='rerun_workflow_from_step'),
    path('workflow/<str:workflow_id>/tool-logs/<str:tool_name>/', views.get_tool_logs, name='get_tool_logs'),
    path('workflow/<str:workflow_id>/enhanced-tool-logs/<str:tool_name>/', views.get_enhanced_tool_logs, name='get_enhanced_tool_logs'),
    path('workflow/<str:workflow_id>/tool-log-file/<str:tool_name>/', views.get_tool_log_file, name='get_tool_log_file'),
    path('workflow/<str:workflow_id>/running-containers/', views.get_running_containers, name='get_running_containers'),
    path('workflow/<str:workflow_id>/container-logs/<str:container_id>/', views.get_container_logs, name='get_container_logs'),
    
    # Enhanced workflow upload URLs - simplified file-based approach
    path('workflow/start-upload/<str:template_id>/', views.start_workflow_with_upload, name='start_workflow_with_upload'),
    path('workflow/upload-file/<str:run_id>/', views.upload_workflow_file, name='upload_workflow_file'),
    path('workflow/upload-progress/<str:run_id>/', views.get_workflow_upload_progress, name='get_workflow_upload_progress'),
    path('workflow/validate-and-start/<str:run_id>/', views.validate_and_start_workflow, name='validate_and_start_workflow'),
    path('workflow/<str:workflow_id>/issues-log/', views.get_workflow_issues_log, name='get_workflow_issues_log'),
    path('workflow/<str:workflow_id>/issues-log/download/', views.download_workflow_issues_log, name='download_workflow_issues_log'),
    path('workflow/<str:workflow_id>/execution-log/', views.get_workflow_execution_log, name='get_workflow_execution_log'),
    path('workflow-list-json/', views.workflow_list_json, name='workflow_list_json'),
    path('create-workflow-for-run/<str:run_id>/', views.create_workflow_for_run, name='create_workflow_for_run'),
    path('initialize-workflow/<str:template_id>/', views.initialize_workflow_run, name='initialize_workflow_run'),
    path('tools/', include('tools.urls')),
    path('workflows/', include('workflows.urls')),
    path('results/', include('results.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
