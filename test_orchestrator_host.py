#!/usr/bin/env python3
"""
Test script to run the orchestrator directly on the host
This bypasses the container-to-container volume mounting issues
"""

import sys
import os
sys.path.append('./workflow-orchestrator')

from orchestrator import WorkflowOrchestrator

def test_host_orchestrator():
    """Test the orchestrator running directly on the host"""
    print("🧪 Testing orchestrator on host...")
    
    # Initialize orchestrator with host data directory
    orchestrator = WorkflowOrchestrator(data_dir='./data', init_docker=True)
    
    print(f"✅ Orchestrator initialized with data_dir: {orchestrator.data_dir}")
    print(f"✅ Runs directory: {orchestrator.runs_dir}")
    
    # Test FastQC execution
    test_output_dir = orchestrator.runs_dir / '56818675-dc30-4121-b734-af273ee1b6a6' / 'host_test_fastqc'
    input_files = ['./data/runs/56818675-dc30-4121-b734-af273ee1b6a6/input/SRR1770413_1.fastq.gz']
    
    print(f"🔄 Testing FastQC with input: {input_files}")
    print(f"🔄 Output directory: {test_output_dir}")
    
    # Execute FastQC
    success, output_files = orchestrator._execute_fastqc(input_files, test_output_dir)
    
    print(f"✅ FastQC execution result: {success}")
    print(f"✅ Output files: {output_files}")
    
    # Check if files were generated
    if test_output_dir.exists():
        print(f"📁 Output directory contents:")
        for item in test_output_dir.iterdir():
            print(f"   - {item.name} ({item.stat().st_size} bytes)")
    else:
        print("❌ Output directory not created")
    
    return success

if __name__ == "__main__":
    try:
        success = test_host_orchestrator()
        if success:
            print("🎉 Host orchestrator test completed successfully!")
        else:
            print("❌ Host orchestrator test failed!")
    except Exception as e:
        print(f"💥 Error during host orchestrator test: {e}")
        import traceback
        traceback.print_exc()
