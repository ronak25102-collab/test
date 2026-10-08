from enum import StrEnum


class Profile(StrEnum):
    BANK = "bank"
    NBFC = "nbfc"
    LIFE_INSURER = "life_insurer"
    GENERAL_INSURER = "general_insurer"
    EXCHANGE = "exchange"
    ASSET_MANAGER = "asset_manager"
    DIVERSIFIED = "diversified"


class RunMode(StrEnum):
    LIVE = "live"
    DEEP = "deep"
    REPLAY = "replay"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RESOLVING = "resolving"
    PLANNING = "planning"
    DISCOVERING = "discovering"
    FETCHING = "fetching"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    HYPOTHESIZING = "hypothesizing"
    INVESTIGATING = "investigating"
    CHALLENGING = "challenging"
    VERIFYING = "verifying"
    COMPOSING = "composing"
    COMPLETED = "completed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ResearchOutcome(StrEnum):
    DISCOVERY = "discovery"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PARTIAL = "partial"


class FactStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class MissingReason(StrEnum):
    NOT_DISCLOSED = "not_disclosed"
    NOT_RETRIEVED = "not_retrieved"
    EXTRACTION_FAILED = "extraction_failed"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    INCOMPARABLE = "incomparable"


class PeriodType(StrEnum):
    INSTANT = "instant"
    DURATION = "duration"


class Scope(StrEnum):
    STANDALONE = "standalone"
    CONSOLIDATED = "consolidated"
    SEGMENT = "segment"


class ClaimKind(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


class EvidenceRelation(StrEnum):
    SUPPORTING = "supporting"
    OPPOSING = "opposing"
    CONTEXT = "context"


class EvidenceStrength(StrEnum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"


class PublicationStatus(StrEnum):
    PUBLISHED = "published"
    EXPLORATORY = "exploratory"
    ABSTAINED = "abstained"


class DatePrecision(StrEnum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    UNKNOWN = "unknown"
