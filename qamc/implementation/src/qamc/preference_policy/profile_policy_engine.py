"""Content-only policy injection using the corrected static Actor data contract."""
from .policy_engine import PolicyEngine
from .profile_input import actor_view


class ProfilePolicyEngine(PolicyEngine):
    build_actor_view=staticmethod(actor_view)
