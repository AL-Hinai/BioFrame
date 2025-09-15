#!/usr/bin/env python3
"""
Test script for enhanced workflow orchestrator with dynamic mounting
"""

import os
import sys
import uuid
from pathlib import Path

# Add the workflow-orchestrator to the path
sys.path.append('workflow-orchestrator')

from orchestrator import WorkflowOrchestrator

def test_enhanced_orchestrator():
    """Test the enhanced workflow orchestrator with dynamic mounting"""
    
    print("🧪 Testing Enhanced Workflow Orchestrator with Dynamic Mounting")
    print("=" * 70)
    
    # Initialize orchestrator
    data_dir = "data"
    orchestrator = WorkflowOrchestrator(data_dir, init_docker=True)
    
    # Create a test workflow run
    run_id = f"enhanced-test-{uuid.uuid4().hex[:8]}"
    workflow_name = f"Enhanced Test Workflow {run_id}"
    tools = ["fastqc", "multiqc"]  # Test multiple tools
    
    # Create a realistic test FASTQ file
    test_dir = Path("data/test_enhanced")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "sample_reads.fastq"
    with open(test_file, 'w') as f:
        # Create a more realistic FASTQ file
        for i in range(100):  # 100 reads
            f.write(f"@read_{i+1}\n")
            f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
            f.write("+\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
    
    print(f"✅ Created test file: {test_file}")
    print(f"📁 File size: {test_file.stat().st_size} bytes")
    
    # Test input files
    input_files = [str(test_file)]
    
    print(f"\n📋 Input files: {input_files}")
    for f in input_files:
        if Path(f).exists():
            print(f"✅ {f} exists ({Path(f).stat().st_size} bytes)")
        else:
            print(f"❌ {f} missing")
    
    try:
        # Create the workflow run
        workflow = orchestrator.create_sample_run(
            run_id=run_id,
            workflow_name=workflow_name,
            tools=tools,
            input_files=input_files,
            output_dir=f"data/runs/{run_id}/outputs"
        )
        
        print(f"\n✅ Workflow created successfully")
        print(f"📄 Workflow ID: {run_id}")
        print(f"🛠️ Tools: {tools}")
        
        # Execute the workflow
        print(f"\n🔄 Executing enhanced workflow...")
        print("-" * 50)
        
        success = orchestrator.execute_pipeline_workflow_enhanced(
            run_id=run_id,
            input_files=input_files,
            workflow_config={}
        )
        
        if success:
            print(f"\n🎉 Workflow completed successfully!")
            
            # Check output files
            run_dir = Path(f"data/runs/{run_id}")
            output_files = []
            for file_path in run_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    output_files.append(str(file_path.relative_to(run_dir)))
            
            print(f"\n📁 Generated {len(output_files)} output files:")
            for file_path in sorted(output_files):
                file_size = (run_dir / file_path).stat().st_size
                print(f"   - {file_path} ({file_size:,} bytes)")
            
            # Check for specific output types
            html_files = [f for f in output_files if f.endswith('.html')]
            if html_files:
                print(f"\n🎯 Found {len(html_files)} HTML report files:")
                for f in html_files:
                    print(f"   - {f}")
            else:
                print(f"\n⚠️ No HTML report files found")
                
        else:
            print(f"\n❌ Workflow failed!")
            
    except Exception as e:
        print(f"\n💥 Error during workflow execution: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            orchestrator.container_manager.stop_monitoring()
        except:
            pass

if __name__ == "__main__":
    test_enhanced_orchestrator()
