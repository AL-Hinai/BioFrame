FROM ubuntu:22.04

# BIOFRAME_TOOL_METADATA
# tool_name: GATK
# tool_description: Genome Analysis Toolkit for variant discovery
# tool_version: 4.4.0.0
# tool_category: Variant Calling
# tool_input_formats: BAM, VCF, FASTA
# tool_output_formats: VCF, BAM, TXT
# tool_author: Broad Institute
# tool_url: https://github.com/broadinstitute/gatk
# tool_icon: search
# tool_color: red
# tool_commands: gatk,HaplotypeCaller,GenotypeGVCFs,SelectVariants,FilterVariants,CombineGVCFs,GenomicsDBImport,ApplyVQSR,BaseRecalibrator,PrintReads,MarkDuplicates,SortSam,AddOrReplaceReadGroups,CreateSequenceDictionary,IndexFeatureFile,IndexVcf,ValidateSamFile,CollectReadCounts,DenoiseReadCounts,ModelSegments,CallCopyRatioSegments,PlotModeledSegments,CollectAllelicCounts,DenoiseReadCounts,ModelSegments,CallCopyRatioSegments,PlotModeledSegments,CollectAllelicCounts
# tool_primary_command: gatk
# tool_command_template: gatk HaplotypeCaller -R {input_file_1} -I {input_file_2} -O {output_dir}/variants.vcf

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    default-jre \
    default-jdk \
    python3 \
    python3-pip \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install GATK
RUN wget https://github.com/broadinstitute/gatk/releases/download/4.4.0.0/gatk-4.4.0.0.zip \
    && unzip gatk-4.4.0.0.zip \
    && chmod +x gatk-4.4.0.0/gatk \
    && ln -s /gatk-4.4.0.0/gatk /usr/local/bin/gatk

# Install additional bioinformatics tools
RUN pip3 install \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    biopython \
    pysam

# Create working directories
RUN mkdir -p /data /logs /output

# Set working directory
WORKDIR /data

# Default command
CMD ["gatk", "--help"]
