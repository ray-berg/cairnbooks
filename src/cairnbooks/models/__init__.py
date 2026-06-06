"""CairnBooks ORM model package.

Import all model modules here so that:
  - Alembic autogenerate can detect every table via Base.metadata
  - Application code can do ``from cairnbooks.models import Tenant, Company``
"""

from cairnbooks.models.company import Company, Tenant  # noqa: F401

__all__ = ["Tenant", "Company"]
