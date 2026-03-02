from django.contrib import admin
from .models import FacultyProfile, LeaveType, LeaveBalance, LeaveRequest

# Register your models here.

@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'get_full_name', 'department', 'designation', 'date_of_joining']
    list_filter = ['department', 'designation', 'date_of_joining']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name', 'user__email']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_days_per_year', 'requires_document', 'is_active']
    list_filter = ['is_active', 'requires_document']
    search_fields = ['name', 'description']


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'leave_type', 'year', 'total_leaves', 'used_leaves', 'get_remaining']
    list_filter = ['year', 'leave_type']
    search_fields = ['faculty__user__first_name', 'faculty__user__last_name', 'faculty__employee_id']
    
    def get_remaining(self, obj):
        return obj.remaining_leaves()
    get_remaining.short_description = 'Remaining Leaves'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'leave_type', 'start_date', 'end_date', 'number_of_days', 'status', 'applied_on']
    list_filter = ['status', 'leave_type', 'applied_on', 'start_date']
    search_fields = ['faculty__user__first_name', 'faculty__user__last_name', 'reason']
    readonly_fields = ['applied_on', 'number_of_days']
    date_hierarchy = 'applied_on'
    
    fieldsets = (
        ('Leave Information', {
            'fields': ('faculty', 'leave_type', 'start_date', 'end_date', 'number_of_days', 'reason')
        }),
        ('Status', {
            'fields': ('status', 'reviewed_by', 'reviewed_on', 'admin_remarks')
        }),
        ('Documents', {
            'fields': ('supporting_document',),
            'classes': ('collapse',)
        }),
    )