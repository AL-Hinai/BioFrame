FROM openjdk:11-jre-slim

# BIOFRAME_TOOL_METADATA
# tool_name: ASTRAL
# tool_description: Accurate Species TRee ALgorithm for reconstructing species trees from gene trees
# tool_version: 5.7.8
# tool_category: Phylogenetic Analysis
# tool_input_formats: NEWICK
# tool_output_formats: NEWICK, LOG
# tool_author: Siavash Mirarab
# tool_url: https://github.com/smirarab/ASTRAL
# tool_icon: tree
# tool_color: red
# tool_commands: java
# tool_primary_command: java
# tool_command_template: java -jar /usr/local/bin/astral.jar -i {input_files} -o {output_file} {options}

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install ASTRAL
RUN wget https://github.com/smirarab/ASTRAL/raw/master/Astral/astral.5.7.8.jar \
    && mv astral.5.7.8.jar /usr/local/bin/astral.jar \
    && chmod +x /usr/local/bin/astral.jar

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["java", "-jar", "/usr/local/bin/astral.jar", "-h"]
