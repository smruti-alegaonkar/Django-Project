from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal

# Create your models here.

class FacultyProfile(models.Model):
    """
    Extended profile for faculty members
    Linked to Django's built-in User model
    """
    user = models.OneToOneField(
    User,
    on_delete=models.CASCADE,
    related_name='faculty_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    date_of_joining = models.DateField()
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"
    
    class Meta:
        verbose_name = "Faculty Profile"
        verbose_name_plural = "Faculty Profiles"
        ordering = ['user__first_name']


class LeaveType(models.Model):
    """
    Different types of leaves available
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    max_days_per_year = models.IntegerField(validators=[MinValueValidator(1)])
    requires_document = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Leave Type"
        verbose_name_plural = "Leave Types"
        ordering = ['name']


class LeaveBalance(models.Model):
    """
    Track leave balance for each faculty member
    """
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    total_leaves = models.IntegerField(validators=[MinValueValidator(0)])
    used_leaves = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    
    def remaining_leaves(self):
        """Calculate remaining leaves"""
        return self.total_leaves - float(self.used_leaves)
    
    def __str__(self):
        return f"{self.faculty.user.username} - {self.leave_type.name} ({self.year})"
    
    class Meta:
        verbose_name = "Leave Balance"
        verbose_name_plural = "Leave Balances"
        unique_together = ['faculty', 'leave_type', 'year']
        ordering = ['-year', 'leave_type']


class LeaveRequest(models.Model):
    """
    Individual leave request submitted by faculty
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    number_of_days = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves')
    reviewed_on = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True)
    supporting_document = models.FileField(upload_to='leave_documents/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.faculty.user.username} - {self.leave_type.name} ({self.start_date} to {self.end_date})"
    
    def save(self, *args, **kwargs):
        """Override save to calculate number of days"""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.number_of_days = Decimal(delta.days + 1)
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"
        ordering = ['-applied_on']
        get_latest_by = 'applied_on'