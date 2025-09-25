from .models import ActivityLog

def log_activity(user, app, table, action, description=""):
    ActivityLog.objects.create(
        user=user,
        role=getattr(user, "role", "staff"),
        app=app,
        table=table,
        action=action,
        description=description
    )