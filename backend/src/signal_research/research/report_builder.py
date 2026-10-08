from __future__ import annotations

from datetime import date
from uuid import UUID, uuid5

from signal_research.domain.enums import (
    ClaimKind,
    EvidenceRelation,
    PublicationStatus,
    ResearchOutcome,
    VerificationStatus,
)
from signal_research.domain.schemas import (
    Abstention,
    Calculation,
    Claim,
    Company,
    Counterargument,
    Discovery,
    EvidenceLink,
    FalsificationRule,
    ResearchReport,
    TimelineEvent,
    WhyItMatters,
)
from signal_research.evidence.independence import check_independence
from signal_research.evidence.strength import label_strength
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.providers.fixtures import synthetic_evidence
from signal_research.research.challenger import challenge_synthetic
from signal_research.research.integrity import attest_report
from signal_research.retrieval.metadata import publication_day


def _id(run_id: UUID, name: str) -> UUID:
    return uuid5(run_id, name)


def build_synthetic_report(run_id: UUID, company: Company, cutoff: date) -> ResearchReport:
    documents, passages, facts = synthetic_evidence(run_id, company, cutoff)
    eligible_documents = [d for d in documents if d.published_at and publication_day(d.published_at) <= cutoff]
    for document in documents:
        if document not in eligible_documents:
            document.cutoff_eligibility = "ineligible"
    if len(eligible_documents) < 2:
        return build_abstention(run_id, company, cutoff, documents, passages, facts, ["two cutoff-eligible origin families"])

    by_key = {fact.metric_key + ("_prior" if fact.period_end and fact.period_end.year == 2025 else "_current"): fact for fact in facts}
    numeric = {key: numeric_fact(f) for key, f in by_key.items()}
    calculations = []
    four = [numeric["gross_advances_current"], numeric["gross_advances_prior"], numeric["deposits_current"], numeric["deposits_prior"]]
    specs = [
        ("advances_growth", "yoy_growth", four[:2]),
        ("deposit_growth", "yoy_growth", four[2:]),
        ("growth_gap", "growth_gap", four),
        ("ldr_prior", "loan_to_deposit", [four[1], four[3]]),
        ("ldr_current", "loan_to_deposit", [four[0], four[2]]),
        ("ldr_change", "ldr_change", four),
    ]
    direct = {}
    for key, formula, inputs in specs:
        result = calculate(formula, inputs)
        result_id = _id(run_id, key)
        direct[key] = result_id
        calculations.append(Calculation(id=result_id, formula_id=formula, formula_version=result.formula_version, input_fact_ids=result.input_fact_ids, output_value=result.output_value, unit=result.unit, period="FY2025-FY2026", scope=facts[0].scope, comparability_checks=result.comparability_checks, limitations=result.limitations, available=result.available))
    ldr_change_id = direct["ldr_change"]
    primary_passage = passages[0]
    context_passage = passages[1]
    claim_ids = {name: _id(run_id, f"claim-{name}") for name in ("advances", "deposits", "gap", "ldr", "qualification")}
    claims = [
        Claim(id=claim_ids["advances"], run_id=run_id, text="Gross advances grew 20.00% from INR 100000 crore to INR 120000 crore at comparable consolidated year-end dates.", calculation_ids=[direct["advances_growth"]], kind=ClaimKind.OBSERVED, evidence_links=[EvidenceLink(claim_id=claim_ids["advances"], passage_or_fact_id=by_key["gross_advances_prior"].id, relation=EvidenceRelation.SUPPORTING, reason="prior-year advances fact"), EvidenceLink(claim_id=claim_ids["advances"], passage_or_fact_id=by_key["gross_advances_current"].id, relation=EvidenceRelation.SUPPORTING, reason="current-year advances fact")], verification_status=VerificationStatus.SUPPORTED),
        Claim(id=claim_ids["deposits"], run_id=run_id, text="Total deposits grew 10.00% from INR 125000 crore to INR 137500 crore over the same dates.", calculation_ids=[direct["deposit_growth"]], kind=ClaimKind.OBSERVED, evidence_links=[EvidenceLink(claim_id=claim_ids["deposits"], passage_or_fact_id=by_key["deposits_prior"].id, relation=EvidenceRelation.SUPPORTING, reason="prior-year deposits fact"), EvidenceLink(claim_id=claim_ids["deposits"], passage_or_fact_id=by_key["deposits_current"].id, relation=EvidenceRelation.SUPPORTING, reason="current-year deposits fact")], verification_status=VerificationStatus.SUPPORTED),
        Claim(id=claim_ids["gap"], run_id=run_id, text="Advances grew 10 percentage points faster than deposits.", kind=ClaimKind.DERIVED, calculation_ids=[direct["advances_growth"], direct["deposit_growth"], direct["growth_gap"]], evidence_links=[EvidenceLink(claim_id=claim_ids["gap"], passage_or_fact_id=primary_passage.id, relation=EvidenceRelation.SUPPORTING, reason="calculation inputs are reported in the issuer passage")], verification_status=VerificationStatus.SUPPORTED),
        Claim(id=claim_ids["ldr"], run_id=run_id, text="The calculated loan-to-deposit ratio rose from 80.00% to approximately 87.27%, a 7.27 percentage-point change.", kind=ClaimKind.DERIVED, calculation_ids=[direct["ldr_prior"], direct["ldr_current"], ldr_change_id], evidence_links=[EvidenceLink(claim_id=claim_ids["ldr"], passage_or_fact_id=primary_passage.id, relation=EvidenceRelation.SUPPORTING, reason="reported advances and deposits supply both denominators")], verification_status=VerificationStatus.SUPPORTED),
        Claim(id=claim_ids["qualification"], run_id=run_id, text="The arithmetic supports a funding-growth observation, not a conclusion of funding stress; deposit composition and funding-cost evidence are still needed.", kind=ClaimKind.INFERRED, evidence_links=[EvidenceLink(claim_id=claim_ids["qualification"], passage_or_fact_id=context_passage.id, relation=EvidenceRelation.SUPPORTING, reason="independent context explicitly limits the interpretation")], verification_status=VerificationStatus.SUPPORTED),
    ]
    event = TimelineEvent(id=_id(run_id, "year-end-change"), event_date=date(2026, 3, 31), published_at=documents[0].published_at, description="Comparable FY2026 disclosure showed advances growing faster than deposits.", claim_ids=list(claim_ids.values()), source_ids=[documents[0].id])
    challenge = challenge_synthetic()
    counterargument = Counterargument(statement=challenge.strongest_alternative, evidence_claim_ids=[claim_ids["qualification"]], search_attempted=challenge.attempted, search_summary=challenge.summary, unresolved=challenge.unresolved)
    rule = FalsificationRule(id=_id(run_id, "falsification"), observable_metric_or_event="Comparable advances and deposits disclosures", operator="growth_gap reverses or scope change explains movement", threshold=None, unit="percentage points / event", required_periods=2, expected_source_type="issuer quarterly results", interpretation="Reconsider the funding-growth observation if two later comparable periods reverse the gap or a documented reclassification accounts for it.", dependencies=[direct["growth_gap"]])
    independence = check_independence(documents, {d.id for d in eligible_documents})
    strength, rationale = label_strength(independent_origins=len(independence.relevant_families), unresolved_alternative=challenge.unresolved, central_calculations_verified=all(c.available for c in calculations))
    discovery = Discovery(id=_id(run_id, "discovery"), discovery_sentence="Comparable year-end balances show advances growing materially faster than deposits, widening the calculated loan-to-deposit ratio; this is a funding-growth observation rather than proof of funding stress.", why_it_matters=[WhyItMatters(text=claims[0].text, claim_id=claim_ids["advances"]), WhyItMatters(text=claims[2].text, claim_id=claim_ids["gap"]), WhyItMatters(text=claims[3].text, claim_id=claim_ids["ldr"]), WhyItMatters(text=claims[4].text, claim_id=claim_ids["qualification"])], evidence_claim_ids=list(claim_ids.values()), timeline_event_ids=[event.id], calculation_ids=[c.id for c in calculations], counterargument=counterargument, falsification_rules=[rule], evidence_strength=strength, strength_rationale=rationale)
    headline_id = _id(run_id, "claim-headline")
    claims.append(Claim(id=headline_id, run_id=run_id, text=discovery.discovery_sentence, kind=ClaimKind.INFERRED,
                        evidence_links=[EvidenceLink(claim_id=headline_id, passage_or_fact_id=p.id, relation=EvidenceRelation.SUPPORTING, reason="manually reviewed synthetic evidence") for p in passages],
                        calculation_ids=[direct["growth_gap"], ldr_change_id], verification_status=VerificationStatus.SUPPORTED))
    discovery.evidence_claim_ids.append(headline_id)
    return attest_report(ResearchReport(run_id=run_id, company=company, cutoff=cutoff, historical_coverage="FY2025-FY2026 comparable consolidated year-end balances", source_coverage={"documents_found": 2, "documents_used": 2, "eligible_origin_families": len(independence.relevant_families), "primary_source": True, "mode": "replay", "synthetic": True}, outcome=ResearchOutcome.DISCOVERY, publication_status=PublicationStatus.PUBLISHED, discoveries=[discovery], limitations=["Replay evidence is synthetic and must not be presented as a live company finding.", "Funding composition and cost were not disclosed in this fixture; the stronger mechanism is intentionally withheld."], generation_metadata={"pipeline": "observation-plan-calculate-challenge-verify", "model_id": None, "prompt_version": "1.0"}, claims=claims, timeline_events=[event], calculations=calculations, facts=facts, documents=documents, passages=passages))


def build_abstention(run_id: UUID, company: Company, cutoff: date, documents=None, passages=None, facts=None, missing=None, mode: str = "replay") -> ResearchReport:
    documents = documents or []
    eligible = [document for document in documents if document.cutoff_eligibility == "eligible"]
    origins = {document.origin_family_id for document in eligible}
    primary = any(document.document_type.startswith("issuer") for document in eligible)
    return ResearchReport(run_id=run_id, company=company, cutoff=cutoff, historical_coverage="insufficient eligible coverage", source_coverage={"documents_found": len(documents), "documents_used": len(eligible), "eligible_origin_families": len(origins), "primary_source": primary, "mode": mode, "synthetic": mode == "replay"}, outcome=ResearchOutcome.INSUFFICIENT_EVIDENCE, publication_status=PublicationStatus.ABSTAINED, discoveries=[], limitations=["No primary discovery was published because the evidence gates did not pass."], generation_metadata={"pipeline": "deterministic-abstention", "model_id": None, "prompt_version": "1.0"}, claims=[], timeline_events=[], calculations=[], facts=facts or [], documents=documents, passages=passages or [], abstention=Abstention(attempted_angles=["growth and funding relationship", "scope or reporting change"], missing_requirements=missing or ["cutoff-eligible primary facts", "independent relevant context"], strongest_unconfirmed_lead=None, next_evidence_needed=["a cutoff-eligible issuer disclosure", "an independently originated relevant source"]))
