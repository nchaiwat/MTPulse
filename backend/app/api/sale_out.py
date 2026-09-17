from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.services.sale_out_report import SaleOutReportError, build_sale_out_report

router = APIRouter(prefix="/api/sale-out", tags=["Sale Out"])


@router.get("")
def get_sale_out_report(
    session: Annotated[Session, Depends(get_session)],
    base_year: Annotated[int, Query(ge=2025, le=9999)] = 2025,
    comparison_year: Annotated[int, Query(ge=2025, le=9999)] = 2026,
    cutoff: Annotated[date | None, Query()] = None,
    sales_basis: Annotated[Literal["net", "gross"], Query()] = "gross",
    metric: Annotated[Literal["amount", "qty", "average_price"], Query()] = "amount",
    mt_code: Annotated[list[str] | None, Query()] = None,
) -> dict:
    try:
        return build_sale_out_report(
            session,
            base_year=base_year,
            comparison_year=comparison_year,
            cutoff=cutoff,
            sales_basis=sales_basis,
            metric=metric,
            mt_codes=mt_code,
        )
    except SaleOutReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
