from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import date, datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings


import logging

# Import all models
from .models import (
    Vehicle,
    ParkingLot,
    ParkingFloor, 
    Block,
    ParkingSlot, 
    ParkingSession,
    PassType,
    MonthlyPass,
    PricingRule,
    Notification,
    UserNotification,
    SupportTicket,
    EntryExitLog,
    GalleryImage,
    SystemSettings,
    Landmark,
    ParkingZone
)
import uuid

logger = logging.getLogger(__name__)

# ==================== AUTHENTICATION VIEWS ====================
def landing(request):
    """Redirect to home if authenticated, otherwise to login"""
    if request.user.is_authenticated:
        return redirect('home')
    return redirect('user_login')

def register(request):
    """Handle user registration"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match!')
            return redirect('register')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists!')
            return redirect('register')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered!')
            return redirect('register')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name
        )
        user.save()
        messages.success(request, '✅ Account created successfully! Please login.')
        return redirect('user_login')
    
    return render(request, 'parking/register.html')

def user_login(request):
    """Handle user login with role-based redirection"""
    
    # ✅ Already logged in - redirect based on role
    if request.user.is_authenticated:
        # 1️⃣ Check if SUPERUSER/ADMIN
        if request.user.is_superuser or (request.user.is_staff and not hasattr(request.user, 'manager_profile')):
            return redirect('admin_dashboard')
        
        # 2️⃣ Check if MANAGER
        if hasattr(request.user, 'manager_profile') and request.user.manager_profile.is_active_manager:
            return redirect('manager_dashboard')
        
        # 3️⃣ Otherwise REGULAR USER
        return redirect('home')
    
    # ✅ Login form submission
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # ==================== ROLE-BASED REDIRECTION ====================
            
            # 1️⃣ SUPERUSER/ADMIN → Admin Dashboard
            if user.is_superuser or (user.is_staff and not hasattr(user, 'manager_profile')):
                messages.success(request, f'✅ Welcome Admin, {username}!')
                return redirect('admin_dashboard')
            
            # 2️⃣ MANAGER → Manager Dashboard
            if hasattr(user, 'manager_profile') and user.manager_profile.is_active_manager:
                messages.success(request, f'✅ Welcome Manager, {username}!')
                return redirect('manager_dashboard')
            
            # 3️⃣ REGULAR USER → User Home
            messages.success(request, f'✅ Welcome back, {username}!')
            return redirect('home')
        else:
            messages.error(request, '❌ Invalid username or password!')
            return redirect('user_login')
    
    return render(request, 'parking/login.html')

def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('user_login')

# ==================== HOME VIEW ====================
@login_required(login_url='user_login')
def home(request):
    """Main dashboard - Fully connected to Admin data"""
    user = request.user
    
    # Get all active parking lots with real-time stats (ADMIN DATA)
    parking_lots = ParkingLot.objects.filter(is_active=True).annotate(
        total_slots=Count('slots'),
        available_count=Count('slots', filter=Q(slots__slot_status='available')),
        occupied_count=Count('slots', filter=Q(slots__slot_status='occupied'))
    ).prefetch_related('landmarks')
    
    # Overall statistics
    total_slots = ParkingSlot.objects.count()
    available_slots = ParkingSlot.objects.filter(slot_status='available').count()
    occupied_slots = ParkingSlot.objects.filter(slot_status='occupied').count()
    
    # Get user's vehicles
    user_vehicles = Vehicle.objects.filter(owner_name=user.username)
    
    # Get current active booking
    current_booking = ParkingSession.objects.filter(
        vehicle__owner_name=user.username,
        exit_time__isnull=True
    ).select_related('vehicle', 'slot', 'slot__parking_lot').first()
    
    # Get recent parking history
    parking_history = ParkingSession.objects.filter(
        vehicle__owner_name=user.username
    ).select_related('vehicle', 'slot', 'slot__parking_lot').order_by('-entry_time')[:10]
    
    # Calculate user's total spent
    total_spent = ParkingSession.objects.filter(
        vehicle__owner_name=user.username,
        fee__isnull=False
    ).aggregate(total=Sum('fee'))['total'] or 0
    
    # Get active notifications (Admin-created)
    notifications = Notification.objects.filter(
        Q(send_to_all=True) | Q(target_users=user),
        is_active=True
    ).order_by('-created_at')[:5]
    
    # Get pricing rules (Admin-configured)
    pricing_rules = PricingRule.objects.filter(is_active=True)
    
    # Get gallery images for homepage banners (Admin-uploaded)
    banner_images = GalleryImage.objects.filter(
        category='banner',
        is_active=True
    ).order_by('-uploaded_at')[:5]
    
    context = {
        'user': user,
        'parking_lots': parking_lots,  # DYNAMIC ADMIN DATA
        'total_slots': total_slots,
        'available_slots': available_slots,
        'occupied_slots': occupied_slots,
        'user_vehicles': user_vehicles,
        'current_booking': current_booking,
        'parking_history': parking_history,
        'total_spent': total_spent,
        'notifications': notifications,
        'pricing_rules': pricing_rules,
        'banner_images': banner_images,
    }
    return render(request, 'parking/home.html', context)

# ==================== ADMIN DASHBOARD ====================
@login_required(login_url='user_login')
@staff_member_required
def admin_dashboard(request):
    """Enhanced Admin Dashboard with Charts and Analytics"""
    
    # ==================== BASIC STATISTICS ====================
    total_lots = ParkingLot.objects.count()
    active_lots = ParkingLot.objects.filter(is_active=True).count()
    total_floors = ParkingFloor.objects.count()
    total_blocks = Block.objects.count()
    total_slots = ParkingSlot.objects.count()
    available_slots = ParkingSlot.objects.filter(slot_status='available').count()
    occupied_slots = ParkingSlot.objects.filter(slot_status='occupied').count()
    maintenance_slots = ParkingSlot.objects.filter(slot_status='maintenance').count()
    
    # Vehicle Statistics
    total_vehicles = Vehicle.objects.count()
    
    # Booking Statistics
    total_bookings = ParkingSession.objects.count()
    active_bookings = ParkingSession.objects.filter(exit_time__isnull=True).count()
    completed_bookings = ParkingSession.objects.filter(exit_time__isnull=False).count()
    today_bookings = ParkingSession.objects.filter(
        entry_time__date=timezone.now().date()
    ).count()
    
    # Revenue Statistics
    total_revenue = ParkingSession.objects.filter(
        exit_time__isnull=False,
        fee__isnull=False
    ).aggregate(total=Sum('fee'))['total'] or 0
    
    today_revenue = ParkingSession.objects.filter(
        entry_time__date=timezone.now().date(),
        exit_time__isnull=False,
        fee__isnull=False
    ).aggregate(total=Sum('fee'))['total'] or 0
    
    month_revenue = ParkingSession.objects.filter(
        entry_time__month=timezone.now().month,
        entry_time__year=timezone.now().year,
        exit_time__isnull=False,
        fee__isnull=False
    ).aggregate(total=Sum('fee'))['total'] or 0
    
    # User Statistics
    total_users = User.objects.filter(is_staff=False).count()
    new_users_today = User.objects.filter(
        date_joined__date=timezone.now().date()
    ).count()
    
    # Monthly Pass Statistics
    active_passes = MonthlyPass.objects.filter(
        status='active',
        end_date__gte=timezone.now().date()
    ).count()
    pending_passes = MonthlyPass.objects.filter(status='pending').count()
    expired_passes = MonthlyPass.objects.filter(status='expired').count()
    
    # Support Tickets
    pending_tickets = SupportTicket.objects.filter(status='pending').count()
    total_tickets = SupportTicket.objects.count()
    
    # ==================== CHART DATA ====================
    
    # 1. Last 7 Days Revenue Chart
    revenue_chart_data = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        revenue = ParkingSession.objects.filter(
            entry_time__date=date,
            exit_time__isnull=False,
            fee__isnull=False
        ).aggregate(total=Sum('fee'))['total'] or 0
        revenue_chart_data.append({
            'date': date.strftime('%a'),
            'revenue': float(revenue)
        })
    
    # 2. Vehicle Type Distribution
    vehicle_types = Vehicle.objects.values('vehicle_type').annotate(
        count=Count('id')
    )
    vehicle_chart_data = [
        {'type': item['vehicle_type'], 'count': item['count']} 
        for item in vehicle_types
    ]
    
    # 3. Hourly Bookings Today
    hourly_bookings = []
    for hour in range(24):
        count = ParkingSession.objects.filter(
            entry_time__date=timezone.now().date(),
            entry_time__hour=hour
        ).count()
        hourly_bookings.append({
            'hour': f"{hour:02d}:00",
            'bookings': count
        })
    
    # 4. Monthly Revenue Trend (Last 6 Months)
    monthly_revenue = []
    for i in range(5, -1, -1):
        date = timezone.now().date() - timedelta(days=30*i)
        revenue = ParkingSession.objects.filter(
            entry_time__month=date.month,
            entry_time__year=date.year,
            exit_time__isnull=False,
            fee__isnull=False
        ).aggregate(total=Sum('fee'))['total'] or 0
        monthly_revenue.append({
            'month': date.strftime('%b %y'),
            'revenue': float(revenue)
        })
    
    # 5. Slot Status Distribution
    slot_status_data = [
        {'status': 'Available', 'count': available_slots, 'color': '#10b981'},
        {'status': 'Occupied', 'count': occupied_slots, 'color': '#ef4444'},
        {'status': 'Maintenance', 'count': maintenance_slots, 'color': '#f59e0b'}
    ]
    
    # 6. Peak Hours Analysis
    peak_hours = ParkingSession.objects.filter(
        entry_time__date__gte=timezone.now().date() - timedelta(days=7)
    ).values('entry_time__hour').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    peak_hours_data = [
        {'hour': f"{item['entry_time__hour']:02d}:00", 'bookings': item['count']}
        for item in peak_hours
    ]
    
    # Recent sessions
    recent_sessions = ParkingSession.objects.select_related(
        'vehicle', 'slot', 'slot__parking_lot'
    ).order_by('-entry_time')[:10]
    
    # Location-wise occupancy
    location_stats = []
    for lot in ParkingLot.objects.filter(is_active=True):
        total = lot.slots.count()
        occupied = lot.slots.filter(slot_status='occupied').count()
        available = lot.slots.filter(slot_status='available').count()
        occupancy_rate = (occupied / total * 100) if total > 0 else 0
        location_stats.append({
            'name': lot.name,
            'total': total,
            'occupied': occupied,
            'available': available,
            'occupancy_rate': round(occupancy_rate, 1)
        })
    
    context = {
        'title': 'Admin Dashboard',
        # Basic Stats
        'total_lots': total_lots,
        'active_lots': active_lots,
        'total_floors': total_floors,
        'total_blocks': total_blocks,
        'total_slots': total_slots,
        'available_slots': available_slots,
        'occupied_slots': occupied_slots,
        'maintenance_slots': maintenance_slots,
        'total_vehicles': total_vehicles,
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'completed_bookings': completed_bookings,
        'today_bookings': today_bookings,
        'total_revenue': int(total_revenue),
        'today_revenue': int(today_revenue),
        'month_revenue': int(month_revenue),
        'total_users': total_users,
        'new_users_today': new_users_today,
        'active_passes': active_passes,
        'pending_passes': pending_passes,
        'expired_passes': expired_passes,
        'pending_tickets': pending_tickets,
        'total_tickets': total_tickets,
        'recent_sessions': recent_sessions,
        'location_stats': location_stats,
        
        # Chart Data
        'revenue_chart_data': revenue_chart_data,
        'vehicle_chart_data': vehicle_chart_data,
        'hourly_bookings': hourly_bookings,
        'monthly_revenue': monthly_revenue,
        'slot_status_data': slot_status_data,
        'peak_hours_data': peak_hours_data,
    }
    return render(request, 'admin/dashboard.html', context)


@login_required(login_url='user_login')
@staff_member_required
def admin_profile(request):
    """Admin Profile with Activity Logs"""
    admin_user = request.user
    
    # Admin statistics
    approved_passes = MonthlyPass.objects.filter(approved_by=admin_user).count()
    resolved_tickets = SupportTicket.objects.filter(resolved_by=admin_user).count()
    
    # Recent activities
    recent_pass_approvals = MonthlyPass.objects.filter(
        approved_by=admin_user
    ).select_related('user', 'vehicle', 'pass_type').order_by('-approved_at')[:10]
    
    recent_ticket_resolutions = SupportTicket.objects.filter(
        resolved_by=admin_user
    ).order_by('-resolved_at')[:10]
    
    context = {
        'admin_user': admin_user,
        'approved_passes': approved_passes,
        'resolved_tickets': resolved_tickets,
        'recent_pass_approvals': recent_pass_approvals,
        'recent_ticket_resolutions': recent_ticket_resolutions,
    }
    return render(request, 'admin/profile.html', context)


# ==================== AI SLOT RECOMMENDATION ====================
def get_ai_recommended_slot(location_id, floor_id=None, block_id=None, vehicle_type='car'):
    """
    AI-based slot recommendation using rule-based logic
    Returns: (slot, score, reason)
    """
    from datetime import datetime
    
    # Get available slots
    available_slots = ParkingSlot.objects.filter(
        parking_lot_id=location_id,
        slot_status='available'
    ).select_related('parking_lot', 'floor', 'block')
    
    if floor_id:
        available_slots = available_slots.filter(floor_id=floor_id)
    if block_id:
        available_slots = available_slots.filter(block_id=block_id)
    
    if not available_slots.exists():
        return None, 0, "No slots available"
    
    # AI SCORING LOGIC
    scored_slots = []
    current_hour = datetime.now().hour
    is_peak_hour = 9 <= current_hour <= 11 or 17 <= current_hour <= 19
    
    for slot in available_slots:
        score = 100  # Base score
        reason_parts = []
        
        # 1. Ground floor preference (easier access)
        if slot.floor and slot.floor.floor_number == 0:
            score += 20
            reason_parts.append("Ground floor")
        
        # 2. Block A preference (usually near entrance)
        if slot.block and slot.block.block_code == 'A':
            score += 15
            reason_parts.append("Near entrance")
        
        # 3. Peak hour strategy - suggest slots near exit
        if is_peak_hour and slot.block and slot.block.block_code in ['A', 'B']:
            score += 25
            reason_parts.append("Quick exit during peak hours")
        
        # 4. Vehicle type matching
        if vehicle_type == 'car' and slot.slot_type in ['medium', 'large']:
            score += 10
            reason_parts.append("Size match")
        elif vehicle_type == 'bike' and slot.slot_type == 'small':
            score += 10
            reason_parts.append("Size match")
        
        # 5. Slot number preference (lower numbers = nearer)
        try:
            slot_num = int(''.join(filter(str.isdigit, slot.slot_number)))
            if slot_num <= 10:
                score += 10
                reason_parts.append("Prime location")
        except:
            pass
        
        # 6. Occupancy-based scoring (fill from one end)
        occupied_nearby = ParkingSlot.objects.filter(
            parking_lot=slot.parking_lot,
            floor=slot.floor,
            block=slot.block,
            slot_status='occupied'
        ).count()
        
        if occupied_nearby > 0:
            score += 5
            reason_parts.append("Near other vehicles")
        
        reason = ", ".join(reason_parts) if reason_parts else "Standard location"
        scored_slots.append((slot, score, reason))
    
    # Sort by score (highest first)
    scored_slots.sort(key=lambda x: x[1], reverse=True)
    
    # Return best slot
    best_slot, best_score, best_reason = scored_slots[0]
    return best_slot, best_score, best_reason

# ==================== PARKING OPERATIONS ====================
@login_required(login_url='user_login')
def park_vehicle(request):
    """Handle vehicle parking booking - WITH MONTHLY PASS & AI SUPPORT"""
    if request.method == 'POST':
        license_plate = request.POST.get('license_plate')
        vehicle_type = request.POST.get('vehicle_type')
        slot_id = request.POST.get('slot_id')
        duration_hours = request.POST.get('duration_hours', 1)
        ai_accepted = request.POST.get('ai_accepted') == 'true'  # ✅ NEW
        
        # Validation
        if not license_plate or not vehicle_type or not slot_id:
            messages.error(request, 'Please fill all required fields!')
            return redirect('park_vehicle')
        
        # Get or create vehicle
        owner_name = request.user.username
        vehicle, created = Vehicle.objects.get_or_create(
            license_plate=license_plate.upper(),
            defaults={'owner_name': owner_name, 'vehicle_type': vehicle_type}
        )
        
        # Check for Active Monthly Pass
        active_monthly_pass = MonthlyPass.objects.filter(
            user=request.user,
            vehicle=vehicle,
            status='active',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).first()
        
        # Check if vehicle is already parked
        existing_session = ParkingSession.objects.filter(
            vehicle=vehicle,
            exit_time__isnull=True
        ).first()
        
        if existing_session:
            messages.error(request, f'Vehicle {license_plate} is already parked!')
            return redirect('park_vehicle')
        
        # Get available slot
        try:
            slot = ParkingSlot.objects.get(
                id=slot_id,
                slot_status='available'
            )
        except ParkingSlot.DoesNotExist:
            messages.error(request, 'Selected slot is not available!')
            return redirect('park_vehicle')
        
        # Monthly Pass Holder - Skip Payment
        if active_monthly_pass:
            session = ParkingSession.objects.create(
                vehicle=vehicle,
                slot=slot,
                duration_hours=int(duration_hours),
                fee=0,
                payment_method='monthly_pass',
                payment_status='paid',
                ai_recommended=ai_accepted,  # ✅ NEW
            )
            
            slot.slot_status = 'occupied'
            slot.is_occupied = True
            slot.save()
            
            EntryExitLog.objects.create(
                session=session,
                log_type='entry',
                gate_number='G1',
                verified_by=request.user,
                notes=f'Monthly Pass: {active_monthly_pass.pass_number}' + (' | AI Recommended' if ai_accepted else '')  # ✅ NEW
            )
            
            messages.success(
                request, 
                f'✅ Entry Successful! Your Monthly Pass ({active_monthly_pass.pass_number}) has been validated. '
                f'Parking is FREE for you! Slot: {slot.slot_number}'
            )
            return redirect('booking_success', session_id=session.id)
        
        # Regular User - Proceed to Payment
        pricing_rule = PricingRule.objects.filter(
            vehicle_type=vehicle_type,
            is_active=True
        ).first()
        rate = pricing_rule.rate_per_hour if pricing_rule else (20 if vehicle_type == 'car' else 10)
        
        # Create parking session
        session = ParkingSession.objects.create(
            vehicle=vehicle,
            slot=slot,
            duration_hours=int(duration_hours),
            ai_recommended=ai_accepted,  # ✅ NEW
        )
        
        # Mark slot as occupied
        slot.slot_status = 'occupied'
        slot.is_occupied = True
        slot.save()
        
        # Create entry log
        EntryExitLog.objects.create(
            session=session,
            log_type='entry',
            gate_number='G1',
            verified_by=request.user,
            notes='AI Recommended' if ai_accepted else 'Manual Selection'  # ✅ NEW
        )
        
        # Store booking details in session
        request.session['booking_id'] = session.id
        request.session['booking_duration'] = int(duration_hours)
        amount = rate * int(duration_hours)
        request.session['booking_amount'] = float(amount)
        
        return redirect('payment_page')
    
    # ==================== GET REQUEST - SHOW PARKING FORM WITH AI ====================
    parking_lots = ParkingLot.objects.filter(is_active=True).prefetch_related('floors', 'landmarks')
    location_filter = request.GET.get('location', '')
    
    available_slots = ParkingSlot.objects.filter(
        slot_status='available',
        parking_lot__is_active=True
    ).select_related('parking_lot', 'floor', 'block', 'zone')
    
    if location_filter:
        available_slots = available_slots.filter(
            parking_lot__name__icontains=location_filter
        )
    
    available_slots = available_slots.order_by('parking_lot', 'floor', 'block', 'slot_number')
    
    # Get user vehicles
    user_vehicles = Vehicle.objects.filter(owner_name=request.user.username)
    
    # Get Active Monthly Passes
    active_passes = MonthlyPass.objects.filter(
        user=request.user,
        status='active',
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).select_related('vehicle', 'pass_type')
    
    # Get pricing rules
    pricing_rules = PricingRule.objects.filter(is_active=True)
    
    # ✅ NEW: AI RECOMMENDATION
    ai_recommended_slot = None
    ai_score = 0
    ai_reason = ""
    
    if parking_lots.exists():
        first_lot = parking_lots.first()
        ai_recommended_slot, ai_score, ai_reason = get_ai_recommended_slot(
            location_id=first_lot.id,
            vehicle_type='car'  # Default, will update via AJAX
        )
    
    context = {
        'parking_lots': parking_lots,
        'available_slots': available_slots,
        'user_vehicles': user_vehicles,
        'pricing_rules': pricing_rules,
        'location_filter': location_filter,
        'active_passes': active_passes,
        'ai_recommended_slot': ai_recommended_slot,  # ✅ NEW
        'ai_score': ai_score,  # ✅ NEW
        'ai_reason': ai_reason,  # ✅ NEW
    }
    return render(request, 'parking/park_vehicle.html', context)

# ==================== AI SLOT RECOMMENDATION API ====================
@require_http_methods(["GET"])
def api_ai_recommend_slot(request):
    """API endpoint to get AI-recommended slot"""
    try:
        location_id = request.GET.get('location')
        floor_id = request.GET.get('floor')
        block_id = request.GET.get('block')
        vehicle_type = request.GET.get('vehicle_type', 'car')
        
        if not location_id:
            return JsonResponse({'error': 'Location required'}, status=400)
        
        slot, score, reason = get_ai_recommended_slot(
            location_id=location_id,
            floor_id=floor_id,
            block_id=block_id,
            vehicle_type=vehicle_type
        )
        
        if not slot:
            return JsonResponse({
                'success': False,
                'message': 'No available slots'
            })
        
        return JsonResponse({
            'success': True,
            'slot': {
                'id': slot.id,
                'slot_number': slot.slot_number,
                'floor': slot.floor.get_floor_name_display() if slot.floor else 'N/A',
                'block': f"Block {slot.block.block_name}" if slot.block else 'N/A',
                'location': slot.parking_lot.name
            },
            'score': float(score),
            'reason': reason
        })
        
    except Exception as e:
        logger.error(f"AI recommendation error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# ==================== MONTHLY PASS ====================
@login_required
def monthly_pass(request):
    """Monthly Pass Page - Uses admin-configured pass types"""
    # Get all active pass types (admin-configured)
    pass_types = PassType.objects.filter(is_active=True).order_by('vehicle_type', 'duration_days')
    
    # Get user's vehicles
    user_vehicles = Vehicle.objects.filter(owner_name=request.user.username)
    
    # Get all parking locations (admin-managed)
    locations = ParkingLot.objects.filter(is_active=True)
    
    # Get user's passes with admin approval status
    user_passes = MonthlyPass.objects.filter(
        user=request.user
    ).select_related('pass_type', 'vehicle', 'approved_by').prefetch_related('parking_lots').order_by('-created_at')
    
    # Separate active and expired passes
    active_passes = user_passes.filter(
        status='active',
        end_date__gte=timezone.now().date()
    )
    pending_passes = user_passes.filter(status='pending')
    expired_passes = user_passes.filter(status='expired')
    
    context = {
        'pass_types': pass_types,
        'user_vehicles': user_vehicles,
        'locations': locations,
        'user_passes': user_passes,
        'active_passes': active_passes,
        'pending_passes': pending_passes,
        'expired_passes': expired_passes,
    }
    return render(request, 'parking/monthly_pass.html', context)

@login_required
def purchase_monthly_pass(request):
    """Purchase Monthly Pass - Requires admin approval"""
    if request.method == 'POST':
        pass_type_id = request.POST.get('pass_type')
        vehicle_id = request.POST.get('vehicle')
        location_ids = request.POST.getlist('locations')
        payment_method = request.POST.get('payment_method')
        auto_renew = request.POST.get('auto_renew') == 'on'
        contact_number = request.POST.get('contact_number', '')
        
        try:
            pass_type = PassType.objects.get(id=pass_type_id, is_active=True)
            vehicle = Vehicle.objects.get(id=vehicle_id, owner_name=request.user.username)
            
            # Calculate dates
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=pass_type.duration_days)
            
            # Create pass (pending admin approval)
            monthly_pass = MonthlyPass.objects.create(
                user=request.user,
                vehicle=vehicle,
                pass_type=pass_type,
                start_date=start_date,
                end_date=end_date,
                amount=pass_type.price,
                payment_method=payment_method,
                auto_renew=auto_renew,
                contact_number=contact_number,
                status='pending',
                payment_status='pending'
            )
            
            # Add selected locations
            if location_ids:
                for loc_id in location_ids:
                    try:
                        location = ParkingLot.objects.get(id=loc_id)
                        monthly_pass.parking_lots.add(location)
                    except ParkingLot.DoesNotExist:
                        pass
            
            messages.success(request, '✅ Monthly Pass application submitted! Awaiting admin approval.')
            return redirect('monthly_pass')
            
        except PassType.DoesNotExist:
            messages.error(request, '❌ Invalid pass type selected.')
        except Vehicle.DoesNotExist:
            messages.error(request, '❌ Invalid vehicle selected.')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    # 🔥 FIX: Redirect to monthly_pass page for GET requests
    return redirect('monthly_pass')

## ==================== CONTACT & SUPPORT ====================
def contact_view(request):
    """Contact page with support ticket creation and email functionality"""
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        mobile_number = request.POST.get('mobile_number', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        try:
            # Create support ticket
            ticket = SupportTicket.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                email=email,
                mobile_number=mobile_number,
                subject=subject,
                message=message,
                status='pending'
            )
            
            # Send confirmation email to customer
            customer_subject = f'Support Ticket Created - {ticket.get_ticket_id()}'
            customer_message = f"""
Dear {full_name},

Thank you for contacting Parkease Support.

Your support ticket has been created successfully!

Ticket Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: {ticket.get_ticket_id()}
Subject: {ticket.get_subject_display()}
Status: Pending Review
Created: {ticket.created_at.strftime('%d %b %Y, %I:%M %p')}

Your Message:
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Our support team will review your ticket and respond within 24 hours.

You can check your ticket status anytime by visiting:
Contact Page → Check Ticket Status → Enter Ticket ID: {ticket.get_ticket_id()}

Thank you for your patience.

Best regards,
Parkease Support Team
Contact: +91 9359845632
Email: ✉️ ajitilage@gmail.com
            """
            
            send_mail(
                subject=customer_subject,
                message=customer_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            # Send notification email to admin
            admin_subject = f'🎫 New Support Ticket - {ticket.get_ticket_id()}'
            admin_message = f"""
New Support Ticket Received!

Ticket ID: {ticket.get_ticket_id()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Customer Details:
• Name: {full_name}
• Email: {email}
• Mobile: {mobile_number or 'Not provided'}

Subject: {ticket.get_subject_display()}
Status: Pending

Message:
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Created: {ticket.created_at.strftime('%d %b %Y, %I:%M %p')}

Please log in to the admin panel to review and respond:
http://127.0.0.1:8000/admin/parking/supportticket/{ticket.id}/change/

Parkease - Admin Notification
            """
            
            send_mail(
                subject=admin_subject,
                message=admin_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['✉️ ajitilage@gmail.com'],
                fail_silently=False,
            )
            
            messages.success(
                request, 
                f'✅ Your ticket ({ticket.get_ticket_id()}) has been submitted successfully! '
                f'Check your email ({email}) for confirmation.'
            )
            logger.info(f"Support ticket {ticket.get_ticket_id()} created and emails sent successfully")
            
        except Exception as e:
            messages.error(request, f'❌ Error submitting ticket: {str(e)}')
            logger.error(f"Error creating support ticket: {str(e)}")
        
        return redirect('contact')
    
    # GET request - show contact form
    try:
        system_settings = SystemSettings.objects.first()
    except SystemSettings.DoesNotExist:
        system_settings = None
    
    context = {
        'user': request.user,
        'system_settings': system_settings,
    }
    return render(request, 'parking/contact.html', context)


# ==================== TICKET STATUS CHECKER (API) ====================
@require_http_methods(["GET"])
def check_ticket_status(request, ticket_id):
    """API endpoint to check support ticket status"""
    try:
        # Extract numeric ID from ticket_id (e.g., "TKT000123" -> 123)
        numeric_id = int(ticket_id.replace('TKT', '').lstrip('0') or '0')
        
        # Get ticket from database
        ticket = SupportTicket.objects.get(id=numeric_id)
        
        # Calculate time elapsed
        time_elapsed = timezone.now() - ticket.created_at
        days = time_elapsed.days
        hours = time_elapsed.seconds // 3600
        
        if days > 0:
            time_str = f"{days} day{'s' if days > 1 else ''} ago"
        elif hours > 0:
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            minutes = time_elapsed.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
        # Status colors and icons
        status_info = {
            'pending': {'color': '#ff9800', 'icon': '⏳', 'text': 'Pending Review'},
            'review': {'color': '#2196f3', 'icon': '👀', 'text': 'In Review'},
            'resolved': {'color': '#4caf50', 'icon': '✅', 'text': 'Resolved'},
            'rejected': {'color': '#f44336', 'icon': '❌', 'text': 'Rejected'},
        }
        
        status = status_info.get(ticket.status, status_info['pending'])
        
        # Prepare response data
        response_data = {
            'success': True,
            'ticket': {
                'id': ticket.get_ticket_id(),
                'full_name': ticket.full_name,
                'email': ticket.email,
                'mobile': ticket.mobile_number or 'Not provided',
                'subject': ticket.get_subject_display(),
                'message': ticket.message,
                'status': ticket.status,
                'status_display': status['text'],
                'status_color': status['color'],
                'status_icon': status['icon'],
                'admin_response': ticket.admin_response or 'No response yet',
                'created_at': ticket.created_at.strftime('%d %b %Y, %I:%M %p'),
                'updated_at': ticket.updated_at.strftime('%d %b %Y, %I:%M %p'),
                'time_elapsed': time_str,
                'resolved_by': ticket.resolved_by.username if ticket.resolved_by else None,
                'resolved_at': ticket.resolved_at.strftime('%d %b %Y, %I:%M %p') if ticket.resolved_at else None,
            }
        }
        
        return JsonResponse(response_data)
        
    except SupportTicket.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Ticket not found',
            'message': f'No ticket found with ID: {ticket_id}'
        }, status=404)
        
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid ticket ID',
            'message': 'Please enter a valid ticket ID (e.g., TKT000123)'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Error checking ticket status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Server error',
            'message': 'An error occurred while checking ticket status'
        }, status=500)
# ==================== PAYMENT & BOOKING ====================
@login_required(login_url='user_login')
def payment_page(request):
    """Payment page"""
    booking_id = request.session.get('booking_id')
    if not booking_id:
        messages.error(request, 'No booking found!')
        return redirect('park_vehicle')
    
    try:
        session = ParkingSession.objects.select_related(
            'vehicle', 'slot', 'slot__parking_lot'
        ).get(id=booking_id)
    except ParkingSession.DoesNotExist:
        messages.error(request, 'Invalid booking!')
        return redirect('park_vehicle')
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        # Process payment
        amount = request.session.get('booking_amount', 0)
        session.fee = amount
        session.payment_method = payment_method
        session.payment_status = 'paid'
        session.save()
        
        # Store payment method
        request.session['payment_method'] = payment_method
        
        # Clear booking session data
        request.session.pop('booking_id', None)
        request.session.pop('booking_amount', None)
        request.session.pop('booking_duration', None)
        
        messages.success(request, '✅ Payment successful!')
        return redirect('booking_success', session_id=session.id)
    
    # Calculate booking details
    rate = 20 if session.vehicle.vehicle_type == 'car' else 10
    duration = request.session.get('booking_duration', 1)
    total_amount = rate * duration
    
    booking_data = {
        'id': session.id,
        'vehicle_number': session.vehicle.license_plate,
        'slot_number': session.slot.slot_number,
        'location': session.slot.parking_lot.name,
        'duration': duration,
        'rate': rate,
        'total_amount': total_amount,
    }
    
    context = {'booking': booking_data}
    return render(request, 'parking/payment.html', context)

@login_required(login_url='user_login')
def booking_success(request, session_id):
    """Booking success page"""
    try:
        session = ParkingSession.objects.select_related(
            'vehicle', 'slot', 'slot__parking_lot'
        ).get(
            id=session_id,
            vehicle__owner_name=request.user.username
        )
    except ParkingSession.DoesNotExist:
        messages.error(request, 'Booking not found!')
        return redirect('home')
    
    payment_method = request.session.get('payment_method', session.payment_method or 'cash')
    request.session.pop('payment_method', None)
    
    context = {
        'booking': session,
        'exit_success': False,
        'payment_method': payment_method,
    }
    return render(request, 'parking/booking_success.html', context)

# ==================== EXIT PARKING ====================
@login_required(login_url='user_login')
def exit_parking(request, session_id):
    """Exit parking page - WITH MONTHLY PASS SUPPORT"""
    if session_id == 0:
        return render(request, 'parking/exit_parking.html', {'booking': None})
    
    session = get_object_or_404(
        ParkingSession.objects.select_related('vehicle', 'slot', 'slot__parking_lot'),
        id=session_id,
        exit_time__isnull=True
    )
    
    # ✅ NEW: Check if user has Monthly Pass
    has_monthly_pass = session.payment_method == 'monthly_pass'
    
    # Calculate duration and charges
    now = timezone.now()
    duration = now - session.entry_time
    total_hours = duration.total_seconds() / 3600
    booked_hours = getattr(session, 'duration_hours', 1) or 1
    is_overtime = total_hours > booked_hours
    extra_hours = max(0, int(total_hours) - booked_hours)
    
    # ✅ NEW: Monthly Pass Holder - NO CHARGES
    if has_monthly_pass:
        context = {
            'booking': session,
            'has_monthly_pass': True,
            'is_overtime': False,
            'total_duration': f"{int(total_hours)}h {int((duration.total_seconds() % 3600) / 60)}m",
            'extra_hours': 0,
            'hourly_rate': 0,
            'base_amount': 0,
            'extra_amount': 0,
            'gst_amount': 0,
            'extra_total': 0,
        }
        return render(request, 'parking/exit_parking.html', context)
    
    # ✅ Regular User - Calculate Charges
    pricing_rule = PricingRule.objects.filter(
        vehicle_type=session.vehicle.vehicle_type,
        is_active=True
    ).first()
    
    hourly_rate = float(pricing_rule.rate_per_hour) if pricing_rule else 20.0
    base_amount = float(booked_hours) * hourly_rate
    extra_amount = float(extra_hours) * hourly_rate if is_overtime else 0.0
    subtotal = base_amount + extra_amount
    gst_amount = round(subtotal * 0.18, 2)
    extra_total = round(extra_amount + (extra_amount * 0.18), 2)
    
    context = {
        'booking': session,
        'has_monthly_pass': False,
        'is_overtime': is_overtime,
        'total_duration': f"{int(total_hours)}h {int((duration.total_seconds() % 3600) / 60)}m",
        'extra_hours': extra_hours,
        'hourly_rate': hourly_rate,
        'base_amount': round(base_amount, 2),
        'extra_amount': round(extra_amount, 2),
        'gst_amount': gst_amount,
        'extra_total': extra_total,
    }
    return render(request, 'parking/exit_parking.html', context)

@login_required(login_url='user_login')
def verify_exit(request):
    """Verify exit booking"""
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip().upper()
        
        if not booking_id or not vehicle_number:
            messages.error(request, '⚠️ Please provide both Booking ID and Vehicle Number')
            return redirect('exit_parking', session_id=0)
        
        booking_id_clean = booking_id.replace('PK-', '').replace('#', '')
        
        try:
            session = ParkingSession.objects.select_related('vehicle').get(
                id=int(booking_id_clean),
                vehicle__license_plate=vehicle_number,
                exit_time__isnull=True
            )
            return redirect('exit_parking', session_id=session.id)
            
        except ParkingSession.DoesNotExist:
            messages.error(request, '❌ Booking not found or already exited!')
        except ValueError:
            messages.error(request, '❌ Invalid Booking ID format!')
    
    return redirect('exit_parking', session_id=0)

@login_required(login_url='user_login')
def process_exit(request, session_id):
    """Process exit and payment - WITH MONTHLY PASS SUPPORT"""
    if request.method != 'POST':
        return redirect('home')

    try:
        session = ParkingSession.objects.select_related(
            'vehicle', 'slot', 'slot__parking_lot'
        ).get(id=session_id, exit_time__isnull=True)
    except ParkingSession.DoesNotExist:
        messages.error(request, '❌ This parking session is already closed or invalid.')
        return redirect('home')

    # ✅ NEW: Check Monthly Pass
    has_monthly_pass = session.payment_method == 'monthly_pass'

    # -------- EXIT PROCESS --------
    session.exit_time = timezone.now()

    if has_monthly_pass:
        # ✅ Monthly Pass Holder - NO FEE
        session.fee = 0
        session.payment_status = 'paid'
    else:
        # ✅ Regular User - Calculate Fee
        extra_amount = float(request.POST.get('extra_amount', 0))
        duration = (session.exit_time - session.entry_time).total_seconds() / 3600
        
        pricing_rule = PricingRule.objects.filter(
            vehicle_type=session.vehicle.vehicle_type,
            is_active=True
        ).first()
        
        rate = float(pricing_rule.rate_per_hour) if pricing_rule else 20.0
        total_fee = round((duration * rate) + extra_amount, 2)
        
        session.fee = total_fee
        session.payment_status = 'paid'

    session.save()

    # -------- FREE SLOT --------
    slot = session.slot
    slot.slot_status = 'available'
    slot.is_occupied = False
    slot.save()

    # -------- EXIT LOG --------
    EntryExitLog.objects.create(
        session=session,
        log_type='exit',
        gate_number='G1',
        verified_by=request.user,
        notes='Monthly Pass Exit' if has_monthly_pass else 'Regular Exit'
    )

    if has_monthly_pass:
        messages.success(request, f'✅ Exit successful! Monthly Pass holder - No charges applied.')
    else:
        messages.success(request, f'✅ Exit successful! Total fee: ₹{session.fee}')

    return redirect('exit_confirmed', session_id=session.id)
# ==================== ENHANCED USER PROFILE VIEW ====================
@login_required(login_url='user_login')
def user_profile(request):
    """User profile with vehicle management and booking history - Fully admin integrated"""
    user = request.user
    
    # ==================== AJAX HANDLERS ====================
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        action = request.POST.get('action')
        
        # -------- EDIT PROFILE --------
        if action == 'edit_profile':
            try:
                user.first_name = request.POST.get('first_name', '').strip()
                user.last_name = request.POST.get('last_name', '').strip()
                email = request.POST.get('email', '').strip()
                
                # Check if email is already taken by another user
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Email already in use by another account'
                    })
                
                user.email = email
                user.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Profile updated successfully!'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error updating profile: {str(e)}'
                })
        
        # -------- ADD VEHICLE --------
        elif action == 'add_vehicle':
            try:
                license_plate = request.POST.get('license_plate', '').strip().upper()
                vehicle_type = request.POST.get('vehicle_type', '').strip()
                
                # Validate inputs
                if not license_plate or not vehicle_type:
                    return JsonResponse({
                        'success': False,
                        'message': 'Please provide both vehicle number and type'
                    })
                
                # Check if vehicle already exists (globally)
                existing_vehicle = Vehicle.objects.filter(license_plate=license_plate).first()
                
                if existing_vehicle:
                    # Vehicle exists - check if it belongs to current user
                    if existing_vehicle.owner_name == user.username:
                        return JsonResponse({
                            'success': False,
                            'message': f'Vehicle {license_plate} is already in your garage'
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': f'Vehicle {license_plate} is already registered to another user'
                        })
                
                # Create new vehicle
                vehicle = Vehicle.objects.create(
                    license_plate=license_plate,
                    owner_name=user.username,
                    vehicle_type=vehicle_type
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Vehicle {license_plate} added successfully!',
                    'vehicle': {
                        'id': vehicle.id,
                        'license_plate': vehicle.license_plate,
                        'vehicle_type': vehicle.vehicle_type,
                        'vehicle_type_display': vehicle.get_vehicle_type_display()
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error adding vehicle: {str(e)}'
                })
        
        # -------- EDIT VEHICLE --------
        elif action == 'edit_vehicle':
            try:
                vehicle_id = request.POST.get('vehicle_id')
                license_plate = request.POST.get('license_plate', '').strip().upper()
                vehicle_type = request.POST.get('vehicle_type', '').strip()
                
                # Get vehicle and verify ownership
                try:
                    vehicle = Vehicle.objects.get(id=vehicle_id, owner_name=user.username)
                except Vehicle.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': 'Vehicle not found or you do not have permission to edit it'
                    })
                
                # Check if new license plate is taken by another vehicle
                if license_plate != vehicle.license_plate:
                    if Vehicle.objects.filter(license_plate=license_plate).exclude(id=vehicle.id).exists():
                        return JsonResponse({
                            'success': False,
                            'message': f'License plate {license_plate} is already registered'
                        })
                
                # Check if vehicle has active parking session
                active_session = ParkingSession.objects.filter(
                    vehicle=vehicle,
                    exit_time__isnull=True
                ).exists()
                
                if active_session and license_plate != vehicle.license_plate:
                    return JsonResponse({
                        'success': False,
                        'message': 'Cannot change license plate while vehicle is parked'
                    })
                
                # Update vehicle
                vehicle.license_plate = license_plate
                vehicle.vehicle_type = vehicle_type
                vehicle.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Vehicle updated successfully!',
                    'vehicle': {
                        'id': vehicle.id,
                        'license_plate': vehicle.license_plate,
                        'vehicle_type': vehicle.vehicle_type,
                        'vehicle_type_display': vehicle.get_vehicle_type_display()
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error updating vehicle: {str(e)}'
                })
        
        # -------- DELETE VEHICLE --------
        elif action == 'delete_vehicle':
            try:
                vehicle_id = request.POST.get('vehicle_id')
                
                # Get vehicle and verify ownership
                try:
                    vehicle = Vehicle.objects.get(id=vehicle_id, owner_name=user.username)
                except Vehicle.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': 'Vehicle not found or you do not have permission to delete it'
                    })
                
                # Check if vehicle has active parking session
                active_session = ParkingSession.objects.filter(
                    vehicle=vehicle,
                    exit_time__isnull=True
                ).exists()
                
                if active_session:
                    return JsonResponse({
                        'success': False,
                        'message': 'Cannot delete vehicle while it is parked. Please exit parking first.'
                    })
                
                # Check if vehicle has any booking history
                has_history = ParkingSession.objects.filter(vehicle=vehicle).exists()
                
                license_plate = vehicle.license_plate
                vehicle.delete()
                
                message = f'Vehicle {license_plate} deleted successfully!'
                if has_history:
                    message += ' (Booking history preserved in system records)'
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error deleting vehicle: {str(e)}'
                })
        
        # Invalid action
        return JsonResponse({
            'success': False,
            'message': 'Invalid action'
        })
    
    # ==================== GET REQUEST - DISPLAY PROFILE ====================
    
    # Get all parking sessions (admin-tracked data)
    sessions = ParkingSession.objects.filter(
        vehicle__owner_name=user.username
    ).select_related('vehicle', 'slot', 'slot__parking_lot', 'slot__floor', 'slot__block').order_by('-entry_time')
    
    # Get active session
    active_session = sessions.filter(exit_time__isnull=True).first()
    
    # Get user vehicles (admin-managed through Vehicle model)
    vehicles = Vehicle.objects.filter(owner_name=user.username).order_by('-created_at')
    
    # Get monthly passes (admin-approved)
    monthly_passes = MonthlyPass.objects.filter(
        user=user
    ).select_related('pass_type', 'vehicle', 'approved_by').prefetch_related('parking_lots').order_by('-created_at')
    
    # Calculate comprehensive statistics
    total_bookings = sessions.count()
    active_bookings = sessions.filter(exit_time__isnull=True).count()
    completed_sessions = sessions.filter(exit_time__isnull=False)
    total_spent = completed_sessions.aggregate(total=Sum('fee'))['total'] or 0
    
    # Calculate total parking hours
    total_hours = 0
    for session in completed_sessions:
        if session.exit_time and session.entry_time:
            duration = (session.exit_time - session.entry_time).total_seconds() / 3600
            total_hours += duration
    
    # Prepare booking history data
    bookings = []
    for session in sessions[:20]:  # Show last 20 bookings
        # Calculate duration
        if session.exit_time:
            duration_seconds = (session.exit_time - session.entry_time).total_seconds()
            duration_hours = round(duration_seconds / 3600, 2)
            status = 'Completed'
        else:
            duration_hours = 0
            status = 'Active'
        
        # Build location path
        location_path = session.slot.parking_lot.name
        if session.slot.floor:
            location_path += f" - {session.slot.floor.get_floor_name_display()}"
        if session.slot.block:
            location_path += f" - Block {session.slot.block.block_name}"
        
        booking = {
            'booking_id': f"PK-{session.id:05d}",
            'vehicle_number': session.vehicle.license_plate,
            'vehicle_type': session.vehicle.get_vehicle_type_display(),
            'slot_number': session.slot.slot_number,
            'parking_lot': location_path,
            'entry_time': session.entry_time,
            'exit_time': session.exit_time,
            'duration': duration_hours,
            'total_amount': session.fee if session.fee else 0,
            'status': status,
            'payment_method': session.get_payment_method_display() if session.payment_method else 'N/A',
        }
        bookings.append(booking)
    
    # Active booking data with full details
    active_booking = None
    if active_session:
        location_path = active_session.slot.parking_lot.name
        if active_session.slot.floor:
            location_path += f" - {active_session.slot.floor.get_floor_name_display()}"
        if active_session.slot.block:
            location_path += f" - Block {active_session.slot.block.block_name}"
        
        active_booking = {
            'id': active_session.id,
            'booking_id': f"PK-{active_session.id:05d}",
            'vehicle_number': active_session.vehicle.license_plate,
            'vehicle_type': active_session.vehicle.get_vehicle_type_display(),
            'slot_number': active_session.slot.slot_number,
            'parking_lot': location_path,
            'entry_time': active_session.entry_time,
            'duration': getattr(active_session, 'duration_hours', 1),
            'total_amount': active_session.fee if active_session.fee else 0,
        }
    
    # Get active and expired monthly passes
    active_passes = monthly_passes.filter(
        status='active',
        end_date__gte=timezone.now().date()
    )
    pending_passes = monthly_passes.filter(status='pending')
    expired_passes = monthly_passes.filter(status='expired')
    
    context = {
        'user': user,
        'bookings': bookings,
        'active_booking': active_booking,
        'vehicles': vehicles,
        'monthly_passes': monthly_passes,
        'active_passes': active_passes,
        'pending_passes': pending_passes,
        'expired_passes': expired_passes,
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'total_spent': int(total_spent) if total_spent else 0,
        'total_hours': int(total_hours) if total_hours else 0,
    }
    return render(request, 'parking/profile.html', context)

# ==================== API ENDPOINTS ====================
@require_http_methods(["GET"])
def api_get_floors(request, location_id):
    """API endpoint to get floors for a parking location"""
    try:
        floors = ParkingFloor.objects.filter(
            parking_lot_id=location_id,
            is_operational=True
        ).order_by('floor_number').values('id', 'floor_name', 'floor_number')
        
        floor_list = [{
            'id': floor['id'],
            'name': floor['floor_name'],
            'floor_number': floor['floor_number']
        } for floor in floors]
        
        return JsonResponse(floor_list, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def api_get_blocks(request, floor_id):
    """API endpoint to get blocks for a floor"""
    try:
        blocks = Block.objects.filter(
            floor_id=floor_id,
            is_active=True
        ).order_by('order', 'block_code').values('id', 'block_name', 'block_code')
        
        block_list = [{
            'id': block['id'],
            'name': f"Block {block['block_name']}",
            'code': block['block_code']
        } for block in blocks]
        
        return JsonResponse(block_list, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def api_get_slots(request):
    """API endpoint to get slots filtered by location, floor, and block"""
    try:
        location_id = request.GET.get('location')
        floor_id = request.GET.get('floor')
        block_id = request.GET.get('block')
        
        slots = ParkingSlot.objects.filter(
            parking_lot_id=location_id
        )
        
        if floor_id:
            slots = slots.filter(floor_id=floor_id)
        if block_id:
            slots = slots.filter(block_id=block_id)
        
        slots = slots.order_by('slot_number').values(
            'id', 'slot_number', 'slot_status', 'slot_type'        )
        
        slot_list = [{
            'id': slot['id'],
            'slot_number': slot['slot_number'],
            'status': slot['slot_status'],
            'type': slot['slot_type']
        } for slot in slots]
        
        return JsonResponse(slot_list, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
 # ==================== NOTIFICATION VIEWS ====================
@login_required(login_url='user_login')
def notifications(request):
    """Display user notifications with filtering"""
    user = request.user
    filter_type = request.GET.get('type', '')
    
    # Get all notifications for user (sent to all or targeted)
    all_notifications = Notification.objects.filter(
        Q(send_to_all=True) | Q(target_users=user),
        is_active=True
    ).distinct()
    
    # Create UserNotification instances if they don't exist
    for notification in all_notifications:
        UserNotification.objects.get_or_create(
            user=user,
            notification=notification
        )
    
    # Get user's notification instances
    user_notifications = UserNotification.objects.filter(
        user=user
    ).select_related('notification')
    
    # Apply filter if specified
    if filter_type:
        user_notifications = user_notifications.filter(
            notification__notification_type=filter_type
        )
    
    user_notifications = user_notifications.order_by('-created_at')
    
    # Calculate statistics
    total_notifications = UserNotification.objects.filter(user=user).count()
    unread_count = UserNotification.objects.filter(user=user, is_read=False).count()
    read_count = UserNotification.objects.filter(user=user, is_read=True).count()
    today_count = UserNotification.objects.filter(
        user=user,
        created_at__date=timezone.now().date()
    ).count()
    
    # Count by type
    announcement_count = UserNotification.objects.filter(
        user=user,
        notification__notification_type='announcement'
    ).count()
    maintenance_count = UserNotification.objects.filter(
        user=user,
        notification__notification_type='maintenance'
    ).count()
    payment_count = UserNotification.objects.filter(
        user=user,
        notification__notification_type='payment'
    ).count()
    pass_expiry_count = UserNotification.objects.filter(
        user=user,
        notification__notification_type='pass_expiry'
    ).count()
    promotion_count = UserNotification.objects.filter(
        user=user,
        notification__notification_type='promotion'
    ).count()
    
    context = {
        'notifications': user_notifications,
        'filter_type': filter_type,
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'read_count': read_count,
        'today_count': today_count,
        'announcement_count': announcement_count,
        'maintenance_count': maintenance_count,
        'payment_count': payment_count,
        'pass_expiry_count': pass_expiry_count,
        'promotion_count': promotion_count,
    }
    return render(request, 'parking/notifications.html', context)


@login_required(login_url='user_login')
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    if request.method == 'POST':
        try:
            user_notification = UserNotification.objects.get(
                id=notification_id,
                user=request.user
            )
            user_notification.is_read = True
            user_notification.read_at = timezone.now()
            user_notification.save()
            messages.success(request, '✅ Notification marked as read!')
        except UserNotification.DoesNotExist:
            messages.error(request, '❌ Notification not found!')
    
    return redirect('notifications')


@login_required(login_url='user_login')
def mark_all_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        updated = UserNotification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        messages.success(request, f'✅ {updated} notifications marked as read!')
    
    return redirect('notifications')


@login_required(login_url='user_login')
def delete_notification(request, notification_id):
    """Delete a notification"""
    if request.method == 'POST':
        try:
            user_notification = UserNotification.objects.get(
                id=notification_id,
                user=request.user
            )
            user_notification.delete()
            messages.success(request, '🗑️ Notification deleted!')
        except UserNotification.DoesNotExist:
            messages.error(request, '❌ Notification not found!')
    
    return redirect('notifications')

def exit_confirmed(request, session_id):
    """Show exit confirmation page"""

    try:
        session = ParkingSession.objects.select_related(
            'vehicle', 'slot', 'slot__parking_lot'
        ).get(id=session_id)
    except ParkingSession.DoesNotExist:
        messages.error(request, '❌ Booking not found!')
        return redirect('home')

    # -------- DURATION CALCULATION --------
    if not session.exit_time:
        messages.error(request, '❌ Exit not completed for this booking.')
        return redirect('home')

    total_seconds = (session.exit_time - session.entry_time).total_seconds()
    total_hours = total_seconds / 3600

    hours = int(total_hours)
    minutes = int((total_hours - hours) * 60)
    total_duration = f"{hours}h {minutes}m"

    # -------- PRICING --------
    pricing_rule = PricingRule.objects.filter(
        vehicle_type=session.vehicle.vehicle_type,
        is_active=True
    ).first()

    hourly_rate = float(pricing_rule.rate_per_hour) if pricing_rule else 20.0

    # -------- BOOKED HOURS --------
    booked_hours = session.duration_hours or 1
    base_amount = booked_hours * hourly_rate

    # -------- OVERTIME --------
    actual_hours = int(total_hours) + (1 if minutes > 0 else 0)
    extra_hours = max(0, actual_hours - booked_hours)
    extra_amount = extra_hours * hourly_rate

    # -------- FINAL BILL --------
    subtotal = base_amount + extra_amount
    gst_amount = round(subtotal * 0.18, 2)
    total_paid = round(subtotal + gst_amount, 2)

    # -------- CONTEXT --------
    context = {
        'booking': session,
        'total_duration': total_duration,
        'base_amount': base_amount,
        'extra_amount': extra_amount,
        'gst_amount': gst_amount,
        'total_paid': total_paid,
        'receipt_id': f"RC-{session.id:05d}",
        'hourly_rate': hourly_rate,
        'extra_hours': extra_hours,
    }

    return render(request, 'parking/exit_confirmed.html', context)


# ==================== VEHICLE STATUS CHECKER API ====================
@require_http_methods(["GET"])
def check_vehicle_status(request, vehicle_number):
    """
    API endpoint to check if a vehicle is currently parked
    URL: /api/vehicle-status/<vehicle_number>/
    """
    try:
        # Normalize vehicle number (uppercase, remove spaces)
        vehicle_number = vehicle_number.upper().strip().replace(" ", "")
        
        # Check if vehicle exists
        try:
            vehicle = Vehicle.objects.get(license_plate=vehicle_number)
        except Vehicle.DoesNotExist:
            return JsonResponse({
                'success': True,
                'vehicle': {
                    'status': 'not_found',
                    'vehicle_number': vehicle_number
                }
            })
        
        # Check for active parking session
        active_session = ParkingSession.objects.filter(
            vehicle=vehicle,
            exit_time__isnull=True
        ).select_related('slot', 'slot__parking_lot', 'slot__floor', 'slot__block').first()
        
        if active_session:
            # Vehicle is currently parked
            slot_info = active_session.slot
            location_path = slot_info.parking_lot.name
            
            if slot_info.floor:
                location_path += f" - {slot_info.floor.get_floor_name_display()}"
            if slot_info.block:
                location_path += f" - Block {slot_info.block.block_name}"
            
            # Calculate duration
            now = timezone.now()
            duration = now - active_session.entry_time
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            
            response_data = {
                'success': True,
                'vehicle': {
                    'status': 'parked',
                    'vehicle_number': vehicle.license_plate,
                    'vehicle_type': vehicle.get_vehicle_type_display(),
                    'slot_number': slot_info.slot_number,
                    'location': location_path,
                    'entry_time': active_session.entry_time.strftime('%d %b %Y, %I:%M %p'),
                    'duration': f"{hours}h {minutes}m",
                    'booking_id': f"PK-{active_session.id:05d}"
                }
            }
        else:
            # Vehicle exists but not currently parked
            # Check for last parking session
            last_session = ParkingSession.objects.filter(
                vehicle=vehicle,
                exit_time__isnull=False
            ).order_by('-exit_time').first()
            
            if last_session:
                last_visit = last_session.exit_time.strftime('%d %b %Y, %I:%M %p')
            else:
                last_visit = 'Never parked'
            
            response_data = {
                'success': True,
                'vehicle': {
                    'status': 'not_found',
                    'vehicle_number': vehicle.license_plate,
                    'last_visit': last_visit
                }
            }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error checking vehicle status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Server error',
            'message': 'An error occurred while checking vehicle status'
        }, status=500)


# ==================== UPDATED CONTACT VIEW (NO TICKET TRACKING) ====================
def contact_view(request):
    """Contact page with support message submission (No ticket tracking)"""
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        mobile_number = request.POST.get('mobile_number', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        try:
            # Create support entry (internal tracking only)
            support_message = SupportTicket.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                email=email,
                mobile_number=mobile_number,
                subject=subject,
                message=message,
                status='pending'
            )
            
            # Send confirmation email to customer
            customer_subject = 'Thank You for Contacting Parkease'
            customer_message = f"""
Dear {full_name},

Thank you for contacting Pune Smart Parking Solutions!

We have received your message and our support team will get back to you within 24 hours.

Your Message Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject: {dict(SupportTicket.SUBJECT_CHOICES).get(subject, subject)}
Submitted: {support_message.created_at.strftime('%d %b %Y, %I:%M %p')}

Your Message:
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For immediate assistance, you can:
📞 Call us: +91 9359845632
💬 WhatsApp: +91 9359845632
📧 Email: ✉️ ajitilage@gmail.com

We appreciate your patience.

Best regards,
Pune Smart Parking Support Team
            """
            
            send_mail(
                subject=customer_subject,
                message=customer_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            # Send notification email to admin
            admin_subject = f'🆕 New Support Message - {dict(SupportTicket.SUBJECT_CHOICES).get(subject, subject)}'
            admin_message = f"""
New Support Message Received!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Customer Details:
• Name: {full_name}
• Email: {email}
• Mobile: {mobile_number or 'Not provided'}

Subject: {dict(SupportTicket.SUBJECT_CHOICES).get(subject, subject)}

Message:
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Received: {support_message.created_at.strftime('%d %b %Y, %I:%M %p')}

Reply Options:
1. Email: {email}
2. Phone: {mobile_number or 'Not provided'}
3. Admin Panel: http://127.0.0.1:8000/admin/parking/supportticket/{support_message.id}/change/

Pune Smart Parking - Admin Notification
            """
            
            send_mail(
                subject=admin_subject,
                message=admin_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['✉️ ajitilage@gmail.com'],
                fail_silently=False,
            )
            
            messages.success(
                request, 
                f'✅ Thank you! Your message has been sent successfully. '
                f'Check your email ({email}) for confirmation. We will respond within 24 hours.'
            )
            logger.info(f"Support message from {email} submitted successfully")
            
        except Exception as e:
            messages.error(request, f'❌ Error submitting message: {str(e)}')
            logger.error(f"Error creating support message: {str(e)}")
        
        return redirect('contact')
    
    # GET request - show contact form
    try:
        system_settings = SystemSettings.objects.first()
    except SystemSettings.DoesNotExist:
        system_settings = None
    
    context = {
        'user': request.user,
        'system_settings': system_settings,
    }
    return render(request, 'parking/contact.html', context)
# ==================== PARKING LOT STATS API ====================
@require_http_methods(["GET"])
def api_parking_lot_stats(request):
    """
    API endpoint to get real-time parking lot statistics for map
    URL: /api/parking-lots-stats/
    """
    try:
        parking_lots = ParkingLot.objects.filter(is_active=True).annotate(
            total_slots_count=Count('slots'),
            available_count=Count('slots', filter=Q(slots__slot_status='available')),
            occupied_count=Count('slots', filter=Q(slots__slot_status='occupied'))
        )
        
        data = []
        for lot in parking_lots:
            data.append({
                'id': lot.id,
                'name': lot.name,
                'address': lot.address,
                'lat': float(lot.latitude) if lot.latitude else 18.5204,
                'lng': float(lot.longitude) if lot.longitude else 73.8567,
                'available': lot.available_count,
                'total': lot.total_slots_count
            })
        
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        logger.error(f"Error fetching parking lot stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        
        
        
        
        
        # ==================== MANAGER PANEL VIEWS ====================
# Add these to your existing views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
import logging
from django.contrib.auth.decorators import user_passes_test

from .models import (
    ManagerProfile, CCTVCamera, CCTVFootage, 
    ManagerActivityLog, SecurityIncident,
    ParkingLot, ParkingSession, Vehicle, ParkingSlot
)

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================
def is_manager(user):
    """Check if user is an active manager"""
    return (
        user.is_authenticated and 
        hasattr(user, 'manager_profile') and 
        user.manager_profile.is_active_manager
    )

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# ==================== MANAGER DASHBOARD ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def manager_dashboard(request):
    """Manager Dashboard with Real-time Stats"""
    manager = request.user
    manager_profile = manager.manager_profile
    
    # Get assigned parking lots
    assigned_lots = manager_profile.assigned_parking_lots.filter(is_active=True)
    
    # Overall Statistics
    total_cameras = CCTVCamera.objects.filter(
        parking_lot__in=assigned_lots
    ).count()
    
    active_cameras = CCTVCamera.objects.filter(
        parking_lot__in=assigned_lots,
        status='active'
    ).count()
    
    total_slots = ParkingSlot.objects.filter(
        parking_lot__in=assigned_lots
    ).count()
    
    available_slots = ParkingSlot.objects.filter(
        parking_lot__in=assigned_lots,
        slot_status='available'
    ).count()
    
    occupied_slots = ParkingSlot.objects.filter(
        parking_lot__in=assigned_lots,
        slot_status='occupied'
    ).count()
    
    # Active Sessions
    active_sessions = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        exit_time__isnull=True
    ).select_related('vehicle', 'slot', 'slot__parking_lot').order_by('-entry_time')[:10]
    
    # Today's Statistics
    today = timezone.now().date()
    today_entries = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        entry_time__date=today
    ).count()
    
    today_exits = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        exit_time__date=today
    ).count()
    
    today_revenue = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        entry_time__date=today,
        exit_time__isnull=False,
        fee__isnull=False
    ).aggregate(total=Sum('fee'))['total'] or 0
    
    # Security Incidents
    pending_incidents = SecurityIncident.objects.filter(
        parking_lot__in=assigned_lots,
        status__in=['reported', 'investigating']
    ).count()
    
    recent_incidents = SecurityIncident.objects.filter(
        parking_lot__in=assigned_lots
    ).select_related('parking_lot', 'vehicle').order_by('-incident_time')[:5]
    
    # Recent Manager Activities
    recent_activities = ManagerActivityLog.objects.filter(
        manager=manager
    ).select_related('vehicle', 'parking_session').order_by('-timestamp')[:10]
    
    # Location-wise Stats
    location_stats = []
    for lot in assigned_lots:
        total = lot.slots.count()
        occupied = lot.slots.filter(slot_status='occupied').count()
        available = lot.slots.filter(slot_status='available').count()
        active_cams = lot.cctv_cameras.filter(status='active').count()
        total_cams = lot.cctv_cameras.count()
        
        location_stats.append({
            'id': lot.id,
            'name': lot.name,
            'total_slots': total,
            'occupied': occupied,
            'available': available,
            'occupancy_rate': round((occupied / total * 100) if total > 0 else 0, 1),
            'active_cameras': active_cams,
            'total_cameras': total_cams
        })
    
    context = {
        'manager': manager,
        'manager_profile': manager_profile,
        'assigned_lots': assigned_lots,
        'total_cameras': total_cameras,
        'active_cameras': active_cameras,
        'total_slots': total_slots,
        'available_slots': available_slots,
        'occupied_slots': occupied_slots,
        'active_sessions': active_sessions,
        'today_entries': today_entries,
        'today_exits': today_exits,
        'today_revenue': today_revenue,
        'pending_incidents': pending_incidents,
        'recent_incidents': recent_incidents,
        'recent_activities': recent_activities,
        'location_stats': location_stats,
    }
    return render(request, 'manager/dashboard.html', context)


# ==================== CCTV MONITORING ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def cctv_monitoring(request):
    """CCTV Live Feed Monitoring Page"""
    manager = request.user
    manager_profile = manager.manager_profile
    assigned_lots = manager_profile.assigned_parking_lots.filter(is_active=True)
    
    # Get selected location
    selected_lot_id = request.GET.get('location')
    if selected_lot_id:
        selected_lot = get_object_or_404(ParkingLot, id=selected_lot_id, id__in=assigned_lots)
    else:
        selected_lot = assigned_lots.first()
    
    # Get cameras for selected location
    if selected_lot:
        entry_cameras = CCTVCamera.objects.filter(
            parking_lot=selected_lot,
            camera_type='entry',
            status='active'
        )
        
        exit_cameras = CCTVCamera.objects.filter(
            parking_lot=selected_lot,
            camera_type='exit',
            status='active'
        )
        
        parking_cameras = CCTVCamera.objects.filter(
            parking_lot=selected_lot,
            camera_type='parking',
            status='active'
        )
        
        overview_cameras = CCTVCamera.objects.filter(
            parking_lot=selected_lot,
            camera_type='overview',
            status='active'
        )
        
        # Get recent footage
        recent_footage = CCTVFootage.objects.filter(
            camera__parking_lot=selected_lot
        ).select_related('camera', 'parking_session', 'verified_by').order_by('-timestamp')[:20]
    else:
        entry_cameras = exit_cameras = parking_cameras = overview_cameras = []
        recent_footage = []
    
    # Active sessions for quick verification
    active_sessions = ParkingSession.objects.filter(
        slot__parking_lot=selected_lot if selected_lot else None,
        exit_time__isnull=True
    ).select_related('vehicle', 'slot').order_by('-entry_time')[:10]
    
    context = {
        'assigned_lots': assigned_lots,
        'selected_lot': selected_lot,
        'entry_cameras': entry_cameras,
        'exit_cameras': exit_cameras,
        'parking_cameras': parking_cameras,
        'overview_cameras': overview_cameras,
        'recent_footage': recent_footage,
        'active_sessions': active_sessions,
    }
    return render(request, 'manager/cctv_monitoring.html', context)


# ==================== ENTRY VERIFICATION ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def entry_verification(request):
    """Vehicle Entry Verification Page"""
    manager = request.user
    manager_profile = manager.manager_profile
    assigned_lots = manager_profile.assigned_parking_lots.filter(is_active=True)
    
    # Get pending entries (active sessions without manual verification)
    pending_entries = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        exit_time__isnull=True
    ).select_related('vehicle', 'slot', 'slot__parking_lot').order_by('-entry_time')[:20]
    
    # Today's entries
    today_entries = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        entry_time__date=timezone.now().date()
    ).select_related('vehicle', 'slot').order_by('-entry_time')[:50]
    
    # Entry statistics
    total_today = today_entries.count()
    verified_count = ManagerActivityLog.objects.filter(
        manager=manager,
        action_type='entry_verify',
        timestamp__date=timezone.now().date()
    ).count()
    
    context = {
        'assigned_lots': assigned_lots,
        'pending_entries': pending_entries,
        'today_entries': today_entries,
        'total_today': total_today,
        'verified_count': verified_count,
    }
    return render(request, 'manager/entry_verification.html', context)


# ==================== EXIT VERIFICATION ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def exit_verification(request):
    """Vehicle Exit Verification Page"""
    manager = request.user
    manager_profile = manager.manager_profile
    assigned_lots = manager_profile.assigned_parking_lots.filter(is_active=True)
    
    # Get vehicles ready for exit (active sessions)
    ready_for_exit = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        exit_time__isnull=True
    ).select_related('vehicle', 'slot', 'slot__parking_lot').order_by('entry_time')[:20]
    
    # Today's exits
    today_exits = ParkingSession.objects.filter(
        slot__parking_lot__in=assigned_lots,
        exit_time__date=timezone.now().date()
    ).select_related('vehicle', 'slot').order_by('-exit_time')[:50]
    
    # Exit statistics
    total_today = today_exits.count()
    verified_count = ManagerActivityLog.objects.filter(
        manager=manager,
        action_type='exit_verify',
        timestamp__date=timezone.now().date()
    ).count()
    
    context = {
        'assigned_lots': assigned_lots,
        'ready_for_exit': ready_for_exit,
        'today_exits': today_exits,
        'total_today': total_today,
        'verified_count': verified_count,
    }
    return render(request, 'manager/exit_verification.html', context)


# ==================== MANUAL ENTRY ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def manual_entry(request):
    """Manual Vehicle Entry (Without Booking)"""
    if request.method == 'POST':
        license_plate = request.POST.get('license_plate', '').strip().upper()
        vehicle_type = request.POST.get('vehicle_type')
        owner_name = request.POST.get('owner_name', '').strip()
        slot_id = request.POST.get('slot_id')
        notes = request.POST.get('notes', '')
        
        try:
            # Get or create vehicle
            vehicle, created = Vehicle.objects.get_or_create(
                license_plate=license_plate,
                defaults={'owner_name': owner_name, 'vehicle_type': vehicle_type}
            )
            
            # Get slot
            slot = ParkingSlot.objects.get(id=slot_id, slot_status='available')
            
            # Create parking session
            session = ParkingSession.objects.create(
                vehicle=vehicle,
                slot=slot,
                duration_hours=1,
                payment_status='pending'
            )
            
            # Update slot status
            slot.slot_status = 'occupied'
            slot.is_occupied = True
            slot.save()
            
            # Log activity
            ManagerActivityLog.objects.create(
                manager=request.user,
                action_type='manual_entry',
                parking_session=session,
                vehicle=vehicle,
                description=f'Manual entry for {license_plate}. Notes: {notes}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'✅ Manual entry successful for vehicle {license_plate}!')
            return redirect('entry_verification')
            
        except ParkingSlot.DoesNotExist:
            messages.error(request, '❌ Selected slot is not available!')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            logger.error(f"Manual entry error: {str(e)}")
    
    return redirect('entry_verification')


# ==================== MANUAL EXIT ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def manual_exit(request, session_id):
    """Manual Vehicle Exit Processing"""
    if request.method == 'POST':
        try:
            session = ParkingSession.objects.get(
                id=session_id,
                exit_time__isnull=True
            )
            
            # Calculate fee
            now = timezone.now()
            duration = (now - session.entry_time).total_seconds() / 3600
            rate = 20 if session.vehicle.vehicle_type == 'car' else 10
            fee = round(duration * rate, 2)
            
            # Process exit
            session.exit_time = now
            session.fee = fee
            session.payment_status = 'paid'
            session.save()
            
            # Free slot
            slot = session.slot
            slot.slot_status = 'available'
            slot.is_occupied = False
            slot.save()
            
            # Log activity
            ManagerActivityLog.objects.create(
                manager=request.user,
                action_type='manual_exit',
                parking_session=session,
                vehicle=session.vehicle,
                description=f'Manual exit for {session.vehicle.license_plate}. Fee: ₹{fee}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'✅ Exit processed for {session.vehicle.license_plate}. Fee: ₹{fee}')
            return JsonResponse({'success': True, 'message': 'Exit processed successfully'})
            
        except ParkingSession.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Session not found'})
        except Exception as e:
            logger.error(f"Manual exit error: {str(e)}")
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


# ==================== SECURITY INCIDENTS ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def security_incidents(request):
    """Security Incidents Management"""
    manager = request.user
    manager_profile = manager.manager_profile
    assigned_lots = manager_profile.assigned_parking_lots.filter(is_active=True)
    
    # Filter incidents
    status_filter = request.GET.get('status', '')
    severity_filter = request.GET.get('severity', '')
    
    incidents = SecurityIncident.objects.filter(
        parking_lot__in=assigned_lots
    ).select_related('parking_lot', 'vehicle', 'reported_by', 'assigned_to')
    
    if status_filter:
        incidents = incidents.filter(status=status_filter)
    if severity_filter:
        incidents = incidents.filter(severity=severity_filter)
    
    incidents = incidents.order_by('-incident_time')[:100]
    
    # Statistics
    total_incidents = SecurityIncident.objects.filter(parking_lot__in=assigned_lots).count()
    pending = SecurityIncident.objects.filter(parking_lot__in=assigned_lots, status='reported').count()
    investigating = SecurityIncident.objects.filter(parking_lot__in=assigned_lots, status='investigating').count()
    resolved = SecurityIncident.objects.filter(parking_lot__in=assigned_lots, status='resolved').count()
    
    context = {
        'incidents': incidents,
        'assigned_lots': assigned_lots,
        'total_incidents': total_incidents,
        'pending': pending,
        'investigating': investigating,
        'resolved': resolved,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
    }
    return render(request, 'manager/security_incidents.html', context)


# ==================== CREATE INCIDENT ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def create_incident(request):
    """Create New Security Incident"""
    if request.method == 'POST':
        try:
            parking_lot_id = request.POST.get('parking_lot')
            incident_type = request.POST.get('incident_type')
            severity = request.POST.get('severity')
            description = request.POST.get('description')
            vehicle_number = request.POST.get('vehicle_number', '').strip().upper()
            
            parking_lot = ParkingLot.objects.get(id=parking_lot_id)
            
            # Get vehicle if provided
            vehicle = None
            if vehicle_number:
                try:
                    vehicle = Vehicle.objects.get(license_plate=vehicle_number)
                except Vehicle.DoesNotExist:
                    pass
            
            # Create incident
            incident = SecurityIncident.objects.create(
                parking_lot=parking_lot,
                incident_type=incident_type,
                severity=severity,
                description=description,
                vehicle=vehicle,
                reported_by=request.user,
                incident_time=timezone.now(),
                status='reported'
            )
            
            # Log activity
            ManagerActivityLog.objects.create(
                manager=request.user,
                action_type='incident_report',
                vehicle=vehicle,
                description=f'Security incident reported: {incident.get_incident_type_display()}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'✅ Incident INC-{incident.id:05d} created successfully!')
            return redirect('security_incidents')
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            logger.error(f"Create incident error: {str(e)}")
    
    return redirect('security_incidents')


# ==================== MANAGER PROFILE ====================
@login_required(login_url='user_login')
@user_passes_test(is_manager, login_url='home')
def manager_profile(request):
    """Manager Profile Page"""
    manager = request.user
    manager_profile = manager.manager_profile
    
    # Activity statistics
    total_activities = ManagerActivityLog.objects.filter(manager=manager).count()
    today_activities = ManagerActivityLog.objects.filter(
        manager=manager,
        timestamp__date=timezone.now().date()
    ).count()
    
    # Recent activities
    recent_activities = ManagerActivityLog.objects.filter(
        manager=manager
    ).select_related('vehicle', 'parking_session').order_by('-timestamp')[:20]
    
    # Incident handling
    assigned_incidents = SecurityIncident.objects.filter(
        assigned_to=manager
    ).count()
    
    resolved_incidents = SecurityIncident.objects.filter(
        assigned_to=manager,
        status='resolved'
    ).count()
    
    context = {
        'manager': manager,
        'manager_profile': manager_profile,
        'total_activities': total_activities,
        'today_activities': today_activities,
        'recent_activities': recent_activities,
        'assigned_incidents': assigned_incidents,
        'resolved_incidents': resolved_incidents,
    }
    return render(request, 'manager/profile.html', context)


# ==================== API: VERIFY BOOKING ====================
@require_http_methods(["POST"])
@login_required
@user_passes_test(is_manager, login_url='home')
def api_verify_booking(request):
    """API to verify vehicle with booking"""
    try:
        session_id = request.POST.get('session_id')
        vehicle_number = request.POST.get('vehicle_number', '').strip().upper()
        action = request.POST.get('action')  # 'entry' or 'exit'
        
        session = ParkingSession.objects.get(id=session_id)
        
        # Verify vehicle number matches
        if session.vehicle.license_plate != vehicle_number:
            return JsonResponse({
                'success': False,
                'message': f'❌ Vehicle mismatch! Booked: {session.vehicle.license_plate}, Actual: {vehicle_number}'
            })
        
        # Log verification
        ManagerActivityLog.objects.create(
            manager=request.user,
            action_type=f'{action}_verify',
            parking_session=session,
            vehicle=session.vehicle,
            description=f'{action.title()} verified for {vehicle_number}',
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {action.title()} verified successfully!',
            'booking_id': f'PK-{session.id:05d}',
            'slot_number': session.slot.slot_number
        })
        
    except ParkingSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Booking not found'})
    except Exception as e:
        logger.error(f"Verify booking error: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)})