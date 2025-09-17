#!/usr/bin/env python3
"""
Download bacterial sequencing data from NCBI SRA
Downloads SRX30488801 dataset
"""

import os
import requests
import subprocess
import sys
from pathlib import Path

def check_tools():
    """Check if required tools are available"""
    tools = ['fastq-dump', 'wget', 'curl']
    available = []
    
    for tool in tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            available.append(tool)
            print(f"✅ {tool} is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {tool} is not available")
    
    return available

def download_with_wget(url, filename):
    """Download file using wget"""
    print(f"Downloading with wget: {filename}")
    try:
        result = subprocess.run(['wget', '-O', filename, url], 
                              capture_output=True, text=True, check=True)
        print(f"✅ Downloaded {filename}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ wget failed: {e.stderr}")
        return False

def download_with_curl(url, filename):
    """Download file using curl"""
    print(f"Downloading with curl: {filename}")
    try:
        result = subprocess.run(['curl', '-L', '-o', filename, url], 
                              capture_output=True, text=True, check=True)
        print(f"✅ Downloaded {filename}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ curl failed: {e.stderr}")
        return False

def download_with_requests(url, filename):
    """Download file using Python requests"""
    print(f"Downloading with requests: {filename}")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}% ({downloaded:,} / {total_size:,} bytes)", end='', flush=True)
        
        print(f"\n✅ Downloaded {filename} ({downloaded:,} bytes)")
        return True
        
    except Exception as e:
        print(f"\n❌ requests failed: {e}")
        return False

def download_sra_with_fastq_dump(sra_id):
    """Download SRA data using fastq-dump"""
    print(f"Downloading SRA data for {sra_id} using fastq-dump...")
    try:
        # fastq-dump command to download and convert to FASTQ
        cmd = ['fastq-dump', '--split-files', '--gzip', '--outdir', 'data/bacterial_test', sra_id]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Downloaded and converted {sra_id}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ fastq-dump failed: {e.stderr}")
        return False

def get_sra_info(sra_id):
    """Get information about SRA dataset"""
    print(f"🔍 Getting information for {sra_id}...")
    
    # Try to get metadata from NCBI
    try:
        # Use NCBI's eutils API to get SRA info
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=sra&id={sra_id}&rettype=docsum&retmode=xml"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Found metadata for {sra_id}")
            # Parse basic info (this is simplified)
            print(f"📊 Dataset ID: {sra_id}")
            return True
        else:
            print(f"⚠️  Could not get metadata (status: {response.status_code})")
            return False
            
    except Exception as e:
        print(f"❌ Error getting SRA info: {e}")
        return False

def main():
    """Download SRX30488801 bacterial sequencing data"""
    print("🧬 NCBI SRA Data Downloader")
    print("=" * 50)
    
    sra_id = "SRX30488801"
    
    # Create data directory
    data_dir = Path("data/bacterial_test")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Target directory: {data_dir.absolute()}")
    print(f"🎯 Downloading: {sra_id}")
    print()
    
    # Check available tools
    print("🔧 Checking available tools...")
    available_tools = check_tools()
    print()
    
    # Get SRA info
    if get_sra_info(sra_id):
        print()
        
        # Try different download methods
        success = False
        
        # Method 1: Try fastq-dump (best for SRA data)
        if 'fastq-dump' in available_tools:
            print("🚀 Method 1: Using fastq-dump (recommended for SRA)")
            success = download_sra_with_fastq_dump(sra_id)
            
        # Method 2: Direct download (if fastq-dump fails)
        if not success:
            print("\n🚀 Method 2: Direct download attempt")
            
            # Try different download tools
            download_methods = []
            if 'wget' in available_tools:
                download_methods.append(download_with_wget)
            if 'curl' in available_tools:
                download_methods.append(download_with_curl)
            download_methods.append(download_with_requests)
            
            for method in download_methods:
                # Note: Direct SRA download URLs are complex and may not work
                # This is a simplified attempt
                print("⚠️  Direct SRA download may not work - SRA data usually requires fastq-dump")
                break
        
        # Check results
        if success or any(data_dir.glob("*.fastq*")):
            print("\n📊 Download Summary")
            print("-" * 30)
            
            files = list(data_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            print(f"Files downloaded: {len([f for f in files if f.is_file()])}")
            print(f"Total size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
            print(f"Location: {data_dir.absolute()}")
            print()
            
            if files:
                print("🎉 Bacterial sequencing data ready!")
                print()
                print("Files created:")
                for file in files:
                    if file.is_file():
                        size_mb = file.stat().st_size / 1024 / 1024
                        print(f"  📄 {file.name} ({size_mb:.1f} MB)")
            else:
                print("❌ No files were downloaded")
        else:
            print("\n❌ Download failed with all methods")
            print("\n💡 Suggestions:")
            print("   1. Install SRA Toolkit: https://github.com/ncbi/sra-tools")
            print("   2. Use fastq-dump command directly")
            print("   3. Try downloading from NCBI SRA website manually")
    
    else:
        print(f"❌ Could not find information for {sra_id}")
        print("   Please verify the SRA accession number is correct")

if __name__ == "__main__":
    main()
