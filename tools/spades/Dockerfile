FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: SPAdes
# tool_description: Assembler for single-cell and multi-cell data
# tool_version: 4.2.0
# tool_category: Assembly
# tool_input_formats: FASTQ, FASTA
# tool_output_formats: FASTA, GFA
# tool_author: Center for Algorithmic Biotechnology
# tool_url: https://github.com/ablab/spades
# tool_icon: puzzle-piece
# tool_color: green
# tool_commands: spades.py
# tool_primary_command: spades.py
# tool_command_template: spades.py --threads 4 --memory 12 -1 {input_file_1} -2 {input_file_2} -o {output_dir}
# tool_memory_requirement: 12g
# tool_cpu_requirement: 4
# tool_expected_outputs: {output_dir}/contigs.fasta,{output_dir}/scaffolds.fasta
# tool_success_indicators: SPAdes pipeline finished,Thank you for using SPAdes
# tool_failure_indicators: ERROR,FATAL,Failed,Segmentation fault

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create python symlink for compatibility
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Install SPAdes from pre-built binary (much faster)
RUN wget https://github.com/ablab/spades/releases/download/v4.2.0/SPAdes-4.2.0-Linux.tar.gz \
    && tar -xzf SPAdes-4.2.0-Linux.tar.gz \
    && cp -r SPAdes-4.2.0-Linux /usr/local/spades \
    && ln -sf /usr/local/spades/bin/* /usr/local/bin/ \
    && rm -rf SPAdes-4.2.0-Linux*

# Set SPAdes environment variables
ENV SPADES_HOME=/usr/local/spades
ENV PATH=/usr/local/spades/bin:$PATH

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
CMD ["spades.py", "--help"]
