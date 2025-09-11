FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: Exonerate
# tool_description: Generic pairwise sequence alignment algorithm
# tool_version: 2.4.0
# tool_category: Sequence Alignment
# tool_input_formats: FASTA, FASTQ
# tool_output_formats: FASTA, ALN, GFF
# tool_author: Guy Slater
# tool_url: http://www.ebi.ac.uk/about/vertebrate-genomics/software/exonerate
# tool_icon: align-center
# tool_color: indigo
# tool_commands: exonerate
# tool_primary_command: exonerate
# tool_command_template: exonerate {query} {target} {options} > {output_file}

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

# Install Exonerate
RUN wget http://www.ebi.ac.uk/about/vertebrate-genomics/software/exonerate/exonerate-2.4.0-x86_64.tar.gz \
    && tar -xzf exonerate-2.4.0-x86_64.tar.gz \
    && cp exonerate-2.4.0-x86_64/bin/* /usr/local/bin/ \
    && chmod +x /usr/local/bin/* \
    && rm -rf exonerate-2.4.0-x86_64.tar.gz exonerate-2.4.0-x86_64

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["exonerate", "--help"]
