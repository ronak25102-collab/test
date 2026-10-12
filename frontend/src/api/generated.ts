export type Company = {
  id: string
  legal_name: string
  symbols: string[]
  business_profiles: string[]
}

export type RunSummary = {
  id: string
  company: Company
  as_of: string
  mode: 'live' | 'deep' | 'replay'
  status: string
  outcome?: string
  stage: string
  progress: Record<string, number>
  limitations: string[]
}

export type Report = {
  run_id: string
  company: Company
  cutoff: string
  historical_coverage: string
  source_coverage: Record<string, unknown>
  outcome: string
  publication_status: string
  discoveries: Discovery[]
  limitations: string[]
  claims: Claim[]
  timeline_events: TimelineEvent[]
  calculations: Calculation[]
  facts: Fact[]
  documents: Document[]
  passages: Passage[]
  abstention?: { attempted_angles: string[]; missing_requirements: string[]; next_evidence_needed: string[] }
}

export type Discovery = {
  id: string
  discovery_sentence: string
  why_it_matters: { text: string; claim_id: string }[]
  evidence_claim_ids: string[]
  timeline_event_ids: string[]
  calculation_ids: string[]
  counterargument: { statement: string; search_attempted: boolean; search_summary: string; unresolved: boolean; evidence_claim_ids: string[] }
  falsification_rules: { id: string; observable_metric_or_event: string; operator: string; threshold?: string; unit?: string; required_periods: number; expected_source_type: string; interpretation: string }[]
  evidence_strength: 'Strong' | 'Moderate' | 'Weak'
  strength_rationale: string
}

export type Claim = { id: string; text: string; kind: string; verification_status: string; calculation_ids: string[]; evidence_links: { passage_or_fact_id: string; relation: string; reason: string }[] }
export type TimelineEvent = { id: string; event_date?: string; description: string; published_at?: string; source_ids: string[] }
export type Calculation = { id: string; formula_id: string; formula_version: string; parameters: Record<string, unknown>; output_value?: string; unit?: string; input_fact_ids: string[]; limitations: string[]; comparability_checks: string[] }
export type Fact = { id: string; metric_key: string; value_raw?: string; value_decimal?: string; unit_raw?: string; unit_normalized?: string; period_end?: string; scope: string; passage_id?: string }
export type Document = { id: string; title: string; publisher: string; canonical_url: string; published_at?: string; retrieved_at?: string; cutoff_eligibility_basis?: string; origin_family_id: string; document_type: string; content_hash: string; cutoff_eligibility: string }
export type Passage = { id: string; document_id: string; section?: string; row_label?: string; column_label?: string; text: string; page_index?: number }
