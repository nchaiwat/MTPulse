import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ModernTrade
from app.services.dh_import import ensure_dh_trade
from app.services.gh_import import ensure_gh_trade
from app.services.hh_import import ensure_hh_trade
from app.services.hp_mh_import import ensure_hp_mh_trades
from app.services.ta_import import ensure_ta_trade


@pytest.mark.parametrize("code", ["HP", "MH", "HH", "GH", "DH", "TA"])
@pytest.mark.parametrize("items,branches", [(False, False), (True, True),
                                           (False, True), (True, False)])
def test_import_setup_preserves_saved_visibility(code, items, branches):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        trade = ModernTrade(code=code, name=code, show_unmatched_items=items,
                            show_unmatched_branches=branches)
        session.add(trade)
        session.commit()
        ensure = {"HH": ensure_hh_trade, "GH": ensure_gh_trade,
                  "DH": ensure_dh_trade, "TA": ensure_ta_trade}
        for _ in range(2):
            if code in {"HP", "MH"}:
                ensure_hp_mh_trades(session)
            else:
                ensure[code](session)
            session.commit()
            session.refresh(trade)
            assert (trade.show_unmatched_items, trade.show_unmatched_branches) == (
                items, branches,
            )
