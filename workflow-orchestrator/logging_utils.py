#!/usr/bin/env python3
"""
BioFrame Logging Utilities
Provides structured logging, execution tracking, and error reporting for bioinformatics tools
"""

import logging
import logging.handlers
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager


@dataclass
class ToolExecutionLog:
    """Structured log entry for tool execution"""
    timestamp: str
    tool_name: str
    step_number: int
    total_steps: int
    event_type: str  # start, progress, success, failure, warning
    message: str
    details: Dict[str, Any]
    execution_time: Optional[float] = None
    input_files: Optional[List[str]] = None
    output_files: Optional[List[str]] = None
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowExecutionLog:
    """Structured log entry for workflow execution"""
    timestamp: str
    workflow_id: str
    event_type: str  # start, tool_start, tool_complete, tool_fail, complete, fail
    message: str
    details: Dict[str, Any]
    tool_name: Optional[str] = None
    step_number: Optional[int] = None
    total_steps: Optional[int] = None


class BioFrameLogger:
    """Enhanced logger for BioFrame with structured logging and execution tracking"""
    
    def __init__(self, name: str, log_dir: Path, workflow_id: str = None):
        self.name = name
        self.log_dir = Path(log_dir)
        self.workflow_id = workflow_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for all logs
        all_logs_file = self.log_dir / f"{name}_all.log"
        file_handler = logging.handlers.RotatingFileHandler(
            all_logs_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Structured JSON logs for execution tracking
        if workflow_id:
            json_logs_file = self.log_dir / f"{workflow_id}_execution.json"
            self.json_logs_file = json_logs_file
            self.execution_logs = []
        else:
            self.json_logs_file = None
            self.execution_logs = []
    
    def log_tool_execution(self, log_entry: ToolExecutionLog):
        """Log a tool execution event"""
        self.execution_logs.append(log_entry)
        
        # Write to JSON file if available
        if self.json_logs_file:
            try:
                with open(self.json_logs_file, 'w') as f:
                    json.dump([asdict(log) for log in self.execution_logs], f, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to write JSON log: {e}")
        
        # Also log to standard logger
        if log_entry.event_type == 'start':
            self.logger.info(f"🔄 {log_entry.message}")
        elif log_entry.event_type == 'progress':
            self.logger.info(f"📊 {log_entry.message}")
        elif log_entry.event_type == 'success':
            self.logger.info(f"✅ {log_entry.message}")
        elif log_entry.event_type == 'failure':
            self.logger.error(f"❌ {log_entry.message}")
        elif log_entry.event_type == 'warning':
            self.logger.warning(f"⚠️ {log_entry.message}")
    
    def log_workflow_execution(self, log_entry: WorkflowExecutionLog):
        """Log a workflow execution event"""
        self.execution_logs.append(log_entry)
        
        # Write to JSON file if available
        if self.json_logs_file:
            try:
                with open(self.json_logs_file, 'w') as f:
                    json.dump([asdict(log) for log in self.execution_logs], f, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to write JSON log: {e}")
        
        # Also log to standard logger
        if log_entry.event_type == 'start':
            self.logger.info(f"🚀 {log_entry.message}")
        elif log_entry.event_type == 'tool_start':
            self.logger.info(f"🔄 {log_entry.message}")
        elif log_entry.event_type == 'tool_complete':
            self.logger.info(f"✅ {log_entry.message}")
        elif log_entry.event_type == 'tool_fail':
            self.logger.error(f"❌ {log_entry.message}")
        elif log_entry.event_type == 'complete':
            self.logger.info(f"🎉 {log_entry.message}")
        elif log_entry.event_type == 'fail':
            self.logger.error(f"💥 {log_entry.message}")
    
    @contextmanager
    def tool_execution_context(self, tool_name: str, step_number: int, total_steps: int, 
                             input_files: List[str] = None):
        """Context manager for tracking tool execution"""
        start_time = time.time()
        
        # Log tool start
        start_log = ToolExecutionLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            step_number=step_number,
            total_steps=total_steps,
            event_type='start',
            message=f'Starting execution of {tool_name} (step {step_number}/{total_steps})',
            details={'input_file_count': len(input_files) if input_files else 0},
            input_files=input_files
        )
        self.log_tool_execution(start_log)
        
        try:
            yield self
            execution_time = time.time() - start_time
            
            # Log tool success
            success_log = ToolExecutionLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                step_number=step_number,
                total_steps=total_steps,
                event_type='success',
                message=f'Successfully completed {tool_name} in {execution_time:.2f} seconds',
                details={'execution_time': execution_time},
                execution_time=execution_time
            )
            self.log_tool_execution(success_log)
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Log tool failure
            failure_log = ToolExecutionLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                step_number=step_number,
                total_steps=total_steps,
                event_type='failure',
                message=f'Failed to execute {tool_name}: {str(e)}',
                details={
                    'execution_time': execution_time,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                },
                execution_time=execution_time,
                error_details={
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc()
                }
            )
            self.log_tool_execution(failure_log)
            raise
    
    def log_progress(self, tool_name: str, step_number: int, total_steps: int, 
                    message: str, details: Dict[str, Any] = None):
        """Log progress during tool execution"""
        progress_log = ToolExecutionLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            step_number=step_number,
            total_steps=total_steps,
            event_type='progress',
            message=message,
            details=details or {}
        )
        self.log_tool_execution(progress_log)
    
    def log_warning(self, tool_name: str, step_number: int, total_steps: int, 
                   message: str, details: Dict[str, Any] = None):
        """Log warnings during tool execution"""
        warning_log = ToolExecutionLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            step_number=step_number,
            total_steps=total_steps,
            event_type='warning',
            message=message,
            details=details or {}
        )
        self.log_tool_execution(warning_log)


def create_execution_summary(execution_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a summary of execution logs"""
    if not execution_logs:
        return {}
    
    summary = {
        'total_events': len(execution_logs),
        'workflow_events': [],
        'tool_events': [],
        'errors': [],
        'warnings': [],
        'execution_timeline': []
    }
    
    for log in execution_logs:
        # Add to timeline
        summary['execution_timeline'].append({
            'timestamp': log.get('timestamp'),
            'event_type': log.get('event_type'),
            'message': log.get('message'),
            'tool_name': log.get('tool_name')
        })
        
        # Categorize events
        if log.get('event_type') in ['start', 'complete', 'fail']:
            summary['workflow_events'].append(log)
        elif log.get('event_type') in ['tool_start', 'tool_complete', 'tool_fail']:
            summary['tool_events'].append(log)
        
        # Track errors and warnings
        if 'error' in log.get('event_type', '').lower() or 'fail' in log.get('event_type', '').lower():
            summary['errors'].append(log)
        elif 'warning' in log.get('event_type', '').lower():
            summary['warnings'].append(log)
    
    return summary


def generate_execution_report(workflow_id: str, execution_logs: List[Dict[str, Any]], 
                            output_dir: Path) -> Path:
    """Generate a comprehensive execution report"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create summary
    summary = create_execution_summary(execution_logs)
    
    # Generate HTML report
    html_report = output_dir / f"{workflow_id}_execution_report.html"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BioFrame Execution Report - {workflow_id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .error {{ background-color: #ffe6e6; border-left: 4px solid #ff0000; }}
            .warning {{ background-color: #fff2cc; border-left: 4px solid #ffcc00; }}
            .success {{ background-color: #d4edda; border-left: 4px solid #28a745; }}
            .timeline {{ background-color: #f8f9fa; padding: 10px; }}
            .timeline-item {{ margin: 5px 0; padding: 5px; border-left: 3px solid #007bff; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>BioFrame Execution Report</h1>
            <p><strong>Workflow ID:</strong> {workflow_id}</p>
            <p><strong>Generated:</strong> {datetime.now(timezone.utc).isoformat()}</p>
        </div>
        
        <div class="section">
            <h2>Execution Summary</h2>
            <p><strong>Total Events:</strong> {summary.get('total_events', 0)}</p>
            <p><strong>Workflow Events:</strong> {len(summary.get('workflow_events', []))}</p>
            <p><strong>Tool Events:</strong> {len(summary.get('tool_events', []))}</p>
            <p><strong>Errors:</strong> {len(summary.get('errors', []))}</p>
            <p><strong>Warnings:</strong> {len(summary.get('warnings', []))}</p>
        </div>
        
        <div class="section">
            <h2>Execution Timeline</h2>
            <div class="timeline">
    """
    
    for event in summary.get('execution_timeline', []):
        html_content += f"""
                <div class="timeline-item">
                    <strong>{event.get('timestamp', 'N/A')}</strong> - 
                    {event.get('event_type', 'N/A')}: {event.get('message', 'N/A')}
                    {f" (Tool: {event.get('tool_name')})" if event.get('tool_name') else ''}
                </div>
        """
    
    html_content += """
            </div>
        </div>
    """
    
    if summary.get('errors'):
        html_content += """
        <div class="section error">
            <h2>Errors</h2>
            <table>
                <tr><th>Timestamp</th><th>Tool</th><th>Message</th></tr>
        """
        for error in summary['errors']:
            html_content += f"""
                <tr>
                    <td>{error.get('timestamp', 'N/A')}</td>
                    <td>{error.get('tool_name', 'N/A')}</td>
                    <td>{error.get('message', 'N/A')}</td>
                </tr>
            """
        html_content += """
            </table>
        </div>
        """
    
    if summary.get('warnings'):
        html_content += """
        <div class="section warning">
            <h2>Warnings</h2>
            <table>
                <tr><th>Timestamp</th><th>Tool</th><th>Message</th></tr>
        """
        for warning in summary['warnings']:
            html_content += f"""
                <tr>
                    <td>{warning.get('timestamp', 'N/A')}</td>
                    <td>{warning.get('tool_name', 'N/A')}</td>
                    <td>{warning.get('message', 'N/A')}</td>
                </tr>
            """
        html_content += """
            </table>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    with open(html_report, 'w') as f:
        f.write(html_content)
    
    return html_report
