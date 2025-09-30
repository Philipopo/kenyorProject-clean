# procurement/utils.py
import json
from django.core.serializers.json import DjangoJSONEncoder
from .models import ProcurementAuditLog

def log_procurement_action(user, action, model_name, object_id, details=None, instance=None):
    """
    Comprehensive audit logging function
    """
    log_details = details or {}
    
    # Add instance details if available
    if instance:
        if hasattr(instance, 'to_dict'):
            log_details['object_data'] = instance.to_dict()
        else:
            # Generic serialization
            try:
                from django.forms.models import model_to_dict
                log_details['object_data'] = model_to_dict(instance)
            except:
                log_details['object_data'] = str(instance)
    
    # Create audit log
    ProcurementAuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=log_details
    )