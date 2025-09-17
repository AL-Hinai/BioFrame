FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: BEDtools
# tool_description: Swiss army knife for genome arithmetic
# tool_version: 2.30.0
# tool_category: Genome Analysis
# tool_input_formats: BED, GFF, VCF, SAM, BAM
# tool_output_formats: BED, GFF, VCF, TXT
# tool_author: Aaron Quinlan
# tool_url: https://github.com/arq5x/bedtools2
# tool_icon: tools
# tool_color: teal
# tool_commands: intersect,union,subtract,merge,coverage,getfasta,slop,flank,closest,window,map,groupby,annotate,genomecov,merge,subtract,complement,shift,shuffle,random,makewindows,getfasta,getoverlap,closest,window,map,groupby,annotate,genomecov,merge,subtract,complement,shift,shuffle,random,makewindows
# tool_primary_command: bedtools
# tool_command_template: bedtools intersect -a {input_file_1} -b {input_file_2} > {output_dir}/intersection.bed

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install BEDtools from pre-built binary
RUN wget https://github.com/arq5x/bedtools2/releases/download/v2.30.0/bedtools.static.binary \
    && chmod +x bedtools.static.binary \
    && mv bedtools.static.binary /usr/local/bin/bedtools

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["bedtools", "--help"]
