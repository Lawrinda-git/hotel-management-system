"""
Reusable mixins for StayHub.

BranchScopedQuerysetMixin
--------------------------
Automatically filters querysets so that ALL staff roles only see records
belonging to their own hotel.  This includes managers — managers can only
see data for their assigned hotel.  Superusers bypass the hotel filter.

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


MANAGER_ROLES = {"admin", "manager"}


class BranchScopedQuerysetMixin:
    """
    Restricts querysets to the current user's assigned hotel.
    All staff roles, including manager, are scoped to their hotel.
    Superusers bypass the hotel filter.
    """

    # Override in the viewset when the model's hotel FK is not direct.
    branch_field = "hotel"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Anonymous users get nothing.
        if not user or not user.is_authenticated:
            return qs.none()

        # Superusers see everything.
        if getattr(user, "is_superuser", False):
            return qs

        # All staff must be assigned to a hotel.
        hotel_id = user.hotel_id
        if hotel_id is None:
            return qs.none()

        # Apply the branch filter using the configured field path.
        # branch_field = None means the viewset scopes the queryset itself.
        if self.branch_field is None:
            return qs
        filter_key = {self.branch_field: hotel_id}
        return qs.filter(**filter_key)