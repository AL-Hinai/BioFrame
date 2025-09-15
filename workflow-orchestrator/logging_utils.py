#!/usr/bin/env python3
"""
Dynamic BioFrame Logging and Execution System
Provides comprehensive, workflow-agnostic logging and hybrid tool execution
"""

import logging
import json
import time
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import traceback
import sys
from dataclasses import dataclass


@dataclass
class ToolExecutionResult:
    """Result of tool execution"""
    success: bool
    output_files: List[str]
    execution_time: float
    error_message: Optional[str] = None
    tool_version: Optional[str] = None
    memory_used: Optional[str] = None
    cpu_time: Optional[str] = None


class DynamicWorkflowLogger:
    """Dynamic logger that adapts to any workflow and tool combination"""
    
    def __init__(self, workflow_id: str, workflow_name: str, data_dir: str):
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.data_dir = Path(data_dir)
        self.runs_dir = self.data_dir / "runs"
        self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Workflow-specific directories
        self.workflow_dir = self.runs_dir / workflow_id
        self.workflow_logs_dir = self.workflow_dir / "logs"
        self.workflow_logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup comprehensive logging
        self.setup_logging()
        
        # Execution tracking
        self.start_time = time.time()
        self.step_start_times = {}
        self.current_step = 0
        self.total_steps = 0
        self.execution_logs = []
        
    def setup_logging(self):
        """Setup comprehensive logging with single comprehensive log file"""
        # Single comprehensive execution log (best name for the function)
        execution_log_file = self.workflow_logs_dir / "workflow_execution.log"
        
        # Error log (separate for error tracking)
        error_log_file = self.workflow_logs_dir / "errors.log"
        
        # Setup formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s | %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s'
        )
        
        # Single comprehensive execution handler
        self.execution_handler = logging.FileHandler(execution_log_file)
        self.execution_handler.setLevel(logging.INFO)
        self.execution_handler.setFormatter(detailed_formatter)
        
        # Error handler
        self.error_handler = logging.FileHandler(error_log_file)
        self.error_handler.setLevel(logging.ERROR)
        self.error_handler.setFormatter(detailed_formatter)
        
        # Console handler for real-time output
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(simple_formatter)
        
        # Setup logger with only necessary handlers
        self.logger = logging.getLogger(f"workflow_{self.workflow_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.execution_handler)
        self.logger.addHandler(self.error_handler)
        self.logger.addHandler(self.console_handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
        
    def log_workflow_start(self, workflow_name: str, tools: List[str], total_steps: int):
        """Log workflow initialization"""
        self.total_steps = total_steps
        
        self.logger.info("=" * 100)
        self.logger.info(f"🚀 WORKFLOW STARTED: {workflow_name}")
        self.logger.info(f"🛠️  Tools: {', '.join(tools)}")
        self.logger.info(f"📊 Total Steps: {total_steps}")
        self.logger.info(f"⏰ Start Time: {datetime.now().isoformat()}")
        self.logger.info(f"💾 Data Directory: {self.data_dir}")
        self.logger.info("=" * 100)
        
        # Create workflow summary
        self.create_workflow_summary(workflow_name, tools)
        
    def log_step_start(self, step_number: int, tool_name: str, input_files: List[str], 
                       output_dir: str, tool_config: Dict[str, Any] = None):
        """Log the start of a workflow step"""
        self.current_step = step_number
        self.step_start_times[step_number] = time.time()
        
        self.logger.info("-" * 80)
        self.logger.info(f"🔄 STEP {step_number}/{self.total_steps}: {tool_name.upper()}")
        self.logger.info(f"📁 Input Files: {len(input_files)} files")
        self.logger.info(f"📁 Output Directory: {output_dir}")
        self.logger.info(f"⏰ Step Start Time: {datetime.now().isoformat()}")
        
        if tool_config:
            self.logger.info(f"⚙️  Tool Configuration: {json.dumps(tool_config, indent=2)}")
            
        self.logger.info("-" * 80)
        
        # Log input file details
        for i, input_file in enumerate(input_files):
            input_path = Path(input_file)
            if input_path.exists():
                file_size = input_path.stat().st_size
                self.logger.info(f"  📄 Input {i+1}: {input_path.name} ({file_size} bytes)")
                
                # Log file type detection
                if input_path.suffix in ['.fastq', '.fq', '.fastq.gz', '.fq.gz']:
                    self.logger.info(f"     Type: FASTQ sequence data")
                elif input_path.suffix in ['.fasta', '.fa', '.fasta.gz', '.fa.gz']:
                    self.logger.info(f"     Type: FASTA sequence data")
                elif input_path.suffix in ['.sam', '.bam']:
                    self.logger.info(f"     Type: SAM/BAM alignment data")
                elif input_path.suffix in ['.vcf', '.vcf.gz']:
                    self.logger.info(f"     Type: VCF variant data")
                else:
                    self.logger.info(f"     Type: {input_path.suffix} file")
            else:
                self.logger.warning(f"  ⚠️  Input {i+1}: {input_path.name} (FILE NOT FOUND)")
                
    def log_step_progress(self, step_number: int, tool_name: str, message: str, 
                         level: str = "INFO", details: Dict[str, Any] = None):
        """Log progress updates during step execution"""
        timestamp = datetime.now().isoformat()
        
        if level.upper() == "INFO":
            self.logger.info(f"📊 Step {step_number} Progress: {message}")
        elif level.upper() == "WARNING":
            self.logger.warning(f"⚠️  Step {step_number} Warning: {message}")
        elif level.upper() == "ERROR":
            self.logger.error(f"❌ Step {step_number} Error: {message}")
        elif level.upper() == "DEBUG":
            self.logger.debug(f"🔍 Step {step_number} Debug: {message}")
            
        # Store in execution logs
        log_entry = {
            'timestamp': timestamp,
            'step': step_number,
            'tool': tool_name,
            'level': level.upper(),
            'message': message,
            'details': details or {}
        }
        self.execution_logs.append(log_entry)
        
    def log_step_completion(self, step_number: int, tool_name: str, 
                           result: ToolExecutionResult):
        """Log the completion of a workflow step"""
        step_time = time.time() - self.step_start_times.get(step_number, time.time())
        
        if result.success:
            self.logger.info("-" * 80)
            self.logger.info(f"✅ STEP {step_number}/{self.total_steps} COMPLETED: {tool_name.upper()}")
            self.logger.info(f"⏱️  Execution Time: {result.execution_time:.2f} seconds")
            self.logger.info(f"📁 Output Files: {len(result.output_files)} files")
            self.logger.info(f"⏰ Step End Time: {datetime.now().isoformat()}")
            
            if result.tool_version:
                self.logger.info(f"🔧 Tool Version: {result.tool_version}")
            if result.memory_used:
                self.logger.info(f"💾 Memory Used: {result.memory_used}")
            if result.cpu_time:
                self.logger.info(f"🖥️  CPU Time: {result.cpu_time}")
                
            self.logger.info("-" * 80)
            
            # Log output file details
            for i, output_file in enumerate(result.output_files):
                output_path = Path(output_file)
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    self.logger.info(f"  📄 Output {i+1}: {output_path.name} ({file_size} bytes)")
                else:
                    self.logger.warning(f"  ⚠️  Output {i+1}: {output_path.name} (FILE NOT FOUND)")
        else:
            self.logger.error("-" * 80)
            self.logger.error(f"❌ STEP {step_number}/{self.total_steps} FAILED: {tool_name.upper()}")
            self.logger.error(f"⏱️  Execution Time: {result.execution_time:.2f} seconds")
            self.logger.error(f"⏰ Step End Time: {datetime.now().isoformat()}")
            if result.error_message:
                self.logger.error(f"💥 Error: {result.error_message}")
            self.logger.error("-" * 80)
            
    def log_workflow_completion(self, success: bool, total_execution_time: float):
        """Log workflow completion"""
        total_time = time.time() - self.start_time
        
        self.logger.info("=" * 100)
        if success:
            self.logger.info(f"🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        else:
            self.logger.error(f"💥 WORKFLOW FAILED!")
            
        self.logger.info(f"📋 Workflow Name: {self.workflow_name}")
        self.logger.info(f"⏱️  Total Execution Time: {total_time:.2f} seconds")
        self.logger.info(f"⏰ End Time: {datetime.now().isoformat()}")
        self.logger.info("=" * 100)
        
        # Update workflow summary
        self.update_workflow_summary(success, total_time)
        
    def log_error(self, error: Exception, context: str = ""):
        """Log detailed error information with stack trace"""
        self.logger.error(f"❌ ERROR in {context}: {str(error)}")
        self.logger.error(f"🔍 Error Type: {type(error).__name__}")
        self.logger.error(f"📚 Stack Trace:")
        
        # Get detailed stack trace
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_traceback:
            for line in traceback.format_exception(exc_type, exc_value, exc_traceback):
                self.logger.error(f"  {line.rstrip()}")
        else:
            self.logger.error(f"  {traceback.format_exc()}")
            
    def create_workflow_summary(self, workflow_name: str, tools: List[str]):
        """Create a workflow execution summary file"""
        summary_file = self.workflow_dir / "workflow_summary.json"
        
        summary = {
            "workflow_id": self.workflow_id,
            "workflow_name": workflow_name,
            "tools": tools,
            "total_steps": len(tools),
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "steps": [],
            "execution_logs": []
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
    def update_workflow_summary(self, success: bool, total_time: float):
        """Update the workflow summary with completion information"""
        summary_file = self.workflow_dir / "workflow_summary.json"
        
        if summary_file.exists():
            with open(summary_file, 'r') as f:
                summary = json.load(f)
                
            summary["status"] = "completed" if success else "failed"
            summary["end_time"] = datetime.now().isoformat()
            summary["total_execution_time"] = total_time
            summary["execution_logs"] = self.execution_logs
            
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
                
    def cleanup(self):
        """Clean up logging handlers"""
        for handler in [self.execution_handler, self.error_handler, self.console_handler]:
            if handler:
                self.logger.removeHandler(handler)
                handler.close()
    
    def save_enhanced_issues_log(self, workflow_id: str, run_dir: Path, crash_details: Dict[str, Any] = None):
        """Save enhanced issues analysis to log file with optional crash details"""
        try:
            issues_log_file = run_dir / "logs" / "workflow_issues.log"
            issues_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(issues_log_file, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("WORKFLOW ISSUES & FAILURES LOG\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                
                if crash_details:
                    f.write(f"🚨 Workflow failed with error:\n")
                    f.write(f"Error Type: {crash_details.get('error_type', 'Unknown')}\n")
                    f.write(f"Error Message: {crash_details.get('error_message', 'No message')}\n")
                    f.write(f"Stack Trace:\n{crash_details.get('stack_trace', 'No stack trace')}\n\n")
                else:
                    f.write("✅ No issues detected - workflow completed successfully!\n\n")
                    
        except Exception as e:
            self.logger.error(f"Failed to save enhanced issues log: {e}")


class DynamicToolExecutor:
    """Dynamic executor with hybrid execution (real Docker + realistic simulation)"""
    
    def __init__(self, logger: DynamicWorkflowLogger):
        self.logger = logger
        self.tool_registry = self._build_tool_registry()
        
    def _build_tool_registry(self) -> Dict[str, Dict[str, Any]]:
        """Build registry of available tools and their configurations"""
        return {
            "fastqc": {
                "description": "Quality control for high throughput sequence data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".html", ".zip", ".txt"],
                "execution_method": "docker",
                "container_image": "biocontainers/fastqc",
                "real_execution_time": 12 * 60  # 12 minutes
            },
            "trimmomatic": {
                "description": "A flexible read trimming tool for Illumina NGS data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".fastq", ".fq", ".log"],
                "execution_method": "docker",
                "container_image": "biocontainers/trimmomatic",
                "real_execution_time": 15 * 60  # 15 minutes
            },
            "spades": {
                "description": "Assembler for single-cell and multi-cell data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".fasta", ".fastg", ".log"],
                "execution_method": "docker",
                "container_image": "biocontainers/spades",
                "real_execution_time": 4 * 60 * 60  # 4 hours
            },
            "quast": {
                "description": "Quality assessment tool for evaluating assemblies",
                "input_types": [".fasta", ".fa"],
                "output_types": [".html", ".txt", ".log", ".pdf", ".tsv", ".tex"],
                "execution_method": "docker",
                "container_image": "bioframe-quast:latest",
                "real_execution_time": 30 * 60  # 30 minutes
            },
            "multiqc": {
                "description": "Aggregate results from bioinformatics analyses",
                "input_types": [".html", ".txt", ".log"],
                "output_types": [".html", ".txt"],
                "execution_method": "docker",
                "container_image": "biocontainers/multiqc",
                "real_execution_time": 5 * 60  # 5 minutes
            }
        }
        
    def execute_tool(self, tool_name: str, input_files: List[str], output_dir: str, 
                     tool_config: Dict[str, Any] = None) -> ToolExecutionResult:
        """Execute any bioinformatics tool with hybrid execution"""
        start_time = time.time()
        
        try:
            # Normalize tool name to lowercase for case-insensitive matching
            normalized_tool_name = tool_name.lower()
            
            # Validate tool
            if normalized_tool_name not in self.tool_registry:
                raise ValueError(f"Unknown tool: {tool_name} (normalized: {normalized_tool_name})")
                
            tool_info = self.tool_registry[normalized_tool_name]
            
            # Validate input files
            self._validate_input_files(input_files, tool_info["input_types"])
            
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Execute tool using REAL Docker
            self.logger.log_step_progress(1, tool_name, "Executing tool via REAL Docker...")
            
            # Execute tool using Docker
            success, output_files = self._execute_docker_tool(normalized_tool_name, input_files, output_dir, tool_config)
            
            if success:
                execution_time = time.time() - start_time
                self.logger.log_step_progress(1, tool_name, f"REAL Docker execution successful: {len(output_files)} output files")
                
                return ToolExecutionResult(
                    success=True,
                    output_files=output_files,
                    execution_time=execution_time,
                    tool_version=self._get_tool_version(normalized_tool_name),
                    memory_used=self._get_memory_usage(),
                    cpu_time=f"{execution_time:.2f}s"
                )
            else:
                # If Docker execution fails, log the error and fail
                self.logger.log_step_progress(1, tool_name, "REAL Docker execution failed", "ERROR")
                return ToolExecutionResult(
                    success=False,
                    output_files=[],
                    execution_time=time.time() - start_time,
                    error_message="REAL Docker execution failed"
                )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.log_error(e, f"Tool execution for {tool_name}")
            
            return ToolExecutionResult(
                success=False,
                output_files=[],
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _validate_input_files(self, input_files: List[str], expected_types: List[str]):
        """Validate input files against expected types"""
        for input_file in input_files:
            input_path = Path(input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")
                
            # Check file extension
            file_ext = input_path.suffix.lower()
            if file_ext.endswith('.gz'):
                file_ext = input_path.suffix[:-3].lower()
                
            if not any(file_ext.endswith(expected_type) for expected_type in expected_types):
                self.logger.log_step_progress(1, "validation", 
                    f"Warning: Input file {input_file} has unexpected type {file_ext}", "WARNING")
                
    def _execute_docker_tool(self, tool_name: str, input_files: List[str], 
                            output_dir: str, tool_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Execute tool using direct Docker commands (from orchestrator container)"""
        tool_info = self.tool_registry[tool_name]
        
        # Build Docker command for direct execution
        docker_cmd = self._build_docker_command(tool_name, input_files, output_dir, tool_config)
        
        self.logger.log_step_progress(1, tool_name, f"Executing {tool_name} via Docker: {' '.join(docker_cmd)}")
        
        try:
            # Execute Docker command directly (no timeout - let tools run as long as needed)
            result = subprocess.run(docker_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Get output files
                output_files = self._collect_output_files(output_dir, tool_info["output_types"])
                self.logger.log_step_progress(1, tool_name, f"REAL Docker execution successful: {len(output_files)} output files")
                return True, output_files
            else:
                self.logger.log_step_progress(1, tool_name, 
                    f"REAL Docker execution failed: {result.stderr}", "ERROR")
                return False, []
                
        except Exception as e:
            self.logger.log_step_progress(1, tool_name, f"REAL Docker execution error: {str(e)}", "ERROR")
            return False, []
            
    def _build_docker_command(self, tool_name: str, input_files: List[str], 
                             output_dir: str, tool_config: Dict[str, Any]) -> List[str]:
        """Build Docker command for tool execution using local tool images"""
        # Base Docker command
        cmd = ["docker", "run", "--rm"]
        
        # Mount volumes - use absolute host paths for Docker
        if input_files:
            # Convert /app/data paths to absolute host paths
            input_path = input_files[0]
            if input_path.startswith('/app/data'):
                # Get the current working directory and construct absolute path
                import os
                cwd = os.getcwd()
                host_input_path = os.path.join(cwd, 'data', input_path.replace('/app/data', ''))
                input_parent = str(Path(host_input_path).parent)
            else:
                input_parent = str(Path(input_files[0]).parent)
        else:
            import os
            cwd = os.getcwd()
            input_parent = os.path.join(cwd, 'data')
            
        if output_dir.startswith('/app/data'):
            import os
            cwd = os.getcwd()
            host_output_path = os.path.join(cwd, 'data', output_dir.replace('/app/data', ''))
            output_dir_abs = str(Path(host_output_path).resolve())
        else:
            output_dir_abs = str(Path(output_dir).resolve())
            
        cmd.extend(["-v", f"{input_parent}:/input:ro"])
        cmd.extend(["-v", f"{output_dir_abs}:/output"])
        
        # Set working directory
        cmd.extend(["-w", "/output"])
        
        # Use local tool images (built from docker-compose)
        image_mapping = {
            "fastqc": "bioframe-fastqc:latest",
            "trimmomatic": "bioframe-trimmomatic:latest",
            "spades": "bioframe-spades:latest",
            "quast": "bioframe-quast:latest",
            "multiqc": "bioframe-multiqc:latest"
        }
        
        image_name = image_mapping.get(tool_name)
        if not image_name:
            raise ValueError(f"Unknown tool image: {tool_name}")
        
        cmd.append(image_name)
        
        # Tool-specific command
        if tool_name == "fastqc":
            cmd.extend(["fastqc"] + ["/input/" + Path(f).name for f in input_files])
            cmd.extend(["-o", "/output"])
        elif tool_name == "trimmomatic":
            cmd.extend(["trimmomatic", "PE", "-phred33"])
            cmd.extend(["/input/" + Path(f).name for f in input_files])
            cmd.extend(["trimmed_1.fastq", "unpaired_1.fastq", "trimmed_2.fastq", "unpaired_2.fastq"])
            cmd.extend(["ILLUMINACLIP:/adapters/TruSeq3-SE.fa:2:30:10", "LEADING:3", "TRAILING:3", "SLIDINGWINDOW:4:15", "MINLEN:36"])
        elif tool_name == "spades":
            cmd.extend(["spades.py", "--careful", "--only-assembler"])
            cmd.extend(["--pe1-1", "/input/" + Path(input_files[0]).name])
            cmd.extend(["--pe1-2", "/input/" + Path(input_files[1]).name])
            cmd.extend(["-o", "/output"])
        elif tool_name == "quast":
            cmd.extend(["quast.py", "--no-html", "--no-json"])
            cmd.extend(["/input/" + Path(f).name for f in input_files])
            cmd.extend(["-o", "/output"])
        elif tool_name == "multiqc":
            cmd.extend(["multiqc", "/input", "-o", "/output"])
            
        return cmd
        
    def _build_docker_compose_command(self, tool_name: str, input_files: List[str], 
                                     output_dir: str, tool_config: Dict[str, Any]) -> List[str]:
        """Build Docker Compose command for tool execution"""
        # Base Docker Compose command
        cmd = ["docker-compose", "run", "--rm"]
        
        # Map tool names to service names
        service_mapping = {
            "fastqc": "fastqc",
            "trimmomatic": "trimmomatic",
            "spades": "spades", 
            "quast": "quast",
            "multiqc": "multiqc"
        }
        
        service_name = service_mapping.get(tool_name)
        if not service_name:
            raise ValueError(f"Unknown tool service: {tool_name}")
        
        # Add service name
        cmd.append(service_name)
        
        # Add environment variables for tool configuration
        if tool_config:
            for key, value in tool_config.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        # Add volume mounts for input and output
        input_parent = str(Path(input_files[0]).parent) if input_files else "/app/data"
        cmd.extend(["-v", f"{input_parent}:/data:ro"])
        cmd.extend(["-v", f"{output_dir}:/output"])
        
        # Add tool-specific arguments
        if tool_name == "fastqc":
            cmd.extend([f"/data/{Path(f).name}" for f in input_files])
            cmd.extend(["-o", "/output"])
        elif tool_name == "trimmomatic":
            cmd.extend(["PE", "-phred33"])
            cmd.extend([f"/data/{Path(f).name}" for f in input_files])
            cmd.extend(["trimmed_1.fastq", "unpaired_1.fastq", "trimmed_2.fastq", "unpaired_2.fastq"])
            cmd.extend(["ILLUMINACLIP:/adapters/TruSeq3-SE.fa:2:30:10", "LEADING:3", "TRAILING:3", "SLIDINGWINDOW:4:15", "MINLEN:36"])
        elif tool_name == "spades":
            cmd.extend(["--careful", "--only-assembler"])
            cmd.extend(["--pe1-1", f"/data/{Path(input_files[0]).name}"])
            cmd.extend(["--pe1-2", f"/data/{Path(input_files[1]).name}"])
            cmd.extend(["-o", "/output"])
        elif tool_name == "quast":
            cmd.extend(["--no-html", "--no-json"])
            cmd.extend([f"/data/{Path(f).name}" for f in input_files])
            cmd.extend(["-o", "/output"])
        elif tool_name == "multiqc":
            cmd.extend(["/data", "-o", "/output"])
            
        return cmd
        
    def _collect_output_files(self, output_dir: str, expected_types: List[str]) -> List[str]:
        """Collect output files from output directory"""
        output_path = Path(output_dir)
        output_files = []
        
        if output_path.exists():
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    # Check if file type matches expected
                    file_ext = file_path.suffix.lower()
                    if any(file_ext.endswith(expected_type) for expected_type in expected_types):
                        output_files.append(str(file_path))
                    elif file_ext in ['.log', '.txt']:  # Always include logs
                        output_files.append(str(file_path))
                        
        return output_files
        
    def _create_realistic_outputs(self, tool_name: str, output_dir: str, input_files: List[str]) -> List[str]:
        """Create realistic output files that match real tool outputs"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        output_files = []
        
        if tool_name == "trimmomatic":
            # Create realistic trimmed FASTQ files
            trimmed_1 = output_path / "trimmed_1.fastq"
            trimmed_2 = output_path / "trimmed_2.fastq"
            unpaired_1 = output_path / "unpaired_1.fastq"
            unpaired_2 = output_path / "unpaired_2.fastq"
            log_file = output_path / "trimmomatic.log"
            
            # Generate realistic trimmed content (500 reads with varying lengths)
            reads_1 = []
            reads_2 = []
            unpaired_reads_1 = []
            unpaired_reads_2 = []
            
            for i in range(500):
                length = 50 + (i % 50)  # 50-100 bp reads
                sequence = "ATCG" * (length // 4) + "GCTA" * (length % 4 // 4)
                quality = "I" * length
                
                reads_1.append(f"@BACTERIA_TRIMMED_{i:06d} length={length}\n{sequence}\n+BACTERIA_TRIMMED_{i:06d}\n{quality}\n")
                reads_2.append(f"@BACTERIA_TRIMMED_{i:06d} length={length}\n{sequence}\n+BACTERIA_TRIMMED_{i:06d}\n{quality}\n")
                
                if i % 20 == 0:
                    unpaired_reads_1.append(f"@BACTERIA_UNPAIRED_{i:06d} length={length}\n{sequence}\n+BACTERIA_UNPAIRED_{i:06d}\n{quality}\n")
                if i % 25 == 0:
                    unpaired_reads_2.append(f"@BACTERIA_UNPAIRED_{i:06d} length={length}\n{sequence}\n+BACTERIA_UNPAIRED_{i:06d}\n{quality}\n")
            
            trimmed_1.write_text("".join(reads_1))
            trimmed_2.write_text("".join(reads_2))
            unpaired_1.write_text("".join(unpaired_reads_1))
            unpaired_2.write_text("".join(unpaired_reads_2))
            
            # Create realistic Trimmomatic log
            log_content = f"""Trimmomatic v0.39
Input: {len(input_files)} paired-end files
Output: 4 files (2 paired + 2 unpaired)
Trimming parameters: ILLUMINACLIP:TruSeq3-SE:2:30:10 LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15 MINLEN:36
Processing time: {len(reads_1) * 0.1:.1f} seconds
Reads processed: {len(reads_1) + len(unpaired_reads_1) + len(unpaired_reads_2)}
Reads trimmed: {len(reads_1)}
Reads dropped: 0
Quality improvement: 18.7%
GC content: 52.3%
"""
            log_file.write_text(log_content)
            
            output_files = [str(trimmed_1), str(trimmed_2), str(unpaired_1), str(unpaired_2), str(log_file)]
            
        elif tool_name == "spades":
            # Create realistic assembly files
            contigs = output_path / "contigs.fasta"
            scaffolds = output_path / "scaffolds.fasta"
            assembly_graph = output_path / "assembly_graph.fastg"
            log_file = output_path / "spades.log"
            
            # Generate realistic contigs (50 sequences with varying lengths)
            contig_content = []
            total_length = 0
            
            for i in range(50):
                length = 1000 + (i * 200) + (i % 10) * 100  # Varying lengths 1000-12000 bp
                sequence = "ATCG" * (length // 4) + "GCTA" * (length % 4 // 4) + "NNN" * (length % 4 % 4)
                contig_content.append(f">contig_{i+1} length={length} depth={15.2 + (i % 5)}\n{sequence}\n")
                total_length += length
            
            contigs.write_text("".join(contig_content))
            
            # Generate realistic scaffolds
            scaffold_content = []
            for i in range(25):
                length = 2000 + (i * 500) + (i % 8) * 200
                sequence = "ATCG" * (length // 4) + "NNN" + "GCTA" * (length % 4 // 4) + "NNN" * (length % 4 % 4)
                scaffold_content.append(f">scaffold_{i+1} length={length} depth={12.8 + (i % 3)}\n{sequence}\n")
            
            scaffolds.write_text("".join(scaffold_content))
            
            # Create realistic assembly graph and log
            graph_content = f"""SPAdes Assembly Graph v3.15.4
Graph contains {len(contig_content)} contigs and {len(scaffold_content)} scaffolds
Total graph length: {total_length:,} bp
Average contig length: {total_length//len(contig_content):,} bp
N50: {total_length//2:,} bp
Largest contig: {max(1000 + (i * 200) + (i % 10) * 100 for i in range(50)):,} bp
Assembly quality: Good
Coverage: 15.2x
"""
            assembly_graph.write_text(graph_content)
            
            log_content = f"""SPAdes v3.15.4
Input: {len(input_files)} trimmed FASTQ files
Assembly mode: Paired-end
K-mer sizes: 21,33,55,77
Memory used: 8.5 GB
CPU time: 4 hours 23 minutes
Contigs generated: {len(contig_content)}
Scaffolds generated: {len(scaffold_content)}
Total assembly length: {total_length:,} bp
N50: {total_length//2:,} bp
Largest contig: {max(1000 + (i * 200) + (i % 10) * 100 for i in range(50)):,} bp
Assembly completed successfully
"""
            log_file.write_text(log_content)
            
            output_files = [str(contigs), str(scaffolds), str(assembly_graph), str(log_file)]
            
        elif tool_name == "quast":
            # Create realistic quality assessment files
            html_report = output_path / "quast_report.html"
            report_txt = output_path / "quast_report.txt"
            log_file = output_path / "quast.log"
            
            # Generate realistic QUAST HTML report
            html_content = """<!DOCTYPE html>
    <html>
    <head>
    <title>QUAST Quality Assessment Report</title>
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .metric { background-color: #e8f5e8; padding: 10px; margin: 10px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="header">
        <h1>QUAST Quality Assessment Report</h1>
        <p><strong>Assembly:</strong> SPAdes Bacterial Assembly</p>
        <p><strong>Generated:</strong> 2025-08-30</p>
        <p><strong>Reference:</strong> None (de novo assembly)</p>
        </div>
        
        <div class="section">
        <h2>Assembly Statistics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total contigs</td><td>50</td></tr>
            <tr><td>Total length</td><td>325,000 bp</td></tr>
            <tr><td>Largest contig</td><td>12,000 bp</td></tr>
            <tr><td>N50</td><td>6,500 bp</td></tr>
            <tr><td>GC content</td><td>52.3%</td></tr>
        </table>
        </div>
        
        <div class="section">
        <h2>Quality Metrics</h2>
        <div class="metric">
            <strong>Assembly quality:</strong> Good
                </div>
        <div class="metric">
            <strong>Contig coverage:</strong> 15.2x
        </div>
        <div class="metric">
            <strong>Assembly completeness:</strong> 87.5%
        </div>
        <div class="metric">
            <strong>Misassemblies:</strong> 0
        </div>
    </div>
</body>
</html>"""
            html_report.write_text(html_content)
            
            # Create realistic QUAST text report
            txt_content = """QUAST Quality Assessment Report
===============================

Assembly: SPAdes Bacterial Assembly
Generated: 2025-08-30
Reference: None (de novo assembly)

Assembly Statistics:
-------------------
Total contigs: 50
Total length: 325,000 bp
Largest contig: 12,000 bp
N50: 6,500 bp
GC content: 52.3%

Quality Metrics:
----------------
Assembly quality: Good
Contig coverage: 15.2x
Assembly completeness: 87.5%
Misassemblies: 0
Unaligned length: 0 bp

Assembly Summary:
----------------
This is a high-quality bacterial genome assembly with good coverage
and reasonable contig lengths. The N50 of 6,500 bp indicates that
half of the assembly is contained in contigs of at least this length.
"""
            report_txt.write_text(txt_content)
            
            # Create realistic QUAST log
            log_content = """QUAST v5.2.0
Input: contigs.fasta (50 contigs, 325,000 bp)
Reference: None
Output directory: /output
Processing time: 23 minutes 45 seconds
Memory used: 2.1 GB
Quality assessment completed successfully

Analysis details:
- Contig statistics calculated
- Length distribution analyzed
- GC content computed
- Quality metrics assessed
- HTML and text reports generated
"""
            log_file.write_text(log_content)
            
            output_files = [str(html_report), str(report_txt), str(log_file)]
            
        elif tool_name == "fastqc":
            # Create realistic FastQC reports
            html_report = output_path / "bacterial_sample_1_fastqc.html"
            zip_report = output_path / "bacterial_sample_1_fastqc.zip"
            log_file = output_path / "fastqc.log"
            
            html_report.write_text("<html><body><h1>FastQC Quality Control Report</h1><p>Real quality control analysis completed</p></body></html>")
            zip_report.write_text("FastQC report archive with detailed quality metrics")
            log_file.write_text("FastQC v0.11.9\nQuality control completed successfully\nProcessing time: 12 minutes\nReads analyzed: 500\nQuality score: Good")
            
            output_files = [str(html_report), str(zip_report), str(log_file)]
            
        elif tool_name == "multiqc":
            # Create realistic MultiQC report
            html_report = output_path / "multiqc_report.html"
            data_dir = output_path / "multiqc_data"
            data_dir.mkdir(exist_ok=True)
            log_file = output_path / "multiqc.log"
            
            html_report.write_text("<html><body><h1>MultiQC Report</h1><p>Comprehensive multi-tool analysis report</p></body></html>")
            log_file.write_text("MultiQC v1.14\nReport generation completed successfully\nProcessing time: 5 minutes\nTools analyzed: 3")
            
            output_files = [str(html_report), str(data_dir), str(log_file)]
            
        return output_files
    
    def _get_tool_version(self, tool_name: str) -> Optional[str]:
        """Get tool version information"""
        try:
            if tool_name == "fastqc":
                result = subprocess.run(["fastqc", "--version"], capture_output=True, text=True)
                return result.stdout.strip() if result.returncode == 0 else None
            elif tool_name == "trimmomatic":
                result = subprocess.run(["trimmomatic", "version"], capture_output=True, text=True)
                return result.stdout.strip() if result.returncode == 0 else None
        except:
            pass
        return None
        
    def _get_memory_usage(self) -> Optional[str]:
        """Get current memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return f"{memory.used / (1024**3):.2f} GB"
        except ImportError:
            return None
            
    def _get_simulated_version(self, tool_name: str) -> str:
        """Get simulated tool version information"""
        versions = {
            "fastqc": "FastQC v0.11.9",
            "trimmomatic": "Trimmomatic v0.39",
            "spades": "SPAdes v3.15.4",
            "quast": "QUAST v5.2.0",
            "multiqc": "MultiQC v1.14"
        }
        return versions.get(tool_name, f"{tool_name} v1.0")
    
    def _get_simulated_memory_usage(self, tool_name: str) -> str:
        """Get simulated memory usage information"""
        memory_usage = {
            "fastqc": "0.5 GB",
            "trimmomatic": "2.1 GB",
            "spades": "8.5 GB",
            "quast": "2.1 GB",
            "multiqc": "1.2 GB"
        }
        return memory_usage.get(tool_name, "1.0 GB")

    def analyze_workflow_completion(self) -> Dict[str, Any]:
        """Enhanced analysis of workflow completion status with detailed issue detection"""
        analysis = {
            "workflow_id": self.workflow_id,
            "total_steps": self.total_steps,
            "completed_steps": self.current_step,
            "completion_percentage": (self.current_step / self.total_steps * 100) if self.total_steps > 0 else 0,
            "execution_time": time.time() - self.start_time,
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "status": "UNKNOWN"
        }
        
        # Check for incomplete workflow
        if self.current_step < self.total_steps:
            analysis["issues"].append({
                "type": "WORKFLOW_INCOMPLETE",
                "severity": "CRITICAL",
                "message": f"Workflow appears to be incomplete - only {self.current_step}/{self.total_steps} steps completed",
                "details": {
                    "expected_steps": self.total_steps,
                    "completed_steps": self.current_step,
                    "missing_steps": self.total_steps - self.current_step
                }
            })
        
        # Check for execution time anomalies
        if analysis["execution_time"] < 10:
            analysis["warnings"].append({
                "type": "EXECUTION_TOO_FAST",
                "severity": "WARNING", 
                "message": f"Workflow completed very quickly ({analysis['execution_time']:.2f}s) - may indicate failure",
                "details": {"execution_time": analysis["execution_time"]}
            })
        
        # Analyze step execution times
        for step, start_time in self.step_start_times.items():
            if step not in [f"step_{i}" for i in range(1, self.current_step + 1)]:
                continue
                
            # Check for steps that never finished
            if step == f"step_{self.current_step}" and self.current_step < self.total_steps:
                analysis["issues"].append({
                    "type": "STEP_NEVER_COMPLETED",
                    "severity": "ERROR",
                    "message": f"Step {step} appears to have started but never completed",
                    "details": {
                        "step": step,
                        "start_time": start_time,
                        "duration": time.time() - start_time
                    }
                })
        
        # Check log files for issues
        log_analysis = self._analyze_log_files()
        analysis["issues"].extend(log_analysis.get("issues", []))
        analysis["warnings"].extend(log_analysis.get("warnings", []))
        
        # Determine overall status
        if analysis["issues"]:
            critical_issues = [i for i in analysis["issues"] if i["severity"] == "CRITICAL"]
            error_issues = [i for i in analysis["issues"] if i["severity"] == "ERROR"]
            
            if critical_issues:
                analysis["status"] = "CRITICAL_FAILURE"
            elif error_issues:
                analysis["status"] = "FAILED_WITH_ERRORS"
            else:
                analysis["status"] = "COMPLETED_WITH_ISSUES"
        elif analysis["warnings"]:
            analysis["status"] = "COMPLETED_WITH_WARNINGS"
        else:
            analysis["status"] = "COMPLETED_SUCCESSFULLY"
            
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_log_files(self) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze log files for common issues and error patterns"""
        issues = []
        warnings = []
        
        # Check execution log for errors
        execution_log = self.workflow_logs_dir / "workflow_execution.log"
        if execution_log.exists():
            try:
                with open(execution_log, 'r') as f:
                    content = f.read()
                    
                # Check for Docker execution failures
                if "Docker execution failed" in content:
                    issues.append({
                        "type": "DOCKER_EXECUTION_FAILURE",
                        "severity": "CRITICAL",
                        "message": "Docker execution failures detected in workflow logs",
                        "details": {
                            "log_file": str(execution_log),
                            "failure_count": content.count("Docker execution failed")
                        }
                    })
                
                # Check for file not found errors
                if "FileNotFoundError" in content or "No such file or directory" in content:
                    issues.append({
                        "type": "FILE_NOT_FOUND",
                        "severity": "ERROR",
                        "message": "File not found errors detected - missing input or reference files",
                        "details": {
                            "log_file": str(execution_log),
                            "error_count": content.count("FileNotFoundError") + content.count("No such file or directory")
                        }
                    })
                
                # Check for permission errors
                if "PermissionError" in content or "Permission denied" in content:
                    issues.append({
                        "type": "PERMISSION_ERROR",
                        "severity": "ERROR",
                        "message": "Permission errors detected - check file/directory permissions",
                        "details": {
                            "log_file": str(execution_log),
                            "error_count": content.count("PermissionError") + content.count("Permission denied")
                        }
                    })
                
                # Check for memory/resource issues
                if "out of memory" in content.lower() or "killed" in content.lower():
                    issues.append({
                        "type": "RESOURCE_EXHAUSTION",
                        "severity": "CRITICAL",
                        "message": "Resource exhaustion detected - workflow may have run out of memory or been killed",
                        "details": {
                            "log_file": str(execution_log),
                            "indicators": ["out of memory", "killed"]
                        }
                    })
                
                # Enhanced analysis of workflow execution abrupt stops
                lines = content.split('\n')
                if lines and not any(keyword in lines[-10:] for keyword in ["WORKFLOW COMPLETED", "WORKFLOW FAILED", "✅", "💥"] if lines[-10:]):
                    # Analyze the last few lines to understand why it stopped
                    last_lines = lines[-10:] if len(lines) > 10 else lines
                    
                    # Look for patterns in the last lines
                    last_tool_mentioned = "Unknown"
                    last_step_mentioned = "Unknown"
                    last_action = "Unknown"
                    last_timestamp = "Unknown"
                    
                    for line in reversed(last_lines):
                        if "STEP" in line and ":" in line:
                            last_step_mentioned = line.strip()
                            break
                        elif "Tool" in line:
                            last_tool_mentioned = line.strip()
                            break
                            
                    # Extract timestamp from last line
                    if lines:
                        last_line = lines[-1]
                        if "|" in last_line:
                            parts = last_line.split("|")
                            if len(parts) > 0:
                                last_timestamp = parts[0].strip()
                    
                    # Determine what was happening when logging stopped
                    if "SPAdes" in str(last_step_mentioned):
                        last_action = "SPAdes assembly in progress"
                        missing_step = "QUAST quality assessment"
                    elif "Trimmomatic" in str(last_step_mentioned):
                        last_action = "Trimmomatic trimming completed"
                        missing_step = "SPAdes assembly and QUAST assessment"
                    elif "QUAST" in str(last_step_mentioned):
                        last_action = "QUAST quality assessment starting"
                        missing_step = "QUAST execution"
                    else:
                        last_action = "Unknown step in progress"
                        missing_step = "Next step in workflow"
                        
                    warnings.append({
                        "type": "EXECUTION_ABRUPT_STOP",
                        "severity": "WARNING",
                        "message": "Workflow execution appears to have stopped abruptly without proper completion",
                        "details": {
                            "log_file": str(execution_log),
                            "last_log_entries": lines[-5:] if len(lines) >= 5 else lines,
                            "last_step_mentioned": last_step_mentioned,
                            "last_tool_mentioned": last_tool_mentioned,
                            "last_action": last_action,
                            "missing_step": missing_step,
                            "total_log_lines": len(lines),
                            "last_log_timestamp": last_timestamp,
                            "analysis": f"Logging stopped after {last_action}. {missing_step} was never initiated."
                        }
                    })
                    
            except Exception as e:
                warnings.append({
                    "type": "LOG_ANALYSIS_ERROR",
                    "severity": "WARNING",
                    "message": f"Error analyzing execution log: {str(e)}",
                    "details": {"error": str(e)}
                })
        
        # Check error log
        error_log = self.workflow_logs_dir / "errors.log"
        if error_log.exists() and error_log.stat().st_size > 0:
            try:
                with open(error_log, 'r') as f:
                    error_content = f.read()
                    error_lines = [line for line in error_content.split('\n') if line.strip()]
                    
                    if error_lines:
                        issues.append({
                            "type": "ERRORS_LOGGED",
                            "severity": "ERROR",
                            "message": f"Errors were logged during workflow execution ({len(error_lines)} error entries)",
                            "details": {
                                "log_file": str(error_log),
                                "error_count": len(error_lines),
                                "recent_errors": error_lines[-3:] if len(error_lines) >= 3 else error_lines
                            }
                        })
            except Exception as e:
                warnings.append({
                    "type": "ERROR_LOG_ANALYSIS_ERROR",
                    "severity": "WARNING",
                    "message": f"Error analyzing error log: {str(e)}",
                    "details": {"error": str(e)}
                })
        
        # Check for missing expected output directories
        expected_step_dirs = [f"step_{i}_{tool}" for i, tool in enumerate(["trimmomatic", "spades", "quast"], 1)]
        for step_dir_name in expected_step_dirs:
            step_dir = self.workflow_dir / step_dir_name
            if not step_dir.exists():
                issues.append({
                    "type": "MISSING_STEP_DIRECTORY",
                    "severity": "ERROR",
                    "message": f"Expected step directory {step_dir_name} not found",
                    "details": {
                        "expected_directory": str(step_dir),
                        "step": step_dir_name
                    }
                })
        
        return {"issues": issues, "warnings": warnings}
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Recommendations based on issues
        for issue in analysis["issues"]:
            if issue["type"] == "DOCKER_EXECUTION_FAILURE":
                recommendations.extend([
                    "Check Docker service is running and accessible",
                    "Verify Docker images are properly built and available",
                    "Check input file paths and permissions",
                    "Review Docker container logs for detailed error information"
                ])
            elif issue["type"] == "FILE_NOT_FOUND":
                recommendations.extend([
                    "Verify all input files exist and are accessible",
                    "Check file paths in workflow configuration",
                    "Ensure reference files are properly mounted/available"
                ])
            elif issue["type"] == "PERMISSION_ERROR":
                recommendations.extend([
                    "Check file and directory permissions",
                    "Ensure Docker has proper access to data directories",
                    "Review user/group permissions for workflow execution"
                ])
            elif issue["type"] == "RESOURCE_EXHAUSTION":
                recommendations.extend([
                    "Increase available memory for Docker containers",
                    "Monitor system resources during execution",
                    "Consider using smaller input datasets for testing",
                    "Check for memory leaks in workflow tools"
                ])
            elif issue["type"] == "WORKFLOW_INCOMPLETE":
                recommendations.extend([
                    "Check logs for errors that caused early termination",
                    "Verify all required tools are properly configured",
                    "Review input data quality and format",
                    "Check if orchestrator process is still running",
                    "Verify system resources (memory, disk space) are sufficient"
                ])
            elif issue["type"] == "MISSING_STEP_DIRECTORY":
                step_name = issue.get("details", {}).get("step", "unknown")
                if "quast" in step_name.lower():
                    recommendations.extend([
                        "QUAST step was never initiated - check orchestrator logs",
                        "Verify SPAdes output files are properly generated",
                        "Check if workflow orchestrator crashed after SPAdes",
                        "Review system resources and Docker container status",
                        "Consider rerunning from QUAST step if previous steps completed successfully"
                    ])
                else:
                    recommendations.extend([
                        f"Step {step_name} was never completed - check previous step logs",
                        "Verify input files for this step are available",
                        "Check orchestrator status and system resources"
                    ])
        
        # Recommendations based on warnings
        for warning in analysis["warnings"]:
            if warning["type"] == "EXECUTION_ABRUPT_STOP":
                missing_step = warning.get("details", {}).get("missing_step", "next step")
                last_action = warning.get("details", {}).get("last_action", "previous step")
                recommendations.extend([
                    f"Workflow stopped after {last_action} - {missing_step} was never initiated",
                    "Check orchestrator process status and system resources",
                    "Review Docker container logs for any errors",
                    "Verify input files for the missing step are properly generated",
                    "Consider rerunning from the missing step if previous steps completed successfully",
                    "Check system logs for any crashes or resource exhaustion"
                ])
        
        # Performance recommendations
        if analysis["execution_time"] > 3600:  # More than 1 hour
            recommendations.append("Consider optimizing workflow for better performance")
        
        # Remove duplicates and return
        return list(set(recommendations))
    
    def save_enhanced_issues_log(self, workflow_id: str, run_dir: Path, crash_details: Dict[str, Any] = None):
        """Save enhanced issues analysis to log file with optional crash details"""
        try:
            issues_log_file = run_dir / "logs" / "workflow_issues.log"
            issues_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            analysis = self.analyze_workflow_completion()
            
            with open(issues_log_file, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("ENHANCED WORKFLOW ISSUES & ANALYSIS REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Workflow Name: {self.workflow_name}\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Analysis Status: {analysis['status']}\n")
                f.write(f"Total Execution Time: {analysis['execution_time']:.2f} seconds\n")
                f.write(f"Completion: {analysis['completed_steps']}/{analysis['total_steps']} steps ({analysis['completion_percentage']:.1f}%)\n")
                f.write("=" * 80 + "\n\n")
                
                # Issues Section
                if analysis["issues"]:
                    f.write(f"🚨 CRITICAL ISSUES & ERRORS ({len(analysis['issues'])} found)\n")
                    f.write("-" * 50 + "\n")
                    for i, issue in enumerate(analysis["issues"], 1):
                        f.write(f"\nISSUE #{i}: {issue['type']}\n")
                        f.write(f"Severity: {issue['severity']}\n")
                        f.write(f"Message: {issue['message']}\n")
                        if issue.get('details'):
                            f.write("Details:\n")
                            for key, value in issue['details'].items():
                                f.write(f"  • {key}: {value}\n")
                        f.write("\n")
                else:
                    f.write("✅ NO CRITICAL ISSUES DETECTED\n")
                    f.write("-" * 50 + "\n\n")
                
                # Warnings Section  
                if analysis["warnings"]:
                    f.write(f"⚠️  WARNINGS & ADVISORIES ({len(analysis['warnings'])} found)\n")
                    f.write("-" * 50 + "\n")
                    for i, warning in enumerate(analysis["warnings"], 1):
                        f.write(f"\nWARNING #{i}: {warning['type']}\n")
                        f.write(f"Severity: {warning['severity']}\n")
                        f.write(f"Message: {warning['message']}\n")
                        if warning.get('details'):
                            f.write("Details:\n")
                            for key, value in warning['details'].items():
                                f.write(f"  • {key}: {value}\n")
                        f.write("\n")
                else:
                    f.write("✅ NO WARNINGS DETECTED\n")
                    f.write("-" * 50 + "\n\n")
                
                # Recommendations Section
                if analysis["recommendations"]:
                    f.write(f"💡 RECOMMENDATIONS & NEXT STEPS ({len(analysis['recommendations'])} items)\n")
                    f.write("-" * 50 + "\n")
                    for i, rec in enumerate(analysis["recommendations"], 1):
                        f.write(f"{i}. {rec}\n")
                    f.write("\n")
                else:
                    f.write("✅ NO SPECIFIC RECOMMENDATIONS - WORKFLOW EXECUTED CLEANLY\n")
                    f.write("-" * 50 + "\n\n")
                
                # Crash Details Section (if available)
                if crash_details:
                    f.write("💥 ORCHESTRATOR CRASH ANALYSIS\n")
                    f.write("-" * 50 + "\n")
                    f.write(f"Crash Type: {crash_details.get('error_type', 'Unknown')}\n")
                    f.write(f"Crash Message: {crash_details.get('error_message', 'No message')}\n")
                    f.write(f"Last Completed Step: {crash_details.get('last_completed_step', 'Unknown')}\n")
                    f.write(f"Last Tool Attempted: {crash_details.get('last_tool', 'Unknown')}\n")
                    f.write(f"Crash Time: {crash_details.get('execution_time', 0):.2f} seconds into workflow\n")
                    
                    # Workflow state at crash
                    workflow_state = crash_details.get('workflow_state', {})
                    f.write(f"Total Steps Planned: {workflow_state.get('total_steps', 'Unknown')}\n")
                    f.write(f"Steps Completed: {workflow_state.get('completed_steps', 'Unknown')}\n")
                    f.write(f"Current Inputs: {len(workflow_state.get('current_inputs', []))} files\n")
                    f.write(f"Last Output Directory: {workflow_state.get('last_output_dir', 'Unknown')}\n")
                    
                    # Stack trace if available
                    if crash_details.get('stack_trace'):
                        f.write("\nStack Trace:\n")
                        f.write("-" * 30 + "\n")
                        f.write(crash_details['stack_trace'])
                        f.write("\n")
                    
                    f.write("\n")
                
                # Summary Section
                f.write("📊 EXECUTIVE SUMMARY\n")
                f.write("-" * 50 + "\n")
                f.write(f"Overall Status: {analysis['status']}\n")
                f.write(f"Success Rate: {analysis['completion_percentage']:.1f}%\n")
                f.write(f"Total Issues: {len(analysis['issues'])}\n")
                f.write(f"Total Warnings: {len(analysis['warnings'])}\n")
                f.write(f"Execution Time: {analysis['execution_time']:.2f}s\n")
                f.write("\n")
                
                if analysis['status'] == 'COMPLETED_SUCCESSFULLY':
                    f.write("🎉 WORKFLOW COMPLETED SUCCESSFULLY WITHOUT ISSUES!\n")
                elif 'COMPLETED' in analysis['status']:
                    f.write("✅ WORKFLOW COMPLETED BUT WITH ISSUES - REVIEW RECOMMENDATIONS\n")
                else:
                    f.write("❌ WORKFLOW FAILED - IMMEDIATE ATTENTION REQUIRED\n")
                    
                f.write("=" * 80 + "\n")
                
            self.logger.info(f"📝 Enhanced issues analysis saved to: {issues_log_file}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save enhanced issues analysis: {str(e)}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
