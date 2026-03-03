from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import LeaveRequest, FacultyProfile
from datetime import date
from django import forms


class ProfileUpdateForm(forms.ModelForm):

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = FacultyProfile
        fields = [
            "first_name",
            "last_name",
            "email",
            "department",
            "designation",
            "phone_number",
            "profile_picture",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        # Prefill user data
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                "class": "form-control"
            })

    def save(self, commit=True):
        faculty = super().save(commit=False)

        # Update User model
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        self.user.save()

        if commit:
            faculty.save()

        return faculty

class LeaveRequestForm(forms.ModelForm):
    """
    Form for faculty to apply for leave
    """
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason', 'supporting_document']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': date.today().isoformat()
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control',
                'min': date.today().isoformat()
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please provide reason for leave...'
            }),
            'leave_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'supporting_document': forms.FileInput(attrs={
                'class': 'form-control'
            })
        }
        labels = {
            'leave_type': 'Type of Leave',
            'start_date': 'From Date',
            'end_date': 'To Date',
            'reason': 'Reason for Leave',
            'supporting_document': 'Supporting Document (if any)'
        }
        help_texts = {
            'start_date': 'Leave start date',
            'end_date': 'Leave end date',
            'supporting_document': 'Upload medical certificate or other documents (PDF, JPG, PNG - Max 5MB)'
        }
    
    def clean(self):
        """
        Custom validation for the entire form
        """
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        leave_type = cleaned_data.get('leave_type')
        
        # Validate dates
        if start_date and end_date:
            # Check if end date is after start date
            if end_date < start_date:
                raise ValidationError('End date must be after start date.')
            
            # Check if dates are not in the past
            if start_date < date.today():
                raise ValidationError('Cannot apply for leave in the past.')
            
            # Calculate number of days
            delta = end_date - start_date
            number_of_days = delta.days + 1
            
            # Check if exceeds maximum days for leave type
            if leave_type and number_of_days > leave_type.max_days_per_year:
                raise ValidationError(
                    f'{leave_type.name} allows maximum {leave_type.max_days_per_year} days. '
                    f'You are requesting {number_of_days} days.'
                )
        
        return cleaned_data
    
    def clean_supporting_document(self):
        """
        Validate uploaded document
        """
        document = self.cleaned_data.get('supporting_document')
        
        if document:
            # Check file size (5MB limit)
            if document.size > 5 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 5MB.')
            
            # Check file extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            file_extension = document.name[document.name.rfind('.'):].lower()
            
            if file_extension not in allowed_extensions:
                raise ValidationError(
                    f'Only {", ".join(allowed_extensions)} files are allowed.'
                )
        
        return document


class LeaveReviewForm(forms.ModelForm):
    """
    Form for admin to review leave requests
    """
    class Meta:
        model = LeaveRequest
        fields = ['status', 'admin_remarks']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'admin_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add remarks (optional)...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit status choices to approved/rejected only
        self.fields['status'].choices = [
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ]


class FacultyRegistrationForm(UserCreationForm):
    """
    Extended registration form for faculty
    """
    # User fields
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Faculty profile fields
    employee_id = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    designation = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    date_of_joining = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only pre-fill if instance is FacultyProfile
        if isinstance(self.instance, FacultyProfile) and self.instance.pk:
            if self.instance.user:
                self.fields['first_name'].initial = self.instance.user.first_name
                self.fields['last_name'].initial = self.instance.user.last_name
                self.fields['email'].initial = self.instance.user.email
    
    def clean_email(self):
        """
        Validate that email is unique
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email
    
    def clean_employee_id(self):
        """
        Validate that employee ID is unique
        """
        employee_id = self.cleaned_data.get('employee_id')
        if FacultyProfile.objects.filter(employee_id=employee_id).exists():
            raise ValidationError('This employee ID is already registered.')
        return employee_id


class FacultyProfileUpdateForm(forms.ModelForm):
    """
    Form to update faculty profile
    """
    # Include User fields
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = FacultyProfile
        fields = ['department', 'designation', 'phone_number', 'profile_picture']
        widgets = {
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate user fields if instance exists
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email