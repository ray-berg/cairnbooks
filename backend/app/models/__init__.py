# Import all models here so SQLAlchemy's mapper registry (and Alembic's
# autogenerate support) can discover them when this package is imported.

from app.models.company import Company  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_role import UserRole  # noqa: F401

__all__ = ["Company", "Role", "Tenant", "User", "UserRole"]
