#!/usr/bin/env python3
"""
Test script to demonstrate the BioFrame Pipeline Workflow functionality
"""

import sys
import os
sys.path.append('./workflow-orchestrator')

from orchestrator import WorkflowOrchestrator
from pathlib import Path

def test_pipeline_workflow():
    """Test the pipeline workflow execution"""
    print("🧪 Testing BioFrame Pipeline Workflow")
    print("=" * 50)
    
    # Initialize orchestrator
    orchestrator = WorkflowOrchestrator(data_dir="./data", init_docker=False)
    
    # Create a test workflow run
    print("📝 Creating test workflow run...")
    workflow_run = orchestrator.create_sample_run(
        name="Test Quality Control Pipeline",
        description="Testing the pipeline workflow where each tool's output becomes the next tool's input",
        tools=['fastqc', 'trimmomatic', 'multiqc']
    )
    
    print(f"✅ Created workflow run: {workflow_run.id}")
    print(f"📁 Run directory: {workflow_run.run_directory}")
    print(f"🔧 Tools: {[tool.tool_name for tool in workflow_run.tools]}")
    
    # Create some dummy input files for testing
    print("\n📁 Creating test input files...")
    input_dir = Path(workflow_run.run_directory) / "input"
    input_dir.mkdir(exist_ok=True)
    
    # Create a dummy FASTQ file
    test_fastq = input_dir / "test_sample.fastq"
    test_fastq.write_text("""@test_read1
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
@test_read2
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII""")
    
    print(f"✅ Created test FASTQ file: {test_fastq}")
    
    # Execute the pipeline workflow
    print("\n🚀 Executing pipeline workflow...")
    print("Pipeline flow:")
    print("  FASTQ → FastQC → Trimmomatic → MultiQC")
    print("  (Each tool's output becomes the next tool's input)")
    
    success = orchestrator.execute_pipeline_workflow(
        run_id=workflow_run.id,
        primary_files=[str(test_fastq)],
        reference_files={}
    )
    
    if success:
        print("\n🎉 Pipeline workflow completed successfully!")
        
        # Show the final workflow state
        final_run = orchestrator.get_workflow_run_by_id(workflow_run.id)
        print(f"\n📊 Final Workflow Status:")
        print(f"  Status: {final_run.status}")
        print(f"  Progress: {final_run.progress}%")
        print(f"  Tools executed: {len([t for t in final_run.tools if t.status == 'completed'])}/{len(final_run.tools)}")
        
        # Show tool execution details
        print(f"\n🔧 Tool Execution Details:")
        for tool in final_run.tools:
            print(f"  {tool.order}. {tool.tool_name}: {tool.status}")
            if tool.status == 'completed':
                print(f"     Input files: {len(tool.input_files)}")
                print(f"     Output files: {len(tool.output_files)}")
                print(f"     Execution time: {tool.execution_time:.2f}s")
            elif tool.status == 'failed':
                print(f"     Error: {tool.error_message}")
        
        # Show the workflow file structure
        print(f"\n📁 Workflow Directory Structure:")
        run_dir = Path(workflow_run.run_directory)
        for item in run_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(run_dir)
                print(f"  📄 {rel_path}")
        
    else:
        print("\n❌ Pipeline workflow failed!")
    
    print("\n" + "=" * 50)
    print("🧪 Pipeline test completed!")

if __name__ == "__main__":
    test_pipeline_workflow()
