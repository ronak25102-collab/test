from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from signal_research.db.models import Base
from signal_research.db.session import build_engine
from signal_research.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Signal Research local setup")
    parser.add_argument("--live", action="store_true", help="perform bounded provider configuration checks")
    args = parser.parse_args()
    settings = get_settings()
    checks: dict[str, object] = {
        "python": sys.version.split()[0],
        "database_url_configured": bool(settings.database_url),
        "data_dir_writable": os.access(settings.data_dir, os.W_OK),
        "raw_dir": str(settings.data_dir / "raw"),
        "migration_tables": len(Base.metadata.tables),
        "docker": bool(shutil.which("docker")),
        "provider_mode": settings.research_mode,
    }
    try:
        engine = build_engine(settings.database_url)
        Base.metadata.create_all(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"unavailable: {exc}"
    if args.live:
        checks["openai_configured"] = bool(settings.openai_api_key and settings.openai_model_research)
        checks["tavily_configured"] = bool(settings.tavily_api_key)
        checks["cost_policy"] = "rate-card" if Path(settings.model_rate_card_path).exists() and json.loads(Path(settings.model_rate_card_path).read_text()).get("models") else ("unknown-cost-with-hard-caps" if settings.allow_unknown_cost else "not-configured")
        if not checks["openai_configured"] or not checks["tavily_configured"]:
            print(json.dumps(checks, indent=2))
            print("Live provider checks require keys and account-accessible model IDs.", file=sys.stderr)
            return 2
    print(json.dumps(checks, indent=2))
    return 0 if checks.get("database") == "ok" and checks.get("data_dir_writable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
