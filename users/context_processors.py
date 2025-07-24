def user_notifications(request):
    if request.user.is_authenticated:
        notifications = request.user.notifications.order_by('-created_at')[:10]
    else:
        notifications = []
    return {'notifications': notifications}