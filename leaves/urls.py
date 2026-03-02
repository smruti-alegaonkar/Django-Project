from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('apply/', views.apply_leave, name='apply_leave'),
    path('history/', views.leave_history, name='leave_history'),
    path('profile/', views.profile, name='profile'),
    path('register/', views.register, name='register'),
    
    # Admin URLs
    path('pending/', views.pending_requests, name='pending_requests'),
    path('review/<int:leave_id>/', views.review_leave, name='review_leave'),
    path('all-leaves/', views.all_leaves, name='all_leaves'),
    path('reports/', views.reports, name='reports'),
    path('reports/my/', views.my_reports, name='my_reports'),
    path('export/csv/', views.export_leaves_csv, name='export_leaves_csv'),
    path('export/pdf/', views.export_leaves_pdf, name='export_leaves_pdf'),
    
]