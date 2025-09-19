from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import os
import yaml
import json
from pathlib import Path
from datetime import datetime
import sys
import hashlib
import shutil
from django.utils import timezone
from .models import FileUploadSession, UploadedFile, WorkflowRun

# Add the orchestrator to the path
sys.path.append('/app/workflow-orchestrator')

# @login_required  # Temporarily disabled for testing
def home(request):
    """Home page view"""
    return render(request, 'bioframe/home.html')

# @login_required  # Temporarily disabled for testing
def dashboard(request):
    """User dashboard with workflow overview and quick actions"""
    print("🚀 Dashboard view called", flush=True)
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🚀 Dashboard view called via logging")
    stats = {
        'total_workflows': 0, 'completed_workflows': 0,
        'running_workflows': 0, 'failed_workflows': 0, 'total_custom_workflows': 0
    }
    recent_activities = []
    
    try:
        # Note: Orchestrator is now a separate service, we read workflow status from files
        
        # Get workflows from file system and read their current status
        all_workflows = []
        runs_dir = Path("/app/data/runs")
        logger.info(f"🔍 Checking runs directory: {runs_dir}")
        logger.info(f"🔍 Runs directory exists: {runs_dir.exists()}")
        
        if runs_dir.exists():
            logger.info(f"🔍 Found {len(list(runs_dir.iterdir()))} items in runs directory")
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir():
                    workflow_id = run_dir.name
                    logger.info(f"🔍 Processing workflow directory: {workflow_id}")
                    
                    # Try to read workflow_summary.json first (most current status)
                    summary_file = run_dir / "workflow_summary.json"
                    workflow_file = run_dir / "workflow.yaml"
                    
                    workflow_data = {}
                    if summary_file.exists():
                        try:
                            with open(summary_file, 'r') as f:
                                workflow_data = json.load(f)
                            logger.info(f"✅ Read summary for {workflow_id}: {workflow_data.get('status', 'unknown')}")
                        except Exception as e:
                            logger.error(f"❌ Error reading summary for {workflow_id}: {e}")
                    
                    # Fallback to workflow.yaml if no summary
                    if not workflow_data and workflow_file.exists():
                        try:
                            with open(workflow_file, 'r') as f:
                                workflow_data = yaml.safe_load(f)
                            logger.info(f"✅ Read workflow.yaml for {workflow_id}: {workflow_data.get('status', 'unknown')}")
                        except Exception as e:
                            logger.error(f"❌ Error reading workflow.yaml for {workflow_id}: {e}")
                    
                    if workflow_data:
                        # Ensure we have the workflow_id
                        workflow_data['workflow_id'] = workflow_id
                        
                        # Determine actual status by analyzing the file system
                        actual_status = workflow_data.get('status', 'unknown')
                        tools = workflow_data.get('tools', [])
                        total_steps = len(tools) if tools else 0
                        
                        if total_steps > 0:
                            # Count completed steps
                            completed_steps = 0
                            for i in range(1, total_steps + 1):
                                step_name = tools[i-1] if i <= len(tools) else f"step_{i}"
                                step_path = run_dir / f"step_{i}_{step_name}"
                                if step_path.exists() and any(step_path.iterdir()):
                                    completed_steps += 1
                                    logger.info(f"✅ Step {i} ({step_name}) completed for {workflow_id}")
                            
                            logger.info(f"🔍 {workflow_id}: {completed_steps}/{total_steps} steps completed")
                            
                            # Determine actual status based on step completion
                            if completed_steps == total_steps:
                                actual_status = 'completed'
                                workflow_data['status'] = 'completed'
                                logger.info(f"✅ {workflow_id}: Marked as completed")
                            elif completed_steps > 0 and actual_status == 'running':
                                # Some steps completed but not all - check if it's been a while
                                # This could indicate a failure or stuck workflow
                                actual_status = 'failed'
                                workflow_data['status'] = 'failed'
                                logger.info(f"⚠️ {workflow_id}: Marked as failed (incomplete)")
                            elif completed_steps == 0 and actual_status == 'running':
                                # No steps completed but marked as running - could be stuck
                                actual_status = 'pending'
                                workflow_data['status'] = 'pending'
                                logger.info(f"⏳ {workflow_id}: Marked as pending (stuck)")
                        
                        all_workflows.append(workflow_data)
                        logger.info(f"✅ Added {workflow_id} to all_workflows list")
                    else:
                        logger.warning(f"❌ No workflow data found for {workflow_id}")
        
        logger.info(f"🔍 Dashboard discovered {len(all_workflows)} workflows from file system")
        
        # Sort workflows by creation date (most recent first)
        def get_workflow_date(workflow):
            try:
                # Try to get creation date from various fields
                created_at = workflow.get('created_at') or workflow.get('start_time')
                logger.debug(f"Processing date for {workflow.get('workflow_id')}: {created_at} (type: {type(created_at)})")
                
                if isinstance(created_at, str):
                    try:
                        # Handle different date formats
                        if 'T' in created_at:
                            # ISO format: 2025-08-30T20:20:18.437632
                            parsed_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            logger.debug(f"Parsed ISO date: {parsed_date}")
                            return parsed_date
                        else:
                            # Other formats, try to parse
                            parsed_date = datetime.fromisoformat(created_at)
                            logger.debug(f"Parsed other date: {parsed_date}")
                            return parsed_date
                    except Exception as e:
                        logger.error(f"Error parsing date '{created_at}' for workflow {workflow.get('workflow_id')}: {e}")
                        return datetime.now()
                elif isinstance(created_at, datetime):
                    logger.debug(f"Already datetime: {created_at}")
                    return created_at
                else:
                    logger.debug(f"No valid date found, using now()")
                    return datetime.now()
            except Exception as e:
                logger.error(f"Unexpected error in get_workflow_date for {workflow.get('workflow_id')}: {e}")
                return datetime.now()
        
        # Sort workflows by date (most recent first)
        try:
            logger.info(f"🔍 Attempting to sort {len(all_workflows)} workflows by date")
            all_workflows.sort(key=get_workflow_date, reverse=True)
            logger.info(f"🔍 Successfully sorted {len(all_workflows)} workflows by date")
        except Exception as e:
            logger.error(f"❌ Error sorting workflows: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            # Continue without sorting
        
        stats['total_workflows'] = len(all_workflows)
        stats['completed_workflows'] = len([w for w in all_workflows if w.get('status') == 'completed'])
        stats['running_workflows'] = len([w for w in all_workflows if w.get('status') == 'running'])
        stats['failed_workflows'] = len([w for w in all_workflows if w.get('status') == 'failed'])
        stats['total_custom_workflows'] = len([w for w in all_workflows if not w.get('template_used', False)])
        
        logger.info(f"📊 Stats calculated: {stats}")
        
        # Process each workflow for the activity timeline (show most recent 10)
        logger.info(f"🔍 Processing {len(all_workflows[:10])} workflows for dashboard")
        for i, workflow in enumerate(all_workflows[:10]):  # Show most recent 10 workflows
            logger.info(f"🔍 Processing workflow {i+1}: {workflow.get('workflow_id', 'unknown')}")
            # Handle both old and new workflow formats
            workflow_id = workflow.get('workflow_id') or workflow.get('id', 'unknown')
            workflow_name = workflow.get('workflow_name') or workflow.get('name', 'Data Analysis Run')
            status = workflow.get('status', 'unknown')
            created_at = workflow.get('created_at', '')
            tools = workflow.get('tools', [])
            
            logger.info(f"🔍 Workflow data: id={workflow_id}, name={workflow_name}, status={status}, tools={tools}")
            
            # Extract tool names from different possible structures
            tool_names = []
            if tools:
                if isinstance(tools[0], dict) and 'tool_name' in tools[0]:
                    # Old format: tools is list of dicts with tool_name
                    tool_names = [tool.get('tool_name', 'unknown') for tool in tools]
                elif isinstance(tools[0], str):
                    # New format: tools is list of strings
                    tool_names = tools
                else:
                    tool_names = ['unknown']
            
            logger.info(f"🔍 Tool names extracted: {tool_names}")
            
            # Parse creation date
            try:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_at = datetime.now()
            except:
                created_at = datetime.now()
            
            # Calculate progress based on actual step completion
            if status == 'completed':
                progress = 100
            elif status == 'running':
                # Check how many steps are completed by looking at step directories
                step_dir = Path(f"/app/data/runs/{workflow_id}")
                completed_steps = 0
                total_steps = len(tool_names) if tool_names else 0
                
                if step_dir.exists() and total_steps > 0:
                    for i in range(1, total_steps + 1):
                        step_name = tool_names[i-1] if i <= len(tool_names) else f"step_{i}"
                        step_path = step_dir / f"step_{i}_{step_name}"
                        if step_path.exists() and any(step_path.iterdir()):
                            completed_steps += 1
                    
                    if total_steps > 0:
                        progress = int((completed_steps / total_steps) * 100)
                    else:
                        progress = 50  # Default for running
                else:
                    progress = 50  # Default for running
            else:
                progress = 0
            
            # Create description
            if tool_names:
                description = f'Workflow with {len(tool_names)} tools: {", ".join(tool_names)}'
            else:
                description = 'Workflow with unknown tools'
            
            activity = {
                'id': workflow_id,
                'name': workflow_name,
                'description': description,
                'status': status,
                'created_at': created_at,
                'updated_at': created_at,
                'progress': progress,
                'step_count': len(tool_names),
                'tools': tool_names,
                'directory': f"/app/data/runs/{workflow_id}",
                'is_file_based': True,
                'execution_time': workflow.get('execution_time', 0),
                'completed_at': workflow.get('completed_at', '')
            }
            recent_activities.append(activity)
            logger.info(f"✅ Added activity for {workflow_id}: {activity}")
        
        logger.info(f"📊 File-based stats: {stats['total_workflows']} total, {stats['completed_workflows']} completed")
        logger.info(f"📋 Recent activities: {len(recent_activities)} workflows processed")
        
    except Exception as e:
        print(f"❌ Error fetching file-based data: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print("❌ End of error traceback")
    
    print(f"🚀 Running in 100% file-based mode - no database dependencies")
    print(f"📋 Final recent_activities count: {len(recent_activities)}")
    
    # Add tools path to sys.path
    import sys
    sys.path.append('/app')
    from tools.views import scan_tools_directory
    available_tools = scan_tools_directory()
    
    context = {
        'user': request.user, 'stats': stats, 'recent_activities': recent_activities,
        'available_tools': available_tools, 'tools_count': len(available_tools),
        'system_status': 'file_based_only', 'file_based_count': len(recent_activities), 'db_based_count': 0
    }
    logger.info(f"📤 Rendering template with context: recent_activities count: {len(recent_activities)}")
    logger.info(f"📤 Context keys: {list(context.keys())}")
    logger.info(f"📤 recent_activities type: {type(recent_activities)}")
    logger.info(f"📤 recent_activities content: {recent_activities[:2] if recent_activities else 'EMPTY'}")
    return render(request, 'bioframe/dashboard.html', context)

def workflow_list_json(request):
    """Return workflow list as JSON for dashboard expansion"""
    try:
        import sys
        sys.path.append('/app/workflow-orchestrator')
        from orchestrator import WorkflowOrchestrator
        
        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
        
        # Get workflows from file system and read their current status
        all_workflows = []
        runs_dir = Path("/app/data/runs")
        
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir():
                    workflow_id = run_dir.name
                    
                    # Try to read workflow_summary.json first (most current status)
                    summary_file = run_dir / "workflow_summary.json"
                    workflow_file = run_dir / "workflow.yaml"
                    
                    workflow_data = {}
                    if summary_file.exists():
                        try:
                            with open(summary_file, 'r') as f:
                                workflow_data = json.load(f)
                        except Exception as e:
                            print(f"Error reading summary for {workflow_id}: {e}")
                    
                    # Fallback to workflow.yaml if no summary
                    if not workflow_data and workflow_file.exists():
                        try:
                            with open(workflow_file, 'r') as f:
                                workflow_data = yaml.safe_load(f)
                        except Exception as e:
                            print(f"Error reading workflow for {workflow_id}: {e}")
                    
                    if workflow_data:
                        # Ensure we have the workflow_id
                        workflow_data['workflow_id'] = workflow_id
                        
                        # Determine actual status by analyzing the file system
                        actual_status = workflow_data.get('status', 'unknown')
                        tools = workflow_data.get('tools', [])
                        total_steps = len(tools) if tools else 0
                        
                        if total_steps > 0:
                            # Count completed steps
                            completed_steps = 0
                            for i in range(1, total_steps + 1):
                                step_name = tools[i-1] if i <= len(tools) else f"step_{i}"
                                step_path = run_dir / f"step_{i}_{step_name}"
                                if step_path.exists() and any(step_path.iterdir()):
                                    completed_steps += 1
                            
                            # Determine actual status based on step completion
                            if completed_steps == total_steps:
                                actual_status = 'completed'
                                workflow_data['status'] = 'completed'
                            elif completed_steps > 0 and actual_status == 'running':
                                # Some steps completed but not all - check if it's been a while
                                # This could indicate a failure or stuck workflow
                                actual_status = 'failed'
                                workflow_data['status'] = 'failed'
                            elif completed_steps == 0 and actual_status == 'running':
                                # No steps completed but marked as running - could be stuck
                                actual_status = 'pending'
                                workflow_data['status'] = 'pending'
                        
                        # Calculate progress
                        if actual_status == 'completed':
                            progress = 100
                        elif actual_status == 'running':
                            if total_steps > 0:
                                progress = int((completed_steps / total_steps) * 100)
                            else:
                                progress = 50
                        else:
                            progress = 0
                        
                        workflow_data['progress'] = progress
                        all_workflows.append(workflow_data)
        
        return JsonResponse({
            'success': True,
            'workflows': all_workflows,
            'total_count': len(all_workflows)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'workflows': [],
            'total_count': 0
        }, status=500)

# @login_required  # Temporarily disabled for testing
def create_workflow(request):
    """Create a new workflow"""
    from tools.views import scan_tools_directory
    available_tools = scan_tools_directory()
    
    # Check if a template was selected
    template_id = request.GET.get('template')
    selected_template = None
    pre_selected_tools = []
    
    if template_id:
        # Define the same templates as in workflow_list
        workflow_templates = [
            {
                'id': 'quality-control-pipeline',
                'name': 'Quality Control Pipeline',
                'description': 'Standard quality control workflow for sequencing data including FastQC, Trimmomatic, and MultiQC',
                'category': 'Quality Control',
                'tools': ['fastqc', 'trimmomatic', 'multiqc'],
                'estimated_time': '2-4 hours',
                'difficulty': 'Beginner',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['HTML Reports', 'Cleaned FASTQ'],
                'icon': 'fas fa-shield-alt',
                'color': 'bg-green-100 text-green-800'
            },
            {
                'id': 'assembly-pipeline',
                'name': 'De Novo Assembly Pipeline',
                'description': 'Complete genome assembly workflow using SPAdes with quality assessment via QUAST',
                'category': 'Assembly',
                'tools': ['spades', 'quast', 'bandage'],
                'estimated_time': '4-8 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['FASTA', 'GFA', 'Assembly Stats'],
                'icon': 'fas fa-puzzle-piece',
                'color': 'bg-blue-100 text-blue-800'
            },
            {
                'id': 'variant-calling-pipeline',
                'name': 'Variant Calling Pipeline',
                'description': 'SNP and indel detection workflow using BWA, SAMtools, and GATK',
                'category': 'Variant Analysis',
                'tools': ['bwa', 'samtools', 'gatk', 'bcftools'],
                'estimated_time': '6-12 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTA Reference'],
                'output_formats': ['VCF', 'BAM', 'Variant Reports'],
                'icon': 'fas fa-dna',
                'color': 'bg-purple-100 text-purple-800'
            },
            {
                'id': 'metagenomics-pipeline',
                'name': 'Metagenomics Analysis Pipeline',
                'description': 'Microbial community analysis workflow including taxonomic classification and functional profiling',
                'category': 'Metagenomics',
                'tools': ['fastqc', 'trimmomatic', 'metaspades', 'quast', 'metaphlan', 'humann'],
                'estimated_time': '8-16 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['Assembly', 'Taxonomy', 'Functional Profiles'],
                'icon': 'fas fa-bacteria',
                'color': 'bg-teal-100 text-teal-800'
            },
            {
                'id': 'rna-seq-pipeline',
                'name': 'RNA-Seq Analysis Pipeline',
                'description': 'Transcriptome analysis workflow including alignment, quantification, and differential expression',
                'category': 'Transcriptomics',
                'tools': ['fastqc', 'trimmomatic', 'star', 'htseq-count', 'deseq2'],
                'estimated_time': '6-10 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTA Reference', 'GTF Annotation'],
                'output_formats': ['BAM', 'Count Matrix', 'DEG Results'],
                'icon': 'fas fa-chart-line',
                'color': 'bg-orange-100 text-orange-800'
            },
            {
                'id': 'phylogenetics-pipeline',
                'name': 'Phylogenetics Pipeline',
                'description': 'Evolutionary analysis workflow including multiple sequence alignment and tree construction',
                'category': 'Phylogenetics',
                'tools': ['muscle', 'clustalw', 'raxml', 'figtree'],
                'estimated_time': '3-6 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTA', 'PHYLIP'],
                'output_formats': ['Alignment', 'Tree Files', 'Phylogenetic Analysis'],
                'icon': 'fas fa-tree',
                'color': 'bg-indigo-100 text-indigo-800'
            }
        ]
        
        # Find the selected template
        for template in workflow_templates:
            if template['id'] == template_id:
                selected_template = template
                pre_selected_tools = template['tools']
                break
    
    if request.method == 'POST':
        # Handle workflow creation
        workflow_name = request.POST.get('workflow_name')
        workflow_description = request.POST.get('workflow_description')
        selected_tools = request.POST.getlist('selected_tools')
        
        if workflow_name and selected_tools:
            try:
                # Store the workflow definition in a simple JSON file
                import os
                from datetime import datetime
                
                # Create workflows directory if it doesn't exist
                workflows_dir = Path("data/workflows")
                workflows_dir.mkdir(parents=True, exist_ok=True)
                
                # Get tool metadata to auto-fill workflow information
                from tools.views import scan_tools_directory
                available_tools = scan_tools_directory()
                
                # Create a lookup for tool metadata (case-insensitive)
                tool_metadata = {}
                for tool in available_tools:
                    tool_name = tool.get('name', '').lower()
                    tool_id = tool.get('tool_id', '').lower()
                    if tool_name:
                        tool_metadata[tool_name] = tool
                    if tool_id:
                        tool_metadata[tool_id] = tool
                
                # Auto-determine workflow category based on first tool
                workflow_category = 'Custom Workflow'
                if selected_tools and selected_tools[0].lower() in tool_metadata:
                    first_tool = tool_metadata[selected_tools[0].lower()]
                    workflow_category = first_tool.get('category', 'Custom Workflow')
                
                # Auto-determine input/output formats based on tools
                input_formats = set()
                output_formats = set()
                
                for tool_name in selected_tools:
                    tool_name_lower = tool_name.lower()
                    # Try to find tool by name or tool_id
                    tool = None
                    if tool_name_lower in tool_metadata:
                        tool = tool_metadata[tool_name_lower]
                    else:
                        # Try to find by partial match
                        for key, t in tool_metadata.items():
                            if tool_name_lower in key.lower() or key.lower() in tool_name_lower:
                                tool = t
                                break
                    
                    if tool:
                        # Add input formats
                        tool_input = tool.get('input_formats', 'Various')
                        if isinstance(tool_input, str) and tool_input != 'Various':
                            if ',' in tool_input:
                                input_formats.update([f.strip() for f in tool_input.split(',')])
                            else:
                                input_formats.add(tool_input)
                        
                        # Add output formats
                        tool_output = tool.get('output_formats', 'Various')
                        if isinstance(tool_output, str) and tool_output != 'Various':
                            if ',' in tool_output:
                                output_formats.update([f.strip() for f in tool_output.split(',')])
                            else:
                                output_formats.add(tool_output)
                
                # If no specific formats found, use the last tool's formats
                if not input_formats and selected_tools:
                    last_tool_name = selected_tools[-1].lower()
                    if last_tool_name in tool_metadata:
                        last_tool = tool_metadata[last_tool_name]
                        last_input = last_tool.get('input_formats', 'Various')
                        if last_input != 'Various':
                            if ',' in last_input:
                                input_formats.update([f.strip() for f in last_input.split(',')])
                            else:
                                input_formats.add(last_input)
                
                # Convert sets to lists and provide fallbacks
                input_formats = list(input_formats) if input_formats else ['Various']
                output_formats = list(output_formats) if output_formats else ['Various']
                
                # Auto-determine estimated time based on number and type of tools
                estimated_time = 'Variable'
                if len(selected_tools) <= 2:
                    estimated_time = '1-3 hours'
                elif len(selected_tools) <= 4:
                    estimated_time = '3-6 hours'
                else:
                    estimated_time = '6+ hours'
                
                # Auto-determine difficulty based on tools
                difficulty = 'Custom'
                assembly_tools = ['spades', 'metaspades', 'velvet', 'abyss']
                variant_tools = ['gatk', 'bcftools', 'freebayes']
                
                if any(tool.lower() in assembly_tools for tool in selected_tools):
                    difficulty = 'Intermediate'
                elif any(tool.lower() in variant_tools for tool in selected_tools):
                    difficulty = 'Advanced'
                elif len(selected_tools) <= 2:
                    difficulty = 'Beginner'
                else:
                    difficulty = 'Intermediate'
                
                # Create workflow definition with auto-filled metadata
                # Normalize tool names to lowercase for orchestrator compatibility
                normalized_tools = [tool.lower() for tool in selected_tools]
                
                workflow_data = {
                    'id': f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'name': workflow_name,
                    'description': workflow_description,
                    'tools': normalized_tools,
                    'created_at': datetime.now().isoformat(),
                    'created_by': request.user.username if request.user.is_authenticated else 'anonymous',
                    'type': 'custom_workflow',
                    'category': workflow_category,
                    'estimated_time': estimated_time,
                    'difficulty': difficulty,
                    'input_formats': input_formats,
                    'output_formats': output_formats
                }
                
                # Save workflow to file
                workflow_file = workflows_dir / f"{workflow_data['id']}.json"
                with open(workflow_file, 'w') as f:
                    json.dump(workflow_data, f, indent=2)
                
                messages.success(request, f'Workflow "{workflow_name}" created successfully!')
                return redirect('workflow_list')
                
            except Exception as e:
                messages.error(request, f'Error creating workflow: {str(e)}')
        else:
            messages.error(request, 'Please provide workflow name and select at least one tool.')
    
    context = {
        'available_tools': available_tools,
        'selected_template': selected_template,
        'pre_selected_tools': pre_selected_tools
    }
    return render(request, 'bioframe/create_workflow.html', context)

@login_required
def workflow_list(request):
    """List pre-created workflow templates and user-created workflows"""
    try:
        # Define pre-created workflow templates
        workflow_templates = [
            {
                'id': 'quality-control-pipeline',
                'name': 'Quality Control Pipeline',
                'description': 'Standard quality control workflow for sequencing data including FastQC, Trimmomatic, and MultiQC',
                'category': 'Quality Control',
                'tools': ['fastqc', 'trimmomatic', 'multiqc'],
                'estimated_time': '2-4 hours',
                'difficulty': 'Beginner',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['HTML Reports', 'Cleaned FASTQ'],
                'icon': 'fas fa-shield-alt',
                'color': 'bg-green-100 text-green-800',
                'type': 'template'
            },
            {
                'id': 'assembly-pipeline',
                'name': 'De Novo Assembly Pipeline',
                'description': 'Complete genome assembly workflow using SPAdes with quality assessment via QUAST',
                'category': 'Assembly',
                'tools': ['spades', 'quast', 'bandage'],
                'estimated_time': '4-8 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['FASTA', 'GFA', 'Assembly Stats'],
                'icon': 'fas fa-puzzle-piece',
                'color': 'bg-blue-100 text-blue-800',
                'type': 'template'
            },
            {
                'id': 'variant-calling-pipeline',
                'name': 'Variant Calling Pipeline',
                'description': 'SNP and indel detection workflow using BWA, SAMtools, and GATK',
                'category': 'Variant Analysis',
                'tools': ['bwa', 'samtools', 'gatk', 'bcftools'],
                'estimated_time': '6-12 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTA Reference'],
                'output_formats': ['VCF', 'BAM', 'Variant Reports'],
                'icon': 'fas fa-dna',
                'color': 'bg-purple-100 text-purple-800',
                'type': 'template'
            },
            {
                'id': 'metagenomics-pipeline',
                'name': 'Metagenomics Analysis Pipeline',
                'description': 'Microbial community analysis workflow including taxonomic classification and functional profiling',
                'category': 'Metagenomics',
                'tools': ['fastqc', 'trimmomatic', 'metaspades', 'quast', 'metaphlan', 'humann'],
                'estimated_time': '8-16 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['Assembly', 'Taxonomy', 'Functional Profiles'],
                'icon': 'fas fa-bacteria',
                'color': 'bg-teal-100 text-teal-800',
                'type': 'template'
            },
            {
                'id': 'rna-seq-pipeline',
                'name': 'RNA-Seq Analysis Pipeline',
                'description': 'Transcriptome analysis workflow including alignment, quantification, and differential expression',
                'category': 'Transcriptomics',
                'tools': ['fastqc', 'trimmomatic', 'star', 'htseq-count', 'deseq2'],
                'estimated_time': '6-10 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTA Reference', 'GTF Annotation'],
                'output_formats': ['BAM', 'Count Matrix', 'DEG Results'],
                'icon': 'fas fa-chart-line',
                'color': 'bg-orange-100 text-orange-800',
                'type': 'template'
            },
            {
                'id': 'phylogenetics-pipeline',
                'name': 'Phylogenetics Pipeline',
                'description': 'Evolutionary analysis workflow including multiple sequence alignment and tree construction',
                'category': 'Phylogenetics',
                'tools': ['muscle', 'clustalw', 'raxml', 'figtree'],
                'estimated_time': '3-6 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTA', 'PHYLIP'],
                'output_formats': ['Alignment', 'Tree Files', 'Phylogenetic Analysis'],
                'icon': 'fas fa-tree',
                'color': 'bg-indigo-100 text-indigo-800',
                'type': 'template'
            }
        ]
        
        # Get user-created workflows from stored workflow files
        user_workflows = []
        try:
            
            # Look for stored workflow definitions
            workflows_dir = Path("data/workflows")
            if workflows_dir.exists():
                for workflow_file in workflows_dir.glob("*.json"):
                    try:
                        with open(workflow_file, 'r') as f:
                            workflow_data = json.load(f)
                            
                        # Only include actual custom workflows
                        if workflow_data.get('type') == 'custom_workflow':
                            user_workflows.append({
                                'id': workflow_data['id'],
                                'name': workflow_data['name'],
                                'description': workflow_data['description'],
                                'category': workflow_data['category'],
                                'tools': workflow_data['tools'],
                                'estimated_time': workflow_data['estimated_time'],
                                'difficulty': workflow_data['difficulty'],
                                'input_formats': workflow_data['input_formats'],
                                'output_formats': workflow_data['output_formats'],
                                'icon': 'fas fa-cogs',
                                'color': 'bg-green-100 text-green-800',
                                'type': 'custom',
                                'created_at': workflow_data['created_at'],
                                'created_by': workflow_data.get('created_by', 'Unknown')
                            })
                    except Exception as e:
                        print(f"Error reading workflow file {workflow_file}: {e}")
                        continue
        except Exception as e:
            print(f"Warning: Could not load user workflows: {e}")
            user_workflows = []
        
        # Combine templates and user workflows
        all_workflows = workflow_templates + user_workflows
        
        context = {
            'workflows': all_workflows,
            'templates': workflow_templates,
            'user_workflows': user_workflows
        }
        return render(request, 'bioframe/workflow_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading workflow templates: {str(e)}')
        print(f"Workflow template list error: {e}")
        import traceback
        traceback.print_exc()
        return render(request, 'bioframe/workflow_list.html', {'workflows': []})

# @login_required  # Temporarily disabled for testing
def workflow_detail(request, workflow_id):
    """Show workflow details and progress"""
    try:
        # Read workflow status from files (orchestrator is now a separate service)
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        if not run_dir.exists():
            messages.error(request, f'Workflow {workflow_id} not found')
            return redirect('workflow_list')
        
        # Read workflow status from workflow.yaml file
        workflow_file = run_dir / "workflow.yaml"
        if workflow_file.exists():
            with open(workflow_file, 'r') as f:
                workflow_status = yaml.safe_load(f)
        else:
            workflow_status = None
        
        if workflow_status and 'error' not in workflow_status:
            return render_file_based_workflow_detail(request, workflow_status, workflow_id)
        else:
            # Check if run directory exists but no workflow file
            run_dir = Path(f"/app/data/runs/{workflow_id}")
            if run_dir.exists():
                return render_create_workflow_for_run(request, workflow_id, run_dir)
            else:
                messages.error(request, f'Workflow {workflow_id} not found')
                return redirect('workflow_list')
                
    except Exception as e:
        messages.error(request, f'Error loading workflow details: {str(e)}')
        return redirect('workflow_list')

def workflow_status_api(request, workflow_id):
    """API endpoint to get real-time workflow status and logs"""
    try:
        # Simple status check without orchestrator dependency
        from pathlib import Path
        import yaml
        import json
        
        # Get workflow info from YAML file
        workflow_file = Path(f'data/runs/{workflow_id}/workflow.yaml')
        if not workflow_file.exists():
            return JsonResponse({'error': 'Workflow not found'}, status=404)
        
        with open(workflow_file, 'r') as f:
            workflow_data = yaml.safe_load(f)
        
        # Basic status response
        status_data = {
            'workflow_id': workflow_id,
            'status': workflow_data.get('status', 'unknown'),
            'tools': workflow_data.get('tools', []),
            'created_at': workflow_data.get('created_at'),
            'started_at': workflow_data.get('started_at'),
            'updated_at': workflow_data.get('updated_at', workflow_data.get('created_at'))
        }
        
        return JsonResponse(status_data)
        
    except Exception as e:
        # Return basic error response if YAML parsing fails
        return JsonResponse({
            'error': f'Unable to load workflow status: {str(e)}',
            'workflow_id': workflow_id,
            'status': 'unknown'
        }, status=500)

def render_file_based_workflow_detail(request, workflow_status, workflow_id):
    """Render workflow detail for file-based workflows"""
    # Define run directory at the beginning
    run_dir = Path(f"/app/data/runs/{workflow_id}")
    
    # Get detailed tool information including logs and errors
    detailed_tools = []
    tools = workflow_status.get('tools', [])
    
    # Handle both old format (list of dicts) and new format (list of strings)
    if tools and isinstance(tools[0], dict):
        # Old format: tools is list of dicts with tool details
        for tool in tools:
            tool_info = {
                'tool_name': tool.get('tool_name', 'unknown'),
                'order': tool.get('order', 0),
                'status': tool.get('status', 'unknown'),
                'started_at': tool.get('started_at'),
                'completed_at': tool.get('completed_at'),
                'execution_time': tool.get('execution_time'),
                'config': tool.get('config', {}),
                'error_message': tool.get('error_message'),
                'input_files': tool.get('input_files', []),
                'output_files': tool.get('output_files', []),
                'logs': tool.get('logs', [])
            }
            detailed_tools.append(tool_info)
    else:
        # New format: tools is list of strings - determine status from step directories
        for i, tool_name in enumerate(tools, 1):
            step_dir = run_dir / f"step_{i}_{tool_name}"
            step_logs_dir = run_dir / "logs"
            
            # Determine tool status based on directory and log analysis
            tool_status = 'pending'
            error_message = None
            execution_time = None
            
            if step_dir.exists():
                # Check if there are output files
                output_files = list(step_dir.glob("*"))
                if output_files:
                    tool_status = 'completed'
                else:
                    # Check logs for status
                    if step_logs_dir.exists():
                        log_files = list(step_logs_dir.glob(f"*{tool_name}*"))
                        if log_files:
                            # Try to determine status from log content
                            for log_file in log_files:
                                try:
                                    with open(log_file, 'r') as f:
                                        log_content = f.read()
                                        if 'ERROR' in log_content or 'FAILED' in log_content:
                                            tool_status = 'failed'
                                            error_message = 'Tool execution failed - check logs for details'
                                            break
                                        elif 'COMPLETED' in log_content or 'SUCCESS' in log_content:
                                            tool_status = 'completed'
                                            break
                                except:
                                    pass
            
            tool_info = {
                'tool_name': tool_name,
                'order': i,
                'status': tool_status,
                'started_at': None,
                'completed_at': None,
                'execution_time': execution_time,
                'config': {},
                'error_message': error_message,
                'input_files': [],
                'output_files': [],
                'logs': []
            }
            detailed_tools.append(tool_info)
    
    # Get execution logs from the workflow run directory
    execution_logs = []
    try:
        log_dir = run_dir / "logs"
        if log_dir.exists():
            # Only show the main workflow execution log file
            log_file = log_dir / "workflow_execution.log"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        execution_logs.append({
                            'file': log_file.name,
                            'content': log_content,
                            'timestamp': datetime.fromtimestamp(log_file.stat().st_mtime)
                        })
                except Exception as e:
                    execution_logs.append({
                        'file': log_file.name,
                        'content': f"Error reading log: {e}",
                        'timestamp': datetime.now()
                    })
    except Exception as e:
        execution_logs.append({
            'file': 'error',
            'content': f"Error accessing logs: {e}",
            'timestamp': datetime.now()
        })
    
    # Get input files from the inputs directory
    input_files = []
    input_dir = run_dir / "inputs"
    if input_dir.exists():
        for file_path in input_dir.glob("*"):
            if file_path.is_file():
                file_info = {
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'type': file_path.suffix.lower(),
                    'relative_path': str(file_path.relative_to(run_dir)),
                    'modified_at': datetime.fromtimestamp(file_path.stat().st_mtime)
                }
                input_files.append(file_info)
    
    # Sort input files by name for consistent display
    input_files.sort(key=lambda x: x['name'])
    
    # Get output files from each step
    output_files_by_step = {}
    
    for i, tool in enumerate(detailed_tools, 1):
        step_dir = run_dir / f"step_{i}_{tool['tool_name']}"
        if step_dir.exists():
            step_files = []
            for file_path in step_dir.glob("*"):
                if file_path.is_file():
                    file_info = {
                        'name': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'type': file_path.suffix.lower(),
                        'relative_path': str(file_path.relative_to(run_dir)),
                        'modified_at': datetime.fromtimestamp(file_path.stat().st_mtime)
                    }
                    step_files.append(file_info)
            # Sort step files by name for consistent display
            step_files.sort(key=lambda x: x['name'])
            output_files_by_step[tool['tool_name']] = step_files
    
    # Calculate accurate workflow status and progress
    completed_tools = sum(1 for tool in detailed_tools if tool['status'] == 'completed')
    failed_tools = sum(1 for tool in detailed_tools if tool['status'] == 'failed')
    total_tools = len(detailed_tools)
    
    if total_tools > 0:
        progress = (completed_tools / total_tools) * 100
    else:
        progress = 0
    
    # Determine overall workflow status
    if failed_tools > 0:
        overall_status = 'failed'
    elif completed_tools == total_tools:
        overall_status = 'completed'
    elif completed_tools > 0:
        overall_status = 'running'
    else:
        overall_status = 'pending'
    
    # Convert timestamp to datetime if needed
    created_at = workflow_status.get('created_at')
    if isinstance(created_at, (int, float)):
        try:
            created_at = datetime.fromtimestamp(created_at)
        except (ValueError, OSError):
            created_at = datetime.now()
    elif isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            created_at = datetime.now()
    elif not isinstance(created_at, datetime):
        created_at = datetime.now()
    
    updated_at = workflow_status.get('last_updated')
    if isinstance(updated_at, (int, float)):
        try:
            updated_at = datetime.fromtimestamp(updated_at)
        except (ValueError, OSError):
            updated_at = created_at
    elif isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        except ValueError:
            updated_at = created_at
    elif not isinstance(updated_at, datetime):
        updated_at = created_at
    
    # Additional safety check - ensure we have valid datetime objects
    if not isinstance(created_at, datetime):
        created_at = datetime.now()
    if not isinstance(updated_at, datetime):
        updated_at = created_at
    
    # Prepare context for the workflow detail template
    context = {
        'workflow': {
            'id': workflow_id,
            'name': workflow_status.get('workflow_name') or workflow_status.get('name', 'Unnamed Workflow'),
            'description': workflow_status.get('description', 'No description'),
            'status': overall_status,
            'progress': progress,
            'created_at': created_at,
            'updated_at': updated_at,
            'tools': detailed_tools,
            'run_directory': f"/app/data/runs/{workflow_id}"
        },
        'execution_logs': execution_logs,
        'input_files': input_files,
        'output_files_by_step': output_files_by_step
    }
    return render(request, 'bioframe/workflow_detail.html', context)

def render_create_workflow_for_run(request, run_id, run_dir):
    """Render the create workflow for existing run page"""
    # List contents of the run directory
    run_contents = []
    try:
        for item in run_dir.iterdir():
            if item.is_file():
                run_contents.append(f"📄 {item.name}")
            elif item.is_dir():
                run_contents.append(f"📁 {item.name}/")
    except Exception as e:
        run_contents.append(f"Error reading directory: {e}")
    
    context = {
        'run_id': run_id,
        'run_directory': str(run_dir),
        'run_contents': run_contents
    }
    return render(request, 'bioframe/create_workflow_for_run.html', context)

@login_required
def create_workflow_for_run(request, run_id):
    """Create a workflow.yaml file for an existing run directory"""
    if request.method == 'POST':
        workflow_name = request.POST.get('workflow_name')
        workflow_description = request.POST.get('workflow_description')
        selected_tools = request.POST.getlist('selected_tools')
        
        if workflow_name and selected_tools:
            try:
                import sys
                sys.path.append('/app/workflow-orchestrator')
                from orchestrator import WorkflowOrchestrator
                orchestrator = WorkflowOrchestrator(data_dir="data", init_docker=False)
                
                # Create workflow file for existing run
                success = orchestrator.create_workflow_file_if_missing(run_id, workflow_name, workflow_description, selected_tools)
                
                if success:
                    messages.success(request, f'Workflow created for run {run_id}!')
                    return redirect('workflow_detail', workflow_id=run_id)
                else:
                    messages.error(request, 'Failed to create workflow file')
                    
            except Exception as e:
                messages.error(request, f'Error creating workflow: {str(e)}')
        else:
            messages.error(request, 'Please provide workflow name and select at least one tool.')
    
    return redirect('create_workflow_for_run', run_id=run_id)

@login_required
def initialize_workflow_run(request, template_id):
    """Initialize a workflow run with enhanced file upload tracking"""
    from pathlib import Path
    import json
    try:
        # First, try to find a pre-created workflow template
        workflow_templates = [
            {
                'id': 'quality-control-pipeline',
                'name': 'Quality Control Pipeline',
                'description': 'Standard quality control workflow for sequencing data including FastQC, Trimmomatic, and MultiQC',
                'category': 'Quality Control',
                'tools': ['fastqc', 'trimmomatic', 'multiqc'],
                'estimated_time': '2-4 hours',
                'difficulty': 'Beginner',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['HTML Reports', 'Cleaned FASTQ'],
                'icon': 'fas fa-shield-alt',
                'color': 'bg-green-100 text-green-800'
            },
            {
                'id': 'assembly-pipeline',
                'name': 'De Novo Assembly Pipeline',
                'description': 'Complete genome assembly workflow using SPAdes with quality assessment via QUAST',
                'category': 'Assembly',
                'tools': ['spades', 'quast', 'bandage'],
                'estimated_time': '4-8 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['FASTA', 'GFA', 'Assembly Stats'],
                'icon': 'fas fa-puzzle-piece',
                'color': 'bg-blue-100 text-blue-800'
            },
            {
                'id': 'variant-calling-pipeline',
                'name': 'Variant Calling Pipeline',
                'description': 'SNP and indel detection workflow using BWA, SAMtools, and GATK',
                'category': 'Variant Analysis',
                'tools': ['bwa', 'samtools', 'gatk', 'bcftools'],
                'estimated_time': '6-12 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTA Reference'],
                'output_formats': ['VCF', 'BAM', 'Variant Reports'],
                'icon': 'fas fa-dna',
                'color': 'bg-purple-100 text-purple-800'
            },
            {
                'id': 'metagenomics-pipeline',
                'name': 'Metagenomics Analysis Pipeline',
                'description': 'Microbial community analysis workflow including taxonomic classification and functional profiling',
                'category': 'Metagenomics',
                'tools': ['fastqc', 'trimmomatic', 'metaspades', 'quast', 'metaphlan', 'humann'],
                'estimated_time': '8-16 hours',
                'difficulty': 'Advanced',
                'input_formats': ['FASTQ', 'FASTQ.GZ'],
                'output_formats': ['Assembly', 'Taxonomy', 'Functional Profiles'],
                'icon': 'fas fa-bacteria',
                'color': 'bg-teal-100 text-teal-800'
            },
            {
                'id': 'rna-seq-pipeline',
                'name': 'RNA-Seq Analysis Pipeline',
                'description': 'Transcriptome analysis workflow including alignment, quantification, and differential expression',
                'category': 'Transcriptomics',
                'tools': ['fastqc', 'trimmomatic', 'star', 'htseq-count', 'deseq2'],
                'estimated_time': '6-10 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTQ', 'FASTA Reference', 'GTF Annotation'],
                'output_formats': ['BAM', 'Count Matrix', 'DEG Results'],
                'icon': 'fas fa-chart-line',
                'color': 'bg-orange-100 text-orange-800'
            },
            {
                'id': 'phylogenetics-pipeline',
                'name': 'Phylogenetics Pipeline',
                'description': 'Evolutionary analysis workflow including multiple sequence alignment and tree construction',
                'category': 'Phylogenetics',
                'tools': ['muscle', 'clustalw', 'raxml', 'figtree'],
                'estimated_time': '3-6 hours',
                'difficulty': 'Intermediate',
                'input_formats': ['FASTA', 'PHYLIP'],
                'output_formats': ['Alignment', 'Tree Files', 'Phylogenetic Analysis'],
                'icon': 'fas fa-tree',
                'color': 'bg-indigo-100 text-indigo-800'
            }
        ]
        
        # Find the selected template from pre-created templates
        selected_template = None
        for template in workflow_templates:
            if template['id'] == template_id:
                selected_template = template
                break
        
        # Check if this is a single-tool workflow (passed via sessionStorage)
        if not selected_template and template_id.startswith('single-'):
            # Extract tool name from template_id (format: single-{toolname}-workflow)
            tool_name = template_id.replace('single-', '').replace('-workflow', '')
            
            # Get tool metadata to create proper template
            from tools.views import scan_tools_directory
            available_tools = scan_tools_directory()
            
            tool_metadata = None
            for tool in available_tools:
                if tool.get('name', '').lower() == tool_name.lower() or tool.get('tool_id', '').lower() == tool_name.lower():
                    tool_metadata = tool
                    break
            
            if tool_metadata:
                # Ensure output_formats is a list for template rendering
                output_formats = tool_metadata.get('output_formats', 'Various')
                if isinstance(output_formats, str):
                    # Split by comma and clean up
                    output_formats = [fmt.strip() for fmt in output_formats.split(',') if fmt.strip()]
                    if not output_formats:
                        output_formats = ['Various']
                
                # Ensure input_formats is a list for template rendering
                input_formats = tool_metadata.get('input_formats', 'Various')
                if isinstance(input_formats, str):
                    # Split by comma and clean up
                    input_formats = [fmt.strip() for fmt in input_formats.split(',') if fmt.strip()]
                    if not input_formats:
                        input_formats = ['Various']
                
                selected_template = {
                    'id': template_id,
                    'name': f"{tool_metadata.get('name', tool_name.title())} Single Tool Workflow",
                    'description': f"Execute {tool_metadata.get('name', tool_name)} as a standalone workflow",
                    'category': tool_metadata.get('category', 'Single Tool'),
                    'tools': [tool_name],
                    'estimated_time': '30 minutes - 2 hours',
                    'difficulty': 'Beginner',
                    'input_formats': input_formats,
                    'output_formats': output_formats,
                    'icon': 'fas fa-cog',
                    'color': 'bg-gray-100 text-gray-800'
                }
        
        # If not found in pre-created templates, try to find a custom workflow
        if not selected_template:
            try:
                # Check stored custom workflows
                
                workflows_dir = Path("data/workflows")
                if workflows_dir.exists():
                    for workflow_file in workflows_dir.glob("*.json"):
                        try:
                            with open(workflow_file, 'r') as f:
                                workflow_data = json.load(f)
                                
                            if workflow_data.get('id') == template_id and workflow_data.get('type') == 'custom_workflow':
                                # Found the custom workflow
                                selected_template = {
                                    'id': workflow_data['id'],
                                    'name': workflow_data['name'],
                                    'description': workflow_data['description'],
                                    'category': workflow_data['category'],
                                    'tools': workflow_data['tools'],
                                    'estimated_time': workflow_data['estimated_time'],
                                    'difficulty': workflow_data['difficulty'],
                                    'input_formats': workflow_data['input_formats'],
                                    'output_formats': workflow_data['output_formats'],
                                    'icon': 'fas fa-cogs',
                                    'color': 'bg-gray-100 text-gray-800',
                                    'type': 'custom'
                                }
                                break
                        except Exception as e:
                            print(f"Error reading workflow file {workflow_file}: {e}")
                            continue
                
                # If still not found, try the orchestrator (for backward compatibility)
                if not selected_template:
                    try:
                        import sys
                        sys.path.append('/app/workflow-orchestrator')
                        from orchestrator import WorkflowOrchestrator
                        orchestrator = WorkflowOrchestrator(data_dir="data", init_docker=False)
                        workflow_run = orchestrator.get_workflow_run_by_id(template_id)
                        
                        if workflow_run and workflow_run.name and workflow_run.name != f"Run {template_id}":
                            # Convert custom workflow to template format
                            tools = [tool.tool_name for tool in workflow_run.tools] if workflow_run.tools else []
                            
                            # Get tool metadata for input/output formats
                            from tools.views import scan_tools_directory
                            available_tools = scan_tools_directory()
                            tool_metadata_lookup = {}
                            for tool in available_tools:
                                tool_name = tool.get('name', '').lower()
                                if tool_name:
                                    input_formats = tool.get('input_formats', 'Various')
                                    output_formats = tool.get('output_formats', 'Various')
                                    
                                    if isinstance(input_formats, str):
                                        input_formats = [f.strip() for f in input_formats.split(',') if f.strip()]
                                    if isinstance(output_formats, str):
                                        output_formats = [f.strip() for f in output_formats.split(',') if f.strip()]
                                    
                                    if not isinstance(input_formats, list):
                                        input_formats = ['Various']
                                    if not isinstance(output_formats, list):
                                        output_formats = ['Various']
                                    
                                    tool_metadata_lookup[tool_name] = {
                                        'input': input_formats,
                                        'output': output_formats
                                    }
                            
                            # Determine input/output formats based on first and last tool
                            input_formats = ['Various']
                            output_formats = ['Various']
                            
                            if tools:
                                first_tool = tools[0].lower()
                                last_tool = tools[-1].lower()
                                
                                first_metadata = tool_metadata_lookup.get(first_tool, {'input': ['Various'], 'output': ['Various']})
                                last_metadata = tool_metadata_lookup.get(last_tool, {'input': ['Various'], 'output': ['Various']})
                                
                                input_formats = first_metadata['input']
                                output_formats = last_metadata['output']
                            
                            selected_template = {
                                'id': workflow_run.id,
                                'name': workflow_run.name,
                                'description': workflow_run.description or 'Custom workflow created by user',
                                'category': 'Custom Workflow',
                                'tools': tools,
                                'estimated_time': 'Variable',
                                'difficulty': 'Custom',
                                'input_formats': input_formats,
                                'output_formats': output_formats,
                                'icon': 'fas fa-cogs',
                                'color': 'bg-gray-100 text-gray-800',
                                'type': 'custom'
                            }
                
                    except Exception as e:
                        print(f"Error with orchestrator lookup: {e}")
                
                # If still not found, show error
                if not selected_template:
                    messages.error(request, f'Template or workflow "{template_id}" not found')
                    return redirect('workflow_list')
                    
            except Exception as e:
                messages.error(request, f'Error loading custom workflow: {str(e)}')
                return redirect('workflow_list')
        
        if request.method == 'POST':
            # Handle workflow run initialization
            run_name = request.POST.get('run_name')
            run_description = request.POST.get('run_description')
            
            if not run_name:
                messages.error(request, 'Please provide a run name')
            else:
                try:
                    # Handle file uploads
                    primary_files = request.FILES.getlist('primary_files')
                    reference_genome = request.FILES.get('reference_genome')
                    annotation_file = request.FILES.get('annotation_file')
                    
                    if not primary_files:
                        messages.error(request, 'Please upload at least one primary input file')
                    else:
                        # Create a new workflow run ID based on the template and timestamp
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        workflow_run_id = f"{template_id}_{timestamp}"
                        
                        # Create inputs directory
                        run_dir = Path(f"/app/data/runs/{workflow_run_id}")
                        input_dir = run_dir / "inputs"
                        input_dir.mkdir(exist_ok=True)
                        
                        # Save primary files
                        saved_primary_files = []
                        for uploaded_file in primary_files:
                            file_path = input_dir / uploaded_file.name
                            with open(file_path, 'wb') as f:
                                for chunk in uploaded_file.chunks():
                                    f.write(chunk)
                            saved_primary_files.append(str(file_path))
                        
                        # Save reference files if provided
                        reference_files = {}
                        if reference_genome:
                            ref_path = input_dir / reference_genome.name
                            with open(ref_path, 'wb') as f:
                                for chunk in reference_genome.chunks():
                                    f.write(chunk)
                            reference_files['reference_genome'] = str(ref_path)
                        
                        if annotation_file:
                            ann_path = input_dir / annotation_file.name
                            with open(ann_path, 'wb') as f:
                                for chunk in annotation_file.chunks():
                                    f.write(chunk)
                            reference_files['annotation_file'] = str(ann_path)
                        
                        # Start the pipeline workflow asynchronously (don't wait for completion)
                        try:
                            # Create a workflow summary file to track status
                            workflow_summary = {
                                "workflow_id": workflow_run_id,
                                "workflow_name": run_name,
                                "tools": selected_template['tools'],
                                "total_steps": len(selected_template['tools']),
                                "start_time": datetime.now().isoformat(),
                                "status": "running",
                                "steps": [],
                                "execution_logs": []
                            }
                            
                            summary_file = run_dir / "workflow_summary.json"
                            with open(summary_file, 'w') as f:
                                json.dump(workflow_summary, f, indent=2, default=str)
                            
                            # Create workflow execution trigger file for orchestrator service to pick up
                            trigger_file = run_dir / "execute_workflow.trigger"
                            with open(trigger_file, 'w') as f:
                                f.write(f"Workflow ready for execution: {workflow_run_id}\n")
                                f.write(f"Created at: {datetime.now().isoformat()}\n")
                                f.write(f"Input files: {', '.join(saved_primary_files)}\n")
                                f.write(f"Tools: {', '.join(selected_template['tools'])}\n")
                            
                            # Update workflow status to indicate it's ready for execution
                            workflow_summary["status"] = "ready_for_execution"
                            workflow_summary["created_at"] = datetime.now().isoformat()
                            
                            # Save updated summary
                            with open(summary_file, 'w') as f:
                                json.dump(workflow_summary, f, indent=2, default=str)
                            
                            messages.success(request, f'Workflow pipeline "{run_name}" started successfully! Redirecting to workflow details page where you can monitor progress.')
                            # Immediately redirect to workflow detail page - don't wait for completion
                            return redirect('workflow_detail', workflow_id=workflow_run_id)
                            
                        except Exception as e:
                            messages.error(request, f'Error starting workflow pipeline: {str(e)}')
                            # Still redirect to workflow detail page to show any error logs
                            return redirect('workflow_detail', workflow_id=workflow_run_id)
                        
                except Exception as e:
                    messages.error(request, f'Error initializing workflow run: {str(e)}')
                    # If we have a workflow_run_id, redirect to its detail page to show errors
                    if 'workflow_run_id' in locals():
                        return redirect('workflow_detail', workflow_id=workflow_run_id)
        
        context = {
            'template': selected_template,
            'available_tools': selected_template['tools'] if selected_template else []
        }
        return render(request, 'bioframe/initialize_workflow_run.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading template: {str(e)}')
        return redirect('workflow_list')


@login_required
def start_workflow_with_upload(request, template_id):
    """Start workflow with file upload - simplified file-based approach"""
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            run_name = data.get('run_name', '')
            run_description = data.get('run_description', '')
            files = data.get('files', [])
            
            if not run_name:
                return JsonResponse({'success': False, 'error': 'Run name is required'})
            
            if not files:
                return JsonResponse({'success': False, 'error': 'No files provided'})
            
            # Create a unique run ID
            import uuid
            run_id = str(uuid.uuid4())
            
            # Create run directory
            run_dir = Path(f"/app/data/runs/{run_id}")
            input_dir = run_dir / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            
            # Store file information for tracking
            file_info = {
                'run_id': run_id,
                'run_name': run_name,
                'run_description': run_description,
                'template_id': template_id,
                'files': files,
                'total_files': len(files),
                'total_size': sum(file.get('size', 0) for file in files),
                'uploaded_files': 0,
                'uploaded_size': 0
            }
            
            # Save file_info.json to run directory for template loading
            file_info_path = run_dir / "file_info.json"
            with open(file_info_path, 'w') as f:
                json.dump(file_info, f, indent=2)
            
            return JsonResponse({
                'success': True,
                'run_id': run_id,
                'message': 'Upload session created successfully'
            })
        
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def upload_workflow_file(request, run_id):
    """Upload a single file for workflow - simplified file-based approach"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'})
        
        uploaded_file = request.FILES['file']
        file_size = uploaded_file.size
        
        # Create file path in run input directory
        run_dir = Path(f"/app/data/runs/{run_id}")
        input_dir = run_dir / "inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = input_dir / uploaded_file.name
        
        # Save file with progress tracking
        total_size = file_size
        uploaded_size = 0
        checksum = hashlib.sha256()
        
        with open(file_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
                uploaded_size += len(chunk)
                checksum.update(chunk)
        
        # Calculate final progress
        progress = int((uploaded_size / total_size) * 100)
        
        return JsonResponse({
            'success': True,
            'file_name': uploaded_file.name,
            'file_size': file_size,
            'progress': progress,
            'checksum': checksum.hexdigest()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_workflow_upload_progress(request, run_id):
    """Get upload progress for workflow run - simplified file-based approach"""
    try:
        # Check run directory
        run_dir = Path(f"/app/data/runs/{run_id}")
        if not run_dir.exists():
            return JsonResponse({'success': False, 'error': 'Run directory not found'})
        
        input_dir = run_dir / "inputs"
        if not input_dir.exists():
            return JsonResponse({'success': False, 'error': 'Input directory not found'})
        
        # Get uploaded files
        uploaded_files = []
        total_size = 0
        uploaded_size = 0
        
        for file_path in input_dir.iterdir():
            if file_path.is_file():
                file_size = file_path.stat().st_size
                uploaded_files.append({
                    'name': file_path.name,
                    'size': file_size,
                    'progress': 100,
                    'status': 'completed'
                })
                total_size += file_size
                uploaded_size += file_size
        
        progress_percentage = int((uploaded_size / total_size) * 100) if total_size > 0 else 0
        
        return JsonResponse({
            'success': True,
            'run_id': run_id,
            'total_files': len(uploaded_files),
            'uploaded_files': len(uploaded_files),
            'total_size': total_size,
            'uploaded_size': uploaded_size,
            'progress_percentage': progress_percentage,
            'files': uploaded_files
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def validate_and_start_workflow(request, run_id):
    """Validate uploaded files and delegate workflow execution to orchestrator service"""
    try:
        # Check run directory
        run_dir = Path(f"/app/data/runs/{run_id}")
        if not run_dir.exists():
            return JsonResponse({'success': False, 'error': 'Run directory not found'})
        
        input_dir = run_dir / "inputs"
        if not input_dir.exists():
            return JsonResponse({'success': False, 'error': 'Input directory not found'})
        
        # Get uploaded files
        uploaded_files = []
        for file_path in input_dir.iterdir():
            if file_path.is_file():
                uploaded_files.append(str(file_path))
        
        if not uploaded_files:
            return JsonResponse({'success': False, 'error': 'No files found in input directory'})
        
        # Try to get template information from file_info.json
        template_tools = ['fastqc', 'trimmomatic', 'multiqc']  # Default fallback
        template_name = f'workflow_{run_id}'
        
        file_info_path = run_dir / "file_info.json"
        if file_info_path.exists():
            try:
                with open(file_info_path, 'r') as f:
                    file_info = json.load(f)
                    template_id = file_info.get('template_id')
                    
                    # Handle single-tool workflows
                    if template_id and template_id.startswith('single-'):
                        # Extract tool name from template_id (format: single-{toolname}-workflow)
                        tool_name = template_id.replace('single-', '').replace('-workflow', '')
                        template_tools = [tool_name]
                        template_name = f"{tool_name.title()} Single Tool Workflow"
                        print(f"✅ Single-tool workflow detected: {tool_name}")
                    elif template_id:
                        # Load template from workflow_templates directory for multi-tool workflows
                        template_path = Path(f"/app/data/workflows/{template_id}.json")
                        if template_path.exists():
                            with open(template_path, 'r') as f:
                                template_data = json.load(f)
                                template_tools = template_data.get('tools', template_tools)
                                template_name = template_data.get('name', template_name)
                                print(f"✅ Loaded template {template_id}: {template_tools}")
                        else:
                            print(f"⚠️ Template file not found: {template_path}")
                    else:
                        print(f"⚠️ Template ID not found in file_info: {template_id}")
            except Exception as e:
                print(f"⚠️ Error loading template info: {e}")
        
        # Create workflow configuration with template tools
        # Normalize tool names to lowercase for orchestrator compatibility
        normalized_tools = [tool.lower() for tool in template_tools]
        
        workflow_config = {
            'workflow_name': template_name,
            'description': f'Workflow run {run_id}',
            'tools': normalized_tools,
            'created_at': datetime.now().isoformat()
        }
        
        # Save workflow configuration
        workflow_file = run_dir / "workflow.yaml"
        with open(workflow_file, 'w') as f:
            yaml.dump(workflow_config, f, default_flow_style=False)
        
        # Create workflow execution trigger file for orchestrator service to pick up
        trigger_file = run_dir / "execute_workflow.trigger"
        with open(trigger_file, 'w') as f:
            f.write(f"Workflow ready for execution: {run_id}\n")
            f.write(f"Created at: {datetime.now().isoformat()}\n")
        
        # Update workflow status to indicate it's ready for execution
        workflow_config['status'] = 'ready_for_execution'
        workflow_config['created_at'] = datetime.now().isoformat()
        
        with open(workflow_file, 'w') as f:
            yaml.dump(workflow_config, f, default_flow_style=False)
        
        return JsonResponse({
            'success': True,
            'workflow_id': run_id,
            'status': 'ready_for_execution',
            'redirect_url': f'/workflow/{run_id}/'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_running_containers(request, workflow_id):
    """Get running containers for a workflow"""
    try:
        import subprocess
        import json
        
        print(f"🔍 Getting running containers for workflow: {workflow_id}")
        
        # Get all running containers with bioframe prefix
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=bioframe', '--format', 'json'],
            capture_output=True, text=True
        )
        
        print(f"🐳 Docker command result: {result.returncode}")
        print(f"🐳 Docker output: {result.stdout[:200]}...")
        
        if result.returncode != 0:
            return JsonResponse({'success': False, 'error': 'Failed to get container list'})
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    container_info = json.loads(line)
                    container_name = container_info.get('Names', '')
                    print(f"🔍 Checking container: {container_name}")
                    
                    # Check if this container belongs to the workflow
                    if workflow_id in container_name:
                        print(f"✅ Found matching container: {container_name}")
                        containers.append({
                            'id': container_info['ID'],
                            'name': container_info['Names'],
                            'status': container_info['Status'],
                            'image': container_info['Image'],
                            'created': container_info['CreatedAt'],
                            'tool_name': extract_tool_name_from_container(container_info['Names'])
                        })
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    continue
        
        print(f"📊 Found {len(containers)} containers")
        
        return JsonResponse({
            'success': True,
            'containers': containers,
            'count': len(containers)
        })
        
    except Exception as e:
        print(f"❌ Exception in get_running_containers: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


def get_container_logs(request, workflow_id, container_id):
    """Get logs for a specific container"""
    try:
        import subprocess
        
        print(f"🔍 Getting real logs for container: {container_id}")
        
        # Use the simple docker logs command that works
        result = subprocess.run(
            ['docker', 'logs', '--tail', '20', container_id],
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        print(f"🐳 Docker logs result: {result.returncode}")
        print(f"🐳 Docker logs stdout length: {len(result.stdout)}")
        print(f"🐳 Docker logs stderr: {result.stderr}")
        print(f"🐳 Docker logs output: {result.stdout[:200]}...")
        
        if result.returncode != 0:
            return JsonResponse({'success': False, 'error': f'Failed to get container logs: {result.stderr}'})
        
        # Docker logs often outputs to stderr, so check both
        logs = result.stdout if result.stdout else result.stderr
        
        return JsonResponse({
            'success': True,
            'logs': logs,
            'container_id': container_id
        })
        
    except Exception as e:
        print(f"❌ Exception in get_container_logs: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


def extract_tool_name_from_container(container_name):
    """Extract tool name from container name"""
    try:
        # Container name format: bioframe-{workflow_id}-step{step_number}-{tool_name}-{timestamp}
        parts = container_name.split('-')
        if len(parts) >= 4:
            # Find the tool name (usually after 'step' and before the timestamp)
            for i, part in enumerate(parts):
                if part.startswith('step') and i + 1 < len(parts):
                    return parts[i + 1]
        return 'unknown'
    except:
        return 'unknown'





@login_required
def open_workflow_file(request, workflow_id):
    """
    Simple file opener for workflow files using web download - no batch scripts needed!
    Returns a download URL that opens the file directly in the browser
    """
    try:
        # Get file path from request
        file_path = request.GET.get('file')
        if not file_path:
            return JsonResponse({
                'success': False,
                'error': 'No file specified'
            }, status=400)
        
        # Security check: ensure the file is within the workflow directory
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        container_file_path = run_dir / file_path
        
        # Security validation
        try:
            if not container_file_path.resolve().is_relative_to(run_dir.resolve()):
                return JsonResponse({
                    'success': False,
                    'error': 'Access denied: File outside workflow directory'
                }, status=403)
        except:
            # Fallback for older Python versions
            if not str(container_file_path.resolve()).startswith(str(run_dir.resolve())):
                return JsonResponse({
                    'success': False,
                    'error': 'Access denied: File outside workflow directory'
                }, status=403)
        
        # Check if file exists
        if not container_file_path.exists():
            return JsonResponse({
                'success': False,
                'error': f'File not found: {container_file_path}'
            }, status=404)
        
        # Create a download URL for the file
        # Extract the relative path from /app/data/
        if str(container_file_path).startswith('/app/data/'):
            relative_path = str(container_file_path)[9:]  # Remove '/app/data/'
        else:
            relative_path = str(container_file_path)
        
        # Create download URL
        download_url = f"/download-file/?path={relative_path}"
        
        return JsonResponse({
            'success': True,
            'message': f'File ready for download: {container_file_path.name}',
            'file_path': str(container_file_path),
            'download_url': download_url,
            'method': 'web_download',
            'instructions': 'Click the download URL to open the file in your browser'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error opening file: {str(e)}'
        }, status=500)


def serve_file_download(request):
    """Serve any file from the data directory for download/viewing"""
    try:
        file_path = request.GET.get('path')
        if not file_path:
            return JsonResponse({'error': 'No file path specified'}, status=400)
        
        # Security check: ensure the file is within the data directory
        full_path = Path(f"/app/data/{file_path}")
        
        # Prevent directory traversal attacks
        if not str(full_path.resolve()).startswith('/app/data/'):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if file exists
        if not full_path.exists():
            return JsonResponse({'error': 'File not found'}, status=404)
        
        # Determine content type
        content_type = 'application/octet-stream'  # Default
        if full_path.suffix.lower() == '.html':
            content_type = 'text/html'
        elif full_path.suffix.lower() == '.txt':
            content_type = 'text/plain'
        elif full_path.suffix.lower() == '.log':
            content_type = 'text/plain'
        elif full_path.suffix.lower() == '.json':
            content_type = 'application/json'
        elif full_path.suffix.lower() == '.xml':
            content_type = 'application/xml'
        
        # Serve the file
        with open(full_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{full_path.name}"'
            return response
            
    except Exception as e:
        return JsonResponse({'error': f'Error serving file: {str(e)}'}, status=500)


def get_workflow_execution_log(request, workflow_id):
    """Get the current workflow execution log for refresh"""
    try:
        # Construct path to the workflow execution log
        log_file = Path(f"/app/data/runs/{workflow_id}/logs/workflow_execution.log")
        
        if not log_file.exists():
            return JsonResponse({'error': 'Execution log not found'}, status=404)
        
        # Read the log file
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        return JsonResponse({
            'file': log_file.name,
            'content': log_content,
            'timestamp': log_file.stat().st_mtime
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error reading execution log: {str(e)}'}, status=500)

def download_workflow_file(request, workflow_id):
    """Download a workflow file"""
    try:
        file_path = request.GET.get('file')
        if not file_path:
            return JsonResponse({'error': 'No file specified'}, status=400)
        
        # Construct full path to the file
        full_path = Path(f"/app/data/runs/{workflow_id}/{file_path}")
        
        # Security check: ensure the file is within the workflow directory
        workflow_dir = Path(f"/app/data/runs/{workflow_id}")
        if not full_path.resolve().is_relative_to(workflow_dir.resolve()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        if not full_path.exists():
            return JsonResponse({'error': 'File not found'}, status=404)
        
        # Get file info
        file_name = full_path.name
        file_size = full_path.stat().st_size
        
        # Prepare response
        response = HttpResponse(open(full_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response['Content-Length'] = file_size
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': f'Error downloading file: {str(e)}'}, status=500)


def rerun_workflow(request, workflow_id):
    """Rerun a workflow from the beginning"""
    try:
        import sys
        sys.path.append('/app/workflow-orchestrator')
        from orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
        
        # Get the original workflow status
        workflow_status = orchestrator.get_workflow_status(workflow_id)
        if not workflow_status or 'error' in workflow_status:
            messages.error(request, f'Workflow {workflow_id} not found')
            return redirect('workflow_list')
        
        # Create a new run ID for the rerun
        import uuid
        from datetime import datetime
        new_run_id = f"rerun_{workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get the original input files
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        input_dir = run_dir / "inputs"
        input_files = []
        
        if input_dir.exists():
            for file_path in input_dir.glob("*"):
                if file_path.is_file():
                    input_files.append(str(file_path))
        
        if not input_files:
            messages.error(request, 'No input files found for rerun')
            return redirect('workflow_detail', workflow_id=workflow_id)
        
        # Create new workflow run
        tools = workflow_status.get('tools', [])
        if isinstance(tools[0], dict):
            tool_names = [tool.get('tool_name', 'unknown') for tool in tools]
        else:
            tool_names = tools
        
        # Create the new run
        new_workflow = orchestrator.create_sample_run(
            run_id=new_run_id,
            workflow_name=f"Rerun: {workflow_status.get('workflow_name', 'Unknown Workflow')}",
            tools=tool_names,
            input_files=input_files,
            output_dir=f"/app/data/runs/{new_run_id}"
        )
        
        if new_workflow:
            # Execute the pipeline
            success = orchestrator.execute_pipeline_workflow(
                run_id=new_run_id,
                input_files=input_files,
                workflow_config={}
            )
            
            if success:
                messages.success(request, f'Workflow rerun started successfully! New run ID: {new_run_id}')
                return redirect('workflow_detail', workflow_id=new_run_id)
            else:
                messages.error(request, 'Workflow rerun failed during execution')
                return redirect('workflow_detail', workflow_id=new_run_id)
        else:
            messages.error(request, 'Failed to create workflow rerun')
            return redirect('workflow_detail', workflow_id=workflow_id)
            
    except Exception as e:
        messages.error(request, f'Error rerunning workflow: {str(e)}')
        return redirect('workflow_detail', workflow_id=workflow_id)


def rerun_workflow_from_step(request, workflow_id, step_number):
    """Rerun a workflow from a specific step"""
    try:
        import sys
        sys.path.append('/app/workflow-orchestrator')
        from orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
        
        # Get the original workflow status
        workflow_status = orchestrator.get_workflow_status(workflow_id)
        if not workflow_status or 'error' in workflow_status:
            messages.error(request, f'Workflow {workflow_id} not found')
            return redirect('workflow_list')
        
        # Create a new run ID for the rerun
        import uuid
        from datetime import datetime
        new_run_id = f"rerun_step{step_number}_{workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get the original input files
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        input_dir = run_dir / "inputs"
        input_files = []
        
        if input_dir.exists():
            for file_path in input_dir.glob("*"):
                if file_path.is_file():
                    input_files.append(str(file_path))
        
        if not input_files:
            messages.error(request, 'No input files found for rerun')
            return redirect('workflow_detail', workflow_id=workflow_id)
        
        # Get tools from the specified step onwards
        tools = workflow_status.get('tools', [])
        if isinstance(tools[0], dict):
            tool_names = [tool.get('tool_name', 'unknown') for tool in tools[step_number-1:]]
        else:
            tool_names = tools[step_number-1:]
        
        # Create the new run
        new_workflow = orchestrator.create_sample_run(
            run_id=new_run_id,
            workflow_name=f"Rerun from Step {step_number}: {workflow_status.get('workflow_name', 'Unknown Workflow')}",
            tools=tool_names,
            input_files=input_files,
            output_dir=f"/app/data/runs/{new_run_id}"
        )
        
        if new_workflow:
            # Execute the pipeline
            success = orchestrator.execute_pipeline_workflow(
                run_id=new_run_id,
                input_files=input_files,
                workflow_config={}
            )
            
            if success:
                messages.success(request, f'Workflow rerun from step {step_number} started successfully! New run ID: {new_run_id}')
                return redirect('workflow_detail', workflow_id=new_run_id)
            else:
                messages.error(request, f'Workflow rerun from step {step_number} failed during execution')
                return redirect('workflow_detail', workflow_id=new_run_id)
        else:
            messages.error(request, f'Failed to create workflow rerun from step {step_number}')
            return redirect('workflow_detail', workflow_id=workflow_id)
            
    except Exception as e:
        messages.error(request, f'Error rerunning workflow from step {step_number}: {str(e)}')
        return redirect('workflow_detail', workflow_id=workflow_id)


# Removed redundant basic get_tool_logs function - consolidated into get_enhanced_tool_logs


def get_tool_logs(request, workflow_id, tool_name):
    """Get comprehensive orchestrator logs and analysis for a specific tool"""
    try:
        from django.http import JsonResponse
        import json
        from datetime import datetime
        
        # Construct path to workflow run directory
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        if not run_dir.exists():
            return JsonResponse({'success': False, 'error': 'Workflow run not found'})
        
        # Comprehensive log analysis - provides all formats
        tool_logs_data = {
            'tool_name': tool_name,
            'workflow_id': workflow_id,
            'orchestrator_logs': [],
            'step_details': {},
            'container_info': {},
            'execution_summary': {},
            'errors': [],
            'warnings': [],
            'running_containers': [],
            'basic_logs': []  # For backward compatibility
        }
        
        
        # Check for running containers and get their logs
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'ps', '--filter', f'name={workflow_id}', '--format', 'json'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            container_info = json.loads(line)
                            container_names = container_info.get('Names', '').lower()
                            # More specific matching to avoid cross-tool contamination
                            if (tool_name.lower() in container_names and 
                                (f"-{tool_name.lower()}-" in container_names or 
                                 container_names.endswith(f"-{tool_name.lower()}") or
                                 f"{tool_name.lower()}_" in container_names)):
                                
                                container_data = {
                                    'id': container_info['ID'],
                                    'name': container_info['Names'],
                                    'status': container_info['Status'],
                                    'image': container_info['Image'],
                                    'created': container_info['CreatedAt'],
                                    'tool_name': tool_name,
                                    'tool_specific': True
                                }
                                tool_logs_data['running_containers'].append(container_data)
                                
                                # Get container logs and add them to orchestrator logs
                                try:
                                    container_logs_result = subprocess.run(
                                        ['docker', 'logs', '--tail', '50', container_info['ID']],
                                        capture_output=True, text=True, timeout=10
                                    )
                                    
                                    if container_logs_result.returncode == 0:
                                        container_output = container_logs_result.stdout or container_logs_result.stderr
                                        if container_output:
                                            # Parse container logs and add to orchestrator logs
                                            for log_line in container_output.strip().split('\n'):
                                                if log_line.strip():
                                                    tool_logs_data['orchestrator_logs'].append({
                                                        'timestamp': datetime.now().isoformat(),
                                                        'message': log_line.strip(),
                                                        'level': 'info',
                                                        'type': 'container_output',
                                                        'tool_specific': True,
                                                        'container_id': container_info['ID']
                                                    })
                                except Exception as container_log_error:
                                    tool_logs_data['warnings'].append(f"Could not get logs for container {container_info['ID']}: {str(container_log_error)}")
                                    
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            tool_logs_data['warnings'].append(f"Could not check running containers: {str(e)}")
        
        # Parse workflow execution log for this tool
        execution_log = run_dir / "logs" / "workflow_execution.log"
        if execution_log.exists():
            with open(execution_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                current_step = None
                in_tool_section = False
                step_start_time = None
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line starts a new step for our specific tool only
                    if f"STEP" in line and tool_name.upper() in line.upper():
                        # Make sure this is exactly our tool, not a substring match
                        if f"STEP" in line and f"{tool_name.upper()}" in line.upper():
                            # Additional check to ensure exact tool match
                            line_upper = line.upper()
                            tool_upper = tool_name.upper()
                            if f"STEP" in line_upper and (f": {tool_upper}" in line_upper or f"/{tool_upper}" in line_upper or line_upper.endswith(tool_upper)):
                                current_step = tool_name
                                in_tool_section = True
                                step_start_time = datetime.now().isoformat()
                                
                                # Extract step information
                                if "|" in line:
                                    parts = line.split("|")
                                    if len(parts) >= 4:
                                        timestamp_str = parts[0].strip()
                                        message = parts[4].strip() if len(parts) > 4 else parts[3].strip()
                                        
                                # Add to both enhanced and basic formats
                                log_entry = {
                                    'timestamp': timestamp_str,
                                    'message': message,
                                    'level': 'info',
                                    'type': 'step_start',
                                    'step_number': extract_step_number(message),
                                    'tool_specific': True
                                }
                                tool_logs_data['orchestrator_logs'].append(log_entry)
                                tool_logs_data['basic_logs'].append(log_entry)
                                
                                # Store step details
                                tool_logs_data['step_details'] = {
                                    'step_number': extract_step_number(message),
                                    'start_time': timestamp_str,
                                    'tool_name': tool_name,
                                    'status': 'running'
                                }
                    
                    # Process tool-related logs - only for our specific tool
                    elif in_tool_section and current_step == tool_name:
                        # Only process logs that are clearly related to our tool during our execution
                        if "|" in line:
                            parts = line.split("|")
                            if len(parts) >= 4:
                                timestamp_str = parts[0].strip()
                                level = parts[1].strip().lower()
                                message = parts[4].strip() if len(parts) > 4 else parts[3].strip()
                                
                                # Only include if message is relevant to our tool
                                message_lower = message.lower()
                                tool_lower = tool_name.lower()
                                
                                # Very strict filtering: only include logs that are definitely about this tool
                                is_tool_specific = False
                                
                                # 1. Direct tool name mention in the message
                                if tool_lower in message_lower:
                                    is_tool_specific = True
                                
                                # 2. Step-specific logs that are clearly about our tool's step execution
                                elif "step" in message_lower:
                                    # Only if it's about step execution, not general progress
                                    if any(keyword in message_lower for keyword in ["output directory", "input files", "execution time"]):
                                        is_tool_specific = True
                                
                                # 3. Docker/container logs but only if they mention our tool or are clearly execution-related
                                elif ("docker" in message_lower or "container" in message_lower) and tool_lower in message_lower:
                                    is_tool_specific = True
                                
                                # 4. Critical errors during our tool's execution section
                                elif level in ['error', 'critical'] and in_tool_section:
                                    is_tool_specific = True
                                
                                # Explicit exclusions - never include these
                                if is_tool_specific:
                                    # Exclude general workflow setup logs
                                    if any(exclude_term in message_lower for exclude_term in [
                                        "workflow started",
                                        "tools:",
                                        "total steps:",
                                        "data directory:",
                                        "using existing file",
                                        "previous step completed",
                                        "ready to start"
                                    ]):
                                        is_tool_specific = False
                                    
                                    # Exclude logs about other tools
                                    other_tools = [t for t in ['trimmomatic', 'spades', 'quast', 'fastqc', 'multiqc'] if t != tool_lower]
                                    if any(other_tool in message_lower for other_tool in other_tools):
                                        # Only exclude if it's clearly about the other tool, not just mentioning it
                                        if not tool_lower in message_lower:
                                            is_tool_specific = False
                                
                                if is_tool_specific:
                                    # Categorize logs
                                    log_entry = {
                                        'timestamp': timestamp_str,
                                        'message': message,
                                        'level': level,
                                        'type': 'orchestrator',
                                        'tool_specific': True
                                    }
                                    
                                    # Check for specific patterns
                                    if "Docker" in message or "docker" in message.lower():
                                        log_entry['type'] = 'container'
                                        if "executing" in message.lower():
                                            tool_logs_data['container_info']['command'] = message
                                        elif "successful" in message.lower():
                                            tool_logs_data['container_info']['status'] = 'success'
                                        elif "failed" in message.lower():
                                            tool_logs_data['container_info']['status'] = 'failed'
                                            tool_logs_data['errors'].append(message)
                                    
                                    elif "Progress" in message:
                                        log_entry['type'] = 'progress'
                                    
                                    elif "Error" in message or "ERROR" in level:
                                        log_entry['type'] = 'error'
                                        tool_logs_data['errors'].append(message)
                                    
                                    elif "Warning" in message or "WARNING" in level:
                                        log_entry['type'] = 'warning'
                                        tool_logs_data['warnings'].append(message)
                                    
                                    # Add to both enhanced and basic formats
                                    tool_logs_data['orchestrator_logs'].append(log_entry)
                                    tool_logs_data['basic_logs'].append(log_entry)
                    
                    # Check for step completion - only for our specific tool
                    elif in_tool_section and current_step == tool_name and ("COMPLETED" in line or "FAILED" in line) and tool_name.upper() in line.upper():
                        # Ensure this completion is for our exact tool
                        line_upper = line.upper()
                        tool_upper = tool_name.upper()
                        if f"{tool_upper}" in line_upper and ("COMPLETED" in line_upper or "FAILED" in line_upper):
                            if "|" in line:
                                parts = line.split("|")
                                if len(parts) >= 4:
                                    timestamp_str = parts[0].strip()
                                    level = parts[1].strip().lower()
                                    message = parts[4].strip() if len(parts) > 4 else parts[3].strip()
                                    
                                completion_entry = {
                                    'timestamp': timestamp_str,
                                    'message': message,
                                    'level': level,
                                    'type': 'step_completion',
                                    'tool_specific': True
                                }
                                tool_logs_data['orchestrator_logs'].append(completion_entry)
                                tool_logs_data['basic_logs'].append(completion_entry)
                                
                                # Update step details
                                if tool_logs_data['step_details']:
                                    tool_logs_data['step_details']['end_time'] = timestamp_str
                                    tool_logs_data['step_details']['status'] = 'completed' if 'COMPLETED' in line else 'failed'
                                
                                # Extract execution time if available
                                if "Execution Time:" in message:
                                    try:
                                        time_part = message.split("Execution Time:")[1].split("seconds")[0].strip()
                                        tool_logs_data['execution_summary']['execution_time'] = float(time_part)
                                    except:
                                        pass
                                    
                                    in_tool_section = False
                    
                    # Check if we've moved to a different tool
                    elif "STEP" in line and tool_name.upper() not in line.upper():
                        in_tool_section = False
        
        # Load step results if available
        step_results_dir = run_dir / "step_results"
        if step_results_dir.exists():
            for step_file in step_results_dir.glob(f"*{tool_name.lower()}*.json"):
                try:
                    with open(step_file, 'r') as f:
                        step_data = json.load(f)
                        
                        # The step result data is nested under 'result' key
                        result_data = step_data.get('result', {})
                        
                        tool_logs_data['execution_summary'].update({
                            'success': result_data.get('success', False),
                            'output_files_count': len(result_data.get('output_files', [])),
                            'execution_time': result_data.get('execution_time', 0),
                            'tool_version': result_data.get('tool_version'),
                            'memory_used': result_data.get('memory_used'),
                            'cpu_time': result_data.get('cpu_time')
                        })
                        
                        if not result_data.get('success', False):
                            error_msg = result_data.get('error_message', 'Unknown error')
                            if error_msg:  # Only add non-empty error messages
                                tool_logs_data['errors'].append(error_msg)
                except Exception as e:
                    tool_logs_data['warnings'].append(f"Could not read step result: {str(e)}")
        
        # Sort logs by timestamp for both formats
        tool_logs_data['orchestrator_logs'].sort(key=lambda x: x['timestamp'])
        tool_logs_data['basic_logs'].sort(key=lambda x: x['timestamp'])
        
        return JsonResponse({
            'success': True,
            'data': tool_logs_data,
            'logs': tool_logs_data['basic_logs'],  # For backward compatibility
            'tool_name': tool_name,
            'total_logs': len(tool_logs_data['basic_logs'])
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error retrieving enhanced tool logs: {str(e)}'
        })


def extract_step_number(message):
    """Extract step number from log message"""
    import re
    match = re.search(r'STEP (\d+)', message)
    return int(match.group(1)) if match else 0


def get_tool_log_file(request, workflow_id, tool_name):
    """Get the actual tool log file content (e.g., spades.log, trimmomatic.log)"""
    try:
        from django.http import JsonResponse
        
        # Construct path to workflow run
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        if not run_dir.exists():
            return JsonResponse({'success': False, 'error': 'Workflow run not found'})
        
        # Common tool log file names - only tools that actually create log files
        tool_log_files = {
            'spades': ['spades.log', 'SPAdes.log'],
            'quast': ['quast.log', 'QUAST.log'],
            'fastqc': ['fastqc.log', 'FastQC.log'],
            'multiqc': ['multiqc.log', 'MultiQC.log'],
            'bwa': ['bwa.log', 'BWA.log'],
            'samtools': ['samtools.log', 'SAMtools.log'],
            'gatk': ['gatk.log', 'GATK.log']
            # Note: Trimmomatic doesn't create log files by default
        }
        
        # Find the tool's log file
        tool_log_path = None
        if tool_name.lower() in tool_log_files:
            for log_file in tool_log_files[tool_name.lower()]:
                # Check in step directories first
                for step_dir in run_dir.glob("step_*"):
                    potential_log = step_dir / log_file
                    if potential_log.exists():
                        tool_log_path = potential_log
                        break
                
                # If not found in step dirs, check root run directory
                if not tool_log_path:
                    potential_log = run_dir / log_file
                    if potential_log.exists():
                        tool_log_path = potential_log
                        break
        
        if not tool_log_path:
            return JsonResponse({
                'success': False, 
                'error': f'No log file found for {tool_name}',
                'searched_paths': [str(p) for p in run_dir.glob("step_*")]
            })
        
        # Read the log file content
        try:
            with open(tool_log_path, 'r') as f:
                content = f.read()
            
            # Limit content to last 1000 lines to avoid overwhelming the UI
            lines = content.split('\n')
            if len(lines) > 1000:
                content = '\n'.join(lines[-1000:])
                content = f"... (showing last 1000 lines of {len(lines)} total lines)\n" + content
            
            return JsonResponse({
                'success': True,
                'tool_name': tool_name,
                'log_file': str(tool_log_path),
                'content': content,
                'total_lines': len(lines),
                'showing_lines': content.count('\n') + 1
            })
            
        except Exception as read_error:
            return JsonResponse({
                'success': False,
                'error': f'Error reading log file: {str(read_error)}'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def get_workflow_issues_log(request, workflow_id):
    """Get comprehensive workflow issues and failures log"""
    try:
        from django.http import JsonResponse
        
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        if not run_dir.exists():
            return JsonResponse({'success': False, 'error': 'Workflow run not found'})
        
        # Check if issues log exists
        issues_log_file = run_dir / "logs" / "workflow_issues.log"
        
        if not issues_log_file.exists():
            # Analyze existing logs to detect issues
            issues = analyze_workflow_for_issues(workflow_id, run_dir)
            
            # Save the issues log for future reference
            save_issues_log(workflow_id, run_dir, issues)
            
            return JsonResponse({
                'success': True,
                'issues': issues,
                'total_issues': len(issues),
                'status': 'ANALYZED',
                'summary': f'Analyzed workflow and found {len(issues)} issues'
            })
        
        # Read existing issues log
        try:
            with open(issues_log_file, 'r') as f:
                content = f.read()
            
            # Parse the issues log content
            issues = parse_issues_log_content(content)
            
            return JsonResponse({
                'success': True,
                'issues': issues,
                'total_issues': len(issues),
                'status': 'LOADED',
                'summary': f'Loaded {len(issues)} issues from existing log'
            })
            
        except Exception as read_error:
            return JsonResponse({
                'success': False,
                'error': f'Error reading issues log: {str(read_error)}'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def download_workflow_issues_log(request, workflow_id):
    """Download the workflow issues log file"""
    try:
        from django.http import HttpResponse
        
        run_dir = Path(f"/app/data/runs/{workflow_id}")
        if not run_dir.exists():
            return HttpResponse('Workflow run not found', status=404)
        
        issues_log_file = run_dir / "logs" / "workflow_issues.log"
        
        if not issues_log_file.exists():
            # Generate issues log if it doesn't exist
            issues = analyze_workflow_for_issues(workflow_id, run_dir)
            save_issues_log(workflow_id, run_dir, issues)
        
        if not issues_log_file.exists():
            return HttpResponse('Failed to generate issues log', status=500)
        
        # Read and return the file
        with open(issues_log_file, 'r') as f:
            content = f.read()
        
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="workflow_issues_{workflow_id}.log"'
        return response
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)


def analyze_workflow_for_issues(workflow_id, run_dir):
    """Analyze workflow logs and files to detect issues"""
    issues = []
    
    try:
        # Check for workflow completion status
        workflow_summary_file = run_dir / "workflow_summary.json"
        if workflow_summary_file.exists():
            with open(workflow_summary_file, 'r') as f:
                summary = json.load(f)
                
            expected_steps = summary.get('total_steps', 0)
            current_status = summary.get('status', 'unknown')
            
            # Check if workflow is stuck or incomplete
            if current_status == 'running' and expected_steps > 0:
                # Analyze step directories to see what's missing
                completed_steps = 0
                for step_dir in run_dir.glob("step_*"):
                    if step_dir.is_dir():
                        completed_steps += 1
                
                if completed_steps < expected_steps:
                    issues.append({
                        'timestamp': datetime.now().isoformat(),
                        'issue_type': 'WORKFLOW_INCOMPLETE',
                        'severity': 'WARNING',
                        'message': f'Workflow appears to be incomplete - only {completed_steps}/{expected_steps} steps completed',
                        'details': {
                            'expected_steps': expected_steps,
                            'completed_steps': completed_steps,
                            'missing_steps': expected_steps - completed_steps,
                            'current_status': current_status
                        }
                    })
        
        # Check for errors in log files
        logs_dir = run_dir / "logs"
        if logs_dir.exists():
            # Check errors.log
            errors_log = logs_dir / "errors.log"
            if errors_log.exists():
                with open(errors_log, 'r') as f:
                    error_content = f.read()
                    if error_content.strip():
                        issues.append({
                            'timestamp': datetime.now().isoformat(),
                            'issue_type': 'ERROR_LOG_DETECTED',
                            'severity': 'ERROR',
                            'message': 'Error log contains error messages',
                            'details': {
                                'error_log_size': len(error_content),
                                'error_log_lines': error_content.count('\n')
                            }
                        })
            
            # Check detailed_execution.log for incomplete execution
            detailed_log = logs_dir / "detailed_execution.log"
            if detailed_log.exists():
                with open(detailed_log, 'r') as f:
                    detailed_content = f.read()
                    
                    # Look for incomplete workflow execution
                    if 'STEP 1' in detailed_content and 'STEP 2' in detailed_content:
                        if 'STEP 3' not in detailed_content and expected_steps >= 3:
                            issues.append({
                                'timestamp': datetime.now().isoformat(),
                                'issue_type': 'EXECUTION_INCOMPLETE',
                                'severity': 'WARNING',
                                'message': 'Workflow execution appears to have stopped after step 2',
                                'details': {
                                    'last_completed_step': 2,
                                    'expected_steps': expected_steps,
                                    'execution_log_size': len(detailed_content)
                                }
                            })
        
        # Check for missing output files
        for step_dir in run_dir.glob("step_*"):
            if step_dir.is_dir():
                step_name = step_dir.name
                step_number = step_name.split('_')[1] if '_' in step_name else 'unknown'
                tool_name = step_name.split('_', 2)[2] if '_' in step_name else 'unknown'
                
                # Check if step directory is empty or has very few files
                files = list(step_dir.glob('*'))
                if len(files) < 2:  # Most tools should produce at least 2 files
                    issues.append({
                        'timestamp': datetime.now().isoformat(),
                        'issue_type': 'STEP_OUTPUT_INSUFFICIENT',
                        'severity': 'WARNING',
                        'message': f'Step {step_number} ({tool_name}) produced very few output files',
                        'details': {
                            'step_number': step_number,
                            'tool_name': tool_name,
                            'output_files_count': len(files),
                            'step_directory': str(step_dir)
                        }
                    })
        
        # Check for orchestrator crash indicators
        workflow_log = logs_dir / "workflow_execution.log"
        if workflow_log.exists():
            with open(workflow_log, 'r') as f:
                workflow_content = f.read()
                
                # Look for abrupt stops in logging
                if workflow_content.strip():
                    lines = workflow_content.split('\n')
                    if lines and not lines[-1].strip():
                        # Last line is empty, might indicate abrupt stop
                        issues.append({
                            'timestamp': datetime.now().isoformat(),
                            'issue_type': 'LOGGING_ABRUPT_STOP',
                            'severity': 'WARNING',
                            'message': 'Workflow logging appears to have stopped abruptly',
                            'details': {
                                'total_log_lines': len(lines),
                                'last_log_line': lines[-2] if len(lines) > 1 else 'N/A'
                            }
                        })
        
        # Check for resource issues
        # This would require system monitoring - for now, just check file sizes
        total_size = 0
        for file_path in run_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        if total_size > 10 * 1024 * 1024 * 1024:  # 10GB
            issues.append({
                'timestamp': datetime.now().isoformat(),
                'issue_type': 'LARGE_WORKFLOW_OUTPUT',
                'severity': 'INFO',
                'message': 'Workflow output is very large',
                'details': {
                    'total_size_gb': round(total_size / (1024**3), 2),
                    'recommendation': 'Consider cleanup or archiving'
                }
            })
        
    except Exception as e:
        issues.append({
            'timestamp': datetime.now().isoformat(),
            'issue_type': 'ISSUE_ANALYSIS_ERROR',
            'severity': 'ERROR',
            'message': f'Error during issue analysis: {str(e)}',
            'details': {
                'error': str(e),
                'workflow_id': workflow_id
            }
        })
    
    return issues


def parse_issues_log_content(content):
    """Parse the content of an issues log file"""
    issues = []
    
    try:
        lines = content.split('\n')
        current_issue = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('ISSUE #'):
                if current_issue:
                    issues.append(current_issue)
                current_issue = {
                    'timestamp': '',
                    'issue_type': '',
                    'severity': '',
                    'message': '',
                    'details': {},
                    'stack_trace': ''
                }
                
            elif line.startswith('Timestamp:') and current_issue:
                current_issue['timestamp'] = line.split(':', 1)[1].strip()
                
            elif line.startswith('Type:') and current_issue:
                current_issue['issue_type'] = line.split(':', 1)[1].strip()
                
            elif line.startswith('Severity:') and current_issue:
                current_issue['severity'] = line.split(':', 1)[1].strip()
                
            elif line.startswith('Message:') and current_issue:
                current_issue['message'] = line.split(':', 1)[1].strip()
                
            elif line.startswith('Details:') and current_issue:
                # Parse details section
                pass  # Simplified for now
                
            elif line.startswith('Stack Trace:') and current_issue:
                # Parse stack trace section
                pass  # Simplified for now
        
        # Add the last issue
        if current_issue:
            issues.append(current_issue)
            
    except Exception as e:
        # If parsing fails, create a generic issue
        issues.append({
            'timestamp': datetime.now().isoformat(),
            'issue_type': 'LOG_PARSING_ERROR',
            'severity': 'ERROR',
            'message': f'Failed to parse issues log: {str(e)}',
            'details': {
                'error': str(e),
                'content_length': len(content)
            }
        })
    
    return issues


def save_issues_log(workflow_id, run_dir, issues):
    """Save issues to a log file"""
    try:
        issues_log_file = run_dir / "logs" / "workflow_issues.log"
        issues_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(issues_log_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"WORKFLOW ISSUES & FAILURES LOG\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            if not issues:
                f.write("✅ No issues detected - workflow completed successfully!\n\n")
            else:
                f.write(f"🚨 {len(issues)} issues detected during workflow execution:\n\n")
                
                for i, issue in enumerate(issues, 1):
                    f.write(f"ISSUE #{i}\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"Timestamp: {issue['timestamp']}\n")
                    f.write(f"Type: {issue['issue_type']}\n")
                    f.write(f"Severity: {issue['severity']}\n")
                    f.write(f"Message: {issue['message']}\n")
                    
                    if issue.get('details'):
                        f.write(f"Details:\n")
                        for key, value in issue['details'].items():
                            f.write(f"  {key}: {value}\n")
                            
                    if issue.get('stack_trace'):
                        f.write(f"Stack Trace:\n{issue['stack_trace']}\n")
                        
                    f.write("\n")
                    
        print(f"📝 Issues log saved to: {issues_log_file}")
        
    except Exception as e:
        print(f"❌ Failed to save issues log: {str(e)}")

def get_container_status(request, workflow_id):
    """Get real-time container status for a workflow"""
    try:
        import subprocess
        import json
        from datetime import datetime
        
        # Get all containers for this workflow
        result = subprocess.run([
            'docker', 'ps', '--all', '--filter', f'name={workflow_id}', '--format', 
            '{"id":"{{.ID}}","name":"{{.Names}}","status":"{{.Status}}","image":"{{.Image}}","created":"{{.CreatedAt}}"}'
        ], capture_output=True, text=True, timeout=10)
        
        containers = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        container_info = json.loads(line)
                        
                        # Extract tool name from container name
                        tool_name = 'unknown'
                        container_name = container_info.get('name', '')
                        if 'step' in container_name:
                            # Extract tool name from pattern: bioframe-{workflow_id}-step{N}-{tool}-{timestamp}
                            parts = container_name.split('-')
                            if len(parts) >= 4:
                                # Find the tool name (after step part)
                                for i, part in enumerate(parts):
                                    if part.startswith('step') and i + 1 < len(parts):
                                        tool_name = parts[i + 1]
                                        break
                        
                        # Determine container status
                        status_text = container_info.get('status', '').lower()
                        if 'up' in status_text:
                            status = 'running'
                        elif 'exited (0)' in status_text:
                            status = 'exited'
                        elif 'exited' in status_text:
                            status = 'failed'
                        else:
                            status = 'unknown'
                        
                        containers.append({
                            'id': container_info.get('id'),
                            'name': container_info.get('name'),
                            'status': status,
                            'status_text': container_info.get('status'),
                            'image': container_info.get('image'),
                            'created': container_info.get('created'),
                            'tool_name': tool_name
                        })
                        
                    except json.JSONDecodeError:
                        continue
        
        return JsonResponse({
            'success': True,
            'containers': containers,
            'count': len(containers)
        })
        
    except subprocess.TimeoutExpired:
        return JsonResponse({'success': False, 'error': 'Timeout while checking container status'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



def get_workflow_files(request, workflow_id):
    """Get list of files generated by workflow"""
    try:
        import os
        from pathlib import Path
        
        # Get workflow run directory
        run_dir = Path(f'data/runs/{workflow_id}')
        files = []
        
        if run_dir.exists():
            # Find all output files in step directories
            for step_dir in run_dir.glob('step_*'):
                if step_dir.is_dir():
                    for file_path in step_dir.rglob('*'):
                        if file_path.is_file() and file_path.name not in ['.gitkeep', 'Dockerfile']:
                            file_info = {
                                'name': file_path.name,
                                'path': str(file_path.relative_to(run_dir)),
                                'size': file_path.stat().st_size,
                                'step': step_dir.name,
                                'type': file_path.suffix.lower() if file_path.suffix else 'unknown'
                            }
                            files.append(file_info)
        
        return JsonResponse({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'files': []})
