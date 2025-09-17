FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: seqtk
# tool_description: Tool for processing sequences in FASTA/Q format
# tool_version: 1.3
# tool_category: Sequence Processing
# tool_input_formats: FASTQ, FASTA
# tool_output_formats: FASTQ, FASTA
# tool_author: Heng Li
# tool_url: https://github.com/lh3/seqtk
# tool_icon: file-text
# tool_color: gray
# tool_commands: seqtk
# tool_primary_command: seqtk
# tool_command_template: seqtk seq -A {input_file_1} > {output_dir}/converted.fasta

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    build-essential \
    gcc \
    g++ \
    make \
    libc6-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install seqtk
RUN git clone https://github.com/lh3/seqtk.git /opt/seqtk \
    && cd /opt/seqtk \
    && make \
    && cp seqtk /usr/local/bin/ \
    && chmod +x /usr/local/bin/seqtk

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["seqtk", "--help"]
