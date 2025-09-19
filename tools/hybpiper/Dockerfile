FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: HybPiper
# tool_description: Targeted sequence capture for phylogenomics and population genomics
# tool_version: 1.3.1
# tool_category: Gene Recovery
# tool_input_formats: FASTQ, FASTA
# tool_output_formats: FASTA, LOG
# tool_author: Matthew Johnson
# tool_url: https://github.com/mossmatters/HybPiper
# tool_icon: dna
# tool_color: orange
# tool_commands: hybpiper, hybpiper_stats
# tool_primary_command: hybpiper
# tool_command_template: hybpiper assemble -r {input_file_1} {input_file_2} -t_aa {input_file_3} --prefix sample --cpu 4 --outdir {output_dir}

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including PERL (REQUIRED for HybPiper)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
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
    python3 \
    python3-pip \
    git \
    perl \
    && rm -rf /var/lib/apt/lists/*

# Create python symlink for compatibility
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Install Python dependencies (complete HybPiper requirements)
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    scipy \
    networkx \
    pebble \
    psutil \
    progressbar2 \
    configparser

# Install BLAST+ (required by HybPiper) - using apt package
RUN apt-get update && apt-get install -y \
    ncbi-blast+ \
    && rm -rf /var/lib/apt/lists/*

# Install seqtk (REQUIRED dependency for HybPiper)
RUN git clone https://github.com/lh3/seqtk.git /opt/seqtk \
    && cd /opt/seqtk \
    && make \
    && cp seqtk /usr/local/bin/ \
    && chmod +x /usr/local/bin/seqtk

# Install HybPiper
RUN git clone https://github.com/mossmatters/HybPiper.git /opt/hybpiper \
    && cd /opt/hybpiper \
    && pip3 install -e . \
    && rm -f /usr/local/bin/hybpiper \
    && ln -s /opt/hybpiper/hybpiper/assemble.py /usr/local/bin/hybpiper \
    && ln -s /opt/hybpiper/hybpiper/hybpiper_stats.py /usr/local/bin/hybpiper_stats

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["hybpiper", "--help"]
