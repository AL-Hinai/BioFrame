FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: Exonerate
# tool_description: Generic tool for pairwise sequence alignment and gene structure annotation
# tool_version: 2.4.0
# tool_category: Gene Recovery
# tool_input_formats: FASTA, FASTQ
# tool_output_formats: GFF, EXN, FASTA, TXT
# tool_author: Guy St.C. Slater
# tool_url: https://github.com/nathanweeks/exonerate
# tool_icon: search
# tool_color: orange
# tool_commands: exonerate
# tool_primary_command: exonerate
# tool_command_template: exonerate --model est2genome --query {input_file_1} --target {input_file_2} --showcigar no --showvulgar no --showalignment yes --minintron 20 --maxintron 2000 > {output_dir}/gene_annotation.exn
# tool_memory_requirement: 
# tool_cpu_requirement:
# tool_expected_outputs: {output_dir}/gene_annotation.exn
# tool_success_indicators: completed exonerate analysis,# Alignment
# tool_failure_indicators: ERROR,FATAL,Segmentation fault,Cannot allocate memory

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
    pkg-config \
    git \
    autotools-dev \
    autoconf \
    automake \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Exonerate v2.4.0
RUN wget https://github.com/nathanweeks/exonerate/archive/v2.4.0.tar.gz \
    && tar -xzf v2.4.0.tar.gz \
    && cd exonerate-2.4.0 \
    && autoreconf -fi \
    && ./configure --prefix=/usr/local \
    && make \
    && make install \
    && cd .. \
    && rm -rf v2.4.0.tar.gz exonerate-2.4.0

# Verify installation (exonerate --version returns exit code 1, but it works)
# RUN exonerate --version

# Install additional bioinformatics tools for phylogenomics
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    scipy

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["exonerate", "--help"]