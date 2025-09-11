FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: RAxML
# tool_description: Randomized Axelerated Maximum Likelihood for phylogenetic tree inference
# tool_version: 8.2.12
# tool_category: Phylogenetic Analysis
# tool_input_formats: FASTA, PHYLIP
# tool_output_formats: NEWICK, LOG
# tool_author: Alexandros Stamatakis
# tool_url: https://github.com/stamatak/standard-RAxML
# tool_icon: tree
# tool_color: blue
# tool_commands: raxmlHPC, raxmlHPC-PTHREADS
# tool_primary_command: raxmlHPC-PTHREADS
# tool_command_template: raxmlHPC-PTHREADS -s {input_files} -n {output_name} -m {model} -T {threads} {options}

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

# Install RAxML
RUN wget https://github.com/stamatak/standard-RAxML/archive/v8.2.12.tar.gz \
    && tar -xzf v8.2.12.tar.gz \
    && cd standard-RAxML-8.2.12 \
    && make -f Makefile.PTHREADS.gcc \
    && make -f Makefile.gcc \
    && cp raxmlHPC /usr/local/bin/ \
    && cp raxmlHPC-PTHREADS /usr/local/bin/ \
    && chmod +x /usr/local/bin/raxmlHPC /usr/local/bin/raxmlHPC-PTHREADS \
    && cd .. \
    && rm -rf v8.2.12.tar.gz standard-RAxML-8.2.12

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["raxmlHPC-PTHREADS", "-h"]
