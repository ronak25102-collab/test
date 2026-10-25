"""SQLite must not hide column limits that reject real evidence in PostgreSQL."""
import json

import pytest
from signal_research.db.models import CalculationModel, FactModel, PassageModel, SourceDocumentModel
from signal_research.precomputed.builder import FIXTURE_DIR, read_json


@pytest.mark.parametrize("symbol", [entry["symbol"] for entry in
                                    read_json(FIXTURE_DIR / "index.json")["companies"]])
def test_reviewed_fixture_values_fit_database_columns(symbol):
    report = json.loads((FIXTURE_DIR / f"{symbol}.json").read_text(encoding="utf-8"))
    models = {"documents": SourceDocumentModel, "passages": PassageModel,
              "facts": FactModel, "calculations": CalculationModel}
    for collection, model in models.items():
        for row in report[collection]:
            for column in model.__table__.columns:
                value = row.get(column.name)
                limit = getattr(column.type, "length", None)
                if isinstance(value, str) and limit is not None:
                    assert len(value) <= limit, (symbol, collection, column.name, len(value), limit)
