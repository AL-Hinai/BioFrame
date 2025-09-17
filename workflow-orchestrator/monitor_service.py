#!/usr/bin/env python3
"""
Workflow Orchestrator Monitoring Service
Monitors for workflow trigger files and executes workflows automatically
"""

import os
import time
import json
import yaml
from pathlib import Path
from datetime import datetime
import logging
from orchestrator import WorkflowOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("workflow_monitor")

class WorkflowMonitor:
    """Monitors for workflow trigger files and executes workflows"""
    
    def __init__(self, data_dir: str = "/data"):
        self.data_dir = Path(data_dir)
        self.runs_dir = self.data_dir / "runs"
        self.orchestrator = WorkflowOrchestrator(data_dir, init_docker=True)
        self.processed_triggers = set()
        
        logger.info("🔍 Workflow Monitor initialized")
        logger.info(f"📁 Monitoring directory: {self.runs_dir}")
        
    def monitor_workflows(self):
        """Main monitoring loop"""
        logger.info("🚀 Starting workflow monitoring service...")
        
        while True:
            try:
                self._check_for_new_workflows()
                time.sleep(5)  # Check every 5 seconds
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring service stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(10)  # Wait longer on error
    
    def _check_for_new_workflows(self):
        """Check for new workflow trigger files and resume stuck workflows"""
        if not self.runs_dir.exists():
            return
            
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
                
            run_id = run_dir.name
            trigger_file = run_dir / "execute_workflow.trigger"
            
            # Check for stuck workflows that need resumption (regardless of trigger file)
            self._check_for_stuck_workflow(run_dir, run_id)
            
            # Skip if already processed or no trigger file
            if run_id in self.processed_triggers or not trigger_file.exists():
                continue
            
            # Check if workflow is ready for execution
            workflow_file = run_dir / "workflow.yaml"
            if not workflow_file.exists():
                logger.warning(f"⚠️ No workflow.yaml found for {run_id}")
                continue
            
            # Load workflow configuration
            try:
                with open(workflow_file, 'r') as f:
                    workflow_config = yaml.safe_load(f)
                
                if workflow_config.get('status') != 'ready_for_execution':
                    continue
                    
                logger.info(f"🎯 Found new workflow to execute: {run_id}")
                
                # Get input files
                input_dir = run_dir / "inputs"
                input_files = []
                if input_dir.exists():
                    input_files = [str(f) for f in input_dir.iterdir() if f.is_file()]
                
                if not input_files:
                    logger.warning(f"⚠️ No input files found for {run_id}")
                    continue
                
                # Mark as processed to avoid duplicate execution
                self.processed_triggers.add(run_id)
                
                # Execute workflow in background
                self._execute_workflow_async(run_id, input_files, workflow_config)
                
            except Exception as e:
                logger.error(f"❌ Error processing workflow {run_id}: {e}")
    
    def _execute_workflow_async(self, run_id: str, input_files: list, workflow_config: dict):
        """Execute workflow asynchronously"""
        import threading
        
        def execute():
            try:
                logger.info(f"🚀 Starting execution of workflow: {run_id}")
                
                # Update status to running
                workflow_config['status'] = 'running'
                workflow_config['started_at'] = datetime.now().isoformat()
                
                workflow_file = self.runs_dir / run_id / "workflow.yaml"
                with open(workflow_file, 'w') as f:
                    yaml.dump(workflow_config, f, default_flow_style=False)
                
                # Execute the workflow
                success = self.orchestrator.execute_pipeline_workflow_enhanced(
                    run_id=run_id,
                    input_files=input_files,
                    workflow_config=workflow_config
                )
                
                # Update final status
                if success:
                    workflow_config['status'] = 'completed'
                    workflow_config['completed_at'] = datetime.now().isoformat()
                    logger.info(f"✅ Workflow {run_id} completed successfully")
                else:
                    workflow_config['status'] = 'failed'
                    workflow_config['failed_at'] = datetime.now().isoformat()
                    logger.error(f"❌ Workflow {run_id} failed")
                
                # Save final status
                with open(workflow_file, 'w') as f:
                    yaml.dump(workflow_config, f, default_flow_style=False)
                
                # Remove trigger file
                trigger_file = self.runs_dir / run_id / "execute_workflow.trigger"
                if trigger_file.exists():
                    trigger_file.unlink()
                    
            except Exception as e:
                logger.error(f"❌ Error executing workflow {run_id}: {e}")
                
                # Update status to failed
                try:
                    workflow_config['status'] = 'failed'
                    workflow_config['failed_at'] = datetime.now().isoformat()
                    workflow_config['error'] = str(e)
                    
                    workflow_file = self.runs_dir / run_id / "workflow.yaml"
                    with open(workflow_file, 'w') as f:
                        yaml.dump(workflow_config, f, default_flow_style=False)
                except:
                    pass
        
        # Start execution in background thread
        thread = threading.Thread(target=execute, daemon=True)
        thread.start()
    
    def _check_for_stuck_workflow(self, run_dir: Path, run_id: str):
        """Check if a workflow is stuck and can be resumed"""
        try:
            workflow_file = run_dir / "workflow.yaml"
            if not workflow_file.exists():
                return
                
            with open(workflow_file, 'r') as f:
                workflow_config = yaml.safe_load(f)
            
            # Only check running workflows
            status = workflow_config.get('status')
            if status != 'running':
                return
            
            logger.info(f"🔍 Checking workflow {run_id} with status: {status}")
            
            # Check if this workflow has been stuck for a while and has completed steps
            step_results_dir = run_dir / "step_results"
            if not step_results_dir.exists():
                return
            
            # Get completed steps
            completed_steps = []
            for step_file in step_results_dir.glob("step_*.json"):
                try:
                    with open(step_file, 'r') as f:
                        step_data = json.load(f)
                        if step_data.get('result', {}).get('success', False):
                            completed_steps.append(step_data.get('step_number', 0))
                except:
                    continue
            
            if not completed_steps:
                return
            
            # Check if we can resume this workflow
            tools = workflow_config.get('tools', [])
            max_completed_step = max(completed_steps) if completed_steps else 0
            next_step = max_completed_step + 1
            
            # If there are more steps to execute, try to resume
            if next_step <= len(tools):
                logger.info(f"🔄 Found stuck workflow {run_id} - resuming from step {next_step}")
                self._resume_workflow(run_id, workflow_config, max_completed_step)
                
        except Exception as e:
            logger.error(f"❌ Error checking stuck workflow {run_id}: {e}")
    
    def _resume_workflow(self, run_id: str, workflow_config: dict, last_completed_step: int):
        """Resume a stuck workflow from where it left off"""
        try:
            # Mark as processed to avoid duplicate resumption
            if run_id in self.processed_triggers:
                return
            self.processed_triggers.add(run_id)
            
            # Get input files from the last completed step
            run_dir = self.runs_dir / run_id
            last_step_dir = run_dir / f"step_{last_completed_step}_{workflow_config['tools'][last_completed_step-1]}"
            
            input_files = []
            if last_step_dir.exists():
                # Get output files from last completed step as input for next step
                input_files = [str(f) for f in last_step_dir.iterdir() if f.is_file()]
            
            if not input_files:
                logger.warning(f"⚠️ No output files found from step {last_completed_step} for resumption")
                return
            
            # Execute workflow continuation
            self._execute_workflow_continuation(run_id, input_files, workflow_config, last_completed_step + 1)
            
        except Exception as e:
            logger.error(f"❌ Error resuming workflow {run_id}: {e}")
    
    def _execute_workflow_continuation(self, run_id: str, input_files: list, workflow_config: dict, start_step: int):
        """Execute workflow continuation from a specific step"""
        import threading
        
        def execute():
            try:
                logger.info(f"🚀 Resuming workflow {run_id} from step {start_step}")
                
                # Create a modified workflow config for continuation
                remaining_tools = workflow_config['tools'][start_step-1:]
                continuation_config = workflow_config.copy()
                continuation_config['tools'] = remaining_tools
                continuation_config['resumed_at'] = datetime.now().isoformat()
                continuation_config['resumed_from_step'] = start_step
                continuation_config['original_run_id'] = run_id
                
                # Execute the remaining workflow
                success = self.orchestrator.execute_pipeline_workflow_enhanced(
                    run_id=run_id,
                    input_files=input_files,
                    workflow_config=continuation_config
                )
                
                # Update final status
                if success:
                    workflow_config['status'] = 'completed'
                    workflow_config['completed_at'] = datetime.now().isoformat()
                    logger.info(f"✅ Workflow {run_id} resumed and completed successfully")
                else:
                    workflow_config['status'] = 'failed'
                    workflow_config['failed_at'] = datetime.now().isoformat()
                    logger.error(f"❌ Workflow {run_id} resumption failed")
                
                # Save final status
                workflow_file = self.runs_dir / run_id / "workflow.yaml"
                with open(workflow_file, 'w') as f:
                    yaml.dump(workflow_config, f, default_flow_style=False)
                
                # Remove trigger file if exists
                trigger_file = self.runs_dir / run_id / "execute_workflow.trigger"
                if trigger_file.exists():
                    trigger_file.unlink()
                    
            except Exception as e:
                logger.error(f"❌ Error executing workflow continuation {run_id}: {e}")
        
        # Start execution in background thread
        thread = threading.Thread(target=execute, daemon=True)
        thread.start()

def main():
    """Main entry point"""
    monitor = WorkflowMonitor()
    monitor.monitor_workflows()

if __name__ == "__main__":
    main()

