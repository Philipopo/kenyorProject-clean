# accounts/permissions.py
from rest_framework.permissions import BasePermission
from .models import PagePermission, ActionPermission
from rest_framework import permissions
from django.conf import settings
from .models import ApiKey
import logging

logger = logging.getLogger(__name__)

class APIKeyPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # Log the request method and parameters for debugging
        logger.debug(f"[APIKeyPermission] Request method: {request.method}, Query params: {request.query_params}, Headers: {request.headers}")
        # Check query parameter first (for GET requests)
        api_key = request.query_params.get('api_key')
        if not api_key:
            # Fallback to header (for POST requests)
            api_key = request.headers.get('X-API-Key')
        if not api_key:
            logger.warning("[APIKeyPermission] No API key provided in query params or headers")
            return False
        try:
            api_key_obj = ApiKey.objects.get(key=api_key, is_active=True)
            logger.info(f"[APIKeyPermission] Valid API key found for user: {api_key_obj.user.email}, key: {api_key[:8]}...")
            return True
        except ApiKey.DoesNotExist:
            logger.error(f"[APIKeyPermission] Invalid or inactive API key: {api_key[:8]}...")
            return False




ROLE_LEVELS = {
    'staff': 1,
    'finance_manager': 2,
    'operations_manager': 3,
    'md': 4,
    'admin': 5,
}



class HasMinimumRole(BasePermission):
    """
    Grant access only if user has the required role level or higher.
    """
    def has_permission(self, request, view):
        required_level = getattr(view, 'required_role_level', 1)
        user_role = getattr(request.user, 'role', 'staff')
        user_level = ROLE_LEVELS.get(user_role.lower(), 0)  # ensure lowercase
        return user_level >= required_level

class DynamicPermission(BasePermission):
    """
    Central, DB-backed permission check.

    Works with PagePermission (by view.page_permission_name) and
    ActionPermission (by view.action_permission_name or auto-inferred).

    If a PagePermission/ActionPermission record is missing in DB, access is denied
    (fail-safe deny).
    """
    # Optional helpers to infer create actions from request + page
    CREATE_ACTIONS = {
        'requisitions': 'create_requisition',
        'purchase_orders': 'create_purchase_order',
        'po_items': 'create_po_item',
        'receiving': 'create_receiving',
        'goods_receipts': 'create_goods_receipt',
        'vendors': 'add_vendor',
        'receipt_archive': 'create_receipt',
        'stock_receipts': 'create_stock_receipt',
        'signing_receipts': 'create_signing_receipt',
        'rentals_active': 'create_rental',  # Added
        'rentals_equipment': 'create_equipment',  # Added
        'rentals_payments': 'create_payment',  # Added
        'analytics_dwell': 'create_dwell',  # Added
        'analytics_eoq': 'create_eoq',  # Added
        'analytics_stock': 'create_stock_analytics',  # Added
    }
    DELETE_ACTIONS = {
        'vendors': 'delete_vendor',
        'rentals_active': 'delete_rental',  # Added
    }

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        user_role = getattr(user, 'role', 'staff') or 'staff'
        user_level = ROLE_LEVELS.get(user_role.lower(), 0)

        # ---- Page check ----
        page_name = getattr(view, 'page_permission_name', None)
        if page_name:
            try:
                page_perm = PagePermission.objects.get(page_name=page_name)
                required_level = ROLE_LEVELS[page_perm.min_role]
                if user_level < required_level:
                    return False
            except PagePermission.DoesNotExist:
                # No config => deny
                return False

        # ---- Action check ----
        action_name = getattr(view, 'action_permission_name', None)

        # If not explicitly set, try to infer actions
        if not action_name and page_name:
            if request.method == 'POST':
                action_name = self.CREATE_ACTIONS.get(page_name)
            elif request.method == 'DELETE':
                action_name = self.DELETE_ACTIONS.get(page_name)
            else:
                action_attr = getattr(view, 'action', None)
                if action_attr in ('approve', 'approve_requisition') and page_name == 'requisitions':
                    action_name = 'approve_requisition'
                elif action_attr in ('approve', 'approve_purchase_order') and page_name == 'purchase_orders':
                    action_name = 'approve_purchase_order'

        # If we have an action to enforce, check it against DB
        if action_name:
            try:
                action_perm = ActionPermission.objects.get(action_name=action_name)
                required_level = ROLE_LEVELS[action_perm.min_role]
                if user_level < required_level:
                    return False
            except ActionPermission.DoesNotExist:
                # No config => deny
                return False

        # If no action_name applicable, page-level decision already handled.
        return True