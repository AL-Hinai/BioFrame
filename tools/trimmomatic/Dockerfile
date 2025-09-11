FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: Trimmomatic
# tool_description: A flexible read trimming tool for Illumina NGS data
# tool_version: 0.39
# tool_category: Quality Control
# tool_input_formats: FASTQ
# tool_output_formats: FASTQ
# tool_author: Usadel Lab
# tool_url: http://www.usadellab.org/cms/?page=trimmomatic
# tool_icon: scissors
# tool_color: green
# tool_commands: trimmomatic
# tool_primary_command: trimmomatic
# tool_command_template: trimmomatic {mode} {input_files} {output_files} {trimming_options}

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

# Install Trimmomatic
RUN wget http://www.usadellab.org/cms/uploads/supplementary/Trimmomatic/Trimmomatic-0.39.zip \
    && unzip Trimmomatic-0.39.zip \
    && chmod +x Trimmomatic-0.39/trimmomatic-0.39.jar \
    && ln -s /Trimmomatic-0.39/trimmomatic-0.39.jar /usr/local/bin/trimmomatic.jar

# Copy adapter files to a standard location
RUN mkdir -p /usr/local/share/trimmomatic/adapters \
    && cp Trimmomatic-0.39/adapters/* /usr/local/share/trimmomatic/adapters/ \
    && ln -s /usr/local/share/trimmomatic/adapters /adapters

# Create wrapper script
RUN echo '#!/bin/bash\njava -jar /usr/local/bin/trimmomatic.jar "$@"' > /usr/local/bin/trimmomatic \
    && chmod +x /usr/local/bin/trimmomatic

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
CMD ["trimmomatic", "-version"]
