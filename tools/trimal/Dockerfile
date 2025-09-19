FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: trimAl
# tool_description: Tool for automated alignment trimming in phylogenetic analyses
# tool_version: 1.4.1
# tool_category: Phylogenetic Analysis
# tool_input_formats: FASTA, ALN
# tool_output_formats: FASTA, ALN
# tool_author: Salvador Capella-Gutierrez
# tool_url: http://trimal.cgenomics.org/
# tool_icon: scissors
# tool_color: teal
# tool_commands: trimal
# tool_primary_command: trimal
# tool_command_template: trimal -in {input_file_1} -out {output_dir}/trimmed_alignment.fasta -automated1
# tool_memory_requirement: 
# tool_cpu_requirement:
# tool_expected_outputs: {output_dir}/trimmed_alignment.fasta
# tool_success_indicators: trimAl finished,Alignment trimmed
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
    git \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install trimAl v1.4.1
RUN wget https://github.com/inab/trimal/archive/v1.4.1.tar.gz \
    && tar -xzf v1.4.1.tar.gz \
    && cd trimal-1.4.1/source \
    && make \
    && cp trimal /usr/local/bin/ \
    && cp readal /usr/local/bin/ \
    && cp statal /usr/local/bin/ \
    && chmod +x /usr/local/bin/trimal /usr/local/bin/readal /usr/local/bin/statal \
    && cd ../.. \
    && rm -rf v1.4.1.tar.gz trimal-1.4.1

# Install additional bioinformatics tools
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
CMD ["trimal", "-h"]
