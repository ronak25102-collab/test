from __future__ import annotations

from signal_research.domain.enums import ClaimKind, FactStatus, VerificationStatus
from signal_research.domain.schemas import ResearchReport
from signal_research.evidence.citation_checks import citation_coverage
from signal_research.evidence.claim_origins import supporting_origins
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.integrity import report_digest
from signal_research.retrieval.metadata import available_by_cutoff


def verify_peer_benchmark(report):
    from signal_research.domain.schemas import Fact, Passage, SourceDocument
    from signal_research.research.peers import compare_peers
    benchmark = report.generation_metadata.get('peer_benchmark', {})
    peers = []
    for bundle in benchmark.get('sources', []):
        documents = {d.id: d for d in map(SourceDocument.model_validate, bundle['documents'])}
        passages = {p.id: p for p in map(Passage.model_validate, bundle['passages'])}
        for fact in map(Fact.model_validate, bundle['facts']):
            passage = passages.get(fact.passage_id)
            document = documents.get(passage.document_id) if passage else None
            if (str(fact.entity_id) != str(bundle['company']['id']) or fact.entity_id == report.company.id
                    or fact.status != FactStatus.VERIFIED or not document or not available_by_cutoff(document, report.cutoff)
                    or not fact.period_end or fact.period_end > report.cutoff):
                raise VerificationFailure('peer figure lacks verified issuer, source or cutoff lineage')
            peers.append(fact)
    reproduced = {r['id']: r for r in compare_peers(report.facts, peers)['comparisons']}
    for comparison in benchmark.get('comparisons', []):
        if reproduced.get(comparison['id']) != comparison:
            raise VerificationFailure('peer comparison failed independent reproduction')
    if benchmark.get('status') == 'verified' and not benchmark.get('comparisons'):
        raise VerificationFailure('peer comparison marked verified without matching observations')


class VerificationFailure(ValueError):
    code = "CITATION_FAILED"


def verify_report(report: ResearchReport) -> ResearchReport:
    if report.publication_status.value == "published" and citation_coverage(report) < 1:
        raise VerificationFailure("published report does not have complete material claim coverage")
    documents = {d.id: d for d in report.documents}
    passages = {p.id: p for p in report.passages}
    facts = {f.id: f for f in report.facts}
    calculations = {c.id: c for c in report.calculations}
    if report.generation_metadata.get('peer_benchmark'):
        verify_peer_benchmark(report)
    used_documents = set()
    if report.publication_status.value == "published":
        if report.generation_metadata.get('pipeline', '').endswith('-review-v2'):
            if (report.generation_metadata.get('novelty_status') != 'additional_supported_synthesis'
                    or not report.generation_metadata.get('non_obvious_synthesis_reviewed')
                    or not report.generation_metadata.get('novelty_rationale')):
                raise VerificationFailure('live discovery lacks reviewed additional synthesis')
        if report.generation_metadata.get("verification_digest") != report_digest(report):
            raise VerificationFailure("report content changed after semantic review or was never reviewed")
        for claim in report.claims:
            if claim.material and claim.verification_status != VerificationStatus.SUPPORTED:
                raise VerificationFailure("material claim was not semantically supported")
            if not set(claim.calculation_ids) <= calculations.keys():
                raise VerificationFailure("unknown claim calculation")
            for link in claim.evidence_links:
                fact = facts.get(link.passage_or_fact_id)
                passage = passages.get(fact.passage_id if fact else link.passage_or_fact_id)
                if not passage or passage.document_id not in documents:
                    raise VerificationFailure("broken evidence lineage")
                if fact and (fact.status != FactStatus.VERIFIED or fact.entity_id != report.company.id or not fact.period_end or fact.period_end > report.cutoff):
                    raise VerificationFailure("unverified or out-of-period fact")
                used_documents.add(passage.document_id)
    for calculation in report.calculations:
        if not set(calculation.input_fact_ids) <= facts.keys():
            raise VerificationFailure("unknown calculation input")
        inputs = [facts[i] for i in calculation.input_fact_ids]
        if any(f.status != FactStatus.VERIFIED or f.entity_id != report.company.id for f in inputs):
            raise VerificationFailure("calculation input is unverified or belongs to another entity")
        result = calculate(calculation.formula_id, [numeric_fact(f) for f in inputs], calculation.parameters)
        if not result.available or not calculation.available or result.formula_version != calculation.formula_version or result.output_value != calculation.output_value or result.unit != calculation.unit:
            raise VerificationFailure("calculation failed independent reproduction")
        for fact in inputs:
            passage = passages.get(fact.passage_id)
            if not passage:
                raise VerificationFailure("calculation input lacks source passage")
            used_documents.add(passage.document_id)
    for identifier in used_documents:
        document = documents[identifier]
        if not available_by_cutoff(document, report.cutoff):
            raise VerificationFailure("unknown or ineligible source availability by cutoff")
    if report.publication_status.value == "published":
        alternative_claims = {identifier for discovery in report.discoveries
                              for identifier in discovery.counterargument.evidence_claim_ids}
        for claim in report.claims:
            if claim.kind == ClaimKind.INFERRED and claim.id not in alternative_claims and len(supporting_origins(claim, facts, passages, documents)) < 2:
                raise VerificationFailure("material inferred claims require independently originated supporting evidence")
        families = {documents[i].origin_family_id for i in used_documents}
        if len(families) < 2 or not any(documents[i].document_type.startswith("issuer") for i in used_documents):
            raise VerificationFailure("discovery requires primary evidence and independent relevant origins")
        for discovery in report.discoveries:
            if report.generation_metadata.get('headline'):
                from signal_research.research.headline import validate_headline
                from signal_research.research.structural import break_calculations
                headline_claim = next((c for c in report.claims if str(c.id) == report.generation_metadata['headline']['claim_id']), None)
                if not headline_claim or headline_claim.text != discovery.discovery_sentence:
                    raise VerificationFailure('plain headline lacks its reviewed claim')
                if validate_headline(discovery.discovery_sentence, report.company.legal_name, report.facts, report.calculations):
                    raise VerificationFailure('plain headline failed word, sentence, unit or numeric validation')
                if set(headline_claim.calculation_ids) & break_calculations(report.generation_metadata.get('structural_breaks', []), report.calculations):
                    raise VerificationFailure('plain headline leads with a structural-break interval')
                if report.generation_metadata.get('peer_benchmark', {}).get('status') != 'verified' and discovery.evidence_strength.value != 'Weak':
                    raise VerificationFailure('unverified peer comparison must cap strength at Weak')
            headline = next((claim for claim in report.claims if claim.text == discovery.discovery_sentence), None)
            if not headline or len(supporting_origins(headline, facts, passages, documents)) < 2:
                raise VerificationFailure("discovery headline requires independently originated supporting evidence")
            if not discovery.counterargument.search_attempted:
                raise VerificationFailure("counterevidence was not searched")
            claim_map = {c.id: c.text for c in report.claims}
            if any(w.text != claim_map.get(w.claim_id) for w in discovery.why_it_matters):
                raise VerificationFailure("significance text is not the verified claim text")
            if discovery.discovery_sentence not in claim_map.values():
                raise VerificationFailure("discovery headline has not been verified")
            for identifier in discovery.timeline_event_ids:
                event = next(e for e in report.timeline_events if e.id == identifier)
                if not set(event.source_ids) <= used_documents or (event.event_date and event.event_date > report.cutoff):
                    raise VerificationFailure("timeline event is not traceable or exceeds cutoff")
    return report
