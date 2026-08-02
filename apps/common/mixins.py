"""
Reusable mixins for StayHub.

BranchScopedQuerysetMixin
--------------------------
Automatically filters querysets so that branch-level staff roles
(receptionist, housekeeping, accountant) only see records belonging
to their own hotel.  Manager and System Administrator roles see all
records.

Usage
-----
    class MyViewSet(BranchScopedQuerysetMixin, ModelViewSet):
        queryset = MyModel.objects.all()
        serializer_class = MySerializer

The mixin overrides get_queryset() and applies the hotel filter
based on request.user.hotel_id.  If the model doesn't have a direct
hotel FK, pass a `branch_field` attribute on the viewset:

    class MyViewSet(BranchScopedQuerysetMixin, ModelViewSet):
        queryset = MyModel.objects.all()
        serializer_class = MySerializer
        branch_field = "reservation__hotel"   # traverses FK chain
"""

from rest_framework.exceptions import PermissionDenied


MANAGER_ROLES = {"manager", "admin"}


class BranchScopedQuerysetMixin:
    """
    Restricts querysets to the current user's hotel (branch) unless
    the user holds a manager / admin role.
    """

    # Override in the viewset when the model's hotel FK is not direct.
    branch_field = "hotel"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Anonymous users get nothing (shouldn't reach here if auth is
        # configured, but be defensive).
        if not user or not user.is_authenticated:
            return qs.none()

        # Manager / admin see everything.
        role = (user.role or "").lower()
        if role in MANAGER_ROLES:
            return qs

        # Branch-level staff must be assigned to a hotel.
        hotel_id = user.hotel_id
        if hotel_id is None:
            return qs.none()

        # Apply the branch filter using the configured field path.
        # branch_field = None means the viewset scopes the queryset itself.
        if self.branch_field is None:
            return qs
        filter_key = {self.branch_field: hotel_id}
        return qs.filter(**filter_key)