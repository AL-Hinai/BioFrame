#!/usr/bin/env python3
"""
Simple test script for workflow execution
"""

import os
import sys
import uuid
from pathlib import Path

# Add the workflow-orchestrator to the path
sys.path.append('/workflow')

from orchestrator import WorkflowOrchestrator

def test_simple_workflow():
    """Test a simple workflow execution"""
    
    print("🧪 Starting Simple Workflow Test")
    print("=" * 50)
    
    # Initialize orchestrator
    data_dir = "/data"
    orchestrator = WorkflowOrchestrator(data_dir, init_docker=True)
    
    # Create a test workflow run
    run_id = f"simple-test-{uuid.uuid4().hex[:8]}"
    workflow_name = f"Simple Test Workflow {run_id}"
    tools = ["fastqc"]  # Start with just FastQC
    
    # Use the existing input files
    input_files = [
        "/data/runs/7a99cfa8-8aea-4c06-9fb8-b3ed8ae66b68/inputs/ecoli_lowqual_R1.fastq.gz",
        "/data/runs/7a99cfa8-8aea-4c06-9fb8-b3ed8ae66b68/inputs/ecoli_lowqual_R2.fastq.gz"
    ]
    
    # Check if input files exist
    for input_file in input_files:
        if not Path(input_file).exists():
            print(f"❌ Input file not found: {input_file}")
            return False
        else:
            print(f"✅ Input file found: {input_file}")
    
    print(f"\n🚀 Creating workflow run: {run_id}")
    print(f"📋 Tools: {', '.join(tools)}")
    print(f"📁 Input files: {len(input_files)} files")
    
    try:
        # Create the workflow run
        workflow = orchestrator.create_sample_run(
            run_id=run_id,
            workflow_name=workflow_name,
            tools=tools,
            input_files=input_files,
            output_dir=f"/data/runs/{run_id}/outputs"
        )
        
        print(f"✅ Workflow created successfully")
        print(f"📄 Workflow ID: {run_id}")
        
        # Execute the workflow
        print(f"\n🔄 Executing workflow...")
        print("-" * 30)
        
        success = orchestrator.execute_pipeline_workflow_enhanced(
            run_id=run_id,
            input_files=input_files,
            workflow_config={}
        )
        
        if success:
            print(f"\n🎉 Workflow completed successfully!")
            
            # Check output files
            run_dir = Path(f"/data/runs/{run_id}")
            output_files = []
            for file_path in run_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    output_files.append(str(file_path.relative_to(run_dir)))
            
            print(f"📁 Generated {len(output_files)} output files:")
            for file_path in sorted(output_files):
                print(f"   - {file_path}")
                
            return True
        else:
            print(f"\n❌ Workflow failed!")
            return False
            
    except Exception as e:
        print(f"\n💥 Error during workflow execution: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simple_workflow()
    if success:
        print(f"\n✅ Simple test completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Simple test failed!")
        sys.exit(1)
