from signal_research.domain.enums import EvidenceRelation


def supporting_origins(claim, facts, passages, documents):
    origins = set()
    for link in claim.evidence_links:
        if link.relation != EvidenceRelation.SUPPORTING:
            continue
        fact = facts.get(link.passage_or_fact_id)
        passage = passages.get(fact.passage_id if fact else link.passage_or_fact_id)
        document = documents.get(passage.document_id) if passage else None
        if document and document.cutoff_eligibility == "eligible":
            origins.add(document.origin_family_id)
    return origins
