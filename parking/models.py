from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid


# ==================== VEHICLE MODEL ====================
class Vehicle(models.Model):
    VEHICLE_TYPES = [
        ('car', 'Car (4 Wheeler)'),
        ('bike', 'Bike (2 Wheeler)'),
        ('ev', 'Electric Vehicle'),
        ('3w', '3 Wheeler (Auto)'),
    ]
    
    license_plate = models.CharField(max_length=20, unique=True)
    owner_name = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=10, choices=VEHICLE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.license_plate} - {self.owner_name}"
    
    class Meta:
        ordering = ['license_plate']


# ==================== PARKING LOT MODEL ====================
class ParkingLot(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField()
    city = models.CharField(max_length=100, default='Unknown')
    state = models.CharField(max_length=100, default='Unknown')
    pincode = models.CharField(max_length=10, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    total_capacity = models.IntegerField(default=0)
    image = models.ImageField(upload_to='parking_lots/', blank=True, null=True)
    thumbnail = models.ImageField(upload_to='parking_lots/thumbnails/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


# ==================== LANDMARK MODEL ====================
class Landmark(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='landmarks')
    name = models.CharField(max_length=200)
    distance_km = models.DecimalField(max_digits=5, decimal_places=2)
    walking_time = models.IntegerField(help_text="Walking time in minutes")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True)
    icon = models.CharField(max_length=10, default='📍')
    image = models.ImageField(upload_to='landmarks/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.parking_lot.name}"
    
    class Meta:
        ordering = ['parking_lot', 'order', 'name']


# ==================== PARKING FLOOR MODEL ====================
class ParkingFloor(models.Model):
    FLOOR_CHOICES = [
        ('G', 'Ground Floor'),
        ('F1', 'First Floor'),
        ('F2', 'Second Floor'),
        ('F3', 'Third Floor'),
        ('F4', 'Fourth Floor'),
        ('T', 'Terrace'),
    ]
    
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='floors')
    landmark = models.ForeignKey(Landmark, on_delete=models.SET_NULL, null=True, blank=True, related_name='floors')
    floor_name = models.CharField(max_length=10, choices=FLOOR_CHOICES)
    floor_number = models.IntegerField()
    total_capacity = models.IntegerField(default=0)
    is_operational = models.BooleanField(default=True)
    floor_image = models.ImageField(upload_to='floor_layouts/', null=True, blank=True)
    allowed_vehicle_types = models.CharField(max_length=100, default='car,bike,ev,3w')
    description = models.TextField(blank=True)
    maintenance_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.parking_lot.name} - {self.get_floor_name_display()}"
    
    def available_slots(self):
        return self.slots.filter(slot_status='available').count()
    
    def occupied_slots(self):
        return self.slots.filter(slot_status='occupied').count()
    
    class Meta:
        ordering = ['parking_lot', 'floor_number']
        unique_together = ['parking_lot', 'floor_name']


# ==================== BLOCK MODEL ====================
class Block(models.Model):
    floor = models.ForeignKey(ParkingFloor, on_delete=models.CASCADE, related_name='blocks')
    block_name = models.CharField(max_length=50)
    block_code = models.CharField(max_length=10)
    total_slots = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Block {self.block_name} - {self.floor}"
    
    class Meta:
        ordering = ['floor', 'order', 'block_code']
        unique_together = ['floor', 'block_code']


# ==================== PARKING ZONE MODEL ====================
class ParkingZone(models.Model):
    ZONE_TYPE = [
        ('regular', 'Regular'),
        ('vip', 'VIP Zone'),
        ('ev', 'EV Zone'),
        ('disabled', 'Disabled Parking'),
    ]
    
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='zones')
    zone_name = models.CharField(max_length=50)
    zone_code = models.CharField(max_length=10)
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPE, default='regular')
    extra_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    zone_image = models.ImageField(upload_to='zone_images/', null=True, blank=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.parking_lot.name} - Zone {self.zone_code}"
    
    class Meta:
        ordering = ['parking_lot', 'zone_code']
        unique_together = ['parking_lot', 'zone_code']


# ==================== PARKING SLOT MODEL ====================
class ParkingSlot(models.Model):
    SLOT_STATUS = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Reserved'),
    ]
    
    SLOT_TYPE = [
        ('small', 'Small (2W)'),
        ('medium', 'Medium (3W/Car)'),
        ('large', 'Large (SUV)'),
        ('ev', 'EV Charging'),
    ]
    
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='slots')
    floor = models.ForeignKey(ParkingFloor, on_delete=models.SET_NULL, null=True, blank=True, related_name='slots')
    block = models.ForeignKey(Block, on_delete=models.SET_NULL, null=True, blank=True, related_name='slots')
    zone = models.ForeignKey(ParkingZone, on_delete=models.SET_NULL, null=True, blank=True, related_name='slots')
    slot_number = models.CharField(max_length=20)
    is_occupied = models.BooleanField(default=False)
    slot_status = models.CharField(max_length=20, choices=SLOT_STATUS, default='available')
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPE, default='medium')
    description = models.TextField(blank=True)
    maintenance_note = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.parking_lot.name} - {self.slot_number}"
    
    class Meta:
        ordering = ['parking_lot', 'floor', 'block', 'slot_number']
        unique_together = ['parking_lot', 'slot_number']


# ==================== PARKING SESSION MODEL ====================
class ParkingSession(models.Model):
    PAYMENT_METHOD = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('wallet', 'Wallet'),
        ('monthly_pass', 'Monthly Pass'),  # ✅ NEW
    ]
    
    # ... rest of the model ...
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE)
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_hours = models.IntegerField(default=1)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    def __str__(self):
        return f"{self.vehicle.license_plate} - Slot {self.slot.slot_number}"
    
    def save(self, *args, **kwargs):
        if self.pk:
            old_session = ParkingSession.objects.get(pk=self.pk)
            if old_session.exit_time is None and self.exit_time is not None:
                self.slot.is_occupied = False
                self.slot.slot_status = 'available'
                self.slot.save()
        else:
            self.slot.is_occupied = True
            self.slot.slot_status = 'occupied'
            self.slot.save()
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-entry_time']
    ai_recommended = models.BooleanField(default=False, help_text="Was this slot AI-recommended?")
    ai_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="AI recommendation confidence score")
    ai_reason = models.CharField(max_length=255, blank=True, help_text="Reason for AI recommendation")


# ==================== PASS TYPE MODEL ====================
class PassType(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('bike', '2 Wheeler'),
        ('car', '4 Wheeler'),
        ('ev', 'Electric Vehicle'),
        ('3w', '3 Wheeler'),
    ]
    
    name = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    duration_days = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=10, default='🎫')  # ✅ NEW FIELD
    
    def __str__(self):
        return f"{self.name} - {self.get_vehicle_type_display()}"


# ==================== MONTHLY PASS MODEL ====================
class MonthlyPass(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('wallet', 'Wallet'),
        ('cash', 'Cash'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_passes')
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE)
    pass_type = models.ForeignKey(PassType, on_delete=models.CASCADE)
    parking_lots = models.ManyToManyField('ParkingLot', related_name='monthly_passes')
    
    pass_number = models.CharField(max_length=50, unique=True, blank=True)
    qr_code = models.CharField(max_length=100, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField()
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, default='pending')
    
    auto_renew = models.BooleanField(default=False)
    contact_number = models.CharField(max_length=15, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_passes')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_valid_for_entry(self):
        """Check if pass is valid for parking entry"""
        today = timezone.now().date()
        return (
            self.status == 'active' and
            self.start_date <= today <= self.end_date
        )
    
    def days_until_expiry(self):
        """Calculate days remaining until expiry"""
        today = timezone.now().date()
        if self.end_date < today:
            return 0
        return (self.end_date - today).days
    
    def is_expiring_soon(self):
        """Check if pass is expiring within 7 days"""
        return 0 < self.days_until_expiry() <= 7
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.pass_number:
            self.pass_number = f"PASS-{uuid.uuid4().hex[:8].upper()}"
        if not self.qr_code:
            self.qr_code = f"QR-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.pass_number} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']


# ==================== PRICING RULE MODEL ====================
class PricingRule(models.Model):
    PRICING_TYPE = [
        ('hourly', 'Hourly Rate'),
        ('daily', 'Daily Rate'),
        ('weekend', 'Weekend Special'),
        ('holiday', 'Holiday Rate'),
        ('peak', 'Peak Hour Rate'),
    ]
    
    name = models.CharField(max_length=100)
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPE)
    vehicle_type = models.CharField(max_length=10, choices=Vehicle.VEHICLE_TYPES)
    rate_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    daily_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    overtime_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} - ₹{self.rate_per_hour}/hr"
    
    class Meta:
        ordering = ['vehicle_type', 'pricing_type']


# ==================== NOTIFICATION MODEL ====================
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('announcement', 'Announcement'),
        ('maintenance', 'Maintenance'),
        ('payment', 'Payment'),
        ('pass_expiry', 'Pass Expiry'),
        ('promotion', 'Promotion'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    send_to_all = models.BooleanField(default=False)
    target_users = models.ManyToManyField(User, blank=True, related_name='targeted_notifications')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


# ==================== USER NOTIFICATION MODEL ====================
class UserNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notifications')
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='user_instances')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'notification']
    
    def __str__(self):
        return f"{self.user.username} - {self.notification.title}"


# ==================== ENTRY/EXIT LOG MODEL ====================
class EntryExitLog(models.Model):
    LOG_TYPE = [
        ('entry', 'Entry'),
        ('exit', 'Exit'),
    ]
    
    session = models.ForeignKey(ParkingSession, on_delete=models.CASCADE, related_name='logs')
    log_type = models.CharField(max_length=10, choices=LOG_TYPE)
    timestamp = models.DateTimeField(auto_now_add=True)
    gate_number = models.CharField(max_length=20)
    qr_scanned = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.session.vehicle.license_plate} at {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']


# ==================== GALLERY IMAGE MODEL ====================
class GalleryImage(models.Model):
    IMAGE_CATEGORY = [
        ('parking_area', 'Parking Area'),
        ('floor_layout', 'Floor Layout'),
        ('slot_map', 'Slot Mapping'),
        ('banner', 'Home Banner'),
        ('facility', 'Facility'),
    ]
    
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='gallery/')
    category = models.CharField(max_length=20, choices=IMAGE_CATEGORY)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
    
    class Meta:
        ordering = ['-uploaded_at']


# ==================== SYSTEM SETTINGS MODEL ====================
class SystemSettings(models.Model):
    site_name = models.CharField(max_length=200, default='ParkEase')
    site_logo = models.ImageField(upload_to='branding/', null=True, blank=True)
    theme_color = models.CharField(max_length=7, default='#667eea')
    terms_conditions = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    payment_gateway_key = models.CharField(max_length=200, blank=True)
    enable_qr_entry = models.BooleanField(default=True)
    enable_monthly_pass = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.site_name
    
    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'


# ==================== ADMIN ACTIVITY LOG MODEL ====================
class AdminActivityLog(models.Model):
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=200)
    target_model = models.CharField(max_length=100)
    target_id = models.IntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.action} at {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']


# ==================== SUPPORT TICKET MODEL (UPDATED WITH EMAIL) ====================
class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]
    
    SUBJECT_CHOICES = [
        ('general', 'General Query'),
        ('lost', 'Lost Vehicle'),
        ('complaint', 'Complaint'),
        ('technical', 'Technical Issue'),
        ('payment', 'Payment Issue'),
        ('feedback', 'Feedback'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15, blank=True)  # NEW
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    message = models.TextField()
    attachment = models.FileField(upload_to='support_tickets/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(blank=True)  # NEW
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_tickets')  # NEW
    resolved_at = models.DateTimeField(null=True, blank=True)  # NEW
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"TKT{self.id:06d} - {self.get_subject_display()}"
    
    def get_ticket_id(self):
        return f"TKT{self.id:06d}"
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    # ==================== MANAGER & CCTV MODELS ====================
# Add these models to your existing models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ==================== MANAGER PROFILE MODEL ====================
class ManagerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='manager_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15)
    assigned_parking_lots = models.ManyToManyField('ParkingLot', related_name='assigned_managers')
    shift_start_time = models.TimeField(null=True, blank=True)
    shift_end_time = models.TimeField(null=True, blank=True)
    is_active_manager = models.BooleanField(default=True)
    profile_image = models.ImageField(upload_to='manager_profiles/', null=True, blank=True)
    joined_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
    
    class Meta:
        ordering = ['-joined_date']


# ==================== CCTV CAMERA MODEL ====================
class CCTVCamera(models.Model):
    CAMERA_TYPE = [
        ('entry', 'Entry Gate'),
        ('exit', 'Exit Gate'),
        ('parking', 'Parking Area'),
        ('overview', 'Overview'),
    ]
    
    CAMERA_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    parking_lot = models.ForeignKey('ParkingLot', on_delete=models.CASCADE, related_name='cctv_cameras')
    camera_name = models.CharField(max_length=100)
    camera_type = models.CharField(max_length=20, choices=CAMERA_TYPE)
    camera_ip = models.GenericIPAddressField()
    rtsp_url = models.URLField(max_length=500, blank=True, help_text="RTSP stream URL for live feed")
    stream_url = models.URLField(max_length=500, blank=True, help_text="HTTP/HTTPS stream URL")
    location_description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=CAMERA_STATUS, default='active')
    is_recording = models.BooleanField(default=True)
    last_maintenance = models.DateTimeField(null=True, blank=True)
    installed_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.camera_name} - {self.parking_lot.name}"
    
    class Meta:
        ordering = ['parking_lot', 'camera_type', 'camera_name']


# ==================== CCTV FOOTAGE MODEL ====================
class CCTVFootage(models.Model):
    FOOTAGE_TYPE = [
        ('entry', 'Entry Recording'),
        ('exit', 'Exit Recording'),
        ('incident', 'Incident Recording'),
        ('scheduled', 'Scheduled Recording'),
    ]
    
    camera = models.ForeignKey(CCTVCamera, on_delete=models.CASCADE, related_name='footages')
    parking_session = models.ForeignKey('ParkingSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='cctv_footages')
    footage_type = models.CharField(max_length=20, choices=FOOTAGE_TYPE)
    video_file = models.FileField(upload_to='cctv_footage/%Y/%m/%d/', null=True, blank=True)
    snapshot_image = models.ImageField(upload_to='cctv_snapshots/%Y/%m/%d/', null=True, blank=True)
    vehicle_number_detected = models.CharField(max_length=20, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(default=0)
    file_size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_footages')
    
    def __str__(self):
        return f"{self.camera.camera_name} - {self.timestamp.strftime('%d %b %Y %H:%M')}"
    
    class Meta:
        ordering = ['-timestamp']


# ==================== MANAGER ACTIVITY LOG ====================
class ManagerActivityLog(models.Model):
    ACTION_TYPES = [
        ('entry_verify', 'Entry Verification'),
        ('exit_verify', 'Exit Verification'),
        ('manual_entry', 'Manual Entry'),
        ('manual_exit', 'Manual Exit'),
        ('booking_override', 'Booking Override'),
        ('slot_change', 'Slot Change'),
        ('incident_report', 'Incident Report'),
        ('camera_check', 'Camera Check'),
    ]
    
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manager_activities')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    parking_session = models.ForeignKey('ParkingSession', on_delete=models.SET_NULL, null=True, blank=True)
    vehicle = models.ForeignKey('Vehicle', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.manager.username} - {self.get_action_type_display()} at {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']


# ==================== SECURITY INCIDENT MODEL ====================
class SecurityIncident(models.Model):
    INCIDENT_TYPE = [
        ('unauthorized_entry', 'Unauthorized Entry'),
        ('suspicious_vehicle', 'Suspicious Vehicle'),
        ('vehicle_damage', 'Vehicle Damage'),
        ('theft_attempt', 'Theft Attempt'),
        ('system_breach', 'System Breach'),
        ('other', 'Other Incident'),
    ]
    
    SEVERITY = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS = [
        ('reported', 'Reported'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    parking_lot = models.ForeignKey('ParkingLot', on_delete=models.CASCADE, related_name='security_incidents')
    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPE)
    severity = models.CharField(max_length=20, choices=SEVERITY, default='medium')
    status = models.CharField(max_length=20, choices=STATUS, default='reported')
    description = models.TextField()
    vehicle = models.ForeignKey('Vehicle', on_delete=models.SET_NULL, null=True, blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    cctv_footage = models.ForeignKey(CCTVFootage, on_delete=models.SET_NULL, null=True, blank=True)
    incident_time = models.DateTimeField()
    resolved_time = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_incident_type_display()} - {self.parking_lot.name} - {self.incident_time.strftime('%d %b %Y')}"
    
    class Meta:
        ordering = ['-incident_time']