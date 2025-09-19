FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: Picard
# tool_description: Java-based command-line utilities for manipulating high-throughput sequencing data
# tool_version: 3.1.0
# tool_category: Gene Recovery
# tool_input_formats: SAM, BAM, FASTQ
# tool_output_formats: BAM, VCF, TXT
# tool_author: Broad Institute
# tool_url: https://github.com/broadinstitute/picard
# tool_icon: cogs
# tool_color: red
# tool_commands: picard
# tool_primary_command: picard
# tool_command_template: picard AddOrReplaceReadGroups I={input_file_1} O={output_dir}/rg_added.bam RGID=sample1 RGLB=lib1 RGPL=illumina RGPU=unit1 RGSM=sample1 && picard MarkDuplicates I={output_dir}/rg_added.bam O={output_dir}/deduped.bam M={output_dir}/duplicate_metrics.txt
# tool_memory_requirement: 
# tool_cpu_requirement:
# tool_expected_outputs: {output_dir}/rg_added.bam,{output_dir}/deduped.bam,{output_dir}/duplicate_metrics.txt
# tool_success_indicators: MarkDuplicates done,AddOrReplaceReadGroups done
# tool_failure_indicators: ERROR,FATAL,Exception,OutOfMemoryError

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    openjdk-17-jre \
    openjdk-17-jdk \
    python3 \
    python3-pip \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and install Picard
RUN wget https://github.com/broadinstitute/picard/releases/download/3.1.0/picard.jar \
    && mv picard.jar /usr/local/bin/picard.jar \
    && chmod +x /usr/local/bin/picard.jar

# Create wrapper script
RUN echo '#!/bin/bash\njava -Xmx8g -jar /usr/local/bin/picard.jar "$@"' > /usr/local/bin/picard \
    && chmod +x /usr/local/bin/picard

# Install additional bioinformatics tools
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    pysam

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["picard", "--help"]
