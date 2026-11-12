"""Legacy opportunity inference is disabled: commit history cannot establish personal profiles."""


class OpportunityAnalyzer:
    ANALYZERS = []

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "opportunity is disabled: unsupported personal profiles and measurements"
        )


def run_opportunity_analyzers(*args, **kwargs):
    raise RuntimeError("opportunity is disabled: unsupported personal profiles and measurements")
