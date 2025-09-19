from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import os


class FileUploadSession(models.Model):
    """Track file upload sessions for workflow runs"""
    
    UPLOAD_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('uploading', 'Uploading'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    workflow_template_id = models.CharField(max_length=100)
    run_name = models.CharField(max_length=200)
    run_description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    uploaded_files = models.IntegerField(default=0)
    total_size = models.BigIntegerField(default=0)  # in bytes
    uploaded_size = models.BigIntegerField(default=0)  # in bytes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Upload Session {self.id} - {self.run_name}"
    
    @property
    def progress_percentage(self):
        """Calculate upload progress percentage"""
        if self.total_size == 0:
            return 0
        return int((self.uploaded_size / self.total_size) * 100)
    
    @property
    def is_complete(self):
        """Check if all files have been uploaded"""
        return self.status == 'completed' and self.uploaded_files == self.total_files


class UploadedFile(models.Model):
    """Track individual uploaded files"""
    
    FILE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('uploading', 'Uploading'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('validated', 'Validated'),
        ('invalid', 'Invalid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(FileUploadSession, on_delete=models.CASCADE, related_name='files')
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=FILE_STATUS_CHOICES, default='pending')
    upload_progress = models.IntegerField(default=0)  # 0-100
    checksum = models.CharField(max_length=64, blank=True)  # SHA-256
    validation_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.original_name} ({self.file_size} bytes)"
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.original_name)[1].lower()
    
    @property
    def is_valid_format(self):
        """Check if file format is valid for bioinformatics"""
        valid_extensions = [
            '.fastq', '.fq', '.fastq.gz', '.fq.gz',
            '.fasta', '.fa', '.fasta.gz', '.fa.gz',
            '.bam', '.sam', '.vcf', '.gtf', '.gff',
            '.txt', '.log', '.html', '.pdf'
        ]
        return self.file_extension in valid_extensions


class WorkflowRun(models.Model):
    """Track workflow runs after successful file upload"""
    
    RUN_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload_session = models.OneToOneField(FileUploadSession, on_delete=models.CASCADE)
    workflow_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=RUN_STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    output_directory = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Workflow Run {self.workflow_id} - {self.upload_session.run_name}"






