"""CairnBooks ORM model package.

Import all model modules here so that:
  - Alembic autogenerate can detect every table via Base.metadata
  - Application code can do ``from cairnbooks.models import Account, Tenant, Company``
"""

from cairnbooks.models.account import Account, AccountType  # noqa: F401
from cairnbooks.models.company import Company, Tenant  # noqa: F401
from cairnbooks.models.item import Item  # noqa: F401

__all__ = ["Account", "AccountType", "Company", "Item", "Tenant"]
