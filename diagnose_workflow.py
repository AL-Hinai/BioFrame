#!/usr/bin/env python3
"""
BioFrame Workflow Diagnostic Script
Analyzes failed workflow runs and provides detailed information about issues
"""

import os
import sys
import yaml
import json
from pathlib import Path
from datetime import datetime
import traceback

def analyze_workflow_run(run_directory: str):
    """Analyze a workflow run directory and identify issues"""
    run_dir = Path(run_directory)
    
    if not run_dir.exists():
        print(f"❌ Run directory does not exist: {run_directory}")
        return
    
    print(f"🔍 Analyzing workflow run: {run_dir.name}")
    print(f"📁 Directory: {run_dir.absolute()}")
    print("=" * 80)
    
    # Check workflow.yaml
    workflow_file = run_dir / "workflow.yaml"
    if workflow_file.exists():
        print("✅ Found workflow.yaml")
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            print(f"📊 Workflow Status: {workflow_data.get('status', 'unknown')}")
            print(f"📈 Progress: {workflow_data.get('progress', 0)}%")
            print(f"🛠️  Tools: {len(workflow_data.get('tools', []))}")
            
            # Analyze tools
            tools = workflow_data.get('tools', [])
            for i, tool in enumerate(tools):
                print(f"\n🔧 Tool {i+1}: {tool.get('tool_name', 'Unknown')}")
                print(f"   Status: {tool.get('status', 'unknown')}")
                print(f"   Started: {tool.get('started_at', 'N/A')}")
                print(f"   Completed: {tool.get('completed_at', 'N/A')}")
                print(f"   Execution Time: {tool.get('execution_time', 'N/A')}")
                
                if tool.get('error_message'):
                    print(f"   ❌ Error: {tool['error_message']}")
                
                if tool.get('execution_details'):
                    details = tool['execution_details']
                    print(f"   📋 Input Files: {details.get('input_file_count', 0)}")
                    print(f"   📤 Output Files: {details.get('output_file_count', 0)}")
                    if details.get('error_message'):
                        print(f"   ❌ Execution Error: {details['error_message']}")
        
        except Exception as e:
            print(f"❌ Error reading workflow.yaml: {e}")
            traceback.print_exc()
    else:
        print("❌ workflow.yaml not found")
    
    print("\n" + "=" * 80)
    
    # Check input files
    input_dir = run_dir / "input"
    if input_dir.exists():
        print("📥 Input Files:")
        input_files = list(input_dir.glob("*"))
        if input_files:
            for file in input_files:
                size = file.stat().st_size if file.is_file() else "DIR"
                print(f"   {file.name} ({size} bytes)")
        else:
            print("   No input files found")
    else:
        print("❌ Input directory not found")
    
    # Check outputs directory
    outputs_dir = run_dir / "outputs"
    if outputs_dir.exists():
        print("\n📤 Outputs Directory:")
        output_files = list(outputs_dir.rglob("*"))
        if output_files:
            for file in output_files:
                if file.is_file():
                    size = file.stat().st_size
                    print(f"   {file.relative_to(outputs_dir)} ({size} bytes)")
        else:
            print("   No output files found")
    
    # Check tool-specific directories
    print("\n🔧 Tool Execution Directories:")
    for item in run_dir.iterdir():
        if item.is_dir() and item.name.startswith("step_"):
            print(f"\n   📁 {item.name}:")
            step_files = list(item.iterdir())
            if step_files:
                for file in step_files:
                    if file.is_file():
                        size = file.stat().st_size
                        print(f"      {file.name} ({size} bytes)")
                    else:
                        print(f"      {file.name}/ (directory)")
            else:
                print("      No files found")
    
    # Check logs directory
    logs_dir = run_dir / "logs"
    if logs_dir.exists():
        print(f"\n📝 Logs Directory:")
        log_files = list(logs_dir.glob("*"))
        if log_files:
            for file in log_files:
                if file.is_file():
                    size = file.stat().st_size
                    print(f"   {file.name} ({size} bytes)")
        else:
            print("   No log files found")
    
    # Check for common issues
    print("\n" + "=" * 80)
    print("🔍 Common Issues Analysis:")
    
    # Check if SPAdes tool actually ran
    spades_dir = run_dir / "step_1_SPAdes"
    if spades_dir.exists():
        spades_outputs = list(spades_dir.glob("*.fasta"))
        spades_logs = list(spades_dir.glob("*.log"))
        
        if not spades_outputs:
            print("❌ SPAdes tool did not generate expected output files")
            print("   Expected: contigs.fasta, scaffolds.fasta, assembly_graph.fastg")
            print("   This suggests the tool execution failed or was incomplete")
        
        if spades_logs:
            print("📝 SPAdes log files found:")
            for log_file in spades_logs:
                print(f"   {log_file.name}")
                try:
                    with open(log_file, 'r') as f:
                        content = f.read()
                        if "error" in content.lower() or "failed" in content.lower():
                            print(f"      ⚠️  Contains error indicators")
                        if len(content.strip()) < 100:
                            print(f"      ⚠️  Very short content - may indicate failure")
                except Exception as e:
                    print(f"      ❌ Error reading log: {e}")
    
    # Check Docker availability
    print("\n🐳 Docker Status Check:")
    try:
        import subprocess
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker is available and running")
            
            # Check for BioFrame containers
            result = subprocess.run(["docker", "images"], capture_output=True, text=True, timeout=10)
            if "bioframe-spades" in result.stdout:
                print("✅ bioframe-spades Docker image found")
            else:
                print("❌ bioframe-spades Docker image not found")
                print("   This is likely why SPAdes failed to run")
        else:
            print("❌ Docker is not available or not running")
            print("   This is why SPAdes failed to run")
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
    
    # Check file permissions
    print("\n🔐 File Permissions Check:")
    try:
        if input_dir.exists():
            input_files = list(input_dir.glob("*"))
            if input_files:
                test_file = input_files[0]
                if os.access(test_file, os.R_OK):
                    print("✅ Input files are readable")
                else:
                    print("❌ Input files are not readable")
                    print("   This could cause tool execution failures")
    except Exception as e:
        print(f"❌ Error checking file permissions: {e}")
    
    print("\n" + "=" * 80)
    print("💡 Recommendations:")
    
    # Provide specific recommendations based on findings
    if workflow_data.get('status') == 'failed':
        print("1. Check the detailed error messages above")
        print("2. Verify Docker is running and bioframe-spades image exists")
        print("3. Check input file formats and permissions")
        print("4. Review the execution logs for specific error details")
    
    print("5. Consider re-running the workflow with improved logging")
    print("6. Check system resources (CPU, memory, disk space)")
    print("7. Verify input file integrity and format")

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python diagnose_workflow.py <run_directory>")
        print("Example: python diagnose_workflow.py data/runs/d515f62b-a06a-4b21-9465-549c032da7fc_20250828_065437")
        sys.exit(1)
    
    run_directory = sys.argv[1]
    analyze_workflow_run(run_directory)

if __name__ == "__main__":
    main()
