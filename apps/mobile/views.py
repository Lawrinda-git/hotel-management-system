import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from apps.rooms.models import Room
from apps.reservations.models import Reservation, RoomReservation
from apps.guests.models import Guest
from apps.notifications.models import Notification


@require_http_methods(["GET"])
def mobile_rooms(request):
    """API endpoint for mobile app to get available rooms."""
    rooms = Room.objects.select_related("hotel", "room_type").filter(status=Room.RoomStatus.AVAILABLE)
    data = [
        {
            "id": room.id,
            "room_number": room.room_number,
            "floor": room.floor,
            "type": room.room_type.type_name if room.room_type else None,
            "price_per_night": str(room.price_per_night),
            "hotel": room.hotel.hotel_name,
        }
        for room in rooms
    ]
    return JsonResponse({"rooms": data})


@require_http_methods(["POST"])
def mobile_checkin(request):
    """API endpoint for mobile check-in."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)
    
    reservation_id = payload.get("reservation_id")
    room_id = payload.get("room_id")
    
    try:
        reservation = Reservation.objects.select_related("hotel").get(pk=reservation_id)
        room = Room.objects.get(pk=room_id, hotel=reservation.hotel)
    except (Reservation.DoesNotExist, Room.DoesNotExist):
        return JsonResponse({"detail": "Invalid reservation or room."}, status=404)
    
    if room.status != Room.RoomStatus.AVAILABLE:
        return JsonResponse({"detail": "Room not available for check-in."}, status=409)
    
    # Update room status
    room.status = Room.RoomStatus.OCCUPIED
    room.reservation = reservation
    room.housekeeping_status = Room.HousekeepingStatus.OUT_OF_SERVICE
    room.save(update_fields=["status", "reservation", "housekeeping_status"])
    
    # Create room reservation link
    RoomReservation.objects.create(resv=reservation, room=room)
    
    return JsonResponse({
        "detail": "Checked in successfully.",
        "room": room.room_number,
        "guest": reservation.guest.guest_name,
    })


@require_http_methods(["POST"])
def mobile_checkout(request):
    """API endpoint for mobile check-out."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)
    
    reservation_id = payload.get("reservation_id")
    
    try:
        reservation = Reservation.objects.select_related("hotel").get(pk=reservation_id)
    except Reservation.DoesNotExist:
        return JsonResponse({"detail": "Invalid reservation."}, status=404)
    
    # Update room status
    rooms = Room.objects.filter(reservation=reservation)
    for room in rooms:
        room.status = Room.RoomStatus.AVAILABLE
        room.reservation = None
        room.housekeeping_status = Room.HousekeepingStatus.DIRTY
        room.save(update_fields=["status", "reservation", "housekeeping_status"])
    
    return JsonResponse({"detail": "Checked out successfully."})


@login_required(login_url="staff_login")
@require_http_methods(["POST"])
def mobile_housekeeping_update(request):
    """API endpoint for housekeeping to update room status."""
    room_id = request.POST.get("room_id")
    status = request.POST.get("status")
    
    try:
        room = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return JsonResponse({"detail": "Room not found."}, status=404)
    
    if status in dict(Room.HousekeepingStatus.choices):
        room.housekeeping_status = status
        # If clean, make room available if not occupied
        if status in [Room.HousekeepingStatus.CLEAN, Room.HousekeepingStatus.INSPECTED]:
            if room.status == Room.RoomStatus.AVAILABLE:
                room.housekeeping_status = Room.HousekeepingStatus.CLEAN
        room.save(update_fields=["housekeeping_status"])
        
        # Create notification
        Notification.objects.create(
            user=request.user,
            notification_type=Notification.NotificationType.USER_CREATED,
            message=f"Room {room.room_number} status updated to {status}",
        )
        
        return JsonResponse({"detail": "Status updated.", "status": status})
    
    return JsonResponse({"detail": "Invalid status."}, status=400)