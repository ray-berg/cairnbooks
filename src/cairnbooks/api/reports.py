"""Reports API router — GET /reports/trial-balance.

Endpoints
---------
GET /reports/trial-balance
    Return per-account debit/credit totals as-of a given date for a company.

Query parameters
~~~~~~~~~~~~~~~~
company_id : UUID (required)
    The company whose ledger to report on.
as_of : date  (required, format YYYY-MM-DD)
    Upper bound for journal dates (inclusive).  Only posted journals on or
    before this date are included.

Response shape
~~~~~~~~~~~~~~
::

    {
      "company_id": "<uuid>",
      "as_of": "2026-06-07",
      "lines": [
        {
          "account_id": "<uuid>",
          "code": "1010",
          "name": "Checking Account",
          "account_type": "asset",
          "total_debit": "5000.00",
          "total_credit": "500.00"
        },
        ...
      ],
      "grand_total_debit":  "5000.00",
      "grand_total_credit": "5000.00",
      "is_balanced": true
    }

Errors
~~~~~~
``422 Unprocessable Entity``
    Missing or malformed query parameters.
``500 Internal Server Error``
    Unexpected database error.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.db import get_db
from cairnbooks.reports.trial_balance import compute_trial_balance

router = APIRouter(prefix="/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Response schemas (Pydantic)
# ---------------------------------------------------------------------------


class TrialBalanceLineSchema(BaseModel):
    """One account row in the trial balance response."""

    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    code: str
    name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal


class TrialBalanceResponse(BaseModel):
    """Full trial balance response body."""

    company_id: uuid.UUID
    as_of: date
    lines: list[TrialBalanceLineSchema]
    grand_total_debit: Decimal
    grand_total_credit: Decimal
    is_balanced: bool


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    company_id: uuid.UUID,
    as_of: date,
    db: AsyncSession = Depends(get_db),
) -> TrialBalanceResponse:
    """Return per-account debit/credit totals as-of a given date.

    Only **posted** journal lines with ``date <= as_of`` are included.

    Parameters
    ----------
    company_id:
        UUID of the company (query parameter).
    as_of:
        Cut-off date for the report (query parameter, format ``YYYY-MM-DD``).
    db:
        Injected database session.

    Returns
    -------
    TrialBalanceResponse
        JSON body with per-account rows and grand totals.
        ``is_balanced`` will be ``true`` for a correctly maintained ledger.
    """
    report = await compute_trial_balance(db, company_id, as_of)

    return TrialBalanceResponse(
        company_id=report.company_id,
        as_of=report.as_of,
        lines=[
            TrialBalanceLineSchema(
                account_id=line.account_id,
                code=line.code,
                name=line.name,
                account_type=line.account_type,
                total_debit=line.total_debit,
                total_credit=line.total_credit,
            )
            for line in report.lines
        ],
        grand_total_debit=report.grand_total_debit,
        grand_total_credit=report.grand_total_credit,
        is_balanced=report.is_balanced,
    )
