FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: MultiQC
# tool_description: Comprehensive quality control reports for multiple tools
# tool_version: 1.16
# tool_category: Quality Control
# tool_input_formats: Multiple tool outputs
# tool_output_formats: HTML, PDF, JSON
# tool_author: Phil Ewels
# tool_url: https://github.com/ewels/MultiQC
# tool_icon: chart-pie
# tool_color: indigo
# tool_commands: multiqc
# tool_primary_command: multiqc
# tool_command_template: multiqc {input_dir} -o {output_dir} {options}

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install MultiQC
RUN pip3 install multiqc

# Install additional bioinformatics tools and dependencies
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    jinja2 \
    click \
    rich \
    tabulate

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["multiqc", "--help"]
