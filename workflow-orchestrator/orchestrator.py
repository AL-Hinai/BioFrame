#!/usr/bin/env python3
"""
BioFrame Workflow Orchestrator
Manages the execution of bioinformatics workflows
"""

import os
import json
import yaml
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import uuid
from datetime import datetime
import subprocess
import logging
import traceback

# Import the new dynamic logging system
from logging_utils import DynamicWorkflowLogger


class WorkflowOrchestrator:
    """Orchestrates the execution of bioinformatics workflows"""
    
    def __init__(self, data_dir: str, init_docker: bool = True):
        self.data_dir = Path(data_dir)
        self.runs_dir = self.data_dir / "runs"
        self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Docker if requested
        if init_docker:
            self._init_docker()
            
        # Setup logging
        self._setup_logging()
        
    def _init_docker(self):
        """Initialize Docker environment"""
        try:
            # Check if Docker is available
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"✅ Docker available: {result.stdout.strip()}")
            else:
                self.logger.warning("⚠️  Docker not available")
        except FileNotFoundError:
            self.logger.warning("⚠️  Docker command not found")
            
    def _setup_logging(self):
        """Setup basic logging for the orchestrator"""
        # Create orchestrator logger
        self.logger = logging.getLogger("orchestrator")
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
        
        # Initialize tool executor
        self.tool_executor = ToolExecutor(self.logger)
        
        # Initialize issues logger
        self.issues_logger = IssuesLogger()
        
    def create_sample_run(self, run_id: str, workflow_name: str, tools: List[str], 
                          input_files: List[str], output_dir: str) -> Dict[str, Any]:
        """Create a new workflow run with sample data"""
        try:
            # Create run directory
            run_dir = self.runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Create workflow structure
            workflow = {
                "workflow_id": run_id,
                "workflow_name": workflow_name,
                "tools": tools,
                "input_files": input_files,
                "output_directory": output_dir,
                "created_at": datetime.now().isoformat(),
                "status": "created"
            }
            
            # Save workflow definition
            workflow_file = run_dir / "workflow.yaml"
            with open(workflow_file, 'w') as f:
                yaml.dump(workflow, f, default_flow_style=False)
                
            self.logger.info(f"✅ Created workflow run: {run_id}")
            return workflow
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create workflow run: {e}")
            raise
            
    def execute_pipeline_workflow(self, run_id: str, input_files: List[str], 
                                 workflow_config: Dict[str, Any]) -> bool:
        """Execute a complete pipeline workflow with comprehensive logging"""
        start_time = time.time()
        
        try:
            # Load workflow definition
            workflow_file = self.runs_dir / run_id / "workflow.yaml"
            if not workflow_file.exists():
                raise FileNotFoundError(f"Workflow file not found: {workflow_file}")
                
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
                
            # Initialize dynamic logger and executor
            workflow_logger = DynamicWorkflowLogger(run_id, workflow.get("workflow_name", "Unknown"), str(self.data_dir))
            tool_executor = self.tool_executor  # Use the orchestrator's tool executor
            
            # Log workflow start
            tools = workflow.get("tools", [])
            workflow_logger.log_workflow_start(workflow.get("workflow_name", "Unknown"), tools, len(tools))
            
            # Handle input files - check if they're already in the inputs directory
            inputs_dir = self.runs_dir / run_id / "inputs"
            inputs_dir.mkdir(exist_ok=True)
            
            copied_files = []
            for input_file in input_files:
                input_path = Path(input_file)
                if input_path.exists():
                    # Check if file is already in inputs directory
                    if str(input_path).startswith(str(inputs_dir)):
                        # File is already in inputs directory, use it directly
                        copied_files.append(str(input_path))
                        workflow_logger.log_step_progress(1, "file_copy", f"Using existing file: {input_path}")
                    else:
                        # Copy file to inputs directory
                        dest_file = inputs_dir / input_path.name
                        shutil.copy2(input_file, dest_file)
                        copied_files.append(str(dest_file))
                        workflow_logger.log_step_progress(1, "file_copy", f"Copied {input_file} to {dest_file}")
                else:
                    workflow_logger.log_step_progress(1, "file_copy", f"Input file not found: {input_file}", "WARNING")
                    
            # Execute each tool in the pipeline
            current_inputs = copied_files
            step_number = 1
            
            for tool_name in tools:
                try:
                    # Create tool output directory
                    tool_output_dir = self.runs_dir / run_id / f"step_{step_number}_{tool_name}"
                    tool_output_dir.mkdir(exist_ok=True)
                    
                    # Log step start
                    workflow_logger.log_step_start(step_number, tool_name, current_inputs, str(tool_output_dir))
                    
                    # Execute tool
                    result = tool_executor.execute_tool(tool_name, current_inputs, str(tool_output_dir))
                    
                    # Log step completion
                    workflow_logger.log_step_completion(step_number, tool_name, result)
                    
                    if result.success:
                        # Update inputs for next step
                        current_inputs = result.output_files
                        step_number += 1
                        
                        # Log progress
                        workflow_logger.log_step_progress(step_number-1, tool_name, 
                            f"Tool completed successfully. Output files: {len(result.output_files)}")
                    else:
                        # Tool failed
                        workflow_logger.log_step_progress(step_number, tool_name, 
                            f"Tool failed: {result.error_message}", "ERROR")
                        raise RuntimeError(f"Tool {tool_name} failed: {result.error_message}")
                    
                except Exception as e:
                    workflow_logger.log_error(e, f"Step {step_number} execution")
                    workflow_logger.log_workflow_completion(False, time.time() - start_time)
                    
                    # Save enhanced issues analysis for failed workflow
                    run_dir = self.runs_dir / run_id
                    workflow_logger.save_enhanced_issues_log(run_id, run_dir)
                    
                    workflow_logger.cleanup()
                    return False
                    
            # Workflow completed successfully
            total_time = time.time() - start_time
            workflow_logger.log_workflow_completion(True, total_time)
            
            # Save enhanced issues analysis
            run_dir = self.runs_dir / run_id
            workflow_logger.save_enhanced_issues_log(run_id, run_dir)
            
            # Update workflow status
            self._update_workflow_status(run_id, "completed", total_time)
            
            # Cleanup logger
            workflow_logger.cleanup()
            
            self.logger.info(f"🎉 Workflow {run_id} completed successfully in {total_time:.2f} seconds")
            return True
            
        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f"❌ Workflow {run_id} failed: {e}")
            
            # Enhanced crash logging with detailed diagnostics
            crash_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "last_completed_step": step_number - 1 if 'step_number' in locals() else 0,
                "last_tool": tool_name if 'tool_name' in locals() else "unknown",
                "execution_time": total_time,
                "stack_trace": traceback.format_exc(),
                "workflow_state": {
                    "total_steps": total_steps if 'total_steps' in locals() else 0,
                    "completed_steps": step_number - 1 if 'step_number' in locals() else 0,
                    "current_inputs": current_inputs if 'current_inputs' in locals() else [],
                    "last_output_dir": output_dir if 'output_dir' in locals() else "unknown"
                }
            }
            
            # Log detailed crash information
            self.logger.error(f"💥 ORCHESTRATOR CRASH DETAILS:")
            self.logger.error(f"   Last completed step: {crash_details['last_completed_step']}")
            self.logger.error(f"   Last tool attempted: {crash_details['last_tool']}")
            self.logger.error(f"   Execution time: {total_time:.2f} seconds")
            self.logger.error(f"   Error type: {crash_details['error_type']}")
            self.logger.error(f"   Error message: {crash_details['error_message']}")
            self.logger.error(f"   Stack trace: {crash_details['stack_trace']}")
            
            # Try to log completion if logger exists
            try:
                if 'workflow_logger' in locals():
                    workflow_logger.log_workflow_completion(False, total_time)
                    
                    # Save enhanced issues analysis for failed workflow with crash details
                    run_dir = self.runs_dir / run_id
                    workflow_logger.save_enhanced_issues_log(run_id, run_dir, crash_details)
                    
                    workflow_logger.cleanup()
            except Exception as log_error:
                self.logger.error(f"Failed to save crash logs: {log_error}")
                
            # Update workflow status
            self._update_workflow_status(run_id, "failed", total_time)
            
            return False
            
    def _update_workflow_status(self, run_id: str, status: str, execution_time: float):
        """Update workflow status in the workflow file"""
        try:
            workflow_file = self.runs_dir / run_id / "workflow.yaml"
            if workflow_file.exists():
                with open(workflow_file, 'r') as f:
                    workflow = yaml.safe_load(f)
                    
                workflow["status"] = status
                workflow["execution_time"] = execution_time
                workflow["completed_at"] = datetime.now().isoformat()
                
                with open(workflow_file, 'w') as f:
                    yaml.dump(workflow, f, default_flow_style=False)
                    
        except Exception as e:
            self.logger.error(f"Failed to update workflow status: {e}")
            
    def get_workflow_status(self, run_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow"""
        try:
            workflow_file = self.runs_dir / run_id / "workflow.yaml"
            if not workflow_file.exists():
                return {"error": "Workflow not found"}
                
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
                
            # Add additional status information
            run_dir = self.runs_dir / run_id
            if run_dir.exists():
                workflow["output_files"] = self._get_output_files(run_dir)
                workflow["logs"] = self._get_log_files(run_dir)
                
            return workflow
            
        except Exception as e:
            return {"error": f"Failed to get workflow status: {e}"}
            
    def _get_output_files(self, run_dir: Path) -> List[str]:
        """Get list of output files from run directory"""
        output_files = []
        try:
            for file_path in run_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    output_files.append(str(file_path.relative_to(run_dir)))
        except Exception as e:
            self.logger.error(f"Failed to get output files: {e}")
        return output_files
        
    def _get_log_files(self, run_dir: Path) -> List[str]:
        """Get list of log files from run directory"""
        log_files = []
        try:
            logs_dir = run_dir / "logs"
            if logs_dir.exists():
                for file_path in logs_dir.glob("*"):
                    if file_path.is_file():
                        log_files.append(str(file_path.relative_to(run_dir)))
        except Exception as e:
            self.logger.error(f"Failed to get log files: {e}")
        return log_files
        
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all available workflows"""
        workflows = []
        try:
            for run_dir in self.runs_dir.iterdir():
                if run_dir.is_dir():
                    workflow_file = run_dir / "workflow.yaml"
                    if workflow_file.exists():
                        with open(workflow_file, 'r') as f:
                            workflow = yaml.safe_load(f)
                            workflows.append(workflow)
        except Exception as e:
            self.logger.error(f"Failed to list workflows: {e}")
        return workflows
        
    def delete_workflow(self, run_id: str) -> bool:
        """Delete a workflow and all its data"""
        try:
            run_dir = self.runs_dir / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)
                self.logger.info(f"✅ Deleted workflow: {run_id}")
                return True
            else:
                self.logger.warning(f"⚠️  Workflow not found: {run_id}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Failed to delete workflow {run_id}: {e}")
            return False


class ToolExecutor:
    """Handles the execution of individual bioinformatics tools"""
    
    def __init__(self, logger):
        self.logger = logger
        
        # Tool registry with execution information
        self.tool_registry = {
            "fastqc": {
                "description": "Quality control for high throughput sequence data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".html", ".zip", ".txt"],
                "execution_method": "docker",
                "container_image": "bioframe-fastqc:latest",
                "real_execution_time": 720
            },
            "trimmomatic": {
                "description": "A flexible read trimming tool for Illumina NGS data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".fastq", ".fq", ".log"],
                "execution_method": "docker",
                "container_image": "bioframe-trimmomatic:latest",
                "real_execution_time": 900
            },
            "spades": {
                "description": "Assembler for single-cell and multi-cell data",
                "input_types": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
                "output_types": [".fasta", ".fastg", ".log"],
                "execution_method": "docker",
                "container_image": "bioframe-spades:latest",
                "real_execution_time": 14400
            },
            "quast": {
                "description": "Quality assessment tool for evaluating assemblies",
                "input_types": [".fasta", ".fa"],
                "output_types": [".html", ".txt", ".log"],
                "execution_method": "docker",
                "container_image": "bioframe-quast:latest",
                "real_execution_time": 1800
            },
            "multiqc": {
                "description": "Aggregate results from bioinformatics analyses",
                "input_types": [".html", ".txt", ".log"],
                "output_types": [".html", ".txt"],
                "execution_method": "docker",
                "container_image": "bioframe-multiqc:latest",
                "real_execution_time": 300
            }
        }
    
    def execute_tool(self, tool_name: str, input_files: List[str], output_dir: str) -> 'ToolExecutionResult':
        """Execute a bioinformatics tool"""
        # Normalize tool name for case-insensitive matching
        tool_name = tool_name.lower()
        
        if tool_name not in self.tool_registry:
            return ToolExecutionResult(
                success=False,
                output_files=[],
                error_message=f"Unknown tool: {tool_name}"
            )
        
        try:
            # Execute tool via Docker
            import time
            start_time = time.time()
            success, output_files = self._execute_docker_tool(tool_name, input_files, output_dir, {})
            execution_time = time.time() - start_time
            
            if success:
                return ToolExecutionResult(
                    success=True,
                    output_files=output_files,
                    error_message="",
                    execution_time=execution_time
                )
            else:
                return ToolExecutionResult(
                    success=False,
                    output_files=[],
                    error_message="Docker execution failed",
                    execution_time=execution_time
                )
                
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                output_files=[],
                error_message=f"Tool execution error: {str(e)}"
            )
    
    def _execute_docker_tool(self, tool_name: str, input_files: List[str], 
                            output_dir: str, tool_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Execute tool using direct Docker commands"""
        tool_info = self.tool_registry[tool_name]
        
        # Build Docker command for direct execution
        docker_cmd = self._build_docker_command(tool_name, input_files, output_dir, tool_config)
        
        self.logger.info(f"Executing {tool_name} via Docker: {' '.join(docker_cmd)}")
        
        try:
            # Execute Docker command directly
            result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                # Get output files
                output_files = self._collect_output_files(output_dir, tool_info["output_types"])
                self.logger.info(f"Docker execution successful: {len(output_files)} output files")
                return True, output_files
            else:
                self.logger.error(f"Docker execution failed: {result.stderr}")
                return False, []
                
        except subprocess.TimeoutExpired:
            self.logger.error("Docker execution timed out")
            return False, []
        except Exception as e:
            self.logger.error(f"Docker execution error: {str(e)}")
            return False, []
    
    def _build_docker_command(self, tool_name: str, input_files: List[str], 
                             output_dir: str, tool_config: Dict[str, Any]) -> List[str]:
        """Build Docker command for tool execution using local tool images"""
        # Base Docker command
        cmd = ["docker", "run", "--rm"]
        
        # Mount volumes - use absolute host paths for Docker
        # Since we're running from within the portal container, we need to use the host path
        # The portal container has /home/msalim/Project/BioFrame mounted as /app
        host_base_path = "/home/msalim/Project/BioFrame"
        
        if input_files:
            # Convert /app/data paths to host paths
            input_path = input_files[0]
            if input_path.startswith('/app/data'):
                # Convert /app/data/... to /home/msalim/Project/BioFrame/data/...
                host_input_path = input_path.replace('/app/data', f"{host_base_path}/data")
                input_parent = str(Path(host_input_path).parent)
            else:
                input_parent = str(Path(input_files[0]).parent)
        else:
            input_parent = f"{host_base_path}/data"
            
        if output_dir.startswith('/app/data'):
            # Convert /app/data/... to /home/msalim/Project/BioFrame/data/...
            host_output_path = output_dir.replace('/app/data', f"{host_base_path}/data")
            output_dir_abs = str(Path(host_output_path).resolve())
        else:
            output_dir_abs = str(Path(output_dir).resolve())
            
        cmd.extend(["-v", f"{input_parent}:/input:ro"])
        cmd.extend(["-v", f"{output_dir_abs}:/output"])
        
        # Set working directory
        cmd.extend(["-w", "/output"])
        
        # Use local tool images (built from docker-compose)
        image_name = self.tool_registry[tool_name]["container_image"]
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
            cmd.extend(["quast.py"])
            cmd.extend(["/input/" + Path(f).name for f in input_files])
            cmd.extend(["-o", "/output"])
        elif tool_name == "multiqc":
            cmd.extend(["multiqc", "/input", "-o", "/output"])
            
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
                    # Special handling for QUAST outputs
                    elif 'quast' in str(output_dir).lower():
                        # Include all QUAST output files regardless of extension
                        if file_ext in ['.html', '.pdf', '.tsv', '.tex', '.log', '.txt']:
                            output_files.append(str(file_path))
                        # Also include important QUAST directories as files for tracking
                        elif file_path.parent.name in ['basic_stats', 'icarus_viewers'] and file_path.is_file():
                            output_files.append(str(file_path))
                        
        return output_files


class ToolExecutionResult:
    """Result of a tool execution"""
    
    def __init__(self, success: bool, output_files: List[str], error_message: str, execution_time: float = 0.0, tool_version: str = None, memory_used: str = None, cpu_time: str = None):
        self.success = success
        self.output_files = output_files
        self.error_message = error_message
        self.execution_time = execution_time
        self.tool_version = tool_version
        self.memory_used = memory_used
        self.cpu_time = cpu_time


class IssuesLogger:
    """Comprehensive logging system for workflow issues, failures, and diagnostics"""
    
    def __init__(self):
        self.issues = []
        
    def log_workflow_issue(self, workflow_id: str, issue_type: str, message: str, 
                          severity: str = "WARNING", details: Dict[str, Any] = None, 
                          stack_trace: str = None):
        """Log a workflow issue with comprehensive details"""
        issue = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": workflow_id,
            "issue_type": issue_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "stack_trace": stack_trace
        }
        
        self.issues.append(issue)
        
        # Also log to console for immediate visibility
        severity_icon = {
            "CRITICAL": "💥",
            "ERROR": "❌", 
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }.get(severity, "❓")
        
        print(f"{severity_icon} WORKFLOW ISSUE [{severity}]: {issue_type} - {message}")
        
    def log_tool_failure(self, workflow_id: str, tool_name: str, step_number: int, 
                         error_message: str, exit_code: int = None, 
                         execution_time: float = None, output_files: List[str] = None):
        """Log a tool execution failure"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="TOOL_FAILURE",
            message=f"Tool {tool_name} failed at step {step_number}",
            severity="ERROR",
            details={
                "tool_name": tool_name,
                "step_number": step_number,
                "error_message": error_message,
                "exit_code": exit_code,
                "execution_time": execution_time,
                "output_files": output_files or []
            }
        )
        
    def log_orchestrator_crash(self, workflow_id: str, error_message: str, 
                              stack_trace: str = None, last_completed_step: int = None):
        """Log orchestrator crash/failure"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="ORCHESTRATOR_CRASH",
            message="Workflow orchestrator crashed or failed",
            severity="CRITICAL",
            details={
                "last_completed_step": last_completed_step,
                "error_message": error_message
            },
            stack_trace=stack_trace
        )
        
    def log_resource_issue(self, workflow_id: str, resource_type: str, 
                          current_value: str, limit: str, message: str):
        """Log resource-related issues (memory, disk, etc.)"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="RESOURCE_ISSUE",
            message=f"Resource issue: {message}",
            severity="WARNING",
            details={
                "resource_type": resource_type,
                "current_value": current_value,
                "limit": limit
            }
        )
        
    def log_docker_issue(self, workflow_id: str, tool_name: str, 
                        docker_error: str, container_id: str = None):
        """Log Docker-related issues"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="DOCKER_ISSUE",
            message=f"Docker issue with {tool_name}: {docker_error}",
            severity="ERROR",
            details={
                "tool_name": tool_name,
                "docker_error": docker_error,
                "container_id": container_id
            }
        )
        
    def log_workflow_timeout(self, workflow_id: str, timeout_duration: int, 
                           completed_steps: int, total_steps: int):
        """Log workflow timeout issues"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="WORKFLOW_TIMEOUT",
            message=f"Workflow timed out after {timeout_duration} seconds",
            severity="WARNING",
            details={
                "timeout_duration": timeout_duration,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "progress_percentage": (completed_steps / total_steps) * 100 if total_steps > 0 else 0
            }
        )
        
    def log_file_system_issue(self, workflow_id: str, file_path: str, 
                             operation: str, error_message: str):
        """Log file system related issues"""
        self.log_workflow_issue(
            workflow_id=workflow_id,
            issue_type="FILESYSTEM_ISSUE",
            message=f"File system issue: {operation} failed for {file_path}",
            severity="ERROR",
            details={
                "file_path": file_path,
                "operation": operation,
                "error_message": error_message
            }
        )
        
    def save_issues_log(self, workflow_id: str, run_dir: Path):
        """Save all issues to a dedicated log file"""
        try:
            issues_log_file = run_dir / "logs" / "workflow_issues.log"
            issues_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(issues_log_file, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write(f"WORKFLOW ISSUES & FAILURES LOG\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                
                if not self.issues:
                    f.write("✅ No issues detected - workflow completed successfully!\n\n")
                else:
                    f.write(f"🚨 {len(self.issues)} issues detected during workflow execution:\n\n")
                    
                    for i, issue in enumerate(self.issues, 1):
                        f.write(f"ISSUE #{i}\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"Timestamp: {issue['timestamp']}\n")
                        f.write(f"Type: {issue['issue_type']}\n")
                        f.write(f"Severity: {issue['severity']}\n")
                        f.write(f"Message: {issue['message']}\n")
                        
                        if issue['details']:
                            f.write(f"Details:\n")
                            for key, value in issue['details'].items():
                                f.write(f"  {key}: {value}\n")
                                
                        if issue['stack_trace']:
                            f.write(f"Stack Trace:\n{issue['stack_trace']}\n")
                            
                        f.write("\n")
                        
            print(f"📝 Issues log saved to: {issues_log_file}")
            
        except Exception as e:
            print(f"❌ Failed to save issues log: {str(e)}")
            
    def get_issues_summary(self, workflow_id: str) -> Dict[str, Any]:
        """Get a summary of all issues for a workflow"""
        if not self.issues:
            return {
                "workflow_id": workflow_id,
                "total_issues": 0,
                "status": "CLEAN",
                "summary": "No issues detected"
            }
            
        # Count issues by severity
        severity_counts = {}
        issue_types = {}
        
        for issue in self.issues:
            severity = issue['severity']
            issue_type = issue['issue_type']
            
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
            
        # Determine overall status
        if any(issue['severity'] == 'CRITICAL' for issue in self.issues):
            overall_status = "CRITICAL_FAILURE"
        elif any(issue['severity'] == 'ERROR' for issue in self.issues):
            overall_status = "ERRORS_DETECTED"
        elif any(issue['severity'] == 'WARNING' for issue in self.issues):
            overall_status = "WARNINGS_DETECTED"
        else:
            overall_status = "CLEAN"
            
        return {
            "workflow_id": workflow_id,
            "total_issues": len(self.issues),
            "status": overall_status,
            "severity_breakdown": severity_counts,
            "issue_type_breakdown": issue_types,
            "summary": f"Detected {len(self.issues)} issues: {', '.join(f'{count} {severity}' for severity, count in severity_counts.items())}"
        }
