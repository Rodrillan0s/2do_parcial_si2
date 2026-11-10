import sys
from app.core import security, tenant_guard, saas_errors, commerce_tenant, db_init, rbac_migration
from app.shared import email_service, cloudinary_service

sys.modules['app.utils.security'] = security
sys.modules['app.utils.tenant_guard'] = tenant_guard
sys.modules['app.utils.saas_errors'] = saas_errors
sys.modules['app.utils.commerce_tenant'] = commerce_tenant
sys.modules['app.utils.db_init'] = db_init
sys.modules['app.utils.rbac_migration'] = rbac_migration
sys.modules['app.utils.email_service'] = email_service
sys.modules['app.utils.cloudinary_service'] = cloudinary_service
