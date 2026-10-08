class ResearchError(RuntimeError):
    code = "RESEARCH_FAILED"
    retryable = False


class BudgetExceeded(ResearchError):
    code = "BUDGET_EXCEEDED"


class SourceBlocked(ResearchError):
    code = "SOURCE_BLOCKED"
    retryable = True


class CitationFailed(ResearchError):
    code = "CITATION_FAILED"


class IncomparableFacts(ResearchError):
    code = "INCOMPARABLE_FACTS"
