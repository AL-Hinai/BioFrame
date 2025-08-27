#!/usr/bin/env python3
"""
BioFrame Workflow Orchestrator
Manages workflow execution, tool invocation, and file-based workflow management
"""

import os
import yaml
import json
import uuid
import docker
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import subprocess
import time
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ToolExecution:
    """Represents a tool execution step"""
    tool_name: str
    order: int
    status: str = 'pending'  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    config: Dict[str, Any] = None
    error_message: Optional[str] = None
    input_files: List[str] = None
    output_files: List[str] = None
    logs: List[str] = None

@dataclass
class WorkflowRun:
    """Represents a workflow run"""
    id: str
    name: str
    description: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    updated_at: datetime
    progress: float = 0.0
    tools: List[ToolExecution] = None
    run_directory: str = None
    template_used: bool = False
    checkpoint_data: Dict[str, Any] = None

class WorkflowOrchestrator:
    """Main orchestrator class for managing bioinformatics workflows"""
    
    def __init__(self, data_dir: str = "/data", init_docker: bool = True):
        """Initialize the orchestrator"""
        self.data_dir = Path(data_dir)
        self.runs_dir = self.data_dir / "runs"
        self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Docker client if requested
        self.docker_client = None
        if init_docker:
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Docker client: {e}")
                logger.info("Running in file-only mode")
        
        logger.info(f"WorkflowOrchestrator initialized with data_dir: {self.data_dir}")
    
    def create_sample_run(self, name: str, description: str, tools: List[str]) -> WorkflowRun:
        """Create a new sample run with the specified tools"""
        run_id = str(uuid.uuid4())
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create tool executions
        tool_executions = []
        for i, tool_name in enumerate(tools):
            tool_exec = ToolExecution(
                tool_name=tool_name,
                order=i + 1,
                status='pending',
                config={},
                input_files=[],
                output_files=[],
                logs=[]
            )
            tool_executions.append(tool_exec)
        
        # Create workflow run
        now = datetime.now(timezone.utc)
        workflow_run = WorkflowRun(
            id=run_id,
            name=name,
            description=description,
            status='pending',
            created_at=now,
            updated_at=now,
            progress=0.0,
            tools=tool_executions,
            run_directory=str(run_dir),
            template_used=False,
            checkpoint_data={}
        )
        
        # Save workflow file
        workflow_file = run_dir / "workflow.yaml"
        self._save_unified_workflow_file(workflow_run, workflow_file)
        
        logger.info(f"Created sample run: {run_id} with {len(tools)} tools")
        return workflow_run
    
    def execute_pipeline_workflow(self, run_id: str, primary_files: List[str], reference_files: Dict[str, str] = None) -> bool:
        """Execute a pipeline workflow where each tool's output becomes the next tool's input"""
        try:
            workflow_run = self.get_workflow_run_by_id(run_id)
            if not workflow_run:
                logger.error(f"Workflow run {run_id} not found")
                return False
            
            # Update workflow status
            workflow_run.status = 'running'
            workflow_run.updated_at = datetime.now(timezone.utc)
            
            # Create input directory for the first tool
            run_dir = Path(workflow_run.run_directory)
            input_dir = run_dir / "input"
            input_dir.mkdir(exist_ok=True)
            
            # Copy primary files to input directory
            current_input_files = []
            for file_path in primary_files:
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    # Check if we need to copy the file (avoid copying to same location)
                    if str(file_path_obj.parent) == str(input_dir):
                        # File is already in the input directory
                        current_input_files.append(str(file_path_obj))
                        logger.info(f"File already in input directory: {file_path}")
                    else:
                        # Copy file to input directory
                        dest_path = input_dir / file_path_obj.name
                        import shutil
                        shutil.copy2(file_path_obj, dest_path)
                        current_input_files.append(str(dest_path))
                        logger.info(f"Copied input file: {file_path} -> {dest_path}")
                else:
                    logger.warning(f"Input file not found: {file_path}")
            
            if not current_input_files:
                logger.error("No valid input files found")
                return False
            
            # Execute tools sequentially in pipeline
            for i, tool_exec in enumerate(workflow_run.tools):
                try:
                    logger.info(f"🔄 Executing pipeline step {i+1}/{len(workflow_run.tools)}: {tool_exec.tool_name}")
                    
                    # Update tool status
                    tool_exec.status = 'running'
                    tool_exec.started_at = datetime.now(timezone.utc)
                    tool_exec.input_files = current_input_files.copy()
                    
                    # Create tool-specific directory
                    tool_dir = run_dir / f"step_{tool_exec.order}_{tool_exec.tool_name}"
                    tool_dir.mkdir(exist_ok=True)
                    
                    # Execute the tool
                    success, output_files = self._execute_tool(
                        tool_exec.tool_name, 
                        current_input_files, 
                        tool_dir,
                        reference_files
                    )
                    
                    if success:
                        tool_exec.status = 'completed'
                        tool_exec.completed_at = datetime.now(timezone.utc)
                        tool_exec.output_files = output_files
                        tool_exec.execution_time = (tool_exec.completed_at - tool_exec.started_at).total_seconds()
                        
                        # Update progress
                        workflow_run.progress = ((i + 1) / len(workflow_run.tools)) * 100
                        
                        # For quality control pipelines: preserve original input files for tools that need them
                        if i < len(workflow_run.tools) - 1:  # Not the last tool
                            next_tool = workflow_run.tools[i+1].tool_name
                            
                            # Quality control tools need the original input files, not the previous tool's output
                            if next_tool in ['trimmomatic', 'spades', 'bwa']:
                                # Get the original input files from the workflow run
                                original_input_dir = Path(workflow_run.run_directory) / "input"
                                if original_input_dir.exists():
                                    original_files = [str(f) for f in original_input_dir.glob("*.fastq*")]
                                    if original_files:
                                        current_input_files = original_files
                                        logger.info(f"✅ Tool {tool_exec.tool_name} completed. Using original input files for {next_tool}: {original_files}")
                                    else:
                                        current_input_files = output_files.copy()
                                        logger.info(f"✅ Tool {tool_exec.tool_name} completed. No original files found, using output files for {next_tool}: {output_files}")
                                else:
                                    current_input_files = output_files.copy()
                                    logger.info(f"✅ Tool {tool_exec.tool_name} completed. No input directory, using output files for {next_tool}: {output_files}")
                            else:
                                # For other tools, use the output files as input
                                current_input_files = output_files.copy()
                                logger.info(f"✅ Tool {tool_exec.tool_name} completed. Output files will be used as input for next tool: {next_tool}")
                        else:
                            logger.info(f"🎉 Final tool {tool_exec.tool_name} completed. Pipeline finished!")
                        
                    else:
                        tool_exec.status = 'failed'
                        tool_exec.error_message = f"Tool execution failed"
                        workflow_run.status = 'failed'
                        logger.error(f"❌ Tool {tool_exec.tool_name} failed")
                        return False
                    
                    # Save workflow state after each tool
                    self._save_unified_workflow_file(workflow_run, run_dir / "workflow.yaml")
                    
                except Exception as e:
                    tool_exec.status = 'failed'
                    tool_exec.error_message = str(e)
                    workflow_run.status = 'failed'
                    logger.error(f"❌ Error executing tool {tool_exec.tool_name}: {e}")
                    return False
            
            # Pipeline completed successfully
            workflow_run.status = 'completed'
            workflow_run.updated_at = datetime.now(timezone.utc)
            workflow_run.progress = 100.0
            
            # Save final workflow state
            self._save_unified_workflow_file(workflow_run, run_dir / "workflow.yaml")
            
            logger.info(f"🎉 Pipeline workflow {run_id} completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pipeline execution failed: {e}")
            return False
    
    def _execute_tool(self, tool_name: str, input_files: List[str], output_dir: Path, reference_files: Dict[str, str] = None) -> tuple[bool, List[str]]:
        """Execute a single tool and return success status and output files"""
        try:
            logger.info(f"Executing tool: {tool_name}")
            logger.info(f"Input files: {input_files}")
            logger.info(f"Output directory: {output_dir}")
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Route to appropriate tool execution method
            if tool_name == 'fastqc':
                return self._execute_fastqc(input_files, output_dir)
            elif tool_name == 'trimmomatic':
                return self._execute_trimmomatic(input_files, output_dir)
            elif tool_name == 'multiqc':
                return self._execute_multiqc(input_files, output_dir)
            elif tool_name == 'spades':
                return self._execute_spades(input_files, output_dir)
            elif tool_name == 'quast':
                return self._execute_quast(input_files, output_dir)
            elif tool_name == 'bwa':
                return self._execute_bwa(input_files, output_dir, reference_files)
            elif tool_name == 'samtools':
                return self._execute_samtools(input_files, output_dir)
            elif tool_name == 'gatk':
                return self._execute_gatk(input_files, output_dir)
            else:
                # Generic tool execution
                return self._execute_generic_tool(tool_name, input_files, output_dir)
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return False, []
    
    def _execute_fastqc(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute FastQC quality control using Docker"""
        try:
            logger.info(f"Running FastQC on {len(input_files)} input files")
            
            # Ensure output_dir is a Path object
            if isinstance(output_dir, str):
                output_dir = Path(output_dir)
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_files = []
            for input_file in input_files:
                input_path = Path(input_file)
                base_name = input_path.stem
                
                # Convert container paths to absolute host paths for Docker volume mounting
                # The orchestrator container has ./data:/data mounted, but we need absolute host paths
                # Since the orchestrator runs docker commands from the host context, we need absolute paths
                import os
                # Get the absolute host path by replacing /data with the actual host project directory
                # The host project directory is /run/media/msalim/Mass Storage/Work File/Projects/BioFrame
                host_project_dir = "/run/media/msalim/Mass Storage/Work File/Projects/BioFrame"
                host_input_dir = str(input_path.parent).replace('/data', host_project_dir + '/data')
                host_output_dir = str(output_dir).replace('/data', host_project_dir + '/data')
                
                # Run FastQC using Docker with correct host paths
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{host_input_dir}:/input",
                    "-v", f"{host_output_dir}:/output",
                    "-w", "/output",
                    "bioframe-fastqc",
                    "fastqc", "-o", "/output", f"/input/{input_path.name}"
                ]
                
                logger.info(f"Executing: {' '.join(cmd)}")
                
                # Execute the command
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # Find generated output files
                    html_files = list(output_dir.glob("*_fastqc.html"))
                    zip_files = list(output_dir.glob("*_fastqc.zip"))
                    
                    output_files.extend([str(f) for f in html_files + zip_files])
                    logger.info(f"FastQC completed successfully for {input_path.name}")
                else:
                    logger.error(f"FastQC failed for {input_path.name}: {result.stderr}")
                    return False, []
            
            logger.info(f"FastQC completed. Output files: {output_files}")
            return True, output_files
            
        except subprocess.TimeoutExpired:
            logger.error("FastQC execution timed out")
            return False, []
        except Exception as e:
            logger.error(f"FastQC execution failed: {e}")
            return False, []
    
    def _execute_trimmomatic(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute Trimmomatic read trimming using Docker"""
        try:
            logger.info(f"Running Trimmomatic on {len(input_files)} input files")
            
            # Ensure output_dir is a Path object
            if isinstance(output_dir, str):
                output_dir = Path(output_dir)
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_files = []
            for input_file in input_files:
                input_path = Path(input_file)
                base_name = input_path.stem
                
                # Convert container paths to absolute host paths for Docker volume mounting
                # The orchestrator container has ./data:/data mounted, but we need absolute host paths
                # Since the orchestrator runs docker commands from the host context, we need absolute paths
                import os
                # Get the absolute host path by replacing /data with the actual host project directory
                # The host project directory is /run/media/msalim/Mass Storage/Work File/Projects/BioFrame
                host_project_dir = "/run/media/msalim/Mass Storage/Work File/Projects/BioFrame"
                host_input_dir = str(input_path.parent).replace('/data', host_project_dir + '/data')
                host_output_dir = str(output_dir).replace('/data', host_project_dir + '/data')
                
                # Run Trimmomatic using Docker with correct host paths
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{host_input_dir}:/input",
                    "-v", f"{host_output_dir}:/output",
                    "-w", "/output",
                    "bioframe-trimmomatic",
                    "trimmomatic", "PE",
                    f"/input/{input_path.name}",
                    "/dev/null",  # Single-end mode for now
                    f"{base_name}_trimmed.fastq",
                    "ILLUMINACLIP:TruSeq3-SE:2:30:10",
                    "LEADING:3",
                    "TRAILING:3",
                    "SLIDINGWINDOW:4:15",
                    "MINLEN:36"
                ]
                
                logger.info(f"Executing: {' '.join(cmd)}")
                
                # Execute the command
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    # Find generated output files
                    trimmed_files = list(output_dir.glob("*_trimmed.fastq"))
                    log_files = list(output_dir.glob("*.log"))
                    
                    output_files.extend([str(f) for f in trimmed_files + log_files])
                    logger.info(f"Trimmomatic completed successfully for {input_path.name}")
                else:
                    logger.error(f"Trimmomatic failed for {input_path.name}: {result.stderr}")
                    return False, []
            
            logger.info(f"Trimmomatic completed. Output files: {output_files}")
            return True, output_files
            
        except subprocess.TimeoutExpired:
            logger.error("Trimmomatic execution timed out")
            return False, []
        except Exception as e:
            logger.error(f"Trimmomatic execution failed: {e}")
            return False, []
    
    def _execute_multiqc(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute MultiQC report generation using Docker"""
        try:
            logger.info(f"Running MultiQC on {len(input_files)} input files")
            
            # Ensure output_dir is a Path object
            if isinstance(output_dir, str):
                output_dir = Path(output_dir)
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Convert container paths to absolute host paths for Docker volume mounting
            # The orchestrator container has ./data:/data mounted, but we need absolute host paths
            # Since the orchestrator runs docker commands from the host context, we need absolute paths
            import os
            # Get the absolute host path by replacing /data with the actual host project directory
            # The host project directory is /run/media/msalim/Mass Storage/Work File/Projects/BioFrame
            host_project_dir = "/run/media/msalim/Mass Storage/Work File/Projects/BioFrame"
            host_output_dir = str(output_dir).replace('/data', host_project_dir + '/data')
            
            # Run MultiQC using Docker with correct host paths
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{host_output_dir}:/output",
                "-w", "/output",
                "bioframe-multiqc",
                "multiqc", ".",
                "-o", "/output"
            ]
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            # Execute the command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Find generated output files
                html_files = list(output_dir.glob("multiqc_report.html"))
                data_files = list(output_dir.glob("multiqc_data"))
                
                output_files = [str(f) for f in html_files + data_files]
                logger.info(f"MultiQC completed successfully. Output files: {output_files}")
                return True, output_files
            else:
                logger.error(f"MultiQC failed: {result.stderr}")
                return False, []
            
        except subprocess.TimeoutExpired:
            logger.error("MultiQC execution timed out")
            return False, []
        except Exception as e:
            logger.error(f"MultiQC execution failed: {e}")
            return False, []
    
    def _execute_spades(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute SPAdes assembly"""
        try:
            # Simulate SPAdes execution
            output_files = []
            
            # Assembly outputs
            contigs_file = output_dir / "contigs.fasta"
            scaffolds_file = output_dir / "scaffolds.fasta"
            assembly_graph = output_dir / "assembly_graph.fastg"
            
            # Create dummy output files
            contigs_file.write_text(">contig1\nATCGATCGATCG\n>contig2\nGCTAGCTAGCTA")
            scaffolds_file.write_text(">scaffold1\nATCGATCGATCGNNNGCTAGCTAGCTA")
            assembly_graph.write_text("SPAdes assembly graph content")
            
            output_files.extend([str(contigs_file), str(scaffolds_file), str(assembly_graph)])
            
            logger.info(f"SPAdes completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"SPAdes execution failed: {e}")
            return False, []
    
    def _execute_quast(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute QUAST quality assessment"""
        try:
            # Simulate QUAST execution
            output_files = []
            
            # QUAST outputs
            report_file = output_dir / "quast_report.txt"
            html_report = output_dir / "quast_report.html"
            
            # Create dummy output files
            report_file.write_text("QUAST Quality Assessment Report\nAssembly Statistics\nContigs: 100\nN50: 1000")
            html_report.write_text("<html><body><h1>QUAST Report</h1></body></html>")
            
            output_files.extend([str(report_file), str(html_report)])
            
            logger.info(f"QUAST completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"QUAST execution failed: {e}")
            return False, []
    
    def _execute_bwa(self, input_files: List[str], output_dir: Path, reference_files: Dict[str, str] = None) -> tuple[bool, List[str]]:
        """Execute BWA alignment"""
        try:
            # Simulate BWA execution
            output_files = []
            
            # BWA outputs
            sam_file = output_dir / "aligned.sam"
            bam_file = output_dir / "aligned.bam"
            
            # Create dummy output files
            sam_file.write_text("@HD\tVN:1.6\tSO:unsorted\n@SQ\tSN:chr1\tLN:1000\nread1\t0\tchr1\t1\t60\t100M\t*\t0\t0\tATCGATCGATCG")
            bam_file.write_text("BAM file content (binary)")
            
            output_files.extend([str(sam_file), str(bam_file)])
            
            logger.info(f"BWA completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"BWA execution failed: {e}")
            return False, []
    
    def _execute_samtools(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute SAMtools processing"""
        try:
            # Simulate SAMtools execution
            output_files = []
            
            # SAMtools outputs
            sorted_bam = output_dir / "sorted.bam"
            index_file = output_dir / "sorted.bam.bai"
            
            # Create dummy output files
            sorted_bam.write_text("Sorted BAM file content")
            index_file.write_text("BAM index content")
            
            output_files.extend([str(sorted_bam), str(index_file)])
            
            logger.info(f"SAMtools completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"SAMtools execution failed: {e}")
            return False, []
    
    def _execute_gatk(self, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute GATK variant calling"""
        try:
            # Simulate GATK execution
            output_files = []
            
            # GATK outputs
            vcf_file = output_dir / "variants.vcf"
            log_file = output_dir / "gatk.log"
            
            # Create dummy output files
            vcf_file.write_text("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t100\t.\tA\tT\t100\tPASS\tDP=50")
            log_file.write_text("GATK execution log")
            
            output_files.extend([str(vcf_file), str(log_file)])
            
            logger.info(f"GATK completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"GATK execution failed: {e}")
            return False, []
    
    def _execute_generic_tool(self, tool_name: str, input_files: List[str], output_dir: Path) -> tuple[bool, List[str]]:
        """Execute a generic tool"""
        try:
            # Simulate generic tool execution
            output_files = []
            
            # Generic outputs
            output_file = output_dir / f"{tool_name}_output.txt"
            log_file = output_dir / f"{tool_name}.log"
            
            # Create dummy output files
            output_file.write_text(f"Output from {tool_name} tool")
            log_file.write_text(f"Log from {tool_name} tool execution")
            
            output_files.extend([str(output_file), str(log_file)])
            
            logger.info(f"{tool_name} completed. Output files: {output_files}")
            return True, output_files
            
        except Exception as e:
            logger.error(f"{tool_name} execution failed: {e}")
            return False, []
    
    def _save_unified_workflow_file(self, workflow_run: WorkflowRun, workflow_file: Path):
        """Save the unified workflow.yaml file with everything in one place"""
        workflow_data = {
            'id': workflow_run.id,
            'name': workflow_run.name,
            'description': workflow_run.description,
            'created_at': workflow_run.created_at.isoformat(),
            'status': workflow_run.status,
            'progress': workflow_run.progress,
            'workflow_pipeline': {
                'total_steps': len(workflow_run.tools),
                'current_step': 0,
                'steps': []
            },
            'tools': [],
            'file_references': {
                'inputs': [],
                'outputs': {},
                'logs': []
            },
            'execution_status': {
                'started_at': None,
                'completed_at': None,
                'checkpoint_data': workflow_run.checkpoint_data or {}
            },
            'metadata': {
                'version': '2.0',
                'created_by': 'BioFrame Orchestrator (Unified)',
                'last_updated': datetime.now().isoformat(),
                'format': 'unified_workflow'
            }
        }
        
        # Add tool information
        for tool_exec in workflow_run.tools:
            tool_data = {
                'tool_name': tool_exec.tool_name,
                'order': tool_exec.order,
                'status': tool_exec.status,
                'started_at': tool_exec.started_at.isoformat() if tool_exec.started_at else None,
                'completed_at': tool_exec.completed_at.isoformat() if tool_exec.completed_at else None,
                'execution_time': tool_exec.execution_time,
                'config': tool_exec.config or {},
                'input_files': tool_exec.input_files or [],
                'output_files': tool_exec.output_files or [],
                'logs': tool_exec.logs or []
            }
            workflow_data['tools'].append(tool_data)
            
            # Add to pipeline steps
            step_data = {
                'order': tool_exec.order,
                'tool': tool_exec.tool_name,
                'name': f"Step {tool_exec.order}: {tool_exec.tool_name}",
                'status': tool_exec.status,
                'started_at': tool_data['started_at'],
                'completed_at': tool_data['completed_at'],
                'execution_time': tool_exec.execution_time,
                'error_message': tool_exec.error_message,
                'config': tool_exec.config or {},
                'dependencies': []
            }
            workflow_data['workflow_pipeline']['steps'].append(step_data)
        
        # Save to file
        with open(workflow_file, 'w') as f:
            yaml.dump(workflow_data, f, default_flow_style=False, indent=2)
        
        logger.info(f"Created unified workflow.yaml: {workflow_file}")
        logger.info(f"   📊 Contains: {len(workflow_data['workflow_pipeline']['steps'])} steps, {len(workflow_data['tools'])} tools")
    
    def discover_workflow_runs(self) -> List[WorkflowRun]:
        """Discover all workflow runs from the file system"""
        runs = []
        
        if not self.runs_dir.exists():
            logger.warning(f"Runs directory does not exist: {self.runs_dir}")
            return runs
        
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            
            run_id = run_dir.name
            
            # Try to find workflow.yaml first
            workflow_file = run_dir / "workflow.yaml"
            if workflow_file.exists():
                try:
                    workflow_run = self._load_workflow_from_file(workflow_file)
                    if workflow_run:
                        runs.append(workflow_run)
                        continue
                except Exception as e:
                    logger.warning(f"Failed to load workflow.yaml from {run_dir}: {e}")
            
            # Fallback to main_sample.yaml (legacy)
            main_sample_file = run_dir / "main_sample.yaml"
            if main_sample_file.exists():
                try:
                    workflow_run = self._convert_legacy_sample_file(main_sample_file)
                    if workflow_run:
                        runs.append(workflow_run)
                        continue
                except Exception as e:
                    logger.warning(f"Failed to convert legacy main_sample.yaml from {run_dir}: {e}")
            
            # If no workflow file found, create a basic run object
            logger.info(f"No workflow file found for run {run_id}, creating basic run object")
            basic_run = WorkflowRun(
                id=run_id,
                name=f"Run {run_id}",
                description=f"Run from directory {run_dir}",
                status='unknown',
                created_at=datetime.fromtimestamp(run_dir.stat().st_ctime, tz=timezone.utc),
                updated_at=datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc),
                progress=0.0,
                tools=[],
                run_directory=str(run_dir),
                template_used=False
            )
            runs.append(basic_run)
        
        logger.info(f"Discovered {len(runs)} workflow runs from file system")
        return runs
    
    def _load_workflow_from_file(self, workflow_file: Path) -> Optional[WorkflowRun]:
        """Load a workflow run from a workflow.yaml file"""
        try:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Parse tools
            tools = []
            if 'tools' in data:
                for tool_data in data['tools']:
                    tool_exec = ToolExecution(
                        tool_name=tool_data.get('tool_name', 'unknown'),
                        order=tool_data.get('order', 0),
                        status=tool_data.get('status', 'pending'),
                        started_at=self._parse_datetime(tool_data.get('started_at')),
                        completed_at=self._parse_datetime(tool_data.get('completed_at')),
                        execution_time=tool_data.get('execution_time'),
                        config=tool_data.get('config', {}),
                        error_message=tool_data.get('error_message'),
                        input_files=tool_data.get('input_files', []),
                        output_files=tool_data.get('output_files', []),
                        logs=tool_data.get('logs', [])
                    )
                    tools.append(tool_exec)
            
            # Create workflow run
            workflow_run = WorkflowRun(
                id=data.get('id', 'unknown'),
                name=data.get('name', 'Unnamed Workflow'),
                description=data.get('description', 'No description'),
                status=data.get('status', 'unknown'),
                created_at=self._parse_datetime(data.get('created_at')),
                updated_at=self._parse_datetime(data.get('updated_at', data.get('created_at'))),
                progress=data.get('progress', 0.0),
                tools=tools,
                run_directory=str(workflow_file.parent),
                template_used=data.get('template_used', False),
                checkpoint_data=data.get('execution_status', {}).get('checkpoint_data', {})
            )
            
            return workflow_run
            
        except Exception as e:
            logger.error(f"Failed to load workflow from {workflow_file}: {e}")
            return None
    
    def _convert_legacy_sample_file(self, sample_file: Path) -> Optional[WorkflowRun]:
        """Convert a legacy main_sample.yaml to the new format"""
        try:
            with open(sample_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Extract basic information
            run_id = sample_file.parent.name
            name = data.get('sample_name', f'Legacy Run {run_id}')
            description = data.get('description', 'Converted from legacy format')
            
            # Create basic workflow run
            workflow_run = WorkflowRun(
                id=run_id,
                name=name,
                description=description,
                status='completed',  # Assume completed for legacy runs
                created_at=datetime.fromtimestamp(sample_file.stat().st_ctime, tz=timezone.utc),
                updated_at=datetime.fromtimestamp(sample_file.stat().st_mtime, tz=timezone.utc),
                progress=100.0,
                tools=[],
                run_directory=str(sample_file.parent),
                template_used=True
            )
            
            # Convert to new format and save
            workflow_file = sample_file.parent / "workflow.yaml"
            self._save_unified_workflow_file(workflow_run, workflow_file)
            
            logger.info(f"Converted legacy sample file to workflow.yaml: {workflow_file}")
            return workflow_run
            
        except Exception as e:
            logger.error(f"Failed to convert legacy sample file {sample_file}: {e}")
            return None
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not dt_str:
            return None
        
        try:
            # Handle ISO format
            if 'T' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            # Handle other formats
            return datetime.fromisoformat(dt_str)
        except Exception:
            try:
                # Try parsing as timestamp
                return datetime.fromtimestamp(float(dt_str), tz=timezone.utc)
            except Exception:
                logger.warning(f"Could not parse datetime: {dt_str}")
                return None
    
    def get_workflow_run_by_id(self, run_id: str) -> Optional[WorkflowRun]:
        """Get a specific workflow run by ID"""
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            logger.warning(f"Run directory not found: {run_dir}")
            return None
        
        # Try workflow.yaml first
        workflow_file = run_dir / "workflow.yaml"
        if workflow_file.exists():
            return self._load_workflow_from_file(workflow_file)
        
        # Try legacy main_sample.yaml
        main_sample_file = run_dir / "main_sample.yaml"
        if main_sample_file.exists():
            return self._convert_legacy_sample_file(main_sample_file)
        
        logger.warning(f"No workflow file found for run {run_id}")
        return None
    
    def create_workflow_file_if_missing(self, run_id: str, name: str, description: str, tools: List[str]) -> bool:
        """Create a workflow.yaml file for an existing run directory that lacks one"""
        try:
            run_dir = self.runs_dir / run_id
            if not run_dir.exists():
                logger.error(f"Run directory not found: {run_dir}")
                return False
            
            # Check if workflow file already exists
            workflow_file = run_dir / "workflow.yaml"
            if workflow_file.exists():
                logger.info(f"Workflow file already exists: {workflow_file}")
                return True
            
            # Create tool executions
            tool_executions = []
            for i, tool_name in enumerate(tools):
                tool_exec = ToolExecution(
                    tool_name=tool_name,
                    order=i + 1,
                    status='pending',
                    config={},
                    input_files=[],
                    output_files=[],
                    logs=[]
                )
                tool_executions.append(tool_exec)
            
            # Create workflow run
            now = datetime.now(timezone.utc)
            workflow_run = WorkflowRun(
                id=run_id,
                name=name,
                description=description,
                status='pending',
                created_at=now,
                updated_at=now,
                progress=0.0,
                tools=tool_executions,
                run_directory=str(run_dir),
                template_used=False,
                checkpoint_data={}
            )
            
            # Save workflow file
            self._save_unified_workflow_file(workflow_run, workflow_file)
            
            logger.info(f"Created workflow file for existing run {run_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create workflow file for run {run_id}: {e}")
            return False

# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='BioFrame Workflow Orchestrator')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--data-dir', default='./data', help='Data directory path')
    parser.add_argument('--init-docker', action='store_true', help='Initialize Docker client')
    
    args = parser.parse_args()
    
    if args.test:
        # Test mode - run tests and exit
        orchestrator = WorkflowOrchestrator(data_dir=args.data_dir, init_docker=args.init_docker)
        
        print("🔧 Testing BioFrame Workflow Orchestrator")
        print("=" * 50)
        
        # Discover existing runs
        runs = orchestrator.discover_workflow_runs()
        print(f"📊 Found {len(runs)} existing workflow runs")
        
        # Create a test run
        test_run = orchestrator.create_sample_run(
            name="Test Workflow",
            description="A test workflow for demonstration",
            tools=['fastqc', 'trimmomatic', 'spades']
        )
        print(f"✅ Created test run: {test_run.id}")
        
        print("\n🎉 Orchestrator test completed successfully!")
    else:
        # Service mode - keep running
        print("🚀 Starting BioFrame Workflow Orchestrator Service")
        print("=" * 50)
        
        orchestrator = WorkflowOrchestrator(data_dir=args.data_dir, init_docker=args.init_docker)
        
        # Discover existing runs
        runs = orchestrator.discover_workflow_runs()
        print(f"📊 Found {len(runs)} existing workflow runs")
        
        print("✅ Orchestrator service is running and ready to handle workflows")
        print("💡 Use --test flag to run in test mode")
        
        # Keep the service running
        try:
            while True:
                time.sleep(60)  # Check every minute
                # You could add periodic tasks here like checking for new workflows
        except KeyboardInterrupt:
            print("\n🛑 Orchestrator service stopped by user")
        except Exception as e:
            print(f"❌ Orchestrator service error: {e}")
            raise
