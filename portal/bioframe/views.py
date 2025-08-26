from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import os
import yaml
from pathlib import Path
from datetime import datetime
import sys

# Add the orchestrator to the path
sys.path.append('/app/workflow-orchestrator')

@login_required
def home(request):
    """Home page view"""
    return render(request, 'bioframe/home.html')

@login_required
def dashboard(request):
    """User dashboard with workflow overview and quick actions"""
    stats = {
        'total_workflows': 0, 'completed_workflows': 0,
        'running_workflows': 0, 'total_custom_workflows': 0
    }
    recent_activities = []
    
    try:
        from orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
        all_file_runs = orchestrator.discover_workflow_runs()
        print(f"🔍 Dashboard discovered {len(all_file_runs)} runs from file system")
        
        stats['total_workflows'] = len(all_file_runs)
        stats['completed_workflows'] = len([r for r in all_file_runs if r.status == 'completed'])
        stats['running_workflows'] = len([r for r in all_file_runs if r.status == 'running'])
        stats['failed_workflows'] = len([r for r in all_file_runs if r.status == 'failed'])
        stats['total_custom_workflows'] = len([r for r in all_file_runs if not r.template_used])
        
        for run in all_file_runs[:10]:
            created_at = run.created_at
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    created_at = created_at
            
            activity = {
                'id': run.id, 'name': run.name or 'Data Analysis Run',
                'description': run.description or f'Run from {run.run_directory}',
                'status': run.status, 'created_at': created_at, 'updated_at': created_at,
                'progress': getattr(run, 'progress', 0),
                'step_count': len(run.tools) if run.tools else 0,
                'tools': [tool.tool_name for tool in run.tools] if run.tools else ['fastqc', 'multiqc', 'trimmomatic'],
                'directory': run.run_directory, 'is_file_based': True
            }
            recent_activities.append(activity)
        
        print(f"📊 File-based stats: {stats['total_workflows']} total, {stats['completed_workflows']} completed")
        
    except Exception as e:
        print(f"❌ Error fetching file-based data: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"🚀 Running in 100% file-based mode - no database dependencies")
    
    from tools.views import scan_tools_directory
    available_tools = scan_tools_directory()
    
    context = {
        'user': request.user, 'stats': stats, 'recent_activities': recent_activities,
        'available_tools': available_tools, 'tools_count': len(available_tools),
        'system_status': 'file_based_only', 'file_based_count': len(recent_activities), 'db_based_count': 0
    }
    return render(request, 'bioframe/dashboard.html', context)

@login_required
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
            # Create workflow using orchestrator
            try:
                from orchestrator import WorkflowOrchestrator
                orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
                
                # Create a new workflow run
                workflow_run = orchestrator.create_sample_run(
                    name=workflow_name,
                    description=workflow_description,
                    tools=selected_tools
                )
                
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
        
        # Get user-created workflows from orchestrator
        user_workflows = []
        try:
            from orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
            discovered_runs = orchestrator.discover_workflow_runs()
            
            # Import tool scanning functionality
            try:
                from tools.views import scan_tools_directory
                available_tools = scan_tools_directory()
                print(f"Successfully scanned {len(available_tools)} tools")
            except ImportError as e:
                print(f"Could not import tools.views: {e}")
                # Try alternative import path
                try:
                    import sys
                    sys.path.append('/app')
                    from tools.views import scan_tools_directory
                    available_tools = scan_tools_directory()
                    print(f"Successfully scanned {len(available_tools)} tools with alternative path")
                except Exception as e2:
                    print(f"Alternative import also failed: {e2}")
                    available_tools = []
            except Exception as e:
                print(f"Error scanning tools: {e}")
                available_tools = []
            
            # Create a lookup dictionary for tool metadata
            tool_metadata_lookup = {}
            for tool in available_tools:
                tool_name = tool.get('name', '').lower()
                if tool_name:
                    # Handle different input/output format formats
                    input_formats = tool.get('input_formats', 'Various')
                    output_formats = tool.get('output_formats', 'Various')
                    
                    # Convert to list if it's a string
                    if isinstance(input_formats, str):
                        input_formats = [f.strip() for f in input_formats.split(',') if f.strip()]
                    if isinstance(output_formats, str):
                        output_formats = [f.strip() for f in output_formats.split(',') if f.strip()]
                    
                    # Ensure we have lists
                    if not isinstance(input_formats, list):
                        input_formats = ['Various']
                    if not isinstance(output_formats, list):
                        output_formats = ['Various']
                    
                    tool_metadata_lookup[tool_name] = {
                        'input': input_formats,
                        'output': output_formats
                    }
            
            print(f"Created metadata lookup for {len(tool_metadata_lookup)} tools")
            print(f"Available tool names: {list(tool_metadata_lookup.keys())}")
            
            for run in discovered_runs:
                if run.name and run.name != f"Run {run.id}":  # Filter out basic/placeholder runs
                    tools = [tool.tool_name for tool in run.tools] if run.tools else []
                    
                    # Determine input/output formats based on first and last tool
                    input_formats = ['Various']
                    output_formats = ['Various']
                    
                    if tools:
                        first_tool = tools[0].lower()
                        last_tool = tools[-1].lower()
                        
                        # Get metadata from scanned tools
                        first_metadata = tool_metadata_lookup.get(first_tool, {'input': ['Various'], 'output': ['Various']})
                        last_metadata = tool_metadata_lookup.get(last_tool, {'input': ['Various'], 'output': ['Various']})
                        
                        input_formats = first_metadata['input']
                        output_formats = last_metadata['output']
                    
                    user_workflow = {
                        'id': run.id,
                        'name': run.name,
                        'description': run.description,
                        'category': 'Custom Workflow',
                        'tools': tools,
                        'estimated_time': 'Variable',
                        'difficulty': 'Custom',
                        'input_formats': input_formats,
                        'output_formats': output_formats,
                        'icon': 'fas fa-cogs',
                        'color': 'bg-gray-100 text-gray-800',
                        'type': 'custom',
                        'status': run.status,
                        'created_at': run.created_at,
                        'progress': run.progress
                    }
                    user_workflows.append(user_workflow)
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

@login_required
def workflow_detail(request, workflow_id):
    """Show workflow details and progress"""
    try:
        from orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
        
        # Try to get the workflow run
        workflow_run = orchestrator.get_workflow_run_by_id(workflow_id)
        
        if workflow_run:
            return render_file_based_workflow_detail(request, workflow_run)
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

def render_file_based_workflow_detail(request, workflow_run):
    """Render workflow detail for file-based workflows"""
    # Prepare context for the workflow detail template
    context = {
        'workflow': {
            'id': workflow_run.id,
            'name': workflow_run.name or 'Unnamed Workflow',
            'description': workflow_run.description or 'No description',
            'status': workflow_run.status,
            'progress': getattr(workflow_run, 'progress', 0),
            'created_at': workflow_run.created_at,
            'tools': workflow_run.tools or [],
            'run_directory': workflow_run.run_directory
        }
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
                from orchestrator import WorkflowOrchestrator
                orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
                
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
    """Initialize a workflow run from a template or custom workflow"""
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
        
        # If not found in pre-created templates, try to find a custom workflow
        if not selected_template:
            try:
                from orchestrator import WorkflowOrchestrator
                orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
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
                else:
                    messages.error(request, 'Template or workflow not found')
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
                        from orchestrator import WorkflowOrchestrator
                        orchestrator = WorkflowOrchestrator(data_dir="/app/data", init_docker=False)
                        
                        # Create a new workflow run with pipeline configuration
                        workflow_run = orchestrator.create_sample_run(
                            name=run_name,
                            description=run_description or selected_template['description'],
                            tools=selected_template['tools']
                        )
                        
                        # Save uploaded files to the workflow run directory
                        run_dir = Path(workflow_run.run_directory)
                        input_dir = run_dir / "input"
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
                        
                        # Execute the pipeline workflow
                        success = orchestrator.execute_pipeline_workflow(
                            run_id=workflow_run.id,
                            primary_files=saved_primary_files,
                            reference_files=reference_files
                        )
                        
                        if success:
                            messages.success(request, f'Workflow pipeline "{run_name}" executed successfully! The pipeline processed your files through {len(selected_template["tools"])} tools sequentially.')
                        else:
                            messages.error(request, f'Workflow pipeline "{run_name}" failed during execution. Please check the logs.')
                        
                        return redirect('workflow_list')
                        
                except Exception as e:
                    messages.error(request, f'Error initializing workflow run: {str(e)}')
        
        context = {
            'template': selected_template,
            'available_tools': selected_template['tools'] if selected_template else []
        }
        return render(request, 'bioframe/initialize_workflow_run.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading template: {str(e)}')
        return redirect('workflow_list')
