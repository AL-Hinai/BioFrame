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
import threading
import queue
import psutil
import signal
import sys

# Import the new dynamic logging system
from logging_utils import DynamicWorkflowLogger


class ContainerProcessManager:
    """Enhanced container-based process management with better logging, tracking, and rerun capabilities"""
    
    def __init__(self, logger, data_dir: str):
        self.logger = logger
        self.data_dir = Path(data_dir)
        self.active_containers = {}
        self.process_queue = queue.Queue()
        self.monitor_thread = None
        self.running = False
        
    def start_monitoring(self):
        """Start the container monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_containers, daemon=True)
            self.monitor_thread.start()
            self.logger.info("🔍 Container monitoring started")
    
    def stop_monitoring(self):
        """Stop the container monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        self.logger.info("🛑 Container monitoring stopped")
    
    def _monitor_containers(self):
        """Monitor active containers for resource usage and health with robust error handling"""
        while self.running:
            try:
                # Create a copy of the keys to avoid modification during iteration
                container_ids = list(self.active_containers.keys())
                
                for container_id in container_ids:
                    container_info = self.active_containers.get(container_id)
                    if not container_info:
                        continue
                        
                    try:
                        # Check if container is still running
                        result = subprocess.run(
                            ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                            capture_output=True, text=True, timeout=10
                        )
                        
                        if result.returncode == 0:
                            status = result.stdout.strip()
                            if status not in ["running"]:
                                # Container finished or failed
                                self._handle_container_completion(container_id, container_info, status)
                        else:
                            # Container not found, remove from tracking
                            self.logger.info(f"🧹 Removing non-existent container {container_id} from tracking")
                            self.active_containers.pop(container_id, None)
                            
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"⚠️ Timeout inspecting container {container_id}, removing from tracking")
                        self.active_containers.pop(container_id, None)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error monitoring container {container_id}: {e}")
                        # CRITICAL FIX: Always remove problematic containers to prevent infinite loops
                        self.logger.info(f"🧹 Removing problematic container {container_id} from tracking")
                        self.active_containers.pop(container_id, None)
                        
                # Intelligent periodic scan for missed completions
                if hasattr(self, '_scan_counter'):
                    self._scan_counter += 1
                else:
                    self._scan_counter = 1
                    
                # Scan frequency: every 6 cycles (30 seconds) for recent workflows
                if self._scan_counter % 6 == 0:
                    self._scan_for_missed_completions()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"❌ Critical error in container monitoring: {e}")
                # Clear all containers if monitoring is completely broken
                self.logger.warning("🚨 Clearing all tracked containers due to critical monitoring error")
                self.active_containers.clear()
                time.sleep(10)
    
    def _handle_container_completion(self, container_id: str, container_info: Dict[str, Any], status: str):
        """Handle container completion or failure with enhanced detection"""
        try:
            workflow_id = container_info.get('workflow_id')
            step_number = container_info.get('step_number')
            tool_name = container_info.get('tool_name')
            
            # Get container logs
            logs = self._get_container_logs(container_id)
            
            # Update container info
            container_info['status'] = status
            container_info['completed_at'] = datetime.now().isoformat()
            container_info['logs'] = logs
            
            # Enhanced completion detection with evidence-based validation
            completion_evidence = self._gather_completion_evidence(workflow_id, step_number, tool_name)
            
            # Log completion with evidence
            if status == "exited" or completion_evidence['has_output_files']:
                self.logger.info(f"✅ Container {container_id} completed successfully")
                self.logger.info(f"📊 Completion evidence: {completion_evidence}")
                
                # Trigger step completion logging if not already done
                if not completion_evidence['has_step_result']:
                    self._create_step_result_from_evidence(workflow_id, step_number, tool_name, completion_evidence)
                    
            else:
                self.logger.warning(f"⚠️ Container {container_id} finished with status: {status}")
                self.logger.warning(f"📊 Evidence check: {completion_evidence}")
            
            # Always remove from active containers
            self.active_containers.pop(container_id, None)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling container completion {container_id}: {e}")
            # Always remove from tracking even on error
            self.active_containers.pop(container_id, None)
    
    def _get_container_logs(self, container_id: str) -> str:
        """Get logs from a container"""
        try:
            result = subprocess.run(
                ["docker", "logs", container_id],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error getting logs: {e}"
    
    def _gather_completion_evidence(self, workflow_id: str, step_number: int, tool_name: str) -> Dict[str, Any]:
        """Gather evidence that a tool completed successfully"""
        evidence = {
            'has_output_files': False,
            'has_tool_log': False,
            'has_step_result': False,
            'output_file_count': 0,
            'tool_log_indicates_completion': False,
            'step_result_success': None
        }
        
        try:
            # Check for output files
            runs_dir = self.data_dir / "runs"
            output_dir = runs_dir / workflow_id / f"step_{step_number}_{tool_name}"
            if output_dir.exists():
                output_files = list(output_dir.glob("*"))
                evidence['has_output_files'] = len(output_files) > 0
                evidence['output_file_count'] = len(output_files)
            
            # Check for tool log file
            tool_log_file = output_dir / f"{tool_name}.log"
            if tool_log_file.exists():
                evidence['has_tool_log'] = True
                # Check if log indicates completion
                try:
                    with open(tool_log_file, 'r') as f:
                        log_content = f.read().lower()
                        completion_indicators = ['finished', 'completed', 'pipeline finished', 'analysis complete']
                        evidence['tool_log_indicates_completion'] = any(indicator in log_content for indicator in completion_indicators)
                except:
                    pass
            
            # Check for step result file
            step_result_file = runs_dir / workflow_id / "step_results" / f"step_{step_number}_{tool_name}.json"
            if step_result_file.exists():
                evidence['has_step_result'] = True
                try:
                    with open(step_result_file, 'r') as f:
                        step_data = json.load(f)
                        evidence['step_result_success'] = step_data.get('result', {}).get('success', False)
                except:
                    pass
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Error gathering completion evidence: {e}")
            
        return evidence
    
    def _create_step_result_from_evidence(self, workflow_id: str, step_number: int, tool_name: str, evidence: Dict[str, Any]):
        """Create step result file based on completion evidence"""
        try:
            runs_dir = self.data_dir / "runs"
            output_dir = runs_dir / workflow_id / f"step_{step_number}_{tool_name}"
            step_results_dir = runs_dir / workflow_id / "step_results"
            step_results_dir.mkdir(exist_ok=True)
            
            # Gather output files
            output_files = []
            if output_dir.exists():
                output_files = [str(f) for f in output_dir.glob("*") if f.is_file()]
            
            # Parse tool log for execution time and warnings
            execution_time = 0
            warnings = []
            tool_log_file = output_dir / f"{tool_name}.log"
            if tool_log_file.exists():
                try:
                    with open(tool_log_file, 'r') as f:
                        log_content = f.read()
                        # Extract warnings
                        for line in log_content.split('\n'):
                            if 'WARN' in line or 'WARNING' in line:
                                warnings.append(line.strip())
                except:
                    pass
            
            # Create step result
            step_result = {
                "step_number": step_number,
                "tool_name": tool_name,
                "input_files": [],  # Could be reconstructed if needed
                "output_dir": str(output_dir),
                "result": {
                    "success": evidence['has_output_files'] or evidence['tool_log_indicates_completion'],
                    "output_files": output_files,
                    "error_message": "",
                    "execution_time": execution_time,
                    "container_id": None,
                    "container_name": None,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": 0,
                    "timestamp": datetime.now().isoformat(),
                    "warnings": warnings,
                    "recovery_method": "evidence_based"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Save step result file
            step_result_file = step_results_dir / f"step_{step_number}_{tool_name}.json"
            with open(step_result_file, 'w') as f:
                json.dump(step_result, f, indent=2)
            
            self.logger.info(f"📄 Created step result from evidence: {step_result_file}")
            
            # Log step completion to workflow execution log
            self._log_recovered_step_completion(workflow_id, step_number, tool_name, evidence)
            
        except Exception as e:
            self.logger.error(f"❌ Error creating step result from evidence: {e}")
    
    def _log_recovered_step_completion(self, workflow_id: str, step_number: int, tool_name: str, evidence: Dict[str, Any]):
        """Log recovered step completion to workflow execution log"""
        try:
            # Create a temporary logger for this workflow
            from logging_utils import DynamicWorkflowLogger
            recovery_logger = DynamicWorkflowLogger(workflow_id, f"Recovery-{tool_name}", str(self.data_dir))
            
            recovery_logger.logger.info("-" * 80)
            recovery_logger.logger.info(f"🔄 RECOVERED STEP {step_number} COMPLETION: {tool_name.upper()}")
            recovery_logger.logger.info(f"📊 Evidence-based recovery performed")
            recovery_logger.logger.info(f"📁 Output Files: {evidence['output_file_count']} files")
            recovery_logger.logger.info(f"📝 Tool Log Available: {evidence['has_tool_log']}")
            recovery_logger.logger.info(f"✅ Tool Log Indicates Completion: {evidence['tool_log_indicates_completion']}")
            recovery_logger.logger.info(f"⏰ Recovery Time: {datetime.now().isoformat()}")
            recovery_logger.logger.info("-" * 80)
            
            recovery_logger.cleanup()
            
        except Exception as e:
            self.logger.error(f"❌ Error logging recovered completion: {e}")
    
    def _scan_for_missed_completions(self):
        """Scan for tools that completed but weren't properly detected"""
        try:
            self.logger.info("🔍 Scanning for missed tool completions...")
            
            # Check all workflow runs
            runs_dir = self.data_dir / "runs"
            for run_dir in runs_dir.glob("*"):
                if not run_dir.is_dir():
                    continue
                    
                workflow_id = run_dir.name
                
                # Check each step directory for completion evidence
                for step_dir in run_dir.glob("step_*"):
                    try:
                        # Extract step info from directory name
                        step_parts = step_dir.name.split('_')
                        if len(step_parts) >= 3:
                            step_number = int(step_parts[1])
                            tool_name = step_parts[2]
                            
                            # Check if we have completion evidence but no step result
                            evidence = self._gather_completion_evidence(workflow_id, step_number, tool_name)
                            
                            if (evidence['has_output_files'] or evidence['tool_log_indicates_completion']) and not evidence['has_step_result']:
                                self.logger.info(f"🔄 Found missed completion: {workflow_id} - {tool_name}")
                                self._create_step_result_from_evidence(workflow_id, step_number, tool_name, evidence)
                                
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error checking step {step_dir}: {e}")
                        
        except Exception as e:
            self.logger.error(f"❌ Error in missed completion scan: {e}")
    
# Manual trigger checking removed - completion scanning is now purely automatic
    def _scan_workflow_for_missed_completions(self, workflow_id: str):
        """Scan a specific workflow for missed completions"""
        try:
            self.logger.info(f"🔍 Scanning workflow {workflow_id} for missed completions...")
            
            runs_dir = self.data_dir / "runs"
            run_dir = runs_dir / workflow_id
            if not run_dir.exists():
                return
                
            # Check each step directory for completion evidence
            for step_dir in run_dir.glob("step_*"):
                try:
                    # Extract step info from directory name
                    step_parts = step_dir.name.split('_')
                    if len(step_parts) >= 3:
                        step_number = int(step_parts[1])
                        tool_name = step_parts[2]
                        
                        # Check if we have completion evidence but no step result
                        evidence = self._gather_completion_evidence(workflow_id, step_number, tool_name)
                        
                        if (evidence['has_output_files'] or evidence['tool_log_indicates_completion']) and not evidence['has_step_result']:
                            self.logger.info(f"🔄 Recovering missed completion: {workflow_id} - {tool_name}")
                            self._create_step_result_from_evidence(workflow_id, step_number, tool_name, evidence)
                            
                except Exception as e:
                    self.logger.warning(f"⚠️ Error checking step {step_dir}: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error in workflow completion scan: {e}")
    
    def execute_tool_in_container(self, tool_name: str, input_files: List[str], 
                                 output_dir: str, workflow_id: str, step_number: int,
                                 tool_config: Dict[str, Any] = None) -> 'ContainerExecutionResult':
        """Execute a tool in a dedicated container with enhanced tracking and validation"""
        container_id = None
        start_time = time.time()
        
        try:
            # Pre-execution validation
            validation_result = self._validate_container_execution(tool_name, input_files, output_dir)
            if not validation_result['valid']:
                return ContainerExecutionResult(
                    success=False,
                    output_files=[],
                    error_message=f"Pre-execution validation failed: {validation_result['error']}",
                    execution_time=0,
                    container_id=None,
                    container_name=None,
                    stdout="",
                    stderr=validation_result['error'],
                    exit_code=-1
                )
            
            # Add container name for tracking
            container_name = f"bioframe-{workflow_id}-step{step_number}-{tool_name}-{int(time.time())}"
            
            # Build container command with name
            docker_cmd = self._build_enhanced_docker_command(
                tool_name, input_files, output_dir, tool_config or {}, container_name
            )
            
            self.logger.info(f"🚀 Starting container execution: {tool_name}")
            self.logger.info(f"📋 Command: {' '.join(docker_cmd)}")
            
            # Validate Docker command before execution
            if not self._validate_docker_command(docker_cmd):
                return ContainerExecutionResult(
                    success=False,
                    output_files=[],
                    error_message="Docker command validation failed",
                    execution_time=0,
                    container_id=None,
                    container_name=container_name,
                    stdout="",
                    stderr="Invalid Docker command",
                    exit_code=-1
                )
            
            # Start container and wait for completion using robust monitoring
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Track container
            container_id = self._get_container_id_by_name(container_name)
            if container_id:
                self.active_containers[container_id] = {
                    'workflow_id': workflow_id,
                    'step_number': step_number,
                    'tool_name': tool_name,
                    'process': process,
                    'started_at': datetime.now().isoformat(),
                    'status': 'running'
                }
            
            # Use robust container monitoring instead of blocking I/O
            stdout_lines, stderr_lines = self._monitor_container_with_fallback(
                container_name, container_id, tool_name, process
            )
            
            execution_time = time.time() - start_time
            
            # CORE FIX: Better success detection for long-running tools
            # Don't rely solely on process.returncode for container-based execution
            output_files = self._collect_output_files(output_dir, tool_name)
            
            # CORE FIX: Now we should have reliable exit codes from improved monitoring
            success = process.returncode == 0
            
            if process.returncode is None:
                self.logger.error(f"❌ MONITORING FAILURE: No exit code captured for {tool_name}")
                success = False
            
            # Create result
            result = ContainerExecutionResult(
                success=success,
                output_files=output_files,
                error_message="\n".join(stderr_lines) if not success else "",
                execution_time=execution_time,
                container_id=container_id,
                container_name=container_name,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
                exit_code=process.returncode
            )
            
            # CRITICAL: Validate tool output and detect file reading failures
            if not self._validate_tool_output(tool_name, result, input_files, output_dir):
                self.logger.error(f"❌ Tool '{tool_name}' output validation FAILED - workflow should stop")
                # Override success to False if validation fails
                result.success = False
                result.error_message = f"Tool output validation failed: {result.stderr}"
                return result
            
            if success:
                self.logger.info(f"✅ Tool {tool_name} completed successfully in {execution_time:.2f}s")
            else:
                self.logger.error(f"❌ Tool {tool_name} failed with exit code {process.returncode}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"❌ Container execution error for {tool_name}: {e}")
            
            return ContainerExecutionResult(
                success=False,
                output_files=[],
                error_message=f"Container execution error: {str(e)}",
                execution_time=execution_time,
                container_id=container_id,
                container_name=container_name if 'container_name' in locals() else None,
                stdout="",
                stderr=str(e),
                exit_code=-1
            )
    
    def _build_enhanced_docker_command(self, tool_name: str, input_files: List[str], 
                                     output_dir: str, tool_config: Dict[str, Any], 
                                     container_name: str = None) -> List[str]:
        """Build Docker command using static volume mounts from docker-compose.yml"""
        # CORE FIX: Don't auto-remove containers until we capture exit codes
        cmd = ["docker", "run"]
        
        # Add resource limits (can be overridden by tool metadata)
        memory_limit = tool_config.get('memory_requirement', '8g')
        cpu_limit = tool_config.get('cpu_requirement', '4')
        cmd.extend(["--memory", memory_limit])
        cmd.extend(["--cpus", str(cpu_limit)])
        cmd.extend(["--ulimit", "nofile=65536:65536"])  # File descriptor limit
        
        # Add environment variables
        cmd.extend(["-e", "PYTHONUNBUFFERED=1"])
        cmd.extend(["-e", f"BIOFRAME_TOOL_NAME={tool_name}"])
        cmd.extend(["-e", f"BIOFRAME_STEP_NUMBER={tool_config.get('step_number', 1)}"])
        
        # Use the same host data directory that the orchestrator can access
        # This ensures both orchestrator and tool containers share the same data directory
        host_data_path = "G:/Work File/Projects/BioFrame/data"
        cmd.extend(["-v", f"{host_data_path}:/data"])
        self.logger.info(f"✅ Using shared data mount: {host_data_path}:/data")
        
        # Also mount the host data directory as host-data for Windows compatibility
        cmd.extend(["-v", f"{host_data_path}:/host-data:ro"])
        self.logger.info(f"✅ Using host data mount: {host_data_path}:/host-data:ro")
        
        # Set working directory to data directory
        cmd.extend(["-w", "/data"])
        
        # Ensure output directory exists in the container
        output_relative = str(Path(output_dir).relative_to(self.data_dir))
        cmd.extend(["-e", f"OUTPUT_DIR=/data/{output_relative}"])
        
        # Add container name for tracking
        if container_name:
            cmd.extend(["--name", container_name])
        
        # Use appropriate container image
        image_name = self._get_container_image(tool_name)
        cmd.append(image_name)
        
        # Add tool-specific command arguments using dynamic metadata extraction
        cmd.extend(self._get_dynamic_tool_command_args(tool_name, input_files, output_dir, tool_config))
        
        return cmd
    
    def _get_dynamic_tool_command_args(self, tool_name: str, input_files: List[str], 
                                      output_dir: str, tool_config: Dict[str, Any]) -> List[str]:
        """Get tool command arguments dynamically from container metadata"""
        try:
            # Get tool metadata from container
            metadata = self._extract_tool_metadata(tool_name)
            if not metadata:
                self.logger.warning(f"No metadata found for tool {tool_name}, falling back to basic command")
                return [tool_name, "--help"]
            
            # Update tool_config with resource requirements from metadata
            if 'tool_memory_requirement' in metadata:
                tool_config['memory_requirement'] = metadata['tool_memory_requirement']
            if 'tool_cpu_requirement' in metadata:
                tool_config['cpu_requirement'] = metadata['tool_cpu_requirement']
            
            # Use the command template from metadata
            command_template = metadata.get('tool_command_template', '')
            if not command_template:
                self.logger.warning(f"No command template found for {tool_name}")
                return [metadata.get('tool_primary_command', tool_name), "--help"]
            
            # Build command based on metadata template
            return self._build_command_from_template(tool_name, metadata, input_files, output_dir, tool_config)
            
        except Exception as e:
            self.logger.error(f"Failed to get dynamic command for {tool_name}: {e}")
            # Fallback to basic command
            return [tool_name, "--help"]
    
    def _extract_tool_metadata(self, tool_name: str) -> Dict[str, str]:
        """
        Extract metadata from tool's Dockerfile directly.
        
        This is the primary method for getting tool configuration - reads metadata
        directly from each tool's Dockerfile in the tools/ directory.
        """
        try:
            # Try to read metadata from the Dockerfile in tools directory
            # Check multiple possible paths since orchestrator might be in container
            possible_paths = [
                Path(f"/workflow/tools/{tool_name.lower()}/Dockerfile"),  # Container mount path
                Path(f"tools/{tool_name.lower()}/Dockerfile"),           # Local development
                Path(f"/app/tools/{tool_name.lower()}/Dockerfile"),      # Alternative container path
                Path(f"../tools/{tool_name.lower()}/Dockerfile")         # Relative path
            ]
            
            dockerfile_path = None
            for path in possible_paths:
                if path.exists():
                    dockerfile_path = path
                    break
            
            if dockerfile_path:
                with open(dockerfile_path, 'r') as f:
                    content = f.read()
                
                # Parse metadata from Dockerfile
                metadata = {}
                lines = content.split('\n')
                in_metadata_section = False
                
                for line in lines:
                    line = line.strip()
                    
                    # Check if this line starts metadata section
                    if 'BIOFRAME_TOOL_METADATA' in line:
                        in_metadata_section = True
                        continue
                    
                    # Parse metadata lines
                    if in_metadata_section and line.startswith('# tool_'):
                        try:
                            metadata_line = line[2:]  # Remove '# '
                            key, value = metadata_line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                        except ValueError:
                            continue
                    elif in_metadata_section and not line.startswith('#'):
                        # End of metadata section
                        break
                
                if metadata:
                    self.logger.info(f"✅ Loaded metadata for {tool_name} from Dockerfile")
                    return metadata
            
            # Fallback to container inspection if Dockerfile not available
            self.logger.warning(f"Dockerfile not found for {tool_name}, using fallback metadata")
            return self._get_fallback_metadata(tool_name)
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata for {tool_name}: {e}")
            return self._get_fallback_metadata(tool_name)
    
    def _get_fallback_metadata(self, tool_name: str) -> Dict[str, str]:
        """
        Get minimal fallback metadata when Dockerfile extraction fails.
        
        This should rarely be used now that the orchestrator reads metadata directly
        from Dockerfiles. Only provides basic functionality for emergency cases.
        """
        self.logger.warning(f"🚨 Using minimal fallback metadata for {tool_name} - Dockerfile metadata should be preferred")
        
        # Minimal generic fallback - just enough to prevent crashes
        return {
            'tool_name': tool_name.title(),
            'tool_primary_command': tool_name.lower(),
            'tool_command_template': f'{tool_name.lower()} --help',
            'tool_description': f'Generic {tool_name} tool',
            'tool_memory_requirement': '4g',
            'tool_cpu_requirement': '2'
        }
    
    def _build_command_from_template(self, tool_name: str, metadata: Dict[str, str], 
                                   input_files: List[str], output_dir: str, 
                                   tool_config: Dict[str, Any]) -> List[str]:
        """Build command dynamically from metadata template"""
        try:
            # Get the command template from metadata
            template = metadata.get('tool_command_template', '')
            primary_command = metadata.get('tool_primary_command', tool_name.lower())
            
            if not template:
                self.logger.warning(f"No command template found for {tool_name}, using basic command")
                return [primary_command, "--help"]
            
            # Build command using template substitution
            command = self._substitute_template_variables(template, input_files, output_dir, metadata)
            
            # Debug: Log the generated command
            self.logger.info(f"🔧 Generated command for {tool_name}: {command}")
            
            # Handle complex command structures
            if self._needs_shell_wrapper(command):
                self.logger.info(f"🐚 Using shell wrapper for complex command")
                return ["sh", "-c", command]
            else:
                args = command.split()
                self.logger.info(f"🔧 Split command args: {args}")
                return args
                
        except Exception as e:
            self.logger.error(f"Error building command for {tool_name}: {e}")
            return [tool_name, "--help"]
    
    def _substitute_template_variables(self, template: str, input_files: List[str], 
                                     output_dir: str, metadata: Dict[str, str]) -> str:
        """Substitute all template variables with actual values"""
        command = template
        
        # Basic substitutions - use actual output directory path instead of environment variable
        output_path = Path(output_dir)
        output_relative = str(output_path.relative_to(self.data_dir))
        container_output_dir = f"/data/{output_relative}"
        
        substitutions = {
            '{output_dir}': container_output_dir,
            '{OUTPUT_DIR}': container_output_dir,
            '{input_files}': self._format_input_files_for_template(input_files),
            '{options}': '',  # Default empty options
            '{threads}': '4',
            '{memory}': '8'
        }
        
        # Add input file specific substitutions
        for i, input_file in enumerate(input_files):
            substitutions[f'{{input_file_{i+1}}}'] = self._get_container_path(input_file)
            
        # Add common aliases
        if len(input_files) >= 1:
            substitutions['{input_file}'] = self._get_container_path(input_files[0])
            substitutions['{read1}'] = self._get_container_path(input_files[0])
            substitutions['{assembly_files}'] = self._get_container_path(input_files[0])
            substitutions['{reference}'] = self._get_container_path(input_files[0])
            
        if len(input_files) >= 2:
            substitutions['{read2}'] = self._get_container_path(input_files[1])
            substitutions['{reads}'] = ' '.join([self._get_container_path(f) for f in input_files[1:]])
        
        # Apply all substitutions
        for placeholder, value in substitutions.items():
            command = command.replace(placeholder, str(value))
        
        return command
    
    def _get_container_path(self, file_path: str) -> str:
        """Convert host file path to container path"""
        file_path_obj = Path(file_path)
        if str(file_path_obj).startswith(str(self.data_dir)):
            relative_path = file_path_obj.relative_to(self.data_dir)
            return f"/data/{relative_path}"
        else:
            return f"/data/{file_path_obj.name}"
    
    def _format_input_files_for_template(self, input_files: List[str]) -> str:
        """Format input files for template substitution"""
        container_paths = [self._get_container_path(f) for f in input_files]
        return ' '.join(container_paths)
    
    def _needs_shell_wrapper(self, command: str) -> bool:
        """Check if command needs shell wrapper (contains pipes, redirects, etc.)"""
        shell_operators = ['>', '<', '|', '&&', '||', ';', '$(', '`']
        return any(op in command for op in shell_operators)
    
    def _validate_container_execution(self, tool_name: str, input_files: List[str], output_dir: str) -> Dict[str, Any]:
        """Validate container execution parameters before running"""
        try:
            # Check if tool is supported
            if tool_name not in self._get_supported_tools():
                return {
                    'valid': False,
                    'error': f"Tool '{tool_name}' is not supported. Supported tools: {', '.join(self._get_supported_tools())}"
                }
            
            # Check if input files exist and are readable
            for input_file in input_files:
                input_path = Path(input_file)
                if not input_path.exists():
                    return {
                        'valid': False,
                        'error': f"Input file does not exist: {input_file}"
                    }
                if not os.access(input_file, os.R_OK):
                    return {
                        'valid': False,
                        'error': f"Input file is not readable: {input_file}"
                    }
            
            # Check if output directory can be created and is writable
            output_path = Path(output_dir)
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                if not os.access(output_dir, os.W_OK):
                    return {
                        'valid': False,
                        'error': f"Output directory is not writable: {output_dir}"
                    }
            except Exception as e:
                return {
                    'valid': False,
                    'error': f"Cannot create or access output directory {output_dir}: {e}"
                }
            
            # Check if Docker is available
            try:
                result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
                if result.returncode != 0:
                    return {
                        'valid': False,
                        'error': "Docker is not available or not running"
                    }
            except Exception as e:
                return {
                    'valid': False,
                    'error': f"Cannot access Docker: {e}"
                }
            
            # Check if container image exists
            image_name = self._get_container_image(tool_name)
            try:
                result = subprocess.run(
                    ["docker", "inspect", image_name], 
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    return {
                        'valid': False,
                        'error': f"Container image '{image_name}' does not exist. Please build the container first."
                    }
            except Exception as e:
                return {
                    'valid': False,
                    'error': f"Cannot check container image '{image_name}': {e}"
                }
            
            return {'valid': True, 'error': None}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Validation error: {e}"
            }
    
    def _validate_tool_output(self, tool_name: str, result: 'ContainerExecutionResult', 
                            input_files: List[str], output_dir: str) -> bool:
        """Simple validation - trust the exit code"""
        # Tool finished and we have reliable exit code - that's all we need!
        return result.exit_code == 0
    
    def _validate_docker_command(self, docker_cmd: List[str]) -> bool:
        """Validate Docker command before execution"""
        try:
            # Check if command starts with 'docker run'
            if not (len(docker_cmd) >= 2 and docker_cmd[0] == "docker" and docker_cmd[1] == "run"):
                self.logger.error("❌ Invalid Docker command: must start with 'docker run'")
                return False
            
            # Check for required volume mounts
            has_volume_mounts = any(arg.startswith("-v") or arg.startswith("--volume") for arg in docker_cmd)
            if not has_volume_mounts:
                self.logger.warning("⚠️ No volume mounts found in Docker command")
            
            # Check for container image
            if len(docker_cmd) < 3:
                self.logger.error("❌ Invalid Docker command: missing container image")
                return False
            
            # The last argument should be the container image
            image_name = docker_cmd[-1]
            if not image_name or not isinstance(image_name, str):
                self.logger.error("❌ Invalid Docker command: missing or invalid container image")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Docker command validation error: {e}")
            return False
    
    def _get_supported_tools(self) -> List[str]:
        """Dynamically discover all available tools from Docker images"""
        try:
            # Get all bioframe tool images
            result = subprocess.run([
                "docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "--filter", "reference=bioframe-*"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.warning("Could not list Docker images, falling back to default tools")
                return ["fastqc", "trimmomatic", "spades", "quast", "multiqc"]
            
            # Extract tool names from image names
            tools = []
            for line in result.stdout.strip().split('\n'):
                if line and 'bioframe-' in line:
                    # Extract tool name from "bioframe-toolname:tag"
                    image_name = line.split(':')[0]  # Remove tag
                    tool_name = image_name.replace('bioframe-', '')
                    if tool_name and tool_name not in tools:
                        tools.append(tool_name)
            
            if not tools:
                self.logger.warning("No bioframe tools found, falling back to default tools")
                return ["fastqc", "trimmomatic", "spades", "quast", "multiqc"]
            
            self.logger.info(f"🔍 Discovered {len(tools)} tools: {', '.join(tools)}")
            return tools
            
        except Exception as e:
            self.logger.error(f"Error discovering tools: {e}")
            return ["fastqc", "trimmomatic", "spades", "quast", "multiqc"]
    
    def _get_container_image(self, tool_name: str) -> str:
        """Dynamically get the appropriate container image for a tool"""
        # Standard naming convention: bioframe-{tool_name}:latest
        return f"bioframe-{tool_name.lower()}:latest"
    
    
    def _get_container_id_by_name(self, container_name: str) -> Optional[str]:
        """Get container ID by name with retry logic and better error handling"""
        if not container_name:
            self.logger.error("❌ Cannot get container ID: container_name is None or empty")
            return None
            
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ["docker", "ps", "-q", "-f", f"name={container_name}"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    container_id = result.stdout.strip()
                    self.logger.info(f"✅ Found container ID: {container_id} for {container_name}")
                    return container_id
                    
                # Container not found yet, wait and retry
                time.sleep(0.5)
                
            except subprocess.TimeoutExpired:
                self.logger.warning(f"⚠️ Timeout getting container ID for {container_name} (attempt {attempt + 1})")
            except Exception as e:
                self.logger.warning(f"⚠️ Error getting container ID for {container_name}: {e}")
                
        self.logger.warning(f"⚠️ Could not find container ID for {container_name} after {max_attempts} attempts")
        return None
    
    def force_completion_scan(self):
        """Manually trigger a scan for missed completions"""
        self.logger.info("🔍 Manually triggered completion scan")
        self._scan_for_missed_completions()
    
    def get_active_containers(self) -> Dict[str, Any]:
        """Get currently tracked active containers"""
        return self.active_containers.copy()
    
    def _collect_output_files(self, output_dir: str, tool_name: str) -> List[str]:
        """Collect output files from output directory"""
        output_path = Path(output_dir)
        output_files = []
        
        if output_path.exists():
            for file_path in output_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    output_files.append(str(file_path))
        
        return output_files
    
    
    def get_active_containers(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active containers"""
        return self.active_containers.copy()
    
    def stop_container(self, container_id: str) -> bool:
        """Stop a specific container"""
        try:
            result = subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.active_containers.pop(container_id, None)
                self.logger.info(f"🛑 Stopped container {container_id}")
                return True
            else:
                self.logger.error(f"Failed to stop container {container_id}: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error stopping container {container_id}: {e}")
            return False
    
    def cleanup_failed_containers(self) -> int:
        """Clean up any failed or stuck containers"""
        cleaned = 0
        for container_id, container_info in list(self.active_containers.items()):
            try:
                # Check if container is still running
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    status = result.stdout.strip()
                    if status not in ["running"]:
                        self.active_containers.pop(container_id, None)
                        cleaned += 1
                        self.logger.info(f"🧹 Cleaned up container {container_id} (status: {status})")
                else:
                    # Container not found
                    self.active_containers.pop(container_id, None)
                    cleaned += 1
                    self.logger.info(f"🧹 Cleaned up missing container {container_id}")
                    
            except Exception as e:
                self.logger.warning(f"Error checking container {container_id}: {e}")
        
        return cleaned
    
    def _monitor_container_with_fallback(self, container_name: str, container_id: str, 
                                       tool_name: str, process: subprocess.Popen) -> Tuple[List[str], List[str]]:
        """
        Robust container monitoring that avoids blocking I/O deadlocks.
        
        Uses a hybrid approach:
        1. Try non-blocking real-time monitoring for short periods
        2. Fall back to docker logs command for reliable output capture
        3. Monitor container status via docker inspect
        """
        stdout_lines = []
        stderr_lines = []
        
        try:
            # Method 1: Try short-term non-blocking monitoring
            max_realtime_attempts = 30  # 3 seconds of real-time monitoring
            realtime_attempts = 0
            
            while process.poll() is None and realtime_attempts < max_realtime_attempts:
                # Non-blocking read attempt
                try:
                    # Use select for non-blocking I/O on Unix-like systems
                    import select
                    ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                    
                    for stream in ready:
                        if stream == process.stdout:
                            line = stream.readline()
                            if line:
                                stdout_lines.append(line.rstrip())
                                self.logger.info(f"[{tool_name}] {line.rstrip()}")
                        elif stream == process.stderr:
                            line = stream.readline()
                            if line:
                                stderr_lines.append(line.rstrip())
                                self.logger.warning(f"[{tool_name}] {line.rstrip()}")
                                
                except (ImportError, OSError):
                    # Fallback for Windows or systems without select
                    break
                
                realtime_attempts += 1
                time.sleep(0.1)
            
            # Method 2: Container-based monitoring for long-running processes
            if process.poll() is None:
                self.logger.info(f"🔄 Switching to container-based monitoring for {tool_name}")
                container_stdout, container_stderr = self._monitor_container_via_docker_logs(
                    container_name, container_id, tool_name, process
                )
                stdout_lines.extend(container_stdout)
                stderr_lines.extend(container_stderr)
            else:
                # Process finished during real-time monitoring
                remaining_stdout, remaining_stderr = process.communicate()
                stdout_lines.extend(remaining_stdout.splitlines())
                stderr_lines.extend(remaining_stderr.splitlines())
                
        except Exception as e:
            self.logger.error(f"❌ Error in container monitoring for {tool_name}: {e}")
            # Fallback: just wait for process to complete
            try:
                stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout
                stdout_lines.extend(stdout.splitlines())
                stderr_lines.extend(stderr.splitlines())
            except subprocess.TimeoutExpired:
                self.logger.error(f"❌ Container {tool_name} timed out after 1 hour")
                process.kill()
                
        return stdout_lines, stderr_lines
    
    def _monitor_container_via_docker_logs(self, container_name: str, container_id: str,
                                         tool_name: str, process: subprocess.Popen) -> Tuple[List[str], List[str]]:
        """
        Monitor container via docker logs command instead of subprocess pipes.
        This avoids the blocking I/O issues with long-running containers.
        """
        stdout_lines = []
        stderr_lines = []
        last_log_size = 0
        
        self.logger.info(f"📊 Starting docker logs monitoring for {tool_name}")
        
        # If no container_id, try to get it again
        if not container_id:
            container_id = self._get_container_id_by_name(container_name)
            if not container_id:
                self.logger.error(f"❌ Cannot monitor container - ID not found for {container_name}")
                # Fall back to process.communicate()
                try:
                    stdout, stderr = process.communicate(timeout=3600)
                    return stdout.splitlines(), stderr.splitlines()
                except subprocess.TimeoutExpired:
                    process.kill()
                    return [], [f"Container {tool_name} timed out"]
        
        while process.poll() is None:
            try:
                # Get container status
                status_result = subprocess.run([
                    "docker", "inspect", "--format", "{{.State.Status}}", container_id
                ], capture_output=True, text=True, timeout=10)
                
                if status_result.returncode == 0:
                    container_status = status_result.stdout.strip()
                    
                    if container_status not in ["running"]:
                        # CORE FIX: Capture exit code before cleaning up
                        exit_code = self._capture_container_exit_code(container_id, tool_name)
                        self.logger.info(f"🏁 Container {tool_name} finished with status: {container_status}, exit_code: {exit_code}")
                        
                        # Update process returncode if we captured it
                        if exit_code is not None and hasattr(process, '_returncode'):
                            process._returncode = exit_code
                        
                        # Clean up container now that we have the exit code
                        self._cleanup_container(container_id, tool_name)
                        
                        break
                    
                    # Get container logs
                    logs_result = subprocess.run([
                        "docker", "logs", container_id
                    ], capture_output=True, text=True, timeout=30)
                    
                    if logs_result.returncode == 0:
                        # Process new log lines
                        all_output = logs_result.stdout + logs_result.stderr
                        current_lines = all_output.splitlines()
                        
                        # Only log new lines since last check
                        if len(current_lines) > last_log_size:
                            new_lines = current_lines[last_log_size:]
                            for line in new_lines:
                                if line.strip():
                                    stdout_lines.append(line)
                                    self.logger.info(f"[{tool_name}] {line}")
                            last_log_size = len(current_lines)
                
                else:
                    # Container not found, might have finished
                    self.logger.warning(f"⚠️ Container {container_id} not found, assuming finished")
                    break
                    
            except subprocess.TimeoutExpired:
                self.logger.warning(f"⚠️ Timeout checking container {tool_name}, continuing...")
            except Exception as e:
                self.logger.warning(f"⚠️ Error monitoring container {tool_name}: {e}")
            
            time.sleep(5)  # Check every 5 seconds instead of 0.1
        
        # Get final logs
        try:
            final_logs = subprocess.run([
                "docker", "logs", container_id
            ], capture_output=True, text=True, timeout=30)
            
            if final_logs.returncode == 0:
                final_output = final_logs.stdout + final_logs.stderr
                final_lines = final_output.splitlines()
                
                # Add any remaining new lines
                if len(final_lines) > last_log_size:
                    remaining_lines = final_lines[last_log_size:]
                    for line in remaining_lines:
                        if line.strip():
                            stdout_lines.append(line)
                            self.logger.info(f"[{tool_name}] {line}")
                            
        except Exception as e:
            self.logger.warning(f"⚠️ Error getting final logs for {tool_name}: {e}")
        
        # Wait for process to complete
        try:
            process.wait(timeout=60)  # Wait up to 1 minute for process cleanup
        except subprocess.TimeoutExpired:
            self.logger.warning(f"⚠️ Process cleanup timeout for {tool_name}")
            
        self.logger.info(f"✅ Container monitoring completed for {tool_name}")
        return stdout_lines, stderr_lines
    
    def _capture_container_exit_code(self, container_id: str, tool_name: str) -> Optional[int]:
        """Capture container exit code before cleanup"""
        try:
            result = subprocess.run([
                "docker", "inspect", "--format", "{{.State.ExitCode}}", container_id
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                exit_code_str = result.stdout.strip()
                exit_code = int(exit_code_str)
                self.logger.info(f"📋 Captured exit code {exit_code} for {tool_name}")
                return exit_code
            else:
                self.logger.warning(f"⚠️ Could not inspect container {container_id}")
                return None
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error capturing exit code for {tool_name}: {e}")
            return None
    
    def _cleanup_container(self, container_id: str, tool_name: str):
        """Remove container after capturing exit code"""
        try:
            subprocess.run([
                "docker", "rm", container_id
            ], capture_output=True, text=True, timeout=10)
            self.logger.info(f"🧹 Cleaned up container {container_id} for {tool_name}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error cleaning up container {container_id}: {e}")
    
class ContainerExecutionResult:
    """Enhanced result of a container execution with detailed tracking information"""
    
    def __init__(self, success: bool, output_files: List[str], error_message: str, 
                 execution_time: float = 0.0, container_id: str = None, 
                 container_name: str = None, stdout: str = "", stderr: str = "", 
                 exit_code: int = 0, tool_version: str = None, 
                 memory_used: str = None, cpu_time: str = None):
        self.success = success
        self.output_files = output_files
        self.error_message = error_message
        self.execution_time = execution_time
        self.container_id = container_id
        self.container_name = container_name
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.tool_version = tool_version
        self.memory_used = memory_used
        self.cpu_time = cpu_time
        self.timestamp = datetime.now().isoformat()


class WorkflowOrchestrator:
    """Orchestrates the execution of bioinformatics workflows"""
    
    def __init__(self, data_dir: str, init_docker: bool = True):
        self.data_dir = Path(data_dir)
        self.runs_dir = self.data_dir / "runs"
        self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging first
        self._setup_logging()
        
        # Initialize Docker if requested
        if init_docker:
            self._init_docker()
            
        # Initialize container process manager
        self.container_manager = ContainerProcessManager(self.logger, str(data_dir))
        self.container_manager.start_monitoring()
        
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
            
    def execute_pipeline_workflow_enhanced(self, run_id: str, input_files: List[str], 
                                          workflow_config: Dict[str, Any]) -> bool:
        """Enhanced pipeline workflow execution with container-based processing"""
        start_time = time.time()
        
        try:
            # Load workflow definition
            workflow_file = self.runs_dir / run_id / "workflow.yaml"
            if not workflow_file.exists():
                raise FileNotFoundError(f"Workflow file not found: {workflow_file}")
                
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
                
            # Initialize dynamic logger
            workflow_logger = DynamicWorkflowLogger(run_id, workflow.get("workflow_name", "Unknown"), str(self.data_dir))
            
            # Log workflow start
            tools = workflow.get("tools", [])
            workflow_logger.log_workflow_start(workflow.get("workflow_name", "Unknown"), tools, len(tools))
            
            # Handle input files
            inputs_dir = self.runs_dir / run_id / "inputs"
            inputs_dir.mkdir(exist_ok=True)
            
            copied_files = []
            for input_file in input_files:
                input_path = Path(input_file)
                if input_path.exists():
                    if str(input_path).startswith(str(inputs_dir)):
                        copied_files.append(str(input_path))
                        workflow_logger.log_step_progress(1, "file_copy", f"Using existing file: {input_path}")
                    else:
                        dest_file = inputs_dir / input_path.name
                        shutil.copy2(input_file, dest_file)
                        copied_files.append(str(dest_file))
                        workflow_logger.log_step_progress(1, "file_copy", f"Copied {input_file} to {dest_file}")
                else:
                    workflow_logger.log_step_progress(1, "file_copy", f"Input file not found: {input_file}", "WARNING")
                    
            # Execute each tool in the pipeline using container manager
            current_inputs = copied_files
            step_number = 1
            step_results = []
            
            for tool_name in tools:
                try:
                    # Create tool output directory
                    tool_output_dir = self.runs_dir / run_id / f"step_{step_number}_{tool_name}"
                    tool_output_dir.mkdir(exist_ok=True)
                    
                    # Log step start
                    workflow_logger.log_step_start(step_number, tool_name, current_inputs, str(tool_output_dir))
                    
                    # Execute tool using container manager
                    tool_config = {
                        'step_number': step_number,
                        'workflow_id': run_id
                        # No timeout - let tools run as long as needed
                    }
                    
                    result = self.container_manager.execute_tool_in_container(
                        tool_name, current_inputs, str(tool_output_dir), 
                        run_id, step_number, tool_config
                    )
                    
                    # Store step result for rerun capability
                    step_result = {
                        'step_number': step_number,
                        'tool_name': tool_name,
                        'input_files': current_inputs,
                        'output_dir': str(tool_output_dir),
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    }
                    step_results.append(step_result)
                    
                    # Save step result for rerun capability
                    self._save_step_result(run_id, step_result)
                    
                    # Log step completion
                    workflow_logger.log_step_completion(step_number, tool_name, result)
                    
                    if result.success:
                        # Update inputs for next step
                        current_inputs = result.output_files
                        step_number += 1
                        
                        # Log progress
                        workflow_logger.log_step_progress(step_number-1, tool_name, 
                            f"Tool completed successfully. Output files: {len(result.output_files)}")
                        
                        # Log that we're ready for the next step
                        if step_number <= len(tools):
                            next_tool = tools[step_number-1]
                            workflow_logger.log_step_progress(step_number, next_tool, 
                                f"Previous step completed successfully. Ready to start {next_tool} with {len(current_inputs)} input files.")
                    else:
                        # Tool failed - provide rerun information
                        workflow_logger.log_step_progress(step_number, tool_name, 
                            f"Tool failed: {result.error_message}", "ERROR")
                        
                        # Log rerun information
                        self._log_rerun_information(run_id, step_number, tool_name, result, workflow_logger)
                        
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
            
            # Save workflow execution summary
            self._save_workflow_execution_summary(run_id, step_results, total_time)
            
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
                    "total_steps": len(tools) if 'tools' in locals() else 0,
                    "completed_steps": step_number - 1 if 'step_number' in locals() else 0,
                    "current_inputs": current_inputs if 'current_inputs' in locals() else [],
                    "last_output_dir": tool_output_dir if 'tool_output_dir' in locals() else "unknown"
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
    
    def _save_step_result(self, run_id: str, step_result: Dict[str, Any]):
        """Save step result for rerun capability"""
        try:
            run_dir = self.runs_dir / run_id
            step_results_dir = run_dir / "step_results"
            step_results_dir.mkdir(exist_ok=True)
            
            step_file = step_results_dir / f"step_{step_result['step_number']}_{step_result['tool_name']}.json"
            
            # Convert ContainerExecutionResult to dict for JSON serialization
            result_dict = {
                'success': step_result['result'].success,
                'output_files': step_result['result'].output_files,
                'error_message': step_result['result'].error_message,
                'execution_time': step_result['result'].execution_time,
                'container_id': step_result['result'].container_id,
                'container_name': step_result['result'].container_name,
                'stdout': step_result['result'].stdout,
                'stderr': step_result['result'].stderr,
                'exit_code': step_result['result'].exit_code,
                'timestamp': step_result['result'].timestamp
            }
            
            step_data = {
                'step_number': step_result['step_number'],
                'tool_name': step_result['tool_name'],
                'input_files': step_result['input_files'],
                'output_dir': step_result['output_dir'],
                'result': result_dict,
                'timestamp': step_result['timestamp']
            }
            
            with open(step_file, 'w') as f:
                json.dump(step_data, f, indent=2, default=str)
                
        except Exception as e:
            self.logger.error(f"Failed to save step result: {e}")
    
    def _log_rerun_information(self, run_id: str, step_number: int, tool_name: str, 
                              result: 'ContainerExecutionResult', workflow_logger):
        """Log detailed rerun information when a step fails"""
        try:
            rerun_info = {
                'workflow_id': run_id,
                'failed_step': step_number,
                'failed_tool': tool_name,
                'container_id': result.container_id,
                'container_name': result.container_name,
                'exit_code': result.exit_code,
                'error_message': result.error_message,
                'execution_time': result.execution_time,
                'timestamp': result.timestamp
            }
            
            # Save rerun information
            run_dir = self.runs_dir / run_id
            rerun_file = run_dir / f"rerun_info_step_{step_number}.json"
            with open(rerun_file, 'w') as f:
                json.dump(rerun_info, f, indent=2, default=str)
            
            # Log rerun instructions
            workflow_logger.log_step_progress(step_number, tool_name, 
                f"Rerun information saved to: {rerun_file}", "INFO")
            workflow_logger.log_step_progress(step_number, tool_name, 
                f"Container ID: {result.container_id}", "INFO")
            workflow_logger.log_step_progress(step_number, tool_name, 
                f"Exit code: {result.exit_code}", "INFO")
            
        except Exception as e:
            self.logger.error(f"Failed to log rerun information: {e}")
    
    def _save_workflow_execution_summary(self, run_id: str, step_results: List[Dict[str, Any]], 
                                       total_time: float):
        """Save comprehensive workflow execution summary"""
        try:
            run_dir = self.runs_dir / run_id
            summary_file = run_dir / "workflow_execution_summary.json"
            
            summary = {
                'workflow_id': run_id,
                'total_execution_time': total_time,
                'total_steps': len(step_results),
                'completed_steps': len([r for r in step_results if r['result'].success]),
                'failed_steps': len([r for r in step_results if not r['result'].success]),
                'step_results': step_results,
                'execution_timestamp': datetime.now().isoformat(),
                'container_manager_status': {
                    'active_containers': len(self.container_manager.get_active_containers()),
                    'monitoring_active': self.container_manager.running
                }
            }
            
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
                
            self.logger.info(f"📊 Workflow execution summary saved to: {summary_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save workflow execution summary: {e}")
    
    def rerun_failed_step(self, run_id: str, step_number: int) -> bool:
        """Rerun a specific failed step"""
        try:
            run_dir = self.runs_dir / run_id
            step_results_dir = run_dir / "step_results"
            
            # Find the step result file
            step_files = list(step_results_dir.glob(f"step_{step_number}_*.json"))
            if not step_files:
                self.logger.error(f"No step result found for step {step_number}")
                return False
            
            step_file = step_files[0]
            with open(step_file, 'r') as f:
                step_data = json.load(f)
            
            # Extract step information
            tool_name = step_data['tool_name']
            input_files = step_data['input_files']
            output_dir = step_data['output_dir']
            
            self.logger.info(f"🔄 Rerunning step {step_number} ({tool_name})")
            
            # Clean up previous output
            if Path(output_dir).exists():
                shutil.rmtree(output_dir)
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Execute the step again
            tool_config = {
                'step_number': step_number,
                'workflow_id': run_id
                # No timeout - let tools run as long as needed
            }
            
            result = self.container_manager.execute_tool_in_container(
                tool_name, input_files, output_dir, run_id, step_number, tool_config
            )
            
            if result.success:
                self.logger.info(f"✅ Step {step_number} rerun successful")
                return True
            else:
                self.logger.error(f"❌ Step {step_number} rerun failed: {result.error_message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to rerun step {step_number}: {e}")
            return False
    
    def get_workflow_execution_status(self, run_id: str) -> Dict[str, Any]:
        """Get detailed workflow execution status including container information"""
        try:
            run_dir = self.runs_dir / run_id
            summary_file = run_dir / "workflow_execution_summary.json"
            
            status = {
                'workflow_id': run_id,
                'run_dir_exists': run_dir.exists(),
                'summary_file_exists': summary_file.exists(),
                'active_containers': self.container_manager.get_active_containers(),
                'container_manager_status': {
                    'monitoring_active': self.container_manager.running,
                    'total_active_containers': len(self.container_manager.get_active_containers())
                }
            }
            
            if summary_file.exists():
                with open(summary_file, 'r') as f:
                    summary = json.load(f)
                status.update(summary)
            
            return status
            
        except Exception as e:
            return {'error': f"Failed to get execution status: {e}"}
    
    def cleanup_workflow_containers(self, run_id: str) -> int:
        """Clean up all containers associated with a workflow"""
        cleaned = 0
        try:
            active_containers = self.container_manager.get_active_containers()
            for container_id, container_info in active_containers.items():
                if container_info.get('workflow_id') == run_id:
                    if self.container_manager.stop_container(container_id):
                        cleaned += 1
            
            self.logger.info(f"🧹 Cleaned up {cleaned} containers for workflow {run_id}")
            return cleaned
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup containers for workflow {run_id}: {e}")
            return 0
    
    def __del__(self):
        """Cleanup when orchestrator is destroyed"""
        try:
            if hasattr(self, 'container_manager'):
                self.container_manager.stop_monitoring()
        except:
            pass


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
