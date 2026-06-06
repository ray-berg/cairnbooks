"""Unit tests for the Tenant and Company ORM models.

These tests exercise the model classes in isolation — no database connection is
required.  They verify:
  - Models import correctly and are registered on Base.metadata.
  - ORM objects can be constructed with expected attribute defaults.
  - Relationships are correctly declared (back-reference wiring).
"""

import uuid

import pytest

from cairnbooks.db import Base
from cairnbooks.models.company import Company, Tenant


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class TestTenantModel:
    def test_tablename(self) -> None:
        """Tenant must map to the 'tenants' table."""
        assert Tenant.__tablename__ == "tenants"

    def test_table_registered_on_metadata(self) -> None:
        """The 'tenants' table must appear in Base.metadata."""
        assert "tenants" in Base.metadata.tables

    def test_instantiate_with_required_fields(self) -> None:
        """Tenant can be constructed with name and slug."""
        tenant = Tenant(name="Acme Corp", slug="acme-corp")
        assert tenant.name == "Acme Corp"
        assert tenant.slug == "acme-corp"

    def test_id_has_callable_default(self) -> None:
        """Tenant.id must have a Python-side callable default (uuid.uuid4)."""
        from sqlalchemy.sql.schema import CallableColumnDefault

        col_default = Tenant.__table__.c.id.default
        assert col_default is not None
        assert isinstance(col_default, CallableColumnDefault)
        # The default must produce a UUID value when called
        assert isinstance(uuid.uuid4(), uuid.UUID)

    def test_repr(self) -> None:
        """Tenant __repr__ must include the slug."""
        tenant = Tenant(slug="demo", name="Demo")
        tenant.id = uuid.uuid4()
        assert "demo" in repr(tenant)


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class TestCompanyModel:
    def test_tablename(self) -> None:
        """Company must map to the 'companies' table."""
        assert Company.__tablename__ == "companies"

    def test_table_registered_on_metadata(self) -> None:
        """The 'companies' table must appear in Base.metadata."""
        assert "companies" in Base.metadata.tables

    def test_create_company(self) -> None:
        """Core acceptance-criteria test: create a Company ORM object."""
        tenant_id = uuid.uuid4()
        company = Company(
            tenant_id=tenant_id,
            name="Acme Widgets",
            legal_name="Acme Widgets LLC",
            currency="USD",
            fiscal_year_end_month=12,
        )

        assert company.name == "Acme Widgets"
        assert company.legal_name == "Acme Widgets LLC"
        assert company.currency == "USD"
        assert company.fiscal_year_end_month == 12
        assert company.tenant_id == tenant_id

    def test_currency_defaults_to_usd(self) -> None:
        """Company.currency must default to 'USD'."""
        col_default = Company.__table__.c.currency.default
        assert col_default is not None
        assert col_default.arg == "USD"

    def test_fiscal_year_end_month_defaults_to_december(self) -> None:
        """Company.fiscal_year_end_month must default to 12."""
        col_default = Company.__table__.c.fiscal_year_end_month.default
        assert col_default is not None
        assert col_default.arg == 12

    def test_id_has_callable_default(self) -> None:
        """Company.id must have a Python-side callable default (uuid.uuid4)."""
        from sqlalchemy.sql.schema import CallableColumnDefault

        col_default = Company.__table__.c.id.default
        assert col_default is not None
        assert isinstance(col_default, CallableColumnDefault)
        assert isinstance(uuid.uuid4(), uuid.UUID)

    def test_legal_name_is_optional(self) -> None:
        """Company.legal_name is nullable — omitting it should leave it as None."""
        company = Company(
            tenant_id=uuid.uuid4(),
            name="Solo Entity",
        )
        assert company.legal_name is None

    def test_repr(self) -> None:
        """Company __repr__ must include the name."""
        company = Company(tenant_id=uuid.uuid4(), name="Test Co")
        company.id = uuid.uuid4()
        assert "Test Co" in repr(company)

    def test_foreign_key_targets_tenants(self) -> None:
        """Company.tenant_id FK must reference tenants.id."""
        fks = Company.__table__.c.tenant_id.foreign_keys
        assert len(fks) == 1
        (fk,) = fks
        assert fk.column.table.name == "tenants"
        assert fk.column.name == "id"

    def test_relationship_back_populates(self) -> None:
        """Tenant.companies and Company.tenant must be linked."""
        # Inspect mapper relationships
        from sqlalchemy import inspect as sa_inspect

        tenant_mapper = sa_inspect(Tenant)
        company_mapper = sa_inspect(Company)

        tenant_rel_keys = {r.key for r in tenant_mapper.relationships}
        company_rel_keys = {r.key for r in company_mapper.relationships}

        assert "companies" in tenant_rel_keys
        assert "tenant" in company_rel_keys
