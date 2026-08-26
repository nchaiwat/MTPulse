from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.twd_settings import get_unmatched_visibility
from app.database import Base
from app.models import ModernTrade


def test_twd_settings_exposes_attention_and_report_page_size() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.commit()

        settings = get_unmatched_visibility(session)
        assert settings["mappingAttentionItems"] == 0
        assert settings["mappingAttentionBranches"] == 0
        assert settings["reportPageSize"] == 25
