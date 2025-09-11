FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: FastTree
# tool_description: Fast approximate maximum likelihood phylogenetic trees
# tool_version: 2.1.11
# tool_category: Phylogenetic Analysis
# tool_input_formats: FASTA, PHYLIP
# tool_output_formats: NEWICK, LOG
# tool_author: Morgan Price
# tool_url: http://www.microbesonline.org/fasttree/
# tool_icon: tree
# tool_color: yellow
# tool_commands: FastTree, FastTreeMP
# tool_primary_command: FastTree
# tool_command_template: FastTree {input_files} > {output_file}

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
    && rm -rf /var/lib/apt/lists/*

# Install FastTree
RUN wget http://www.microbesonline.org/fasttree/FastTree.c \
    && gcc -O3 -finline-functions -funroll-loops -o FastTree FastTree.c -lm \
    && cp FastTree /usr/local/bin/ \
    && chmod +x /usr/local/bin/FastTree \
    && rm FastTree.c

# Create FastTreeMP (multi-threaded version)
RUN wget http://www.microbesonline.org/fasttree/FastTree.c \
    && gcc -DOPENMP -fopenmp -O3 -finline-functions -funroll-loops -o FastTreeMP FastTree.c -lm \
    && cp FastTreeMP /usr/local/bin/ \
    && chmod +x /usr/local/bin/FastTreeMP \
    && rm FastTree.c

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["FastTree", "--help"]
