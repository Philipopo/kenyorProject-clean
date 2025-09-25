# accounts/signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import PagePermission, ActionPermission, ALL_PAGES, ALL_ACTIONS, PERMISSION_ROLES, PRODUCT_DOCUMENTATION_PAGES, WAREHOUSE_PAGES, WAREHOUSE_ACTIONS, PRODUCT_DOCUMENTATION_ACTIONS

@receiver(post_migrate, sender=None)
def create_permissions(sender, **kwargs):
    if sender.name == 'accounts':
        # Create PagePermission records
        for page in ALL_PAGES:
            role = (
                PERMISSION_ROLES['product_documentation'] if page in PRODUCT_DOCUMENTATION_PAGES
                else PERMISSION_ROLES['warehouse'] if page in WAREHOUSE_PAGES
                else PERMISSION_ROLES['default']
            )
            obj, created = PagePermission.objects.get_or_create(page_name=page, defaults={'min_role': role})
            if not created and obj.min_role != role:
                obj.min_role = role
                obj.save()

        # Create ActionPermission records
        for action in ALL_ACTIONS:
            role = (
                PERMISSION_ROLES['delete_product_inflow'] if action == 'delete_product_inflow'
                else PERMISSION_ROLES['delete_product_outflow'] if action == 'delete_product_outflow'
                else PERMISSION_ROLES['product_documentation'] if action in PRODUCT_DOCUMENTATION_ACTIONS
                else PERMISSION_ROLES['warehouse'] if action in WAREHOUSE_ACTIONS
                else PERMISSION_ROLES['default']
            )
            obj, created = ActionPermission.objects.get_or_create(action_name=action, defaults={'min_role': role})
            if not created and obj.min_role != role:
                obj.min_role = role
                obj.save()