from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@login_required
def workflow_list(request):
    """List all workflows"""
    # This will be handled by the main bioframe views
    return redirect('workflow_list')

@login_required
def workflow_detail(request, workflow_id):
    """Show workflow details"""
    # This will be handled by the main bioframe views
    return redirect('workflow_detail', workflow_id=workflow_id)

@login_required
@require_http_methods(["POST"])
def create_workflow(request):
    """Create a new workflow via API"""
    try:
        workflow_name = request.POST.get('workflow_name')
        workflow_description = request.POST.get('workflow_description')
        selected_tools = json.loads(request.POST.get('selected_tools', '[]'))
        
        if not workflow_name or not selected_tools:
            return JsonResponse({
                'success': False,
                'error': 'Workflow name and selected tools are required'
            })
        
        # Import the orchestrator to create the workflow
        try:
            from orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
            
            # Create a new workflow run using the correct method
            workflow_run = orchestrator.create_sample_run(
                name=workflow_name,
                description=workflow_description,
                tools=selected_tools
            )
            
            if workflow_run and hasattr(workflow_run, 'id'):
                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_run.id,
                    'message': 'Workflow created successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to create workflow - invalid response from orchestrator'
                })
                
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Workflow orchestrator not available'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error creating workflow: {str(e)}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid tools data format'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })
