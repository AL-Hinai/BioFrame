FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: MAFFT
# tool_description: Multiple sequence alignment program for nucleotide and amino acid sequences
# tool_version: 7.505
# tool_category: Sequence Alignment
# tool_input_formats: FASTA
# tool_output_formats: FASTA, ALN
# tool_author: Kazutaka Katoh
# tool_url: https://mafft.cbrc.jp/alignment/software/
# tool_icon: align-left
# tool_color: purple
# tool_commands: mafft
# tool_primary_command: mafft
# tool_command_template: mafft {input_file_1} > {output_dir}/alignment.fasta

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
    && rm -rf /var/lib/apt/lists/*

# Install MAFFT
RUN wget https://mafft.cbrc.jp/alignment/software/mafft-7.505-with-extensions-src.tgz \
    && tar -xzf mafft-7.505-with-extensions-src.tgz \
    && cd mafft-7.505-with-extensions \
    && make \
    && make install \
    && cd .. \
    && rm -rf mafft-7.505-with-extensions-src.tgz mafft-7.505-with-extensions

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["mafft", "--help"]
