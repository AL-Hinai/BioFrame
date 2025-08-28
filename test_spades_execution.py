#!/usr/bin/env python3
"""
Test SPAdes Execution
Verifies that the improved SPAdes tool execution works correctly
"""

import sys
import os
from pathlib import Path

# Add the orchestrator to the path
sys.path.append('workflow-orchestrator')

def test_spades_execution():
    """Test the improved SPAdes execution"""
    try:
        from orchestrator import WorkflowOrchestrator
        
        print("🔬 Testing Improved SPAdes Execution")
        print("=" * 50)
        
        # Initialize orchestrator
        orchestrator = WorkflowOrchestrator(data_dir="data", init_docker=False)
        
        # Test input files (use the existing ones)
        test_input_files = [
            "data/runs/d515f62b-a06a-4b21-9465-549c032da7fc_20250828_065437/input/SRR1770413_1.fastq.gz",
            "data/runs/d515f62b-a06a-4b21-9465-549c032da7fc_20250828_065437/input/SRR1770413_2.fastq.gz"
        ]
        
        # Verify input files exist
        for input_file in test_input_files:
            if not Path(input_file).exists():
                print(f"❌ Input file not found: {input_file}")
                return False
            else:
                print(f"✅ Input file found: {input_file}")
        
        # Create test output directory
        test_output_dir = Path("data/test_spades_output")
        test_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📁 Test output directory: {test_output_dir.absolute()}")
        
        # Test SPAdes execution with new multi-strategy approach
        print("\n🚀 Testing SPAdes execution with multi-strategy fallback...")
        print("Note: This will try multiple strategies to handle segmentation faults")
        
        success, output_files = orchestrator._execute_spades(test_input_files, test_output_dir)
        
        if success:
            print("✅ SPAdes execution completed successfully!")
            print(f"📤 Generated {len(output_files)} output files:")
            for output_file in output_files:
                print(f"   {output_file}")
            
            # Verify expected outputs
            expected_outputs = ["contigs.fasta", "scaffolds.fasta", "assembly_graph.fastg"]
            for expected in expected_outputs:
                expected_path = test_output_dir / expected
                if expected_path.exists():
                    size = expected_path.stat().st_size
                    print(f"✅ {expected} exists ({size} bytes)")
                else:
                    print(f"❌ {expected} missing")
            
            return True
        else:
            print("❌ SPAdes execution failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("🧪 BioFrame SPAdes Execution Test")
    print("This test will verify that the improved SPAdes tool execution works correctly")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("workflow-orchestrator").exists():
        print("❌ Please run this script from the BioFrame project root directory")
        sys.exit(1)
    
    # Check Docker availability
    try:
        import subprocess
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Docker is not available. Please ensure Docker is running.")
            sys.exit(1)
        else:
            print("✅ Docker is available")
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        sys.exit(1)
    
    # Check for bioframe-spades image
    try:
        result = subprocess.run(["docker", "images"], capture_output=True, text=True, timeout=10)
        if "bioframe-spades" not in result.stdout:
            print("❌ bioframe-spades Docker image not found")
            print("Please build the image first:")
            print("cd tools/spades && docker build -t bioframe-spades .")
            sys.exit(1)
        else:
            print("✅ bioframe-spades Docker image found")
    except Exception as e:
        print(f"❌ Error checking Docker images: {e}")
        sys.exit(1)
    
    print("\n🚀 Starting SPAdes execution test...")
    success = test_spades_execution()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("The improved SPAdes execution is working correctly.")
    else:
        print("\n💥 Test failed!")
        print("There are still issues with SPAdes execution that need to be resolved.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
