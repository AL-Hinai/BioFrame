FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: SAMtools
# tool_description: SAM/BAM processing and analysis tools
# tool_version: 1.18
# tool_category: Sequence Analysis
# tool_input_formats: SAM, BAM, CRAM
# tool_output_formats: SAM, BAM, CRAM, TXT
# tool_author: Genome Research Limited
# tool_url: https://github.com/samtools/samtools
# tool_icon: file-alt
# tool_color: purple

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
    && rm -rf /var/lib/apt/lists/*

# Install SAMtools
RUN wget https://github.com/samtools/samtools/releases/download/1.18/samtools-1.18.tar.bz2 \
    && tar -xjf samtools-1.18.tar.bz2 \
    && cd samtools-1.18 \
    && ./configure \
    && make \
    && make install \
    && cd / \
    && rm -rf samtools-1.18*

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
CMD ["samtools", "--help"]
