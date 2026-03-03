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
from django.utils.timezone import now
from reportlab.pdfgen import canvas
import io
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import ProfileUpdateForm

class CustomLoginView(LoginView):
    template_name = "leaves/login.html"

    def get_success_url(self):
        user = self.request.user

        if user.is_superuser:
            return reverse_lazy('leaves:reports')   # Admin goes to reports
        else:
            return reverse_lazy('leaves:dashboard') # Faculty goes to dashboard

@login_required
def export_leaves_csv(request):

    year = request.GET.get('year', now().year)

    # Role-based filtering
    if request.user.is_superuser:
        leaves = LeaveRequest.objects.filter(start_date__year=year)
    else:
        faculty_profile = FacultyProfile.objects.get(user=request.user)
        leaves = LeaveRequest.objects.filter(
            faculty=faculty_profile,
            start_date__year=year
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_report_{year}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Faculty",
        "Leave Type",
        "Start Date",
        "End Date",
        "Days",
        "Status"
    ])

    for leave in leaves:
        writer.writerow([
            leave.faculty.user.get_full_name(),
            leave.leave_type.name,
            leave.start_date,
            leave.end_date,
            leave.number_of_days,
            leave.status
        ])

    return response


@login_required
def export_leaves_pdf(request):

    year = request.GET.get("year", now().year)

    if request.user.is_superuser:
        leaves = LeaveRequest.objects.filter(start_date__year=year)
    else:
        faculty_profile = FacultyProfile.objects.get(user=request.user)
        leaves = LeaveRequest.objects.filter(
            faculty=faculty_profile,
            start_date__year=year
        )

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    y = 800
    p.drawString(200, y, f"Leave Report - {year}")
    y -= 30

    for leave in leaves:
        text = f"{leave.faculty.user.get_full_name()} | {leave.leave_type.name} | {leave.start_date} | {leave.status}"
        p.drawString(50, y, text)
        y -= 20

    p.showPage()
    p.save()

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="leave_report_{year}.pdf"'

    return response


@login_required
def reports(request):

    current_year = now().year

    # 🔹 Role-based filtering
    if request.user.is_superuser:
        leaves = LeaveRequest.objects.filter(start_date__year=current_year)
    else:
        faculty_profile = FacultyProfile.objects.get(user=request.user)
        leaves = LeaveRequest.objects.filter(
            faculty=faculty_profile,
        )

    # 🔹 Leave type stats
    leave_type_data = leaves.values('leave_type__name').annotate(
        total=Count('id')
    )

    leave_type_labels = [item['leave_type__name'] for item in leave_type_data]
    leave_type_totals = [item['total'] for item in leave_type_data]

    leave_type_approved = []
    leave_type_rejected = []
    leave_type_pending = []

    for label in leave_type_labels:
        leave_type_approved.append(
            leaves.filter(leave_type__name=label, status='approved').count()
        )
        leave_type_rejected.append(
            leaves.filter(leave_type__name=label, status='rejected').count()
        )
        leave_type_pending.append(
            leaves.filter(leave_type__name=label, status='pending').count()
        )

    # 🔹 Monthly approved
    monthly_leaves = []
    for month in range(1, 13):
        monthly_leaves.append(
            leaves.filter(
                status='approved',
                start_date__month=month
            ).count()
        )

    # 🔹 ADDITION: Admin-only analytics tables
    if request.user.is_superuser:

        leave_by_dept = leaves.values(
            'faculty__department'
        ).annotate(
            total=Count('id'),
            total_days=Sum('number_of_days')
        )

        top_requesters = leaves.values(
            'faculty__user__first_name',
            'faculty__user__last_name',
            'faculty__department'
        ).annotate(
            total_requests=Count('id'),
            total_days=Sum('number_of_days')
        ).order_by('-total_requests')[:5]

    else:
        leave_by_dept = None
        top_requesters = None

    context = {
        "current_year": current_year,
        "leave_type_labels": json.dumps(leave_type_labels),
        "leave_type_totals": json.dumps(leave_type_totals),
        "leave_type_approved": json.dumps(leave_type_approved),
        "leave_type_rejected": json.dumps(leave_type_rejected),
        "leave_type_pending": json.dumps(leave_type_pending),
        "monthly_leaves": json.dumps(monthly_leaves),

        # 🔹 ADDED
        "leave_by_dept": leave_by_dept,
        "top_requesters": top_requesters,
    }

    return render(request, "leaves/reports.html", context)

def is_staff_user(user):
    return user.is_superuser

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
    faculty_profile = FacultyProfile.objects.get(user=request.user)

    leave_requests = LeaveRequest.objects.filter(
        faculty=faculty_profile
    ).order_by('-applied_on')

    return render(request, 'leaves/leave_history.html', {
        'leave_requests': leave_requests
    })


@login_required
def profile(request):

    faculty = FacultyProfile.objects.get(user=request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=faculty,
            user=request.user
        )

        if form.is_valid():
            form.save()
            return redirect("leaves:profile")

    else:
        form = ProfileUpdateForm(instance=faculty, user=request.user)

    return render(request, "leaves/profile.html", {
        "faculty": faculty,
        "form": form
    })