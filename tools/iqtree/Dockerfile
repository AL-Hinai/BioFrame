FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: IQ-TREE
# tool_description: Efficient and versatile phylogenomic software for maximum likelihood inference
# tool_version: 2.2.0
# tool_category: Phylogenetic Analysis
# tool_input_formats: FASTA, PHYLIP, NEXUS
# tool_output_formats: NEWICK, PDF, SVG, LOG
# tool_author: Bui Quang Minh
# tool_url: http://www.iqtree.org/
# tool_icon: tree
# tool_color: green
# tool_commands: iqtree2, iqtree
# tool_primary_command: iqtree2
# tool_command_template: iqtree2 -s {input_file_1} -pre {output_dir}/phylo_tree

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    build-essential \
    cmake \
    gcc \
    g++ \
    make \
    libc6-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install IQ-TREE
RUN wget https://github.com/iqtree/iqtree2/releases/download/v2.2.0/iqtree-2.2.0-Linux.tar.gz \
    && tar -xzf iqtree-2.2.0-Linux.tar.gz \
    && cp iqtree-2.2.0-Linux/bin/iqtree2 /usr/local/bin/ \
    && cp iqtree-2.2.0-Linux/bin/iqtree /usr/local/bin/ \
    && chmod +x /usr/local/bin/iqtree2 /usr/local/bin/iqtree \
    && rm -rf iqtree-2.2.0-Linux.tar.gz iqtree-2.2.0-Linux

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["iqtree2", "--help"]
