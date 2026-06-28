from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe  # ✅ ADDED THIS IMPORT
from django.db.models import Count, Q, Sum
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
import csv
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Vehicle, ParkingLot, ParkingSlot, ParkingSession,
    ParkingFloor, ParkingZone, MonthlyPass, PassType,
    PricingRule, Notification, UserNotification, EntryExitLog, GalleryImage,
    SystemSettings, AdminActivityLog, Landmark, Block, SupportTicket
)

# Customize Admin Site Headers
admin.site.site_header = "🚗 Parkease Admin Panel"
admin.site.site_title = "Parkease Admin"
admin.site.index_title = "Welcome to Vihicle Parking System"

from django.contrib import admin
from .models import SupportTicket


@admin.register(PassType)
class PassTypeAdmin(admin.ModelAdmin):
    list_display = ('name_with_icon', 'vehicle_type', 'duration_days', 'price', 'is_active')
    list_filter = ('vehicle_type', 'is_active')
    search_fields = ('name',)
    
    def name_with_icon(self, obj):
        return format_html('<strong>{} {}</strong>', obj.icon, obj.name)
    name_with_icon.short_description = 'Pass Type'



@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'message', 'user__username')

# ==================== USER MANAGEMENT ====================
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['username_display', 'email', 'full_name', 'total_bookings', 
                    'monthly_pass_status', 'is_active', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    actions = ['activate_users', 'deactivate_users']
    
    def username_display(self, obj):
        return format_html('<strong style="color: #667eea;">👤 {}</strong>', obj.username)
    username_display.short_description = 'Username'
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name else "—"
    full_name.short_description = 'Full Name'
    
    def total_bookings(self, obj):
        count = ParkingSession.objects.filter(vehicle__owner_name=obj.username).count()
        return format_html('<strong>{}</strong>', count)
    total_bookings.short_description = 'Total Bookings'
    
    def monthly_pass_status(self, obj):
        active_pass = MonthlyPass.objects.filter(
            user=obj, status='active', end_date__gte=timezone.now().date()
        ).first()
        if active_pass:
            return mark_safe('<span style="background: #4caf50; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 600;">✓ Active</span>')
        return mark_safe('<span style="color: #999;">No Pass</span>')
    monthly_pass_status.short_description = 'Monthly Pass'
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} users activated successfully.')
    activate_users.short_description = "✅ Activate Selected Users"
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} users deactivated successfully.')
    deactivate_users.short_description = "❌ Deactivate Selected Users"

admin.site.unregister(User)
admin.site.register(User, UserProfileAdmin)


# ==================== VEHICLE MANAGEMENT ====================
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['license_plate_display', 'owner_name', 'vehicle_type_badge', 'session_count', 'total_spent', 'first_visit']
    list_filter = ['vehicle_type']
    search_fields = ['license_plate', 'owner_name']
    ordering = ['license_plate']
    actions = ['export_to_csv']
    
    def license_plate_display(self, obj):
        icons = {'car': '🚗', 'bike': '🏍️', 'ev': '⚡', '3w': '🛺'}
        icon = icons.get(obj.vehicle_type, '🚗')
        return format_html('<strong>{} {}</strong>', icon, obj.license_plate)
    license_plate_display.short_description = 'Vehicle'
    
    def vehicle_type_badge(self, obj):
        colors = {'car': '#2196f3', 'bike': '#4caf50', 'ev': '#ff9800', '3w': '#9c27b0'}
        return format_html('<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem;">{}</span>',
            colors.get(obj.vehicle_type, '#666'), obj.get_vehicle_type_display())
    vehicle_type_badge.short_description = 'Type'
    
    def session_count(self, obj):
        count = ParkingSession.objects.filter(vehicle=obj).count()
        return format_html('<strong style="color: #667eea;">{}</strong>', count)
    session_count.short_description = 'Sessions'
    
    def total_spent(self, obj):
     total = ParkingSession.objects.filter(
        vehicle=obj,
        exit_time__isnull=False
      ).aggregate(total=Sum('fee'))['total'] or 0

     total = float(total)  
    
     return format_html(
        '<strong style="color: #4caf50;">₹{}</strong>',
        f"{total:.2f}"
    )

    total_spent.short_description = 'Total Spent'

    
    def first_visit(self, obj):
        first = ParkingSession.objects.filter(vehicle=obj).order_by('entry_time').first()
        return first.entry_time.date() if first else "—"
    first_visit.short_description = 'First Visit'
    
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vehicles.csv"'
        writer = csv.writer(response)
        writer.writerow(['License Plate', 'Owner', 'Type', 'Sessions', 'Total Spent'])
        for vehicle in queryset:
            count = ParkingSession.objects.filter(vehicle=vehicle).count()
            total = ParkingSession.objects.filter(vehicle=vehicle, exit_time__isnull=False).aggregate(Sum('fee'))['fee__sum'] or 0
            writer.writerow([vehicle.license_plate, vehicle.owner_name, vehicle.get_vehicle_type_display(), count, f'₹{total:.2f}'])
        return response
    export_to_csv.short_description = "📄 Export to CSV"


# ==================== PARKING LOT MANAGEMENT ====================
@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    list_display = ['name_display', 'address_display', 'total_slots_display', 
                    'available_slots_display', 'occupied_slots_display', 
                    'maintenance_slots_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'address', 'city']
    ordering = ['name']
    actions = ['activate_locations', 'deactivate_locations', 'export_to_csv']
    
    fieldsets = (
        ('📍 Basic Information', {'fields': ('name', 'address', 'city', 'state', 'pincode')}),
        ('🗺️ Map Coordinates', {'fields': ('latitude', 'longitude')}),
        ('📸 Images', {'fields': ('image', 'thumbnail')}),
        ('⚙️ Settings', {'fields': ('is_active', 'total_capacity', 'description')}),
    )
    
    def name_display(self, obj):
        status_icon = '🟢' if obj.is_active else '🔴'
        return format_html('{} <strong style="color: #6366f1; font-size: 16px;">🅿️ {}</strong>', status_icon, obj.name)
    name_display.short_description = 'Location Name'
    
    def address_display(self, obj):
        return format_html('<span style="color: #64748b;">📍 {}, {}</span>',
            obj.address[:40] + '...' if len(obj.address) > 40 else obj.address, obj.city)
    address_display.short_description = 'Address'
    
    def total_slots_display(self, obj):
        total = obj.slots.count()
        return format_html('<strong style="color: #333; font-size: 18px;">{}</strong>', total)
    total_slots_display.short_description = 'Total Slots'
    
    def available_slots_display(self, obj):
        available = obj.slots.filter(slot_status='available').count()
        return format_html('<span style="background: #10b981; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🟢 {}</span>', available)
    available_slots_display.short_description = 'Available'
    
    def occupied_slots_display(self, obj):
        occupied = obj.slots.filter(slot_status='occupied').count()
        return format_html('<span style="background: #ef4444; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🔴 {}</span>', occupied)
    occupied_slots_display.short_description = 'Occupied'
    
    def maintenance_slots_display(self, obj):
        maintenance = obj.slots.filter(slot_status='maintenance').count()
        if maintenance > 0:
            return format_html('<span style="background: #f59e0b; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🔧 {}</span>', maintenance)
        return mark_safe('<span style="color: #94a3b8;">—</span>')
    maintenance_slots_display.short_description = 'Maintenance'
    
    def activate_locations(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'✅ {queryset.count()} locations activated successfully.')
    activate_locations.short_description = "🟢 Activate Selected Locations"
    
    def deactivate_locations(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'🔴 {queryset.count()} locations deactivated.')
    deactivate_locations.short_description = "⛔ Deactivate Selected Locations"
    
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="parking_locations.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Address', 'City', 'Total Slots', 'Available', 'Occupied', 'Status'])
        for lot in queryset:
            writer.writerow([lot.name, lot.address, lot.city, lot.slots.count(),
                lot.slots.filter(slot_status='available').count(),
                lot.slots.filter(slot_status='occupied').count(),
                'Active' if lot.is_active else 'Inactive'])
        return response
    export_to_csv.short_description = "📄 Export to CSV"


# ==================== LANDMARK MANAGEMENT ====================
@admin.register(Landmark)
class LandmarkAdmin(admin.ModelAdmin):
    list_display = ['name_display', 'parking_lot_display', 'distance_display', 'walking_time', 'is_active', 'order']
    list_filter = ['parking_lot', 'is_active']
    search_fields = ['name', 'parking_lot__name']
    ordering = ['parking_lot', 'order']
    actions = ['activate_landmarks', 'deactivate_landmarks']
    
    fieldsets = (
        ('📍 Landmark Details', {'fields': ('name', 'parking_lot', 'description')}),
        ('📏 Distance Information', {'fields': ('distance_km', 'walking_time')}),
        ('🗺️ Map Integration', {'fields': ('latitude', 'longitude', 'google_maps_url')}),
        ('📸 Visual', {'fields': ('icon', 'image')}),
        ('⚙️ Settings', {'fields': ('is_active', 'order')}),
    )
    
    def name_display(self, obj):
        icon = obj.icon if obj.icon else '📍'
        status = '🟢' if obj.is_active else '🔴'
        return format_html('{} {} <strong style="color: #6366f1;">{}</strong>', status, icon, obj.name)
    name_display.short_description = 'Landmark Name'
    
    def parking_lot_display(self, obj):
        return format_html('<span style="color: #64748b;">🅿️ {}</span>', obj.parking_lot.name)
    parking_lot_display.short_description = 'Parking Location'
    
    def distance_display(self, obj):
        if obj.distance_km:
            return format_html('<strong style="color: #3b82f6;">📏 {} km</strong>', obj.distance_km)
        return '—'
    distance_display.short_description = 'Distance'
    
    def activate_landmarks(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'✅ {queryset.count()} landmarks activated.')
    activate_landmarks.short_description = "🟢 Activate Landmarks"
    
    def deactivate_landmarks(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'🔴 {queryset.count()} landmarks deactivated.')
    deactivate_landmarks.short_description = "⛔ Deactivate Landmarks"


# ==================== FLOOR MANAGEMENT ====================
@admin.register(ParkingFloor)
class ParkingFloorAdmin(admin.ModelAdmin):
    list_display = ['floor_display', 'parking_lot', 'landmark', 'total_capacity_display',
                    'available_display', 'occupied_display', 'operational_status']
    list_filter = ['parking_lot', 'landmark', 'is_operational']
    search_fields = ['floor_name', 'parking_lot__name', 'landmark__name']
    ordering = ['parking_lot', 'floor_number']
    actions = ['mark_operational', 'mark_closed', 'export_floor_data']
    
    fieldsets = (
        ('🏢 Floor Information', {'fields': ('floor_name', 'floor_number', 'parking_lot', 'landmark')}),
        ('📊 Capacity', {'fields': ('total_capacity', 'description')}),
        ('⚙️ Settings', {'fields': ('is_operational', 'maintenance_note')}),
    )
    
    def floor_display(self, obj):
        status = '🟢' if obj.is_operational else '🔴'
        return format_html('{} <strong style="color: #6366f1; font-size: 16px;">🏢 {}</strong>', status, obj.get_floor_name_display())
    floor_display.short_description = 'Floor'
    
    def total_capacity_display(self, obj):
        return format_html('<strong style="color: #333; font-size: 16px;">{}</strong>', obj.total_capacity)
    total_capacity_display.short_description = 'Capacity'
    
    def available_display(self, obj):
        available = obj.slots.filter(slot_status='available').count()
        return format_html('<span style="background: #10b981; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🟢 {}</span>', available)
    available_display.short_description = 'Available'
    
    def occupied_display(self, obj):
        occupied = obj.slots.filter(slot_status='occupied').count()
        return format_html('<span style="background: #ef4444; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🔴 {}</span>', occupied)
    occupied_display.short_description = 'Occupied'
    
    def operational_status(self, obj):
        if obj.is_operational:
            return mark_safe('<span style="color: #10b981; font-weight: 700;">✓ OPEN</span>')
        return mark_safe('<span style="color: #ef4444; font-weight: 700;">✗ CLOSED</span>')
    operational_status.short_description = 'Status'
    
    def mark_operational(self, request, queryset):
        queryset.update(is_operational=True)
        self.message_user(request, f'✅ {queryset.count()} floors marked as operational.')
    mark_operational.short_description = "🟢 Mark as Operational"
    
    def mark_closed(self, request, queryset):
        queryset.update(is_operational=False)
        self.message_user(request, f'🔴 {queryset.count()} floors closed for maintenance.')
    mark_closed.short_description = "🔧 Close for Maintenance"
    
    def export_floor_data(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="floors_data.csv"'
        writer = csv.writer(response)
        writer.writerow(['Floor', 'Location', 'Landmark', 'Capacity', 'Available', 'Occupied', 'Status'])
        for floor in queryset:
            writer.writerow([floor.get_floor_name_display(), floor.parking_lot.name,
                floor.landmark.name if floor.landmark else 'N/A', floor.total_capacity,
                floor.slots.filter(slot_status='available').count(),
                floor.slots.filter(slot_status='occupied').count(),
                'Operational' if floor.is_operational else 'Closed'])
        return response
    export_floor_data.short_description = "📄 Export Floor Data"


# ==================== BLOCK MANAGEMENT ====================
@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ['block_display', 'floor', 'parking_lot_display', 'total_slots_display',
                    'available_display', 'occupied_display', 'is_active']
    list_filter = ['floor__parking_lot', 'floor', 'is_active']
    search_fields = ['block_name', 'block_code', 'floor__parking_lot__name']
    ordering = ['floor', 'block_code']
    actions = ['activate_blocks', 'deactivate_blocks', 'auto_generate_slots']
    
    fieldsets = (
        ('🅰️ Block Information', {'fields': ('block_name', 'block_code', 'floor')}),
        ('📊 Capacity', {'fields': ('total_slots', 'description')}),
        ('⚙️ Settings', {'fields': ('is_active', 'order')}),
    )
    
    def block_display(self, obj):
        status = '🟢' if obj.is_active else '🔴'
        return format_html('{} <strong style="color: #6366f1; font-size: 16px;">🅰️ Block {}</strong>', status, obj.block_name)
    block_display.short_description = 'Block'
    
    def parking_lot_display(self, obj):
        return format_html('<span style="color: #64748b;">🅿️ {} → 🏢 {}</span>',
            obj.floor.parking_lot.name, obj.floor.get_floor_name_display())
    parking_lot_display.short_description = 'Location → Floor'
    
    def total_slots_display(self, obj):
        actual = obj.slots.count()
        return format_html('<strong style="color: #333;">{} / {}</strong>', actual, obj.total_slots)
    total_slots_display.short_description = 'Slots (Created/Planned)'
    
    def available_display(self, obj):
        available = obj.slots.filter(slot_status='available').count()
        return format_html('<span style="background: #10b981; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🟢 {}</span>', available)
    available_display.short_description = 'Available'
    
    def occupied_display(self, obj):
        occupied = obj.slots.filter(slot_status='occupied').count()
        return format_html('<span style="background: #ef4444; color: white; padding: 5px 14px; border-radius: 15px; font-weight: 700;">🔴 {}</span>', occupied)
    occupied_display.short_description = 'Occupied'
    
    def activate_blocks(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'✅ {queryset.count()} blocks activated.')
    activate_blocks.short_description = "🟢 Activate Blocks"
    
    def deactivate_blocks(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'🔴 {queryset.count()} blocks deactivated.')
    deactivate_blocks.short_description = "⛔ Deactivate Blocks"
    
    def auto_generate_slots(self, request, queryset):
        total_created = 0
        for block in queryset:
            existing = block.slots.count()
            needed = block.total_slots - existing
            if needed > 0:
                for i in range(needed):
                    slot_number = f"{block.block_code}{existing + i + 1}"
                    ParkingSlot.objects.create(
                        parking_lot=block.floor.parking_lot,
                        floor=block.floor,
                        block=block,
                        slot_number=slot_number,
                        slot_status='available'
                    )
                    total_created += 1
        self.message_user(request, f'✅ Auto-generated {total_created} slots successfully!')
    auto_generate_slots.short_description = "⚡ Auto-Generate Slots"


# ==================== SLOT MANAGEMENT ====================
@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_number_display', 'full_path_display', 'slot_type_badge',
                    'status_badge', 'current_vehicle', 'last_updated']
    list_filter = ['parking_lot', 'floor', 'block', 'slot_status', 'slot_type']
    search_fields = ['slot_number', 'parking_lot__name', 'block__block_name']
    ordering = ['parking_lot', 'floor', 'block', 'slot_number']
    actions = ['mark_available', 'mark_maintenance', 'mark_reserved', 'export_slots']
    
    fieldsets = (
        ('🅿️ Slot Information', {'fields': ('slot_number', 'parking_lot', 'floor', 'block')}),
        ('🚗 Slot Type & Status', {'fields': ('slot_type', 'slot_status')}),
        ('📝 Additional Info', {'fields': ('description', 'maintenance_note')}),
    )
    
    def slot_number_display(self, obj):
        return format_html('<strong style="color: #6366f1; font-size: 18px;">🅿️ {}</strong>', obj.slot_number)
    slot_number_display.short_description = 'Slot Number'
    
    def full_path_display(self, obj):
        path = f"🅿️ {obj.parking_lot.name}"
        if obj.floor:
            path += f" → 🏢 {obj.floor.get_floor_name_display()}"
        if obj.block:
            path += f" → 🅰️ Block {obj.block.block_name}"
        return format_html('<span style="color: #64748b; font-size: 13px;">{}</span>', path)
    full_path_display.short_description = 'Location Path'
    
    def slot_type_badge(self, obj):
        colors = {'small': '#10b981', 'medium': '#3b82f6', 'large': '#f59e0b', 'ev': '#8b5cf6'}
        return format_html('<span style="background: {}; color: white; padding: 4px 10px; border-radius: 10px; font-size: 12px; font-weight: 600;">{}</span>',
            colors.get(obj.slot_type, '#64748b'), obj.get_slot_type_display())
    slot_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {'available': '#10b981', 'occupied': '#ef4444', 'maintenance': '#f59e0b', 'reserved': '#3b82f6'}
        icons = {'available': '🟢', 'occupied': '🔴', 'maintenance': '🔧', 'reserved': '🔵'}
        return format_html('<span style="background: {}; color: white; padding: 6px 14px; border-radius: 15px; font-weight: 700; font-size: 13px;">{} {}</span>',
            colors.get(obj.slot_status, '#64748b'), icons.get(obj.slot_status, ''), obj.get_slot_status_display().upper())
    status_badge.short_description = 'Status'
    
    def current_vehicle(self, obj):
        if obj.slot_status == 'occupied':
            session = ParkingSession.objects.filter(slot=obj, exit_time__isnull=True).first()
            if session:
                return format_html('<strong style="color: #f59e0b;">🚗 {}</strong>', session.vehicle.license_plate)
        return mark_safe('<span style="color: #94a3b8;">—</span>')
    current_vehicle.short_description = 'Current Vehicle'
    
    def mark_available(self, request, queryset):
        queryset.update(slot_status='available', is_occupied=False)
        self.message_user(request, f'🟢 {queryset.count()} slots marked as available.')
    mark_available.short_description = "🟢 Mark as Available"
    
    def mark_maintenance(self, request, queryset):
        queryset.update(slot_status='maintenance', is_occupied=False)
        self.message_user(request, f'🔧 {queryset.count()} slots marked for maintenance.')
    mark_maintenance.short_description = "🔧 Mark for Maintenance"
    
    def mark_reserved(self, request, queryset):
        queryset.update(slot_status='reserved')
        self.message_user(request, f'🔵 {queryset.count()} slots marked as reserved.')
    mark_reserved.short_description = "🔵 Mark as Reserved"
    
    def export_slots(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="parking_slots.csv"'
        writer = csv.writer(response)
        writer.writerow(['Slot Number', 'Location', 'Floor', 'Block', 'Type', 'Status', 'Vehicle'])
        for slot in queryset:
            vehicle = '—'
            if slot.slot_status == 'occupied':
                session = ParkingSession.objects.filter(slot=slot, exit_time__isnull=True).first()
                if session:
                    vehicle = session.vehicle.license_plate
            writer.writerow([slot.slot_number, slot.parking_lot.name,
                slot.floor.get_floor_name_display() if slot.floor else 'N/A',
                f"Block {slot.block.block_name}" if slot.block else 'N/A',
                slot.get_slot_type_display(), slot.get_slot_status_display(), vehicle])
        return response
    export_slots.short_description = "📄 Export Slots to CSV"


# ==================== PARKING SESSION ====================
@admin.register(ParkingSession)
class ParkingSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id_display', 'vehicle_display', 'slot_display', 
                    'entry_time', 'exit_time', 'duration_display', 'fee_display', 'status_badge']
    list_filter = ['entry_time', 'payment_method', 'payment_status', 'slot__parking_lot']
    search_fields = ['vehicle__license_plate', 'slot__slot_number']
    ordering = ['-entry_time']
    date_hierarchy = 'entry_time'
    
    def session_id_display(self, obj):
        return format_html('<strong style="color: #667eea;">📋 PK-{}</strong>', obj.id)
    session_id_display.short_description = 'Session ID'
    
    def vehicle_display(self, obj):
        icons = {'car': '🚗', 'bike': '🏍️', 'ev': '⚡', '3w': '🛺'}
        icon = icons.get(obj.vehicle.vehicle_type, '🚗')
        return format_html('{} <strong>{}</strong>', icon, obj.vehicle.license_plate)
    vehicle_display.short_description = 'Vehicle'
    
    def slot_display(self, obj):
        return format_html('🅿️ {} <span style="color: #999;">@ {}</span>', obj.slot.slot_number, obj.slot.parking_lot.name)
    slot_display.short_description = 'Slot & Location'
    
    def duration_display(self, obj):
        if obj.exit_time:
            duration = (obj.exit_time - obj.entry_time).total_seconds() / 3600
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return format_html('<strong style="color: #333;">{}h {}m</strong>', hours, minutes)
        else:
            duration = (timezone.now() - obj.entry_time).total_seconds() / 3600
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return format_html('<strong style="color: #ff9800;">{}h {}m (Active)</strong>', hours, minutes)
    duration_display.short_description = 'Duration'
    
    def fee_display(self, obj):
        if obj.fee:
            return format_html('<strong style="color: #4caf50; font-size: 1.1rem;">₹{}</strong>', obj.fee)
        return mark_safe('<span style="color: #999;">Pending</span>')
    fee_display.short_description = 'Fee'
    
    def status_badge(self, obj):
        if obj.exit_time:
            return mark_safe('<span style="background: #e8f5e9; color: #2e7d32; padding: 5px 12px; border-radius: 15px; font-weight: 600;">✓ Completed</span>')
        return mark_safe('<span style="background: #fff3e0; color: #f57c00; padding: 5px 12px; border-radius: 15px; font-weight: 600;">🟡 Active</span>')
    status_badge.short_description = 'Status'


## ==================== ZONE MANAGEMENT ====================
@admin.register(ParkingZone)
class ParkingZoneAdmin(admin.ModelAdmin):
    list_display = ['zone_display', 'parking_lot', 'zone_type_badge', 'extra_charge_display', 'slot_count']
    list_filter = ['zone_type', 'parking_lot']
    search_fields = ['zone_name', 'zone_code']
    
    def zone_display(self, obj):
        return format_html('<strong style="color: #667eea;">📍 {} ({})</strong>', obj.zone_name, obj.zone_code)
    zone_display.short_description = 'Zone'
    
    def zone_type_badge(self, obj):
        colors = {'regular': '#2196f3', 'vip': '#ff9800', 'ev': '#4caf50', 'disabled': '#9c27b0'}
        return format_html('<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 600;">{}</span>',
            colors.get(obj.zone_type, '#666'), obj.get_zone_type_display())
    zone_type_badge.short_description = 'Type'
    
    def extra_charge_display(self, obj):
        if obj.extra_charge > 0:
            return format_html('<strong style="color: #ff9800;">+₹{}</strong>', obj.extra_charge)
        return "—"
    extra_charge_display.short_description = 'Extra Charge'
    
    def slot_count(self, obj):
        return obj.slots.count()
    slot_count.short_description = 'Total Slots'


# ==================== MONTHLY PASS MANAGEMENT ====================
@admin.register(MonthlyPass)
class MonthlyPassAdmin(admin.ModelAdmin):
    autocomplete_fields = ('pass_type',)

    list_display = ['pass_id_display', 'user', 'vehicle', 'pass_type', 'validity_period', 
                    'days_remaining_display', 'status_badge', 'amount']
    list_filter = ['status', 'pass_type', 'start_date', 'auto_renew']
    search_fields = ['user__username', 'vehicle__license_plate', 'pass_number']
    actions = ['approve_passes', 'cancel_passes', 'send_expiry_reminder']
    readonly_fields = ['pass_number', 'qr_code', 'created_at', 'updated_at', 'approved_by', 'approved_at']
    
    
    fieldsets = (
        ('🎫 Pass Information', {
            'fields': ('pass_number', 'qr_code', 'user', 'vehicle', 'pass_type')
        }),
        ('📍 Parking Locations', {
            'fields': ('parking_lots',)
        }),
        ('📅 Validity', {
            'fields': ('start_date', 'end_date')
        }),
        ('💳 Payment', {
            'fields': ('amount', 'payment_method', 'payment_status')
        }),
        ('⚙️ Settings', {
            'fields': ('auto_renew', 'contact_number', 'status')
        }),
        ('👤 Approval Details', {
            'fields': ('approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        
    )
    
    def pass_id_display(self, obj):
      if not obj.pass_number:
        return mark_safe('<span style="color:#999;">—</span>')
      return format_html('<strong>🎫 {}</strong>', obj.pass_number)
    pass_id_display.short_description = 'Pass ID'


    def validity_period(self, obj):
       if not obj.start_date or not obj.end_date:
        return mark_safe('<span style="color:#999;">—</span>')
       return format_html(
        '{} to {}',
        obj.start_date.strftime('%d %b %Y'),
        obj.end_date.strftime('%d %b %Y')
    )
    validity_period.short_description = 'Validity'


    def days_remaining_display(self, obj):
      if not obj.end_date:
        return mark_safe('<span style="color:#999;">—</span>')

      days = (obj.end_date - timezone.now().date()).days

      if days <= 0:
            return mark_safe('<span style="color: #f44336; font-weight: 700;">⏰ Expired</span>')
      elif days <= 7:
          return format_html(
            '<span style="color: #ff9800; font-weight: 700;">⚠️ {} days left</span>',
            days
        )
      else:
           return format_html(
            '<span style="color: #4caf50; font-weight: 700;">✓ {} days left</span>',
            days
        )
    days_remaining_display.short_description = 'Days Remaining'


    def status_badge(self, obj):
     colors = {
        'active': '#4caf50',
        'expired': '#f44336',
        'pending': '#ff9800',
        'cancelled': '#999'
    }
     return format_html(
        '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 15px; font-weight: 600;">{}</span>',
        colors.get(obj.status, '#666'),
        obj.get_status_display().upper()
    )
    status_badge.short_description = 'Status'
    def approve_passes(self, request, queryset):
        """Approve selected monthly passes"""
        updated = queryset.update(
            status='active', 
            approved_by=request.user, 
            approved_at=timezone.now()
        )
        
        # ✅ Send approval email to users
        for monthly_pass in queryset:
            try:
                send_mail(
                    subject=f'✅ Monthly Pass Approved - {monthly_pass.pass_number}',
                    message=f'''
Dear {monthly_pass.user.get_full_name() or monthly_pass.user.username},

Your Monthly Pass has been APPROVED!

Pass Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pass Number: {monthly_pass.pass_number}
Vehicle: {monthly_pass.vehicle.license_plate}
Pass Type: {monthly_pass.pass_type.name}
Valid From: {monthly_pass.start_date.strftime('%d %b %Y')}
Valid Until: {monthly_pass.end_date.strftime('%d %b %Y')}
Amount: ₹{monthly_pass.amount}

Benefits:
✓ Unlimited entry/exit 24/7
✓ No parking fees during validity
✓ Priority parking access
✓ QR code quick entry

You can now use your monthly pass for FREE parking!
View your pass in Profile → My Passes section.

Thank you for choosing Pune Smart Parking!

Best regards,
Parkease Team
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[monthly_pass.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Error sending approval email: {str(e)}")
        
        self.message_user(request, f'✅ {updated} passes approved successfully. Approval emails sent.')
    approve_passes.short_description = "✅ Approve Selected Passes"
    
    def cancel_passes(self, request, queryset):
        """Cancel selected passes"""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'❌ {updated} passes cancelled.')
    cancel_passes.short_description = "❌ Cancel Selected Passes"
    
    def send_expiry_reminder(self, request, queryset):
        """Send expiry reminder to pass holders"""
        count = 0
        for monthly_pass in queryset.filter(status='active'):
            days = monthly_pass.days_until_expiry()
            if 0 < days <= 7:
                try:
                    send_mail(
                        subject=f'⏰ Monthly Pass Expiring Soon - {monthly_pass.pass_number}',
                        message=f'''
Dear {monthly_pass.user.get_full_name() or monthly_pass.user.username},

Your Monthly Pass is expiring soon!

Pass Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pass Number: {monthly_pass.pass_number}
Vehicle: {monthly_pass.vehicle.license_plate}
Expiry Date: {monthly_pass.end_date.strftime('%d %b %Y')}
Days Remaining: {days} days

⚠️ IMPORTANT: After expiry, regular parking charges will apply.

To continue enjoying FREE parking:
1. Renew your pass before {monthly_pass.end_date.strftime('%d %b %Y')}
2. Visit: Monthly Pass → Renew Pass
3. Or enable auto-renewal in your profile

Need help? Contact support: +91 9876543210

Best regards,
Parkease Team
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[monthly_pass.user.email],
                        fail_silently=True,
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Error sending expiry reminder: {str(e)}")
        
        self.message_user(request, f'📧 Expiry reminders sent to {count} pass holders.')
    send_expiry_reminder.short_description = "📧 Send Expiry Reminder"



# ==================== PRICING MANAGEMENT ====================
@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'pricing_type', 'vehicle_type', 'rate_display', 'daily_max', 'is_active']
    list_filter = ['pricing_type', 'vehicle_type', 'is_active']
    
    def rate_display(self, obj):
        return format_html('<strong style="color: #4caf50; font-size: 1.1rem;">₹{}/hr</strong>', obj.rate_per_hour)
    rate_display.short_description = 'Rate'


# ==================== NOTIFICATION MANAGEMENT ====================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title_display', 'notification_type_badge', 'send_to_all', 'is_active', 'created_by', 'created_at']
    list_filter = ['notification_type', 'is_active', 'send_to_all', 'created_at']
    search_fields = ['title', 'message']
    filter_horizontal = ['target_users']
    actions = ['activate_notifications', 'deactivate_notifications', 'send_to_all_users']
    
    fieldsets = (
        ('📧 Notification Details', {'fields': ('title', 'message', 'notification_type')}),
        ('👥 Target Audience', {'fields': ('send_to_all', 'target_users'), 
                                'description': 'Select specific users OR check "Send to All"'}),
        ('⚙️ Settings', {'fields': ('is_active',)}),
    )
    
    def title_display(self, obj):
        icons = {
            'announcement': '📢',
            'maintenance': '🔧',
            'payment': '💳',
            'pass_expiry': '⏰',
            'promotion': '🎉'
        }
        icon = icons.get(obj.notification_type, '📧')
        return format_html('{} <strong style="color: #667eea;">{}</strong>', icon, obj.title)
    title_display.short_description = 'Title'
    
    def notification_type_badge(self, obj):
        colors = {
            'announcement': '#2196f3',
            'maintenance': '#ff9800',
            'payment': '#f44336',
            'pass_expiry': '#9c27b0',
            'promotion': '#4caf50'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 12px;">{}</span>',
            colors.get(obj.notification_type, '#666'),
            obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Type'
    
    def activate_notifications(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'✅ {queryset.count()} notifications activated.')
    activate_notifications.short_description = "🟢 Activate Notifications"
    
    def deactivate_notifications(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'🔴 {queryset.count()} notifications deactivated.')
    deactivate_notifications.short_description = "⛔ Deactivate Notifications"
    
    def send_to_all_users(self, request, queryset):
        queryset.update(send_to_all=True)
        self.message_user(request, f'📢 {queryset.count()} notifications set to send to all users.')
    send_to_all_users.short_description = "📢 Send to All Users"
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== ENTRY/EXIT LOGS ====================
@admin.register(EntryExitLog)
class EntryExitLogAdmin(admin.ModelAdmin):
    list_display = ['log_type_badge', 'vehicle_display', 'gate_number', 'timestamp', 'qr_status', 'verified_by']
    list_filter = ['log_type', 'qr_scanned', 'timestamp']
    search_fields = ['session__vehicle__license_plate', 'gate_number']
    date_hierarchy = 'timestamp'
    
    def log_type_badge(self, obj):
        colors = {'entry': '#4caf50', 'exit': '#f44336'}
        icons = {'entry': '→', 'exit': '←'}
        return format_html('<span style="background: {}; color: white; padding: 5px 12px; border-radius: 15px; font-weight: 600;">{} {}</span>',
            colors.get(obj.log_type, '#666'), icons.get(obj.log_type, ''), obj.get_log_type_display())
    log_type_badge.short_description = 'Type'
    
    def vehicle_display(self, obj):
        return format_html('🚗 <strong>{}</strong>', obj.session.vehicle.license_plate)
    vehicle_display.short_description = 'Vehicle'
    
    def qr_status(self, obj):
        if obj.qr_scanned:
            return mark_safe('<span style="color: #4caf50;">✓ Scanned</span>')  # ✅ FIXED
        return mark_safe('<span style="color: #999;">Manual</span>')  # ✅ FIXED
    qr_status.short_description = 'QR Status'


# ==================== GALLERY MANAGEMENT ====================
@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['image_thumbnail', 'title', 'category_badge', 'is_active', 'uploaded_at', 'uploaded_by']
    list_filter = ['category', 'is_active', 'uploaded_at']
    search_fields = ['title', 'description']
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 8px;"/>', obj.image.url)
        return "No Image"
    image_thumbnail.short_description = 'Preview'
    
    def category_badge(self, obj):
        colors = {'parking_area': '#2196f3', 'floor_layout': '#4caf50', 'slot_map': '#ff9800', 'banner': '#9c27b0', 'facility': '#f44336'}
        return format_html('<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 600;">{}</span>',
            colors.get(obj.category, '#666'), obj.get_category_display())
    category_badge.short_description = 'Category'


# ==================== SYSTEM SETTINGS ====================
@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'contact_email', 'contact_phone', 'enable_qr_entry', 'enable_monthly_pass', 'updated_at']
    
    def has_add_permission(self, request):
        return not SystemSettings
    
    
    
    
    
    
    
    
    # Add these to your existing admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    ManagerProfile, CCTVCamera, CCTVFootage, 
    ManagerActivityLog, SecurityIncident
)

# ==================== MANAGER PROFILE ADMIN ====================
@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ['manager_display', 'employee_id', 'phone_number', 'shift_time', 
                    'assigned_lots_count', 'is_active_manager', 'joined_date']
    list_filter = ['is_active_manager', 'joined_date']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'employee_id', 'phone_number']
    filter_horizontal = ['assigned_parking_lots']
    actions = ['activate_managers', 'deactivate_managers']
    
    fieldsets = (
        ('👤 Manager Information', {
            'fields': ('user', 'employee_id', 'phone_number', 'profile_image')
        }),
        ('🅿️ Parking Assignment', {
            'fields': ('assigned_parking_lots',)
        }),
        ('🕐 Shift Timing', {
            'fields': ('shift_start_time', 'shift_end_time')
        }),
        ('⚙️ Status', {
            'fields': ('is_active_manager',)
        }),
    )
    
    def manager_display(self, obj):
        status = '🟢' if obj.is_active_manager else '🔴'
        return format_html('{} <strong style="color: #6366f1;">👨‍💼 {}</strong>', 
                          status, obj.user.get_full_name() or obj.user.username)
    manager_display.short_description = 'Manager'
    
    def shift_time(self, obj):
        if obj.shift_start_time and obj.shift_end_time:
            return format_html('<span style="color: #2196f3;">🕐 {} - {}</span>',
                             obj.shift_start_time.strftime('%I:%M %p'),
                             obj.shift_end_time.strftime('%I:%M %p'))
        return mark_safe('<span style="color: #999;">Not Set</span>')
    shift_time.short_description = 'Shift Timing'
    
    def assigned_lots_count(self, obj):
        count = obj.assigned_parking_lots.count()
        return format_html('<strong style="color: #4caf50;">{} Location(s)</strong>', count)
    assigned_lots_count.short_description = 'Assigned Locations'
    
    def activate_managers(self, request, queryset):
        queryset.update(is_active_manager=True)
        self.message_user(request, f'✅ {queryset.count()} managers activated.')
    activate_managers.short_description = "🟢 Activate Managers"
    
    def deactivate_managers(self, request, queryset):
        queryset.update(is_active_manager=False)
        self.message_user(request, f'🔴 {queryset.count()} managers deactivated.')
    deactivate_managers.short_description = "⛔ Deactivate Managers"


# ==================== CCTV CAMERA ADMIN ====================
@admin.register(CCTVCamera)
class CCTVCameraAdmin(admin.ModelAdmin):
    list_display = ['camera_display', 'parking_lot', 'camera_type_badge', 
                    'camera_ip', 'status_badge', 'is_recording', 'installed_date']
    list_filter = ['parking_lot', 'camera_type', 'status', 'is_recording']
    search_fields = ['camera_name', 'camera_ip', 'parking_lot__name']
    actions = ['activate_cameras', 'deactivate_cameras', 'start_recording', 'stop_recording']
    
    fieldsets = (
        ('📹 Camera Details', {
            'fields': ('camera_name', 'parking_lot', 'camera_type', 'location_description')
        }),
        ('🌐 Network Configuration', {
            'fields': ('camera_ip', 'rtsp_url', 'stream_url')
        }),
        ('⚙️ Settings', {
            'fields': ('status', 'is_recording', 'last_maintenance')
        }),
    )
    
    def camera_display(self, obj):
        icons = {'entry': '🚪', 'exit': '🚪', 'parking': '🅿️', 'overview': '👁️'}
        icon = icons.get(obj.camera_type, '📹')
        status = '🟢' if obj.status == 'active' else '🔴' if obj.status == 'inactive' else '🔧'
        return format_html('{} {} <strong style="color: #6366f1;">{}</strong>', status, icon, obj.camera_name)
    camera_display.short_description = 'Camera'
    
    def camera_type_badge(self, obj):
        colors = {'entry': '#4caf50', 'exit': '#f44336', 'parking': '#2196f3', 'overview': '#ff9800'}
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 10px; font-weight: 600;">{}</span>',
            colors.get(obj.camera_type, '#666'), obj.get_camera_type_display()
        )
    camera_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {'active': '#10b981', 'inactive': '#ef4444', 'maintenance': '#f59e0b'}
        icons = {'active': '🟢', 'inactive': '🔴', 'maintenance': '🔧'}
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 12px; font-weight: 600;">{} {}</span>',
            colors.get(obj.status, '#666'), icons.get(obj.status, ''), obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def activate_cameras(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f'✅ {queryset.count()} cameras activated.')
    activate_cameras.short_description = "🟢 Activate Cameras"
    
    def deactivate_cameras(self, request, queryset):
        queryset.update(status='inactive')
        self.message_user(request, f'🔴 {queryset.count()} cameras deactivated.')
    deactivate_cameras.short_description = "⛔ Deactivate Cameras"
    
    def start_recording(self, request, queryset):
        queryset.update(is_recording=True)
        self.message_user(request, f'▶️ {queryset.count()} cameras started recording.')
    start_recording.short_description = "▶️ Start Recording"
    
    def stop_recording(self, request, queryset):
        queryset.update(is_recording=False)
        self.message_user(request, f'⏸️ {queryset.count()} cameras stopped recording.')
    stop_recording.short_description = "⏸️ Stop Recording"


# ==================== CCTV FOOTAGE ADMIN ====================
@admin.register(CCTVFootage)
class CCTVFootageAdmin(admin.ModelAdmin):
    list_display = ['footage_display', 'camera', 'footage_type_badge', 'vehicle_number', 
                    'timestamp', 'duration_display', 'file_size_display', 'verified_by']
    list_filter = ['footage_type', 'camera__parking_lot', 'camera', 'timestamp']
    search_fields = ['vehicle_number_detected', 'camera__camera_name', 'notes']
    readonly_fields = ['timestamp', 'file_size_mb']
    date_hierarchy = 'timestamp'
    
    def footage_display(self, obj):
        if obj.snapshot_image:
            return format_html(
                '<img src="{}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 8px;"/>',
                obj.snapshot_image.url
            )
        return mark_safe('<span style="color: #999;">📹 Video Only</span>')
    footage_display.short_description = 'Preview'
    
    def footage_type_badge(self, obj):
        colors = {'entry': '#4caf50', 'exit': '#f44336', 'incident': '#ff9800', 'scheduled': '#2196f3'}
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 10px; font-weight: 600;">{}</span>',
            colors.get(obj.footage_type, '#666'), obj.get_footage_type_display()
        )
    footage_type_badge.short_description = 'Type'
    
    def vehicle_number(self, obj):
        if obj.vehicle_number_detected:
            return format_html('<strong style="color: #2196f3;">🚗 {}</strong>', obj.vehicle_number_detected)
        return mark_safe('<span style="color: #999;">Not Detected</span>')
    vehicle_number.short_description = 'Vehicle'
    
    def duration_display(self, obj):
        mins = obj.duration_seconds // 60
        secs = obj.duration_seconds % 60
        return format_html('<span style="color: #666;">{}m {}s</span>', mins, secs)
    duration_display.short_description = 'Duration'
    
    def file_size_display(self, obj):
        return format_html('<span style="color: #666;">{} MB</span>', obj.file_size_mb)
    file_size_display.short_description = 'Size'


# ==================== MANAGER ACTIVITY LOG ADMIN ====================
@admin.register(ManagerActivityLog)
class ManagerActivityLogAdmin(admin.ModelAdmin):
    list_display = ['manager_display', 'action_type_badge', 'vehicle_info', 'timestamp', 'ip_address']
    list_filter = ['action_type', 'timestamp', 'manager']
    search_fields = ['manager__username', 'description', 'vehicle__license_plate']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def manager_display(self, obj):
        return format_html('<strong style="color: #6366f1;">👨‍💼 {}</strong>', obj.manager.get_full_name() or obj.manager.username)
    manager_display.short_description = 'Manager'
    
    def action_type_badge(self, obj):
        colors = {
            'entry_verify': '#4caf50',
            'exit_verify': '#f44336',
            'manual_entry': '#ff9800',
            'manual_exit': '#ff9800',
            'booking_override': '#9c27b0',
            'slot_change': '#2196f3',
            'incident_report': '#f44336',
            'camera_check': '#666'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 10px; font-weight: 600;">{}</span>',
            colors.get(obj.action_type, '#666'), obj.get_action_type_display()
        )
    action_type_badge.short_description = 'Action'
    
    def vehicle_info(self, obj):
        if obj.vehicle:
            return format_html('<strong>🚗 {}</strong>', obj.vehicle.license_plate)
        return mark_safe('<span style="color: #999;">—</span>')
    vehicle_info.short_description = 'Vehicle'


# ==================== SECURITY INCIDENT ADMIN ====================
@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ['incident_display', 'parking_lot', 'incident_type_badge', 
                    'severity_badge', 'status_badge', 'incident_time', 'assigned_to']
    list_filter = ['incident_type', 'severity', 'status', 'parking_lot', 'incident_time']
    search_fields = ['description', 'vehicle__license_plate', 'resolution_notes']
    actions = ['mark_investigating', 'mark_resolved', 'mark_closed']
    date_hierarchy = 'incident_time'
    
    fieldsets = (
        ('🚨 Incident Details', {
            'fields': ('parking_lot', 'incident_type', 'severity', 'description', 'incident_time')
        }),
        ('🚗 Vehicle Information', {
            'fields': ('vehicle',)
        }),
        ('📹 Evidence', {
            'fields': ('cctv_footage',)
        }),
        ('👥 Assignment', {
            'fields': ('reported_by', 'assigned_to', 'status')
        }),
        ('✅ Resolution', {
            'fields': ('resolved_time', 'resolution_notes')
        }),
    )
    
    def incident_display(self, obj):
        return format_html('🚨 <strong style="color: #f44336;">INC-{:05d}</strong>', obj.id)
    incident_display.short_description = 'Incident ID'
    
    def incident_type_badge(self, obj):
        colors = {
            'unauthorized_entry': '#f44336',
            'suspicious_vehicle': '#ff9800',
            'vehicle_damage': '#ff5722',
            'theft_attempt': '#f44336',
            'system_breach': '#9c27b0',
            'other': '#666'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 10px; font-weight: 600;">{}</span>',
            colors.get(obj.incident_type, '#666'), obj.get_incident_type_display()
        )
    incident_type_badge.short_description = 'Type'
    
    def severity_badge(self, obj):
        colors = {'low': '#4caf50', 'medium': '#ff9800', 'high': '#f44336', 'critical': '#9c27b0'}
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 12px; font-weight: 700;">{}</span>',
            colors.get(obj.severity, '#666'), obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'
    
    def status_badge(self, obj):
        colors = {'reported': '#2196f3', 'investigating': '#ff9800', 'resolved': '#4caf50', 'closed': '#666'}
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 12px; font-weight: 600;">{}</span>',
            colors.get(obj.status, '#666'), obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def mark_investigating(self, request, queryset):
        queryset.update(status='investigating')
        self.message_user(request, f'🔍 {queryset.count()} incidents marked as investigating.')
    mark_investigating.short_description = "🔍 Mark as Investigating"
    
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='resolved', resolved_time=timezone.now())
        self.message_user(request, f'✅ {queryset.count()} incidents resolved.')
    mark_resolved.short_description = "✅ Mark as Resolved"
    
    def mark_closed(self, request, queryset):
        queryset.update(status='closed')
        self.message_user(request, f'🔒 {queryset.count()} incidents closed.')
    mark_closed.short_description = "🔒 Close Incidents"