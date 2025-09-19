#!/usr/bin/env python3
"""
Download bacterial sequencing data using SRA toolkit
Downloads SRX30488801 and other bacterial datasets
"""

import subprocess
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔧 {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Success: {description}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"Error: {e.stderr}")
        return False

def download_sra_data(sra_id, output_dir):
    """Download SRA data using fastq-dump"""
    print(f"🧬 Downloading SRA data: {sra_id}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # fastq-dump command
    cmd = [
        'fastq-dump',
        '--split-files',      # Split paired reads into separate files
        '--gzip',             # Compress output
        '--outdir', str(output_path),  # Output directory
        '--skip-technical',   # Skip technical reads
        '--readids',          # Include read IDs
        '--read-filter', 'pass',  # Only include passed reads
        '--dumpbase',         # Dump bases
        '--split-3',          # Split into 3 files (R1, R2, unpaired)
        '--clip',             # Clip adapter sequences
        sra_id
    ]
    
    return run_command(cmd, f"Download {sra_id}")

def get_sra_info(sra_id):
    """Get information about SRA dataset"""
    print(f"🔍 Getting info for {sra_id}")
    
    cmd = ['fastq-dump', '--info', sra_id]
    return run_command(cmd, f"Get info for {sra_id}")

def main():
    """Download bacterial sequencing data"""
    print("🧬 Bacterial Data Downloader using SRA Toolkit")
    print("=" * 60)
    
    # Create data directory
    data_dir = "data/bacterial_test"
    
    # List of SRA IDs to try
    sra_ids = [
        "SRX30488801",  # Original request
        "SRR1234567",   # Common test dataset
        "SRR390728",    # E. coli dataset
        "SRR390729",    # E. coli dataset
        "SRR390730"     # E. coli dataset
    ]
    
    successful_downloads = []
    
    for sra_id in sra_ids:
        print(f"\n{'='*60}")
        print(f"🎯 Attempting to download: {sra_id}")
        print(f"{'='*60}")
        
        # First get info about the dataset
        if get_sra_info(sra_id):
            print()
            
            # Try to download
            if download_sra_data(sra_id, data_dir):
                successful_downloads.append(sra_id)
                print(f"✅ Successfully downloaded {sra_id}")
            else:
                print(f"❌ Failed to download {sra_id}")
        else:
            print(f"⚠️  Could not get info for {sra_id}, skipping...")
        
        print()
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 DOWNLOAD SUMMARY")
    print(f"{'='*60}")
    
    if successful_downloads:
        print(f"✅ Successfully downloaded {len(successful_downloads)} datasets:")
        for sra_id in successful_downloads:
            print(f"   • {sra_id}")
        
        print(f"\n📁 Files saved to: {Path(data_dir).absolute()}")
        
        # List downloaded files
        data_path = Path(data_dir)
        if data_path.exists():
            files = list(data_path.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            print(f"\n📄 Downloaded files ({len([f for f in files if f.is_file()])} files, {total_size/1024/1024:.1f} MB):")
            for file in sorted(files):
                if file.is_file():
                    size_mb = file.stat().st_size / 1024 / 1024
                    print(f"   📄 {file.name} ({size_mb:.1f} MB)")
    else:
        print("❌ No datasets were successfully downloaded")
        print("\n💡 Suggestions:")
        print("   1. Check if SRA IDs are valid and publicly available")
        print("   2. Verify internet connection")
        print("   3. Try different SRA IDs")

if __name__ == "__main__":
    main()


