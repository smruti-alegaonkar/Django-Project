from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import LeaveRequest, LeaveBalance, FacultyProfile
from .forms import LeaveReviewForm, LeaveRequestForm
from django.http import HttpResponse
from django.utils import timezone
import csv
from datetime import datetime, timedelta
from django.contrib.auth import login
from .forms import FacultyRegistrationForm
from django.db.models import Count, Q, Sum
from django.db import models
import json

@login_required
@user_passes_test(lambda u: u.is_staff)
def reports(request):
    """Generate leave reports and analytics"""
    current_year = datetime.now().year
    
    # Leave statistics by type
    leave_by_type = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).values('leave_type__name').annotate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected')),
        pending=Count('id', filter=Q(status='pending'))
    )
    
    # Leave statistics by department
    leave_by_dept = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).values('faculty__department').annotate(
        total=Count('id'),
        total_days=Sum('number_of_days')
    ).order_by('-total')
    
    # Monthly leave trend
    monthly_leaves = []
    for month in range(1, 13):
        count = LeaveRequest.objects.filter(
            start_date__year=current_year,
            start_date__month=month,
            status='approved'
        ).count()
        monthly_leaves.append(count)
    
    # Top leave requesters
    top_requesters = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).values(
        'faculty__user__first_name',
        'faculty__user__last_name',
        'faculty__department'
    ).annotate(
        total_requests=Count('id'),
        total_days=Sum('number_of_days')
    ).order_by('-total_requests')[:10]
    
    context = {
        'leave_by_type': leave_by_type,
        'leave_by_dept': leave_by_dept,
        'monthly_leaves': monthly_leaves,
        'top_requesters': top_requesters,
        'current_year': current_year,
    }
    return render(request, 'leaves/reports.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def export_leaves_csv(request):
    """Export leave requests to CSV"""
    # Get filter parameters
    status = request.GET.get('status', '')
    department = request.GET.get('department', '')
    year = request.GET.get('year', datetime.now().year)
    
    # Build queryset
    leaves = LeaveRequest.objects.filter(start_date__year=year)
    if status:
        leaves = leaves.filter(status=status)
    if department:
        leaves = leaves.filter(faculty__department=department)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_requests_{year}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Faculty Name', 'Employee ID', 'Department', 'Leave Type',
        'Start Date', 'End Date', 'Days', 'Status', 'Applied On',
        'Reviewed By', 'Reviewed On', 'Remarks'
    ])
    
    for leave in leaves:
        writer.writerow([
            leave.faculty.user.get_full_name(),
            leave.faculty.employee_id,
            leave.faculty.department,
            leave.leave_type.name,
            leave.start_date,
            leave.end_date,
            leave.number_of_days,
            leave.get_status_display(),
            leave.applied_on.strftime('%Y-%m-%d %H:%M'),
            leave.reviewed_by.get_full_name() if leave.reviewed_by else '',
            leave.reviewed_on.strftime('%Y-%m-%d %H:%M') if leave.reviewed_on else '',
            leave.admin_remarks or ''
        ])
    
    return response


@login_required
@user_passes_test(lambda u: u.is_staff)
def export_leaves_pdf(request):
    """Export leave summary to PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from io import BytesIO
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0d6efd'),
        spaceAfter=30,
        alignment=1  # Center
    )
    elements.append(Paragraph('Leave Management Report', title_style))
    elements.append(Paragraph(f'Generated on: {datetime.now().strftime("%B %d, %Y")}', styles['Normal']))
    elements.append(Spacer(1, 0.5*inch))
    
    # Statistics
    current_year = datetime.now().year
    total = LeaveRequest.objects.filter(start_date__year=current_year).count()
    pending = LeaveRequest.objects.filter(start_date__year=current_year, status='pending').count()
    approved = LeaveRequest.objects.filter(start_date__year=current_year, status='approved').count()
    rejected = LeaveRequest.objects.filter(start_date__year=current_year, status='rejected').count()
    
    stats_data = [
        ['Statistics', 'Count'],
        ['Total Requests', str(total)],
        ['Pending', str(pending)],
        ['Approved', str(approved)],
        ['Rejected', str(rejected)],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Department-wise summary
    elements.append(Paragraph('Department-wise Leave Summary', styles['Heading2']))
    elements.append(Spacer(1, 0.2*inch))
    
    dept_data = [['Department', 'Total Requests', 'Total Days']]
    dept_summary = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).values('faculty__department').annotate(
        total=Count('id'),
        days=Sum('number_of_days')
    ).order_by('-total')
    
    for dept in dept_summary:
        dept_data.append([
            dept['faculty__department'],
            str(dept['total']),
            str(dept['days'])
        ])
    
    dept_table = Table(dept_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
    dept_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(dept_table)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="leave_report_{current_year}.pdf"'
    response.write(pdf)
    
    return response


@login_required
def reports(request):

    if not request.user.is_superuser:
        return redirect("leaves:dashboard")

    current_year = datetime.now().year

    # 🔥 FIXED FILTER (use start_date not applied_on)
    leaves = LeaveRequest.objects.filter(
        start_date__year=current_year
    )

    # Leave by type
    leave_by_type = leaves.values("leave_type__name").annotate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
        rejected=Count("id", filter=Q(status="rejected")),
        pending=Count("id", filter=Q(status="pending"))
    )

    leave_type_labels = [x["leave_type__name"] for x in leave_by_type]
    leave_type_totals = [x["total"] for x in leave_by_type]
    leave_type_approved = [x["approved"] for x in leave_by_type]
    leave_type_rejected = [x["rejected"] for x in leave_by_type]
    leave_type_pending = [x["pending"] for x in leave_by_type]

    # Department report
    leave_by_dept = leaves.values("faculty__department").annotate(
        total=Count("id"),
        total_days=Sum("number_of_days")
    )

    # Monthly approved using start_date
    monthly_data = []
    for month in range(1, 13):
        count = leaves.filter(
            status="approved",
            start_date__month=month
        ).count()
        monthly_data.append(count)

    # Top requesters
    top_requesters = leaves.values(
        "faculty__user__first_name",
        "faculty__user__last_name",
        "faculty__department"
    ).annotate(
        total_requests=Count("id"),
        total_days=Sum("number_of_days")
    ).order_by("-total_requests")[:5]

    context = {
        "current_year": current_year,
        "leave_by_dept": leave_by_dept,
        "top_requesters": top_requesters,
        "leave_type_labels": json.dumps(leave_type_labels),
        "leave_type_totals": json.dumps(leave_type_totals),
        "leave_type_approved": json.dumps(leave_type_approved),
        "leave_type_rejected": json.dumps(leave_type_rejected),
        "leave_type_pending": json.dumps(leave_type_pending),
        "monthly_leaves": json.dumps(monthly_data),
    }

    return render(request, "leaves/reports.html", context)

@login_required
def is_staff_user(user):
    return user.is_staff

@user_passes_test(is_staff_user)
def pending_requests(request):
    """View all pending leave requests"""
    leave_requests = LeaveRequest.objects.filter(
        status='pending'
    ).order_by('-applied_on')
    
    context = {
        'leave_requests': leave_requests,
    }
    return render(request, 'leaves/pending_requests.html', context)


@login_required
@user_passes_test(is_staff_user)
def review_leave(request, leave_id):
    """Review and approve/reject leave request"""
    leave_request = get_object_or_404(LeaveRequest, id=leave_id)
    
    if request.method == 'POST':
        form = LeaveReviewForm(request.POST, instance=leave_request)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.reviewed_by = request.user
            leave.reviewed_on = timezone.now()
            
            # Update leave balance if approved
            if leave.status == 'approved':
                try:
                    leave_balance = LeaveBalance.objects.get(
                        faculty=leave.faculty,
                        leave_type=leave.leave_type,
                        year=leave.start_date.year
                    )
                    leave_balance.used_leaves = leave_balance.used_leaves + leave.number_of_days
                    leave_balance.save()
                    
                    messages.success(request, f'Leave request approved for {leave.faculty.user.get_full_name()}.')
                except LeaveBalance.DoesNotExist:
                    messages.warning(request, 'Leave approved but balance not found.')
            else:
                messages.info(request, f'Leave request rejected for {leave.faculty.user.get_full_name()}.')
            
            leave.save()
            return redirect('leaves:pending_requests')
    else:
        form = LeaveReviewForm(instance=leave_request)
    
    context = {
        'form': form,
        'leave_request': leave_request,
    }
    return render(request, 'leaves/review_leave.html', context)


@login_required
@user_passes_test(is_staff_user)
def all_leaves(request):
    """View all leave requests (admin dashboard)"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    department_filter = request.GET.get('department', '')
    
    # Base query
    leave_requests = LeaveRequest.objects.all()
    
    # Apply filters
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    if department_filter:
        leave_requests = leave_requests.filter(faculty__department=department_filter)
    
    # Order by latest
    leave_requests = leave_requests.order_by('-applied_on')
    
    # Get statistics
    total_requests = LeaveRequest.objects.count()
    pending_count = LeaveRequest.objects.filter(status='pending').count()
    approved_count = LeaveRequest.objects.filter(status='approved').count()
    rejected_count = LeaveRequest.objects.filter(status='rejected').count()
    
    # Get unique departments for filter
    from .models import FacultyProfile
    departments = FacultyProfile.objects.values_list('department', flat=True).distinct()
    
    context = {
        'leave_requests': leave_requests,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'departments': departments,
        'current_status': status_filter,
        'current_department': department_filter,
    }
    return render(request, 'leaves/all_leaves.html', context)

def register(request):
    if request.method == 'POST':
        form = FacultyRegistrationForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()

            FacultyProfile.objects.create(
                user=user,
                employee_id=form.cleaned_data['employee_id'],
                department=form.cleaned_data['department'],
                designation=form.cleaned_data['designation'],
                phone_number=form.cleaned_data['phone_number'],
                date_of_joining=form.cleaned_data['date_of_joining'],
                profile_picture=form.cleaned_data.get('profile_picture')
            )

            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect('leaves:dashboard')

        else:
            print(form.errors)   # VERY IMPORTANT FOR DEBUG

    else:
        form = FacultyRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})

@login_required
def dashboard(request):

    # If admin → redirect to admin panel
    if request.user.is_superuser:
        return redirect("admin:index")

    # Ensure faculty profile exists
    if not hasattr(request.user, "faculty_profile"):
        return redirect("logout")

    faculty = request.user.faculty_profile
    current_year = datetime.now().year

    # Leave counts
    pending_count = LeaveRequest.objects.filter(
        faculty=faculty,
        status="pending"
    ).count()

    approved_count = LeaveRequest.objects.filter(
        faculty=faculty,
        status="approved"
    ).count()

    rejected_count = LeaveRequest.objects.filter(
        faculty=faculty,
        status="rejected"
    ).count()

    total_count = LeaveRequest.objects.filter(
        faculty=faculty
    ).count()

    # Leave balances
    leave_balances = LeaveBalance.objects.filter(
        faculty=faculty,
        year=current_year
    )

    # Recent leave requests (latest 5)
    recent_leaves = LeaveRequest.objects.filter(
        faculty=faculty
    ).order_by("-applied_on")[:5]

    context = {
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "total_count": total_count,
        "leave_balances": leave_balances,
        "recent_leaves": recent_leaves,
    }

    return render(request, "leaves/dashboard.html", context)

@login_required
def apply_leave(request):

    if request.user.is_staff:
        return redirect('leaves:pending_requests')

    try:
        faculty = request.user.faculty_profile
    except FacultyProfile.DoesNotExist:
        return redirect('leaves:register')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.faculty = faculty
            leave.save()
            messages.success(request, "Leave applied successfully.")
            return redirect('leaves:dashboard')
    else:
        form = LeaveRequestForm()

    return render(request, 'leaves/apply_leave.html', {'form': form})


@login_required
def leave_history(request):
    faculty = request.user.faculty_profile
    leaves = LeaveRequest.objects.filter(
        faculty=faculty
    ).order_by('-applied_on')

    return render(request, 'leaves/leave_history.html', {
        'leaves': leaves
    })


@login_required
def profile(request):
    return render(request, 'leaves/profile.html')

@login_required
def my_reports(request):

    if request.user.is_superuser:
        return redirect("leaves:reports")

    try:
        faculty = request.user.faculty_profile
    except:
        messages.error(request, "Faculty profile not found.")
        return redirect("leaves:dashboard")

    current_year = datetime.now().year

    leaves = LeaveRequest.objects.filter(
        faculty=faculty,
        start_date__year=current_year
    )

    # Leave by type
    leave_by_type = leaves.values("leave_type__name").annotate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
        rejected=Count("id", filter=Q(status="rejected")),
        pending=Count("id", filter=Q(status="pending"))
    )

    leave_type_labels = [x["leave_type__name"] for x in leave_by_type]
    leave_type_totals = [x["total"] for x in leave_by_type]
    leave_type_approved = [x["approved"] for x in leave_by_type]
    leave_type_rejected = [x["rejected"] for x in leave_by_type]
    leave_type_pending = [x["pending"] for x in leave_by_type]

    # Monthly approved
    monthly_data = []
    for month in range(1, 13):
        count = leaves.filter(
            status="approved",
            start_date__month=month
        ).count()
        monthly_data.append(count)

    context = {
        "current_year": current_year,
        "leave_type_labels": json.dumps(leave_type_labels),
        "leave_type_totals": json.dumps(leave_type_totals),
        "leave_type_approved": json.dumps(leave_type_approved),
        "leave_type_rejected": json.dumps(leave_type_rejected),
        "leave_type_pending": json.dumps(leave_type_pending),
        "monthly_leaves": json.dumps(monthly_data),
    }

    return render(request, "leaves/reports.html", context)