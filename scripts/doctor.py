from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys

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
        "llm_provider": settings.llm_provider,
        "research_model": settings.model_for_role("research"),
        "extract_model": settings.model_for_role("extract"),
        "poppler": bool(shutil.which(settings.pdftoppm_path)),
        "tesseract": bool(shutil.which(settings.tesseract_path) or
                          (importlib.util.find_spec("tesserocr") and (settings.data_dir / "tessdata" / "eng.traineddata").exists())),
        "pdf_renderer": bool(shutil.which(settings.pdftoppm_path) or importlib.util.find_spec("pypdfium2")),
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
        checks["llm_configured"] = settings.llm_configured
        checks["tavily_configured"] = bool(settings.tavily_api_key)
        from signal_research.worker.machine import ResearchMachine
        try:
            ResearchMachine(None, settings)._check_live_cost_policy()
            checks["cost_policy"] = "unknown-cost-with-hard-caps" if settings.allow_unknown_cost else "validated configured rates"
        except Exception as exc:
            checks["cost_policy"] = f"not configured: {exc}"
        if not checks["llm_configured"] or not checks["tavily_configured"]:
            print(json.dumps(checks, indent=2))
            print("Live provider checks require keys and account-accessible model IDs.", file=sys.stderr)
            return 2
        if str(checks["cost_policy"]).startswith("not configured"):
            print(json.dumps(checks, indent=2))
            return 2
    print(json.dumps(checks, indent=2))
    return 0 if checks.get("database") == "ok" and checks.get("data_dir_writable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
