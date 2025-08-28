#!/usr/bin/env python3
"""
Test Portal Workflow
Simulates the complete workflow from file upload to execution using the portal
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
import subprocess

def test_portal_workflow():
    """Test the complete portal workflow"""
    print("🧪 Testing BioFrame Portal Workflow")
    print("=" * 50)
    
    # Check if portal is running
    print("🔍 Checking portal status...")
    try:
        response = requests.get("http://localhost:8000/", timeout=10)
        if response.status_code == 302:  # Redirect to login
            print("✅ Portal is running (redirecting to login)")
        else:
            print(f"⚠️ Portal responded with status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Portal is not accessible: {e}")
        return False
    
    # Test workflow creation through the orchestrator directly
    print("\n🚀 Testing workflow creation and execution...")
    
    try:
        # Import the orchestrator
        sys.path.append('workflow-orchestrator')
        from orchestrator import WorkflowOrchestrator
        
        # Initialize orchestrator
        orchestrator = WorkflowOrchestrator(data_dir="data", init_docker=False)
        
        # Create a test workflow
        workflow_name = "Portal Test Workflow"
        workflow_description = "Testing workflow creation and execution through portal simulation"
        selected_tools = ["spades"]
        
        print(f"📝 Creating workflow: {workflow_name}")
        print(f"🛠️ Selected tools: {selected_tools}")
        
        # Create workflow run
        workflow_run = orchestrator.create_sample_run(
            name=workflow_name,
            description=workflow_description,
            tools=selected_tools
        )
        
        if not workflow_run:
            print("❌ Failed to create workflow run")
            return False
        
        print(f"✅ Workflow created with ID: {workflow_run.id}")
        print(f"📁 Run directory: {workflow_run.run_directory}")
        
        # Simulate file upload by copying test files
        print("\n📁 Simulating file upload...")
        
        # Use existing test files
        source_input_dir = Path("data/runs/d515f62b-a06a-4b21-9465-549c032da7fc_20250828_065437/input")
        target_input_dir = Path(workflow_run.run_directory) / "input"
        
        if not source_input_dir.exists():
            print("❌ Source input directory not found")
            return False
        
        # Create target input directory
        target_input_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy input files
        input_files = []
        for source_file in source_input_dir.glob("*.fastq.gz"):
            target_file = target_input_dir / source_file.name
            import shutil
            shutil.copy2(source_file, target_file)
            input_files.append(str(target_file))
            print(f"📋 Copied: {source_file.name} -> {target_file}")
        
        if not input_files:
            print("❌ No input files copied")
            return False
        
        print(f"✅ Uploaded {len(input_files)} files: {[Path(f).name for f in input_files]}")
        
        # Execute the workflow
        print("\n🚀 Executing workflow...")
        print("Note: This will run the actual SPAdes tool with the uploaded files")
        
        success = orchestrator.execute_pipeline_workflow(
            run_id=workflow_run.id,
            primary_files=input_files,
            reference_files={}
        )
        
        if success:
            print("✅ Workflow executed successfully!")
            
            # Check outputs
            print("\n📤 Checking workflow outputs...")
            workflow_dir = Path(workflow_run.run_directory)
            
            # Check for SPAdes outputs
            spades_dir = workflow_dir / "step_1_SPAdes"
            if spades_dir.exists():
                print(f"📁 SPAdes output directory: {spades_dir}")
                
                # List all files in SPAdes directory
                spades_files = list(spades_dir.rglob("*"))
                if spades_files:
                    print("📋 SPAdes output files:")
                    for file in spades_files:
                        if file.is_file():
                            size = file.stat().st_size
                            print(f"   {file.relative_to(spades_dir)} ({size} bytes)")
                        else:
                            print(f"   {file.relative_to(spades_dir)}/ (directory)")
                else:
                    print("   No files found")
            
            # Check workflow status
            print(f"\n📊 Workflow Status: {workflow_run.status}")
            print(f"📈 Progress: {workflow_run.progress}%")
            
            if workflow_run.tools:
                for i, tool in enumerate(workflow_run.tools):
                    print(f"\n🔧 Tool {i+1}: {tool.tool_name}")
                    print(f"   Status: {tool.status}")
                    print(f"   Started: {tool.started_at}")
                    print(f"   Completed: {tool.completed_at}")
                    print(f"   Execution Time: {tool.execution_time}")
                    
                    if tool.error_message:
                        print(f"   ❌ Error: {tool.error_message}")
                    
                    if tool.execution_details:
                        details = tool.execution_details
                        print(f"   📋 Input Files: {details.get('input_file_count', 0)}")
                        print(f"   📤 Output Files: {details.get('output_file_count', 0)}")
            
            return True
        else:
            print("❌ Workflow execution failed")
            
            # Check what went wrong
            if workflow_run.tools:
                for tool in workflow_run.tools:
                    if tool.status == 'failed':
                        print(f"❌ Tool {tool.tool_name} failed: {tool.error_message}")
                        if tool.execution_details:
                            details = tool.execution_details
                            if details.get('traceback'):
                                print(f"   Traceback: {details['traceback']}")
            
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("🧪 BioFrame Portal Workflow Test")
    print("This test simulates the complete workflow from file upload to execution")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("workflow-orchestrator").exists():
        print("❌ Please run this script from the BioFrame project root directory")
        sys.exit(1)
    
    # Check if portal is accessible
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        print("✅ Portal is accessible")
    except requests.exceptions.RequestException:
        print("❌ Portal is not accessible. Please start the portal first:")
        print("cd portal && python manage.py runserver 0.0.0.0:8000")
        sys.exit(1)
    
    # Run the workflow test
    print("\n🚀 Starting portal workflow test...")
    success = test_portal_workflow()
    
    if success:
        print("\n🎉 Portal workflow test completed successfully!")
        print("The portal workflow system is working correctly.")
    else:
        print("\n💥 Portal workflow test failed!")
        print("There are issues that need to be resolved.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
