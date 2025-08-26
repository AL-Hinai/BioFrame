from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import docker
import json
import os
from pathlib import Path

def scan_tools_directory():
    """Scan the tools directory and extract tool information from Dockerfiles"""
    tools = []
    
    # Try multiple possible paths for tools directory
    possible_paths = [
        Path("/app/host-tools"),  # Host tools directory mounted in portal
        Path("/app/tools"),       # Alternative portal path
        Path("tools"),            # Relative path
        Path("/tools"),           # Alternative absolute path
        Path("../tools")          # Parent directory
    ]
    
    tools_dir = None
    for path in possible_paths:
        if path.exists():
            tools_dir = path
            break
    
    if not tools_dir:
        print(f"Tools directory not found in any of: {[str(p) for p in possible_paths]}")
        # Return hardcoded tool list as fallback
        return get_fallback_tools()
    
    # Scan each tool subdirectory
    for tool_dir in tools_dir.iterdir():
        if tool_dir.is_dir() and not tool_dir.name.startswith('.'):
            dockerfile_path = tool_dir / "Dockerfile"
            
            if dockerfile_path.exists():
                tool_info = extract_tool_info_from_dockerfile(dockerfile_path, tool_dir.name)
                if tool_info:
                    tools.append(tool_info)
    
    if not tools:
        print(f"No tools found in {tools_dir}, using fallback list")
        return get_fallback_tools()
    
    print(f"Scanned {len(tools)} tools from directory: {tools_dir}")
    return tools

def get_fallback_tools():
    """Return a hardcoded list of available bioinformatics tools"""
    return [
        {
            'name': 'fastqc',
            'description': 'Quality control for high throughput sequence data',
            'version': '0.11.9',
            'category': 'Quality Control',
            'status': 'available'
        },
        {
            'name': 'trimmomatic',
            'description': 'A flexible read trimming tool for Illumina NGS data',
            'version': '0.39',
            'category': 'Read Processing',
            'status': 'available'
        },
        {
            'name': 'spades',
            'description': 'Assembler for single-cell and multi-cell data',
            'version': '3.15.5',
            'category': 'Assembly',
            'status': 'available'
        },
        {
            'name': 'quast',
            'description': 'Quality assessment tool for genome assemblies',
            'version': '5.2.0',
            'category': 'Quality Assessment',
            'status': 'available'
        },
        {
            'name': 'bwa',
            'description': 'Burrows-Wheeler Aligner for short-read alignment',
            'version': '0.7.17',
            'category': 'Alignment',
            'status': 'available'
        },
        {
            'name': 'samtools',
            'description': 'Tools for manipulating SAM/BAM files',
            'version': '1.18',
            'category': 'File Processing',
            'status': 'available'
        },
        {
            'name': 'multiqc',
            'description': 'Aggregate results from bioinformatics analyses',
            'version': '1.14',
            'category': 'Quality Assessment',
            'status': 'available'
        },
        {
            'name': 'gatk',
            'description': 'Genome Analysis Toolkit for variant discovery',
            'version': '4.2.6.1',
            'category': 'Variant Calling',
            'status': 'available'
        },
        {
            'name': 'bedtools',
            'description': 'Tools for genome arithmetic and set operations',
            'version': '2.30.0',
            'category': 'Genome Analysis',
            'status': 'available'
        },
        {
            'name': 'pilon',
            'description': 'Automated assembly improvement and variant calling',
            'version': '1.24',
            'category': 'Assembly Improvement',
            'status': 'available'
        }
    ]

def extract_tool_info_from_dockerfile(dockerfile_path, tool_name):
    """Extract tool information from a Dockerfile"""
    try:
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        
        # Default tool information
        tool_info = {
            'name': tool_name,
            'description': f'Bioinformatics tool: {tool_name}',
            'version': 'latest',
            'category': 'Bioinformatics',
            'status': 'available',
            'dockerfile_path': str(dockerfile_path),
            'tool_dir': str(dockerfile_path.parent),
            'author': 'BioFrame Team',
            'input_formats': 'Various',
            'output_formats': 'Various',
            'tool_id': tool_name,
            'last_modified': 'Unknown'
        }
        
        # Parse BIOFRAME_TOOL_METADATA section
        lines = content.split('\n')
        in_metadata_section = False
        
        for line in lines:
            line = line.strip()
            
            # Check if we're entering the metadata section
            if line == '# BIOFRAME_TOOL_METADATA':
                in_metadata_section = True
                continue
            
            # If we're in metadata section, parse the metadata
            if in_metadata_section and line.startswith('#') and ':' in line:
                if line == '#':  # End of metadata section
                    break
                    
                # Parse metadata line
                key_value = line[1:].strip().split(':', 1)  # Remove # and split on first :
                if len(key_value) == 2:
                    key = key_value[0].strip().lower()
                    value = key_value[1].strip()
                    
                    # Map metadata keys to tool_info fields
                    if key == 'tool_name':
                        tool_info['name'] = value
                    elif key == 'tool_description':
                        tool_info['description'] = value
                    elif key == 'tool_version':
                        tool_info['version'] = value
                    elif key == 'tool_category':
                        tool_info['category'] = value
                    elif key == 'tool_input_formats':
                        tool_info['input_formats'] = value
                    elif key == 'tool_output_formats':
                        tool_info['output_formats'] = value
                    elif key == 'tool_author':
                        tool_info['author'] = value
                    elif key == 'tool_url':
                        tool_info['url'] = value
                    elif key == 'tool_icon':
                        tool_info['icon'] = value
                    elif key == 'tool_color':
                        tool_info['color'] = value
        
        # Ensure we have a valid tool name
        if tool_info['name'] == tool_name:
            tool_info['name'] = tool_name.title()
        
        return tool_info
        
    except Exception as e:
        print(f"Error reading Dockerfile {dockerfile_path}: {e}")
        return None

@login_required
def tool_list(request):
    """List available bioinformatics tools"""
    # Auto-detect tools from the tools directory
    tools = scan_tools_directory()
    
    # If no tools found, fall back to hardcoded list
    if not tools:
        print("No tools auto-detected, using fallback list")
        tools = get_fallback_tools()
    
    print(f"Tool list view found {len(tools)} tools")
    
    context = {'tools': tools}
    return render(request, 'tools/tool_list.html', context)

@login_required
def tool_detail(request, tool_name):
    """Show detailed information about a specific tool"""
    tool_info = {
        'fastqc': {
            'name': 'FastQC',
            'description': 'Quality control for high throughput sequence data',
            'version': '0.11.9',
            'category': 'Quality Control',
            'documentation': 'https://www.bioinformatics.babraham.ac.uk/projects/fastqc/',
            'parameters': [
                {'name': 'input_files', 'type': 'file', 'required': True, 'description': 'Input FASTQ files'},
                {'name': 'output_dir', 'type': 'directory', 'required': False, 'description': 'Output directory'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 4}
            ]
        },
        'trimmomatic': {
            'name': 'Trimmomatic',
            'description': 'A flexible read trimming tool for Illumina NGS data',
            'version': '0.39',
            'category': 'Read Processing',
            'documentation': 'http://www.usadellab.org/cms/?page=trimmomatic',
            'parameters': [
                {'name': 'input_files', 'type': 'file', 'required': True, 'description': 'Input FASTQ files'},
                {'name': 'output_files', 'type': 'file', 'required': True, 'description': 'Output FASTQ files'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 4}
            ]
        },
        'spades': {
            'name': 'SPAdes',
            'description': 'Assembler for single-cell and multi-cell data',
            'version': '3.15.5',
            'category': 'Assembly',
            'documentation': 'https://github.com/ablab/spades',
            'parameters': [
                {'name': 'input_files', 'type': 'file', 'required': True, 'description': 'Input FASTQ files (PE)'},
                {'name': 'output_dir', 'type': 'directory', 'required': True, 'description': 'Output directory'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 8},
                {'name': 'memory', 'type': 'integer', 'required': False, 'description': 'Memory in GB', 'default': 16}
            ]
        },
        'quast': {
            'name': 'QUAST',
            'description': 'Quality assessment tool for genome assemblies',
            'version': '5.2.0',
            'category': 'Quality Assessment',
            'documentation': 'https://github.com/ablab/quast',
            'parameters': [
                {'name': 'input_files', 'type': 'file', 'required': True, 'description': 'Input assembly files'},
                {'name': 'output_dir', 'type': 'directory', 'required': True, 'description': 'Output directory'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 4}
            ]
        },
        'bwa': {
            'name': 'BWA',
            'description': 'Burrows-Wheeler Aligner for short-read alignment',
            'version': '0.7.17',
            'category': 'Alignment',
            'documentation': 'https://github.com/lh3/bwa',
            'parameters': [
                {'name': 'input_files', 'type': 'file', 'required': True, 'description': 'Input FASTQ files'},
                {'name': 'reference', 'type': 'file', 'required': True, 'description': 'Reference genome'},
                {'name': 'output_file', 'type': 'file', 'required': True, 'description': 'Output SAM file'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 4}
            ]
        },
        'samtools': {
            'name': 'SAMtools',
            'description': 'Tools for manipulating SAM/BAM files',
            'version': '1.18',
            'category': 'File Processing',
            'documentation': 'https://github.com/samtools/samtools',
            'parameters': [
                {'name': 'input_file', 'type': 'file', 'required': True, 'description': 'Input SAM/BAM file'},
                {'name': 'output_file', 'type': 'file', 'required': True, 'description': 'Output file'},
                {'name': 'threads', 'type': 'integer', 'required': False, 'description': 'Number of threads', 'default': 4}
            ]
        }
    }
    
    if tool_name not in tool_info:
        return JsonResponse({'error': 'Tool not found'}, status=404)
    
    context = {'tool': tool_info[tool_name]}
    return render(request, 'tools/tool_detail.html', context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_tool(request, tool_name):
    """Execute a bioinformatics tool"""
    try:
        # Get tool parameters from request
        parameters = request.data.get('parameters', {})
        
        # Validate parameters based on tool
        if not validate_tool_parameters(tool_name, parameters):
            return Response({'error': 'Invalid parameters for tool'}, status=400)
        
        # Execute tool using Docker
        result = run_tool_docker(tool_name, parameters)
        
        return Response({
            'success': True,
            'result': result,
            'message': f'Tool {tool_name} executed successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

def validate_tool_parameters(tool_name, parameters):
    """Validate tool parameters"""
    required_params = {
        'fastqc': ['input_files'],
        'trimmomatic': ['input_files', 'output_files'],
        'spades': ['input_files', 'output_dir'],
        'quast': ['input_files', 'output_dir'],
        'bwa': ['input_files', 'reference', 'output_file'],
        'samtools': ['input_file', 'output_file']
    }
    
    if tool_name not in required_params:
        return False
    
    for param in required_params[tool_name]:
        if param not in parameters:
            return False
    
    return True

def run_tool_docker(tool_name, parameters):
    """Run a tool using Docker"""
    try:
        client = docker.from_env()
        
        # Build container configuration
        container_config = {
            'image': f'bioframe-{tool_name}:latest',
            'command': build_tool_command(tool_name, parameters),
            'volumes': {
                '/data': {'bind': '/data', 'mode': 'rw'},
                '/logs': {'bind': '/logs', 'mode': 'rw'},
            },
            'detach': False,
            'remove': True,
        }
        
        # Execute container
        container = client.containers.run(**container_config)
        
        # Get logs
        logs = container.logs().decode('utf-8')
        
        return {
            'exit_code': container.attrs['State']['ExitCode'],
            'stdout': logs,
            'stderr': '',
            'container_id': container.id,
        }
        
    except Exception as e:
        raise Exception(f"Docker execution error: {e}")

def build_tool_command(tool_name, parameters):
    """Build the command for a specific tool"""
    if tool_name == 'fastqc':
        input_files = parameters['input_files']
        output_dir = parameters.get('output_dir', f"/data/fastqc_output")
        threads = parameters.get('threads', 4)
        return ['fastqc', '-o', output_dir, '-t', str(threads)] + input_files
    
    elif tool_name == 'trimmomatic':
        input_files = parameters['input_files']
        output_files = parameters['output_files']
        threads = parameters.get('threads', 4)
        return ['trimmomatic', 'PE', '-threads', str(threads)] + input_files + output_files
    
    elif tool_name == 'spades':
        input_files = parameters['input_files']
        output_dir = parameters['output_dir']
        threads = parameters.get('threads', 8)
        memory = parameters.get('memory', 16)
        return ['spades.py', '--pe1-1', input_files[0], '--pe1-2', input_files[1], 
                '--threads', str(threads), '--memory', str(memory), '-o', output_dir]
    
    elif tool_name == 'quast':
        input_files = parameters['input_files']
        output_dir = parameters['output_dir']
        threads = parameters.get('threads', 4)
        return ['quast.py', '-o', output_dir, '--threads', str(threads)] + input_files
    
    elif tool_name == 'bwa':
        input_files = parameters['input_files']
        reference = parameters['reference']
        output_file = parameters['output_file']
        threads = parameters.get('threads', 4)
        return ['bwa', 'mem', '-t', str(threads), reference] + input_files + [output_file]
    
    elif tool_name == 'samtools':
        input_file = parameters['input_file']
        output_file = parameters['output_file']
        return ['samtools', 'view', '-b', '-S', input_file, '-o', output_file]
    
    else:
        return ['echo', 'Tool not configured']

def tools_api(request):
    """API endpoint to return available tools as JSON"""
    tools = scan_tools_directory()
    
    # If no tools found, fall back to hardcoded list
    if not tools:
        print("No tools auto-detected, using fallback list")
        tools = get_fallback_tools()
    
    # Ensure all tools have the required fields for the frontend
    for tool in tools:
        if 'author' not in tool:
            tool['author'] = 'BioFrame Team'
        if 'input_formats' not in tool:
            tool['input_formats'] = 'Various'
        if 'output_formats' not in tool:
            tool['output_formats'] = 'Various'
        if 'url' not in tool:
            tool['url'] = '#'
        if 'icon' not in tool:
            tool['icon'] = 'fas fa-tools'
        
        # Map tool categories to proper colors
        category_colors = {
            'Quality Control': 'bg-blue-100 text-blue-800',
            'Read Processing': 'bg-green-100 text-green-800',
            'Assembly': 'bg-green-100 text-green-800',
            'Alignment': 'bg-purple-100 text-purple-800',
            'Variant Calling': 'bg-red-100 text-red-800',
            'Genome Analysis': 'bg-teal-100 text-teal-800',
            'Quality Assessment': 'bg-orange-100 text-orange-800',
            'Assembly Improvement': 'bg-indigo-100 text-indigo-800',
            'Sequence Analysis': 'bg-pink-100 text-pink-800'
        }
        
        if 'color' not in tool or tool['color'] not in ['bg-blue-100 text-blue-800', 'bg-green-100 text-green-800', 'bg-purple-100 text-purple-800', 'bg-red-100 text-red-800', 'bg-teal-100 text-teal-800', 'bg-orange-100 text-orange-800', 'bg-indigo-100 text-indigo-800', 'bg-pink-100 text-pink-800']:
            tool['color'] = category_colors.get(tool.get('category', 'Bioinformatics'), 'bg-gray-100 text-gray-800')
    
    print(f"Tools API returning {len(tools)} tools")
    return JsonResponse(tools, safe=False)
