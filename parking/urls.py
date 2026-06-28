from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # ==================== AUTHENTICATION ====================
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),

    # ==================== MAIN PAGES ====================
    path('home/', views.home, name='home'),
    path('park/', views.park_vehicle, name='park_vehicle'),
    path('monthly-pass/', views.monthly_pass, name='monthly_pass'),
    path('purchase-pass/', views.purchase_monthly_pass, name='purchase_monthly_pass'),
    path('profile/', views.user_profile, name='user_profile'),
    path('contact/', views.contact_view, name='contact'),
    path('api/ticket-status/<str:ticket_id>/', views.check_ticket_status, name='check_ticket_status'),

    # ==================== NOTIFICATIONS ====================
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),

    # ==================== BOOKING PROCESS ====================
    path('payment/', views.payment_page, name='payment_page'),
    path('booking-success/<int:session_id>/', views.booking_success, name='booking_success'),
    path('exit/<int:session_id>/', views.exit_parking, name='exit_parking'),
    path('exit-confirmed/<int:session_id>/', views.exit_confirmed, name='exit_confirmed'),
    path('verify-exit/', views.verify_exit, name='verify_exit'),
    path('process-exit/<int:session_id>/', views.process_exit, name='process_exit'),

    # ==================== ADMIN DASHBOARD & PROFILE ====================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-profile/', views.admin_profile, name='admin_profile'),

    # Add this line in API ENDPOINTS section
path('api/ai-recommend-slot/', views.api_ai_recommend_slot, name='api_ai_recommend_slot'),
    # ==================== API ENDPOINTS ====================
    path('api/parking/floors/<int:location_id>/', views.api_get_floors, name='api_get_floors'),
    path('api/parking/blocks/<int:floor_id>/', views.api_get_blocks, name='api_get_blocks'),
    path('api/parking/slots/', views.api_get_slots, name='api_get_slots'),
    path('api/parking-lots-stats/', views.api_parking_lot_stats, name='api_parking_lot_stats'),  
    path('api/vehicle-status/<str:vehicle_number>/', views.check_vehicle_status, name='check_vehicle_status'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
path('manager/profile/', views.manager_profile, name='manager_profile'),
path('manager/cctv/', views.cctv_monitoring, name='cctv_monitoring'),
path('manager/entry/', views.entry_verification, name='entry_verification'),
path('manager/exit/', views.exit_verification, name='exit_verification'),
path('manager/manual-entry/', views.manual_entry, name='manual_entry'),
path('manager/manual-exit/<int:session_id>/', views.manual_exit, name='manual_exit'),
path('manager/incidents/', views.security_incidents, name='security_incidents'),
path('manager/incidents/create/', views.create_incident, name='create_incident'),

# Manager API Endpoints
path('api/manager/verify-booking/', views.api_verify_booking, name='api_verify_booking'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)