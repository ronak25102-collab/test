# Issuer website reference correction, 14 October 2026

Live validation exposed a trust-registry defect. A document mentioning the target
company and its ISIN could authorize every `Website:` reference in that document,
including a registrar, trustee, depository or another issuer. Such entries must
not authorize primary target-company evidence.

The shared reference parser now binds each website to its nearby issuer identity.
Directory links must belong to the target's own row. An unrelated owner, party-role
heading or a distant name/ISIN mention cannot authorize a website. A bare `www`
fragment is not a domain. The original source must still be an authoritative
exchange disclosure or an already verified issuer site and must be cutoff-eligible.

New proof records use `issuer-reference-v2` and identify the owning company and
original document hash. Domains and proof records are saved in one transaction.
Startup retains the curated identity domains and their subdomains, plus domains
with current-policy proof belonging to that company's own research run. Other
legacy entries are quarantined. A private JSON backup under
`data/exports/domain-audits` preserves every removed entry and identity source ID.
Saved research reports, source files and historical proof records are not rewritten.

The local retained-document audit reviewed 21 distinct legacy references and
restored four issuer-owned reference records for ICICI Lombard's own site. Trustee,
registrar and unrelated-company entries remained quarantined. The complete
backend/security suite passed 408 tests before the additional atomic-owner check;
focused ownership and registry tests passed after that check.

Revalidate retained references without network/provider calls:

```powershell
.\.venv\Scripts\python.exe scripts/audit_issuer_domains.py
.\.venv\Scripts\python.exe scripts/audit_issuer_domains.py --apply
```

The second command restores only references that pass the current ownership
policy against the original retained document with a matching SHA-256 hash.
Missing, ambiguous or modified sources cannot restore trust. The audit output
identifies accepted and rejected references. This checks website ownership only;
it does not establish financial claim support or certify a discovery.

Controlled regression tests cover issuer-directory rows, incidental investment
mentions, trustee/registrar references, invalid host fragments, backup preservation,
atomic proof persistence, cross-company proof rejection and retained-hash recovery.
