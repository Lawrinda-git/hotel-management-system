from django.db import models


class Notification(models.Model):
    """System notification for critical actions."""
    
    class NotificationType(models.TextChoices):
        USER_CREATED = "user_created", "User Created"
        USER_DELETED = "user_deleted", "User Deleted"
        BOOKING_CREATED = "booking_created", "Booking Created"
        BOOKING_CANCELLED = "booking_cancelled", "Booking Cancelled"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"
        LOGIN_SUCCESS = "login_success", "Login Success"
        LOGIN_FAILED = "login_failed", "Login Failed"
        PASSWORD_CHANGED = "password_changed", "Password Changed"
    
    user = models.ForeignKey("accounts.Staff", on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.notification_type} - {self.user.username}"