FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: Pilon
# tool_description: Automated assembly improvement and variant calling tool for genome assemblies
# tool_version: 1.24
# tool_category: Assembly Improvement
# tool_input_formats: FASTA, BAM, VCF
# tool_output_formats: FASTA, VCF, GFF
# tool_author: Broad Institute
# tool_url: https://github.com/broadinstitute/pilon
# tool_icon: dna
# tool_color: purple

# Install dependencies
RUN apt-get update && apt-get install -y \
    openjdk-11-jre \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download and install Pilon
RUN wget https://github.com/broadinstitute/pilon/releases/download/v1.24/pilon-1.24.jar -O /usr/local/bin/pilon.jar

# Create wrapper script
RUN echo '#!/bin/bash\njava -jar /usr/local/bin/pilon.jar "$@"' > /usr/local/bin/pilon && \
    chmod +x /usr/local/bin/pilon

# Set working directory
WORKDIR /data

# Default command
CMD ["pilon", "--help"]
