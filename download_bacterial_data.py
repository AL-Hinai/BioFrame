#!/usr/bin/env python3
"""
Simple script to download bacterial sequencing data using SRA toolkit
Usage: python download_bacterial_data.py <SRA_ACCESSION>
Example: python download_bacterial_data.py SRR390728
"""

import subprocess
import sys
from pathlib import Path

def download_sra_data(sra_id, output_dir="data/bacterial_test"):
    """Download SRA data using fastq-dump"""
    print(f"🧬 Downloading SRA data: {sra_id}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # fastq-dump command
    cmd = [
        'fastq-dump',
        '--split-3',          # 3-way splitting for mate-pairs
        '--gzip',             # Compress output
        '--outdir', str(output_path),  # Output directory
        '--skip-technical',   # Skip technical reads
        '--readids',          # Include read IDs
        '--read-filter', 'pass',  # Only include passed reads
        '--dumpbase',         # Dump bases
        '--clip',             # Clip adapter sequences
        sra_id
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✅ Successfully downloaded {sra_id}")
        
        # List downloaded files
        files = list(output_path.glob(f"{sra_id}*"))
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        print(f"📄 Files created ({total_size/1024/1024:.1f} MB):")
        for file in files:
            size_mb = file.stat().st_size / 1024 / 1024
            print(f"   • {file.name} ({size_mb:.1f} MB)")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to download {sra_id}")
        print(f"Error: {e}")
        return False

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python download_bacterial_data.py <SRA_ACCESSION>")
        print("Example: python download_bacterial_data.py SRR390728")
        print("\nSome publicly available bacterial datasets to try:")
        print("  • SRR390728 - E. coli dataset")
        print("  • SRR390729 - E. coli dataset") 
        print("  • SRR390730 - E. coli dataset")
        print("  • SRR000001 - Classic test dataset")
        sys.exit(1)
    
    sra_id = sys.argv[1]
    
    print("🧬 Bacterial Data Downloader")
    print("=" * 40)
    print(f"SRA Accession: {sra_id}")
    print(f"Output Directory: data/bacterial_test")
    print()
    
    success = download_sra_data(sra_id)
    
    if success:
        print(f"\n🎉 Download complete!")
        print(f"Files saved to: data/bacterial_test/")
    else:
        print(f"\n❌ Download failed")
        print("Try a different SRA accession or check your internet connection")

if __name__ == "__main__":
    main()


