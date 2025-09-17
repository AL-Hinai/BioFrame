FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: BWA
# tool_description: Burrows-Wheeler Aligner for short-read alignment
# tool_version: 0.7.17
# tool_category: Alignment
# tool_input_formats: FASTQ, FASTA
# tool_output_formats: SAM, BAM
# tool_author: Heng Li
# tool_url: https://github.com/lh3/bwa
# tool_icon: dna
# tool_color: blue
# tool_commands: bwa,index,mem,aln,samse,sampe,bwasw,bwtsw
# tool_primary_command: bwa
# tool_command_template: bwa mem -t 4 {input_file_1} {input_file_2} > {output_dir}/alignment.sam

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libbz2-dev \
    liblzma-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and install BWA (using a more recent version)
RUN wget https://github.com/lh3/bwa/releases/download/v0.7.17/bwa-0.7.17.tar.bz2 \
    && tar -xjf bwa-0.7.17.tar.bz2 \
    && cd bwa-0.7.17 \
    && sed -i 's/-DHAVE_PTHREAD/-DHAVE_PTHREAD -fcommon/' Makefile \
    && make \
    && cp bwa /usr/local/bin/ \
    && cd .. \
    && rm -rf bwa-0.7.17*

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["bwa"]