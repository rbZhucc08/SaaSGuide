"""Bounded AI orchestration for SaaSGuide V3."""

__all__ = ["orchestrate_risk_candidate"]


def __getattr__(name):
    if name == "orchestrate_risk_candidate":
        from .orchestrator import orchestrate_risk_candidate

        return orchestrate_risk_candidate
    raise AttributeError(name)
