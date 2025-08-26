FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: QUAST
# tool_description: Quality assessment tool for genome assemblies
# tool_version: 5.2.0
# tool_category: Quality Assessment
# tool_input_formats: FASTA, GFA
# tool_output_formats: HTML, TXT, TSV
# tool_author: Center for Algorithmic Biotechnology
# tool_url: https://github.com/ablab/quast
# tool_icon: chart-bar
# tool_color: orange

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    python3 \
    python3-pip \
    build-essential \
    cmake \
    zlib1g-dev \
    libncurses5-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Install QUAST using pip (faster than conda)
RUN pip3 install quast

# Install additional bioinformatics tools
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["quast.py", "--help"]
