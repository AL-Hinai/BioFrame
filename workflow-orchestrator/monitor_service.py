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
        """Check for new workflow trigger files"""
        if not self.runs_dir.exists():
            return
            
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
                
            run_id = run_dir.name
            trigger_file = run_dir / "execute_workflow.trigger"
            
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

def main():
    """Main entry point"""
    monitor = WorkflowMonitor()
    monitor.monitor_workflows()

if __name__ == "__main__":
    main()

