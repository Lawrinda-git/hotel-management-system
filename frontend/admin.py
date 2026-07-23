from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from apps.accounts.models import Staff
from apps.hotels.models import Hotel, Department
from apps.rooms.models import Room, RoomType, Maintenance
from apps.guests.models import Guest
from apps.reservations.models import Reservation
from apps.billing.models import Invoice, Payment
from apps.notifications.models import Notification


@admin.register(Staff)
class StaffAdmin(UserAdmin):
    list_display = ('staff_name', 'email', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'department')
    search_fields = ('staff_name', 'email', 'username')
    ordering = ('staff_name',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('staff_name', 'email', 'staff_phone', 'first_name', 'last_name')}),
        ('Work info', {'fields': ('role', 'department', 'hotel', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'staff_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('hotel_name', 'hotel_address', 'created_at')
    search_fields = ('hotel_name', 'hotel_address')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('dept_name', 'hotel')
    list_filter = ('hotel',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'hotel', 'status', 'housekeeping_status')
    list_filter = ('status', 'housekeeping_status', 'hotel')
    search_fields = ('room_number',)


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name', 'hotel', 'price_per_night')
    list_filter = ('hotel',)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('guest_name', 'guest_email', 'guest_phone', 'nationality')
    search_fields = ('guest_name', 'guest_email')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'hotel', 'status', 'check_in', 'check_out')
    list_filter = ('status', 'hotel')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'total_amount', 'status')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'status', 'payment_date')
    list_filter = ('method', 'status')


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ('room', 'issue', 'status', 'report_date')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
