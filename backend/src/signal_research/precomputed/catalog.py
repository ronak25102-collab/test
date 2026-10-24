"""Strict local fixture lookup. A missing company never falls back to another issuer."""
import json
from datetime import date

from signal_research.domain.enums import PublicationStatus
from signal_research.domain.schemas import ResearchReport
from signal_research.research.verifier import verify_report


class PrecomputedUnavailable(ValueError):
    code = "UNSUPPORTED_SECTOR"


def load_report(settings, company, cutoff: date):
    roster_path = settings.precomputed_dir / 'roster.json'
    if roster_path.is_file():
        roster = json.loads(roster_path.read_text(encoding='utf-8'))
        members = {entry['symbol'] for entry in roster.get('companies', [])}
        if not set(company.symbols) & members:
            raise PrecomputedUnavailable('Company is outside the verified NIFTY 50 Track A roster')
    for symbol in company.symbols:
        if not symbol or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in symbol):
            continue
        if (settings.precomputed_dir / 'index.json').is_file() and symbol not in {
                entry['symbol'] for entry in index_entries(settings)}:
            continue
        path = settings.precomputed_dir / f"{symbol}.json"
        if not path.is_file():
            continue
        report = ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))
        if (report.company.id != company.id or symbol not in report.company.symbols
                or report.company.business_profiles != company.business_profiles):
            raise PrecomputedUnavailable("Stored evidence does not match the selected company")
        if report.publication_status != PublicationStatus.PUBLISHED:
            raise PrecomputedUnavailable(f"No published stored discovery is available for {symbol}")
        if cutoff < report.cutoff:
            raise PrecomputedUnavailable(f"Stored evidence for {symbol} requires cutoff {report.cutoff} or later")
        return verify_report(report)
    raise PrecomputedUnavailable(f"No verified precomputed discovery is available for {', '.join(company.symbols)}")


def index_entries(settings):
    path = settings.precomputed_dir / "index.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("companies", []) if isinstance(payload, dict) else payload


def bootstrap_catalog(store, settings):
    """Register identities from validated fixtures without refreshing any directory."""
    from signal_research.db.models import CompanyModel

    with store.session_factory() as session:
        roster_path = settings.precomputed_dir / "roster.json"
        if roster_path.is_file():
            roster = json.loads(roster_path.read_text(encoding="utf-8"))
            for entry in roster.get("companies", []):
                row = session.get(CompanyModel, entry["id"])
                if row is None:
                    row = CompanyModel(id=entry["id"], legal_name=entry["legal_name"],
                                       symbols=[entry["symbol"]], business_profiles=[entry["profile"]],
                                       verified_ir_domains=[entry["ir_domain"]], identity_source_ids=[])
                    session.add(row)
                row.aliases = list(dict.fromkeys([*(row.aliases or []), *entry.get("aliases", [])]))
                row.isin = entry.get("isin") or row.isin
                row.exchange = "NSE"
            session.flush()
        for entry in index_entries(settings):
            symbol = entry["symbol"]
            if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in symbol):
                raise ValueError("Invalid precomputed catalog symbol")
            path = settings.precomputed_dir / f"{symbol}.json"
            if not path.is_file():
                continue
            report = ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))
            if symbol not in report.company.symbols:
                raise ValueError("Precomputed index and report issuer differ")
            company = report.company
            row = session.get(CompanyModel, str(company.id))
            if row is None:
                row = CompanyModel(id=str(company.id), legal_name=company.legal_name)
                session.add(row)
            row.symbols = list(company.symbols)
            row.aliases = list(dict.fromkeys([*(row.aliases or []), *company.aliases, *entry.get("aliases", [])]))
            row.isin = company.isin or row.isin
            row.exchange = company.exchange or row.exchange
            row.business_profiles = [p.value for p in company.business_profiles]
            row.verified_ir_domains = list(company.verified_ir_domains)
            row.identity_source_ids = [str(i) for i in company.identity_source_ids]
        session.commit()
