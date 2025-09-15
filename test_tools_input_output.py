#!/usr/bin/env python3
"""
Comprehensive test for BioFrame tools to verify input/output functionality
Tests multiple tools and validates they properly consume input and produce output
"""

import os
import sys
import uuid
import time
from pathlib import Path

# Add the workflow-orchestrator to the path
sys.path.append('workflow-orchestrator')

from orchestrator import WorkflowOrchestrator

def create_test_data():
    """Create various test data files for different tools"""
    test_dir = Path("data/test_tools_validation")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create FASTQ files for sequencing tools
    fastq_file = test_dir / "test_reads.fastq"
    with open(fastq_file, 'w') as f:
        for i in range(100):
            f.write(f"@read_{i+1}\n")
            f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
            f.write("+\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
    
    # Create paired-end FASTQ files
    fastq_r1 = test_dir / "test_reads_R1.fastq"
    fastq_r2 = test_dir / "test_reads_R2.fastq"
    
    with open(fastq_r1, 'w') as f1, open(fastq_r2, 'w') as f2:
        for i in range(50):
            # R1 reads
            f1.write(f"@read_{i+1}/1\n")
            f1.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
            f1.write("+\n")
            f1.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
            
            # R2 reads
            f2.write(f"@read_{i+1}/2\n")
            f2.write("GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n")
            f2.write("+\n")
            f2.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
    
    # Create FASTA file for assembly tools
    fasta_file = test_dir / "test_assembly.fasta"
    with open(fasta_file, 'w') as f:
        f.write(">contig_1\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
        f.write(">contig_2\n")
        f.write("GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n")
        f.write("GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n")
    
    # Create reference genome
    ref_file = test_dir / "test_reference.fasta"
    with open(ref_file, 'w') as f:
        f.write(">reference\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n")
    
    return {
        'fastq_single': str(fastq_file),
        'fastq_paired': [str(fastq_r1), str(fastq_r2)],
        'fasta_assembly': str(fasta_file),
        'fasta_reference': str(ref_file)
    }

def test_tool_execution(orchestrator, tool_name, input_files, expected_output_types, test_name):
    """Test a single tool execution and validate input/output"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing {test_name}")
    print(f"🛠️  Tool: {tool_name}")
    print(f"📁 Input files: {len(input_files)} files")
    for f in input_files:
        size = Path(f).stat().st_size
        print(f"   - {Path(f).name} ({size:,} bytes)")
    
    # Create output directory
    run_id = f"test-{tool_name}-{uuid.uuid4().hex[:8]}"
    output_dir = f"data/runs/{run_id}/step_1_{tool_name}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    try:
        # Execute tool
        result = orchestrator.container_manager.execute_tool_in_container(
            tool_name=tool_name,
            input_files=input_files,
            output_dir=output_dir,
            workflow_id=run_id,
            step_number=1,
            tool_config={'step_number': 1, 'workflow_id': run_id}
        )
        
        execution_time = time.time() - start_time
        
        # Validate results
        print(f"\n📊 Execution Results:")
        print(f"   ✅ Success: {result.success}")
        print(f"   ⏱️  Time: {execution_time:.2f}s")
        print(f"   📤 Output files: {len(result.output_files)}")
        print(f"   🐳 Container: {result.container_name}")
        print(f"   📋 Exit code: {result.exit_code}")
        
        if result.error_message:
            print(f"   ❌ Error: {result.error_message}")
        
        # Check output files
        if result.output_files:
            print(f"\n📁 Generated Output Files:")
            for output_file in result.output_files:
                file_size = Path(output_file).stat().st_size
                file_name = Path(output_file).name
                print(f"   - {file_name} ({file_size:,} bytes)")
                
                # Check if file type matches expected
                file_ext = Path(output_file).suffix.lower()
                if any(file_ext.endswith(expected_type) for expected_type in expected_output_types):
                    print(f"     ✅ Correct output type: {file_ext}")
                else:
                    print(f"     ⚠️  Unexpected output type: {file_ext}")
        else:
            print(f"\n⚠️  No output files generated!")
        
        # Check for specific output patterns
        output_dir_path = Path(output_dir)
        if output_dir_path.exists():
            all_files = list(output_dir_path.rglob("*"))
            print(f"\n📂 All files in output directory ({len(all_files)} total):")
            for file_path in all_files[:10]:  # Show first 10
                if file_path.is_file():
                    size = file_path.stat().st_size
                    rel_path = file_path.relative_to(output_dir_path)
                    print(f"   - {rel_path} ({size:,} bytes)")
        
        return {
            'tool': tool_name,
            'success': result.success,
            'execution_time': execution_time,
            'output_files': len(result.output_files),
            'error': result.error_message,
            'output_dir': output_dir
        }
        
    except Exception as e:
        print(f"\n❌ Tool execution failed: {e}")
        return {
            'tool': tool_name,
            'success': False,
            'execution_time': time.time() - start_time,
            'output_files': 0,
            'error': str(e),
            'output_dir': output_dir
        }

def main():
    """Main test function"""
    print("🧪 BioFrame Tools Input/Output Validation Test")
    print("=" * 70)
    
    # Initialize orchestrator
    print("🚀 Initializing Workflow Orchestrator...")
    data_dir = "data"
    orchestrator = WorkflowOrchestrator(data_dir, init_docker=True)
    
    # Create test data
    print("\n📁 Creating test data files...")
    test_data = create_test_data()
    
    # Define test cases
    test_cases = [
        {
            'tool': 'fastqc',
            'input_files': [test_data['fastq_single']],
            'expected_output_types': ['.html', '.zip', '.txt'],
            'test_name': 'FastQC Quality Control (Single-end)'
        },
        {
            'tool': 'fastqc',
            'input_files': test_data['fastq_paired'],
            'expected_output_types': ['.html', '.zip', '.txt'],
            'test_name': 'FastQC Quality Control (Paired-end)'
        },
        {
            'tool': 'trimmomatic',
            'input_files': test_data['fastq_paired'],
            'expected_output_types': ['.fastq', '.log'],
            'test_name': 'Trimmomatic Read Trimming'
        },
        {
            'tool': 'quast',
            'input_files': [test_data['fasta_assembly']],
            'expected_output_types': ['.html', '.txt', '.tsv'],
            'test_name': 'QUAST Assembly Quality Assessment'
        },
        {
            'tool': 'multiqc',
            'input_files': [test_data['fastq_single']],  # MultiQC can work with any input
            'expected_output_types': ['.html', '.txt'],
            'test_name': 'MultiQC Report Generation'
        }
    ]
    
    # Run tests
    results = []
    for test_case in test_cases:
        result = test_tool_execution(
            orchestrator=orchestrator,
            tool_name=test_case['tool'],
            input_files=test_case['input_files'],
            expected_output_types=test_case['expected_output_types'],
            test_name=test_case['test_name']
        )
        results.append(result)
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print(f"{'='*70}")
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"✅ Successful tests: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed tests: {len(failed_tests)}/{len(results)}")
    
    if successful_tests:
        print(f"\n🎉 Successful Tools:")
        for result in successful_tests:
            print(f"   - {result['tool']}: {result['output_files']} output files in {result['execution_time']:.2f}s")
    
    if failed_tests:
        print(f"\n💥 Failed Tools:")
        for result in failed_tests:
            print(f"   - {result['tool']}: {result['error']}")
    
    # Overall assessment
    if len(successful_tests) == len(results):
        print(f"\n🎉 ALL TESTS PASSED! All tools successfully consumed input and produced output.")
    elif len(successful_tests) > 0:
        print(f"\n⚠️  PARTIAL SUCCESS: {len(successful_tests)}/{len(results)} tools worked correctly.")
    else:
        print(f"\n❌ ALL TESTS FAILED: No tools produced expected output.")
    
    print(f"\n✅ Input/Output validation test complete!")
    
    # Cleanup
    try:
        orchestrator.container_manager.stop_monitoring()
    except:
        pass

if __name__ == "__main__":
    main()
