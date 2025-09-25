# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.conf import settings
import secrets

ROLE_LEVELS = {
    "staff": 1,
    "finance_manager": 2,
    "operations_manager": 3,
    "md": 4,
    "admin": 5,
}

class ApiKey(models.Model):
    key = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, blank=True, help_text="Descriptive name for the API key")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_api_keys',
        help_text="User who created this API key"
    )
    is_active = models.BooleanField(default=True)
    is_viewed = models.BooleanField(default=False, help_text="True if key has been viewed")

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(32)  # Generates a 64-char secure key
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name or 'API Key'} ({self.user.email})"



class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role='staff', **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(email, password, role='admin', **extra_fields)

ROLE_CHOICES = (
    ('staff', 'Staff'),
    ('finance_manager', 'Finance Manager'),
    ('operations_manager', 'Operations Manager'),
    ('md', 'Managing Director'),
    ('admin', 'Admin'),
)

NIGERIAN_STATES = (
    ('Abia', 'Abia'), ('Adamawa', 'Adamawa'), ('Akwa Ibom', 'Akwa Ibom'), ('Anambra', 'Anambra'),
    ('Bauchi', 'Bauchi'), ('Bayelsa', 'Bayelsa'), ('Benue', 'Benue'), ('Borno', 'Borno'),
    ('Cross River', 'Cross River'), ('Delta', 'Delta'), ('Ebonyi', 'Ebonyi'), ('Edo', 'Edo'),
    ('Ekiti', 'Ekiti'), ('Enugu', 'Enugu'), ('FCT', 'FCT'), ('Gombe', 'Gombe'),
    ('Imo', 'Imo'), ('Jigawa', 'Jigawa'), ('Kaduna', 'Kaduna'), ('Kano', 'Kano'),
    ('Katsina', 'Katsina'), ('Kebbi', 'Kebbi'), ('Kogi', 'Kogi'), ('Kwara', 'Kwara'),
    ('Lagos', 'Lagos'), ('Nasarawa', 'Nasarawa'), ('Niger', 'Niger'), ('Ogun', 'Ogun'),
    ('Ondo', 'Ondo'), ('Osun', 'Osun'), ('Oyo', 'Oyo'), ('Plateau', 'Plateau'),
    ('Rivers', 'Rivers'), ('Sokoto', 'Sokoto'), ('Taraba', 'Taraba'), ('Yobe', 'Yobe'),
    ('Zamfara', 'Zamfara'),
)

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='staff')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    full_name = models.CharField(max_length=100, blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    EMAIL_FIELD = 'email'
    def __str__(self):
        return self.email

def profile_image_upload_path(instance, filename):
    return f'profile_images/user_{instance.user.id}/{filename}'

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, blank=True)
    profile_image = models.ImageField(upload_to=profile_image_upload_path, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, choices=NIGERIAN_STATES, default='Lagos')
    last_location_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.full_name or self.user.email

class PagePermission(models.Model):
    page_name = models.CharField(max_length=100, unique=True)
    min_role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='staff')
    def __str__(self):
        return f"Page: {self.page_name} requires {self.min_role}+"

class ActionPermission(models.Model):
    action_name = models.CharField(max_length=100, unique=True)
    min_role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='staff')
    def __str__(self):
        return f"Action: {self.action_name} requires {self.min_role}+"

PERMISSION_ROLES = {
    'default': 'staff',
    'product_documentation': 'finance_manager',
    'delete_product_inflow': 'admin',
    'delete_product_outflow': 'admin',
    'warehouse': 'finance_manager',
    'update_location': 'staff',
}

INVENTORY_PAGES = [
    'inventory_metrics',
    'storage_bins',
    'expired_items',
    'items',
    'stock_records',
    'expiry_tracked_items',
    'aisle_rack_dashboard',
    'update_expiry_tracked_item',
    'delete_expiry_tracked_item',  # Added
]

INVENTORY_ACTIONS = [
    'create_storage_bin', 'create_item', 'create_stock_record', 'create_expiry_tracked_item',
    'update_storage_bin', 'update_item', 'update_stock_record', 'update_expiry_tracked_item',
    'delete_item', 'delete_storage_bin', 'delete_stock_record', 'delete_expiry_tracked_item',
     'generate_api_key',  # Added
    'view_api_key',      # Added
    'delete_api_key',
    'create_warehouse', 'update_warehouse', 'delete_warehouse', 
]

PROCUREMENT_PAGES = [
    "requisitions", "purchase_orders", "po_items", "receiving", "goods_receipts", "vendors", "procurement_audit_logs"
]

PROCUREMENT_ACTIONS = [
    "create_requisition", "approve_requisition", "reject_requisition", "update_requisition", "delete_requisition",
    "create_purchase_order", "approve_purchase_order", "update_purchase_order", "delete_purchase_order",
    "create_po_item", "update_po_item", "delete_po_item",
    "create_receiving", "update_receiving", "delete_receiving",
    "add_vendor", "update_vendor", "delete_vendor",
    "view_procurement_audit_logs"
]

RECEIPT_PAGES = ["receipt_archive", "stock_receipts", "signing_receipts"]
RECEIPT_ACTIONS = [
    "create_receipt", "create_stock_receipt", "create_signing_receipt",
    "update_receipt", "delete_receipt",  # Added
    "update_stock_receipt", "delete_stock_receipt",  # Added
    "update_signing_receipt", "delete_signing_receipt"  # Added
]

FINANCE_PAGES = ["finance_categories", "finance_transactions", "finance_overview"]
FINANCE_ACTIONS = [
    "create_finance_category", "create_finance_transaction",
    "update_finance_category", "delete_finance_category",
    "update_finance_transaction", "delete_finance_transaction",
]

RENTALS_PAGES = ["rentals_active", "rentals_equipment", "rentals_payments"]
RENTALS_ACTIONS = ["create_rental", "update_rental", "delete_rental", "create_equipment", "create_payment"]

ANALYTICS_PAGES = ["analytics_dwell", "analytics_eoq", "analytics_stock"]
ANALYTICS_ACTIONS = ["create_dwell", "create_eoq", "create_stock_analytics"]

PRODUCT_DOCUMENTATION_PAGES = ["product_documentation", "product_inflow", "product_outflow"]
PRODUCT_DOCUMENTATION_ACTIONS = [
    "create_product_inflow", "update_product_inflow", "delete_product_inflow",
    "create_product_outflow", "update_product_outflow", "delete_product_outflow",
]

PRODUCT_DOCUMENTATION_NEW_PAGES = ["product_documentation_new", "product_inflow_new", "product_outflow_inflow_new"]
PRODUCT_DOCUMENTATION_NEW_ACTIONS = [
    "create_product_new_inflow", "update_product_new_inflow", "delete_product_new_inflow",
    "create_product__new_outflow", "update_product_new_outflow", "delete_product_outflow",
]

RENTALS_ACTIONS = [
    "create_rental", "update_rental", "delete_rental",
    "create_equipment", "update_equipment", "delete_equipment",
    "create_payment", "update_payment", "delete_payment"
]


WAREHOUSE_NEW_PAGES = ['warehouse_new']
WAREHOUSE_NEW_ACTIONS = ['create_warehouse_new_item', 'update_warehouse_item', 'delete_warehouse_item', 'update_location']

WAREHOUSE_PAGES = ['warehouse_']
WAREHOUSE_ACTIONS = ['create_warehouse_item', 'update_warehouse_new_item', 'delete_warehouse_new_item', 'update_location']


BRANDING_PAGES = ["branding", "company_branding"]  # Added company_branding
ANNOUNCEMENT_PAGES = ["announcement"]

BRANDING_ACTIONS = ["update_branding", "create_branding", "delete_branding"]
ANNOUNCEMENT_ACTIONS = ["create_announcement", "update_announcement", "delete_announcement"]

# Add these to your ERP and Tracker pages if they don't exist
ERP_PAGES = ['erp_integration']
TRACKER_PAGES = ['trackers']

ALL_PAGES = (
    INVENTORY_PAGES + PROCUREMENT_PAGES + RECEIPT_PAGES + FINANCE_PAGES +
    RENTALS_PAGES + ANALYTICS_PAGES + PRODUCT_DOCUMENTATION_PAGES + PRODUCT_DOCUMENTATION_NEW_PAGES + WAREHOUSE_NEW_PAGES + WAREHOUSE_PAGES + BRANDING_PAGES + ANNOUNCEMENT_PAGES +
    ERP_PAGES + TRACKER_PAGES  # Added new pages
)

ALL_ACTIONS = (
    INVENTORY_ACTIONS + PROCUREMENT_ACTIONS + RECEIPT_ACTIONS + FINANCE_ACTIONS +
    RENTALS_ACTIONS + ANALYTICS_ACTIONS + PRODUCT_DOCUMENTATION_ACTIONS + PRODUCT_DOCUMENTATION_NEW_ACTIONS + 
    WAREHOUSE_NEW_ACTIONS + WAREHOUSE_ACTIONS + BRANDING_ACTIONS + ANNOUNCEMENT_ACTIONS
)