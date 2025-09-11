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
# tool_command_template: hybpiper assemble -r {input_files} -t_aa {target_genes} -o {output_dir} {options}

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
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
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    scipy \
    networkx

# Install BLAST+ (required by HybPiper)
RUN wget https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ncbi-blast-2.14.0+-x64-linux.tar.gz \
    && tar -xzf ncbi-blast-2.14.0+-x64-linux.tar.gz \
    && cp ncbi-blast-2.14.0+/bin/* /usr/local/bin/ \
    && chmod +x /usr/local/bin/* \
    && rm -rf ncbi-blast-2.14.0+-x64-linux.tar.gz ncbi-blast-2.14.0+

# Install HybPiper
RUN git clone https://github.com/mossmatters/HybPiper.git /opt/hybpiper \
    && cd /opt/hybpiper \
    && pip3 install -e . \
    && ln -s /opt/hybpiper/hybpiper/assemble.py /usr/local/bin/hybpiper \
    && ln -s /opt/hybpiper/hybpiper/hybpiper_stats.py /usr/local/bin/hybpiper_stats

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["hybpiper", "--help"]
