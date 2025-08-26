FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: FastQC
# tool_description: Quality control for high throughput sequence data
# tool_version: 0.11.9
# tool_category: Quality Control
# tool_input_formats: FASTQ, BAM, SAM
# tool_output_formats: HTML, ZIP, TXT
# tool_author: Babraham Institute
# tool_url: https://www.bioinformatics.babraham.ac.uk/projects/fastqc/
# tool_icon: chart-line
# tool_color: blue

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    default-jre \
    default-jdk \
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

# Install FastQC
RUN wget https://www.bioinformatics.babraham.ac.uk/projects/fastqc/fastqc_v0.11.9.zip \
    && unzip fastqc_v0.11.9.zip \
    && chmod +x FastQC/fastqc \
    && ln -s /FastQC/fastqc /usr/local/bin/fastqc

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
CMD ["fastqc", "--help"]
