#!/usr/bin/env python3
"""
BioFrame Workflow Management Script
Provides command-line interface for managing bioinformatics workflows.
"""

import argparse
import json
import yaml
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkflowManager:
    def __init__(self, data_dir: str = "data", workflows_dir: str = "workflows"):
        self.data_dir = Path(data_dir)
        self.workflows_dir = Path(workflows_dir)
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.workflows_dir.mkdir(exist_ok=True)
        
        # Available workflow templates
        self.templates = {
            'quality_control': {
                'name': 'Quality Control Pipeline',
                'description': 'FastQC + Trimmomatic quality control workflow',
                'steps': [
                    {
                        'name': 'FastQC Analysis',
                        'tool': 'fastqc',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['fastqc_reports/'],
                        'config': {'threads': 4}
                    },
                    {
                        'name': 'Trimmomatic Trimming',
                        'tool': 'trimmomatic',
                        'order': 2,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'quality': 20,
                            'minlen': 50,
                            'adapters': 'TruSeq3-PE.fa'
                        }
                    },
                    {
                        'name': 'Post-trimming QC',
                        'tool': 'fastqc',
                        'order': 3,
                        'inputs': ['trimmed/*.fastq.gz'],
                        'outputs': ['post_trim_qc/'],
                        'config': {'threads': 4}
                    },
                    {
                        'name': 'MultiQC Report',
                        'tool': 'multiqc',
                        'order': 4,
                        'inputs': ['fastqc_reports/*', 'post_trim_qc/*'],
                        'outputs': ['multiqc_report/'],
                        'config': {'output_dir': 'multiqc_report'}
                    }
                ]
            },
            'genome_assembly': {
                'name': 'Genome Assembly Pipeline',
                'description': 'Complete genome assembly workflow',
                'steps': [
                    {
                        'name': 'Quality Control',
                        'tool': 'fastqc',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['qc_reports/'],
                        'config': {'threads': 4}
                    },
                    {
                        'name': 'Trimming',
                        'tool': 'trimmomatic',
                        'order': 2,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'quality': 20,
                            'minlen': 50
                        }
                    },
                    {
                        'name': 'Assembly',
                        'tool': 'spades',
                        'order': 3,
                        'inputs': ['trimmed/*.fastq.gz'],
                        'outputs': ['assembly/'],
                        'config': {
                            'threads': 8,
                            'memory': 16,
                            'k': [21, 33, 55]
                        }
                    },
                    {
                        'name': 'Quality Assessment',
                        'tool': 'quast',
                        'order': 4,
                        'inputs': ['assembly/contigs.fasta'],
                        'outputs': ['quast_results/'],
                        'config': {'threads': 4}
                    }
                ]
            },
            'read_mapping': {
                'name': 'Read Mapping Pipeline',
                'description': 'BWA + SAMtools read mapping workflow',
                'steps': [
                    {
                        'name': 'Quality Control',
                        'tool': 'fastqc',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['qc_reports/'],
                        'config': {'threads': 4}
                    },
                    {
                        'name': 'Trimming',
                        'tool': 'trimmomatic',
                        'order': 2,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'quality': 20,
                            'minlen': 50
                        }
                    },
                    {
                        'name': 'Read Mapping',
                        'tool': 'bwa',
                        'order': 3,
                        'inputs': ['trimmed/*.fastq.gz', 'reference/*.fasta'],
                        'outputs': ['mapped/'],
                        'config': {
                            'threads': 4,
                            'algorithm': 'mem'
                        }
                    },
                    {
                        'name': 'SAM Processing',
                        'tool': 'samtools',
                        'order': 4,
                        'inputs': ['mapped/*.sam'],
                        'outputs': ['processed/'],
                        'config': {
                            'threads': 4,
                            'format': 'bam'
                        }
                    }
                ]
            },
            'variant_calling': {
                'name': 'Variant Calling Pipeline',
                'description': 'GATK-based variant calling workflow',
                'steps': [
                    {
                        'name': 'Quality Control',
                        'tool': 'fastqc',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['qc_reports/'],
                        'config': {'threads': 4}
                    },
                    {
                        'name': 'Trimming',
                        'tool': 'trimmomatic',
                        'order': 2,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'quality': 20,
                            'minlen': 50
                        }
                    },
                    {
                        'name': 'Read Mapping',
                        'tool': 'bwa',
                        'order': 3,
                        'inputs': ['trimmed/*.fastq.gz', 'reference/*.fasta'],
                        'outputs': ['mapped/'],
                        'config': {
                            'threads': 4,
                            'algorithm': 'mem'
                        }
                    },
                    {
                        'name': 'SAM Processing',
                        'tool': 'samtools',
                        'order': 4,
                        'inputs': ['mapped/*.sam'],
                        'outputs': ['processed/'],
                        'config': {
                            'threads': 4,
                            'format': 'bam'
                        }
                    },
                    {
                        'name': 'Variant Calling',
                        'tool': 'gatk',
                        'order': 5,
                        'inputs': ['processed/*.bam', 'reference/*.fasta'],
                        'outputs': ['variants/'],
                        'config': {
                            'threads': 4,
                            'memory': 16
                        }
                    }
                ]
            },
            'phylogenomics_gene_recovery': {
                'name': 'Phylogenomics Gene Recovery Pipeline',
                'description': 'Extract genes from Illumina sequencing data using Paftools or HybPiper',
                'steps': [
                    {
                        'name': 'Quality Control',
                        'tool': 'trimmomatic',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'mode': 'PE',
                            'trimming_options': ['ILLUMINACLIP:/adapters/TruSeq3-PE.fa:2:30:10', 'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15', 'MINLEN:36']
                        }
                    },
                    {
                        'name': 'Gene Recovery - Paftools',
                        'tool': 'paftools',
                        'order': 2,
                        'inputs': ['trimmed/*.fastq.gz'],
                        'outputs': ['recovered_genes/'],
                        'config': {
                            'method': 'paftools',
                            'target_genes': 'auto',
                            'output_format': 'fasta'
                        }
                    },
                    {
                        'name': 'Sequence Processing',
                        'tool': 'seqtk',
                        'order': 3,
                        'inputs': ['recovered_genes/*.fasta'],
                        'outputs': ['processed_genes/'],
                        'config': {
                            'subcommand': 'seq',
                            'format': 'fasta'
                        }
                    }
                ]
            },
            'phylogenomics_analysis': {
                'name': 'Phylogenomics Phylogenetic Analysis Pipeline',
                'description': 'Construct species trees from recovered genes using multiple phylogenetic methods',
                'steps': [
                    {
                        'name': 'Multiple Sequence Alignment',
                        'tool': 'mafft',
                        'order': 1,
                        'inputs': ['input/*.fasta'],
                        'outputs': ['alignments/'],
                        'config': {
                            'algorithm': 'auto',
                            'output_format': 'fasta',
                            'threads': 4,
                            'options': ['--auto', '--reorder']
                        }
                    },
                    {
                        'name': 'Gene Tree Construction - IQ-TREE',
                        'tool': 'iqtree',
                        'order': 2,
                        'inputs': ['alignments/*.fasta'],
                        'outputs': ['gene_trees/'],
                        'config': {
                            'model': 'MFP',
                            'bootstrap': 1000,
                            'threads': 4,
                            'options': ['-bb', '1000', '-nt', '4']
                        }
                    },
                    {
                        'name': 'Species Tree Construction - ASTRAL',
                        'tool': 'astral',
                        'order': 3,
                        'inputs': ['gene_trees/*.nwk'],
                        'outputs': ['species_trees/'],
                        'config': {
                            'method': 'astral',
                            'bootstrap': 100,
                            'options': ['-i', 'gene_trees.nwk', '-o', 'species_tree_astral.nwk']
                        }
                    },
                    {
                        'name': 'Species Tree Construction - Concatenated',
                        'tool': 'iqtree',
                        'order': 4,
                        'inputs': ['alignments/concatenated.fasta'],
                        'outputs': ['species_trees/concatenated/'],
                        'config': {
                            'model': 'MFP',
                            'bootstrap': 1000,
                            'threads': 4,
                            'options': ['-bb', '1000', '-nt', '4', '-s', 'concatenated_alignment.fasta']
                        }
                    }
                ]
            },
            'complete_phylogenomics': {
                'name': 'Complete Phylogenomics Pipeline',
                'description': 'End-to-end phylogenomics analysis from raw sequencing data to species trees',
                'steps': [
                    {
                        'name': 'Quality Control',
                        'tool': 'trimmomatic',
                        'order': 1,
                        'inputs': ['input/*.fastq.gz'],
                        'outputs': ['trimmed/'],
                        'config': {
                            'threads': 4,
                            'mode': 'PE',
                            'trimming_options': ['ILLUMINACLIP:/adapters/TruSeq3-PE.fa:2:30:10', 'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15', 'MINLEN:36']
                        }
                    },
                    {
                        'name': 'Gene Recovery',
                        'tool': 'paftools',
                        'order': 2,
                        'inputs': ['trimmed/*.fastq.gz'],
                        'outputs': ['recovered_genes/'],
                        'config': {
                            'method': 'paftools',
                            'target_genes': 'auto',
                            'output_format': 'fasta'
                        }
                    },
                    {
                        'name': 'Sequence Processing',
                        'tool': 'seqtk',
                        'order': 3,
                        'inputs': ['recovered_genes/*.fasta'],
                        'outputs': ['processed_genes/'],
                        'config': {
                            'subcommand': 'seq',
                            'format': 'fasta'
                        }
                    },
                    {
                        'name': 'Multiple Sequence Alignment',
                        'tool': 'mafft',
                        'order': 4,
                        'inputs': ['processed_genes/*.fasta'],
                        'outputs': ['alignments/'],
                        'config': {
                            'algorithm': 'auto',
                            'output_format': 'fasta',
                            'threads': 4,
                            'options': ['--auto', '--reorder']
                        }
                    },
                    {
                        'name': 'Gene Tree Construction',
                        'tool': 'iqtree',
                        'order': 5,
                        'inputs': ['alignments/*.fasta'],
                        'outputs': ['gene_trees/'],
                        'config': {
                            'model': 'MFP',
                            'bootstrap': 1000,
                            'threads': 4,
                            'options': ['-bb', '1000', '-nt', '4']
                        }
                    },
                    {
                        'name': 'Species Tree Construction - ASTRAL',
                        'tool': 'astral',
                        'order': 6,
                        'inputs': ['gene_trees/*.nwk'],
                        'outputs': ['species_trees/astral/'],
                        'config': {
                            'method': 'astral',
                            'bootstrap': 100,
                            'options': ['-i', 'gene_trees.nwk', '-o', 'species_tree_astral.nwk']
                        }
                    },
                    {
                        'name': 'Species Tree Construction - Concatenated',
                        'tool': 'iqtree',
                        'order': 7,
                        'inputs': ['alignments/concatenated.fasta'],
                        'outputs': ['species_trees/concatenated/'],
                        'config': {
                            'model': 'MFP',
                            'bootstrap': 1000,
                            'threads': 4,
                            'options': ['-bb', '1000', '-nt', '4', '-s', 'concatenated_alignment.fasta']
                        }
                    }
                ]
            }
        }
    
    def list_templates(self):
        """List available workflow templates"""
        print("Available Workflow Templates:")
        print("=" * 50)
        
        for template_id, template in self.templates.items():
            print(f"\n📋 {template['name']}")
            print(f"   ID: {template_id}")
            print(f"   Description: {template['description']}")
            print(f"   Steps: {len(template['steps'])}")
            
            for step in template['steps']:
                print(f"     {step['order']}. {step['name']} ({step['tool']})")
    
    def create_workflow(self, template_id: str, name: str, description: str = "", 
                       output_file: str = None) -> str:
        """Create a new workflow from a template"""
        
        if template_id not in self.templates:
            raise ValueError(f"Template '{template_id}' not found")
        
        template = self.templates[template_id]
        
        # Create workflow configuration
        workflow = {
            'metadata': {
                'name': name,
                'description': description or template['description'],
                'template_id': template_id,
                'created_at': str(Path().cwd()),
                'version': '1.0'
            },
            'steps': template['steps']
        }
        
        # Determine output file
        if not output_file:
            safe_name = name.lower().replace(' ', '_').replace('-', '_')
            output_file = self.workflows_dir / f"{safe_name}_workflow.yaml"
        
        # Save workflow
        with open(output_file, 'w') as f:
            yaml.dump(workflow, f, default_flow_style=False, indent=2)
        
        logger.info(f"Created workflow: {output_file}")
        return str(output_file)
    
    def validate_workflow(self, workflow_file: str) -> bool:
        """Validate a workflow file"""
        
        try:
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Check required fields
            required_fields = ['metadata', 'steps']
            for field in required_fields:
                if field not in workflow:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate metadata
            metadata = workflow['metadata']
            required_metadata = ['name', 'template_id']
            for field in required_metadata:
                if field not in metadata:
                    logger.error(f"Missing required metadata field: {field}")
                    return False
            
            # Validate steps
            steps = workflow['steps']
            if not isinstance(steps, list) or len(steps) == 0:
                logger.error("Workflow must have at least one step")
                return False
            
            for i, step in enumerate(steps):
                required_step_fields = ['name', 'tool', 'order']
                for field in required_step_fields:
                    if field not in step:
                        logger.error(f"Step {i+1} missing required field: {field}")
                        return False
                
                # Check for duplicate order numbers
                order_numbers = [s['order'] for s in steps]
                if len(order_numbers) != len(set(order_numbers)):
                    logger.error("Duplicate order numbers found in steps")
                    return False
            
            logger.info(f"✅ Workflow validation passed: {workflow_file}")
            return True
            
        except Exception as e:
            logger.error(f"Workflow validation failed: {e}")
            return False
    
    def list_workflows(self) -> List[str]:
        """List all workflow files"""
        
        workflow_files = []
        for workflow_file in self.workflows_dir.glob("*.yaml"):
            workflow_files.append(str(workflow_file))
        
        return workflow_files
    
    def show_workflow(self, workflow_file: str):
        """Display workflow details"""
        
        try:
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            metadata = workflow['metadata']
            steps = workflow['steps']
            
            print(f"\n📋 Workflow: {metadata['name']}")
            print("=" * 60)
            print(f"Description: {metadata.get('description', 'N/A')}")
            print(f"Template ID: {metadata.get('template_id', 'N/A')}")
            print(f"Created: {metadata.get('created_at', 'N/A')}")
            print(f"Version: {metadata.get('version', 'N/A')}")
            print(f"Total Steps: {len(steps)}")
            
            print("\nWorkflow Steps:")
            print("-" * 40)
            
            for step in sorted(steps, key=lambda x: x['order']):
                print(f"\n{step['order']}. {step['name']}")
                print(f"   Tool: {step['tool']}")
                print(f"   Inputs: {', '.join(step.get('inputs', []))}")
                print(f"   Outputs: {', '.join(step.get('outputs', []))}")
                
                config = step.get('config', {})
                if config:
                    print(f"   Configuration: {json.dumps(config, indent=2)}")
            
        except Exception as e:
            logger.error(f"Error reading workflow file: {e}")
    
    def create_sample_run(self, workflow_file: str, sample_name: str, 
                         input_files: List[str], output_dir: str = None) -> str:
        """Create a sample run from a workflow"""
        
        try:
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Create sample run directory
            if not output_dir:
                safe_name = sample_name.lower().replace(' ', '_').replace('-', '_')
                output_dir = self.data_dir / "runs" / safe_name
            
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create main sample file
            main_file = output_dir / "main_sample.yaml"
            
            # Create sample run configuration
            sample_run = {
                'metadata': {
                    'sample_name': sample_name,
                    'workflow_file': str(workflow_file),
                    'created_at': str(Path().cwd()),
                    'status': 'pending'
                },
                'workflow': workflow,
                'input_files': input_files,
                'output_directory': str(output_dir),
                'current_step': 0,
                'total_steps': len(workflow['steps']),
                'progress': 0.0
            }
            
            # Save main sample file
            with open(main_file, 'w') as f:
                yaml.dump(sample_run, f, default_flow_style=False, indent=2)
            
            # Create directory structure
            (output_dir / "inputs").mkdir(exist_ok=True)
            (output_dir / "outputs").mkdir(exist_ok=True)
            (output_dir / "logs").mkdir(exist_ok=True)
            (output_dir / "checkpoints").mkdir(exist_ok=True)
            (output_dir / "temp").mkdir(exist_ok=True)
            
            # Create tool-specific directories
            for step in workflow['steps']:
                tool_dir = output_dir / "outputs" / step['tool']
                tool_dir.mkdir(parents=True, exist_ok=True)
                (tool_dir / "logs").mkdir(exist_ok=True)
                (tool_dir / "results").mkdir(exist_ok=True)
                (tool_dir / "metadata").mkdir(exist_ok=True)
            
            logger.info(f"Created sample run: {main_file}")
            return str(main_file)
            
        except Exception as e:
            logger.error(f"Error creating sample run: {e}")
            raise
    
    def list_sample_runs(self) -> List[str]:
        """List all sample runs"""
        
        runs_dir = self.data_dir / "runs"
        if not runs_dir.exists():
            return []
        
        run_files = []
        for run_dir in runs_dir.iterdir():
            if run_dir.is_dir():
                main_file = run_dir / "main_sample.yaml"
                if main_file.exists():
                    run_files.append(str(main_file))
        
        return run_files

def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(description='BioFrame Workflow Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List templates command
    list_templates_parser = subparsers.add_parser('list-templates', help='List available workflow templates')
    
    # Create workflow command
    create_workflow_parser = subparsers.add_parser('create-workflow', help='Create a new workflow from template')
    create_workflow_parser.add_argument('template', help='Template ID to use')
    create_workflow_parser.add_argument('name', help='Workflow name')
    create_workflow_parser.add_argument('--description', '-d', help='Workflow description')
    create_workflow_parser.add_argument('--output', '-o', help='Output file path')
    
    # Validate workflow command
    validate_parser = subparsers.add_parser('validate', help='Validate a workflow file')
    validate_parser.add_argument('workflow_file', help='Path to workflow file')
    
    # List workflows command
    list_workflows_parser = subparsers.add_parser('list-workflows', help='List all workflow files')
    
    # Show workflow command
    show_workflow_parser = subparsers.add_parser('show-workflow', help='Show workflow details')
    show_workflow_parser.add_argument('workflow_file', help='Path to workflow file')
    
    # Create sample run command
    create_run_parser = subparsers.add_parser('create-run', help='Create a sample run from workflow')
    create_run_parser.add_argument('workflow_file', help='Path to workflow file')
    create_run_parser.add_argument('sample_name', help='Name of the sample')
    create_run_parser.add_argument('input_files', nargs='+', help='Input files for the workflow')
    create_run_parser.add_argument('--output-dir', '-o', help='Output directory for the run')
    
    # List sample runs command
    list_runs_parser = subparsers.add_parser('list-runs', help='List all sample runs')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize workflow manager
    manager = WorkflowManager()
    
    try:
        if args.command == 'list-templates':
            manager.list_templates()
        
        elif args.command == 'create-workflow':
            output_file = manager.create_workflow(
                args.template,
                args.name,
                args.description,
                args.output
            )
            print(f"✅ Workflow created: {output_file}")
        
        elif args.command == 'validate':
            if manager.validate_workflow(args.workflow_file):
                print("✅ Workflow is valid")
            else:
                print("❌ Workflow validation failed")
                sys.exit(1)
        
        elif args.command == 'list-workflows':
            workflows = manager.list_workflows()
            if workflows:
                print("Available Workflows:")
                for workflow in workflows:
                    print(f"  - {workflow}")
            else:
                print("No workflows found")
        
        elif args.command == 'show-workflow':
            manager.show_workflow(args.workflow_file)
        
        elif args.command == 'create-run':
            main_file = manager.create_sample_run(
                args.workflow_file,
                args.sample_name,
                args.input_files,
                args.output_dir
            )
            print(f"✅ Sample run created: {main_file}")
        
        elif args.command == 'list-runs':
            runs = manager.list_sample_runs()
            if runs:
                print("Available Sample Runs:")
                for run in runs:
                    print(f"  - {run}")
            else:
                print("No sample runs found")
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
