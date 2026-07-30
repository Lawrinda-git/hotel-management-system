def stayhub_context(request):
    """Expose small, safe identity/navigation values to every template."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"display_name": "Guest", "user_role": "guest"}
    name = user.get_full_name().strip() or getattr(user, "staff_name", "") or user.get_username()
    return {"display_name": name, "user_role": getattr(user, "role", "guest") or "guest"}
