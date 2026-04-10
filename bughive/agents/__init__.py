"""BugHive v2 — Agent Registry."""
from bughive.agents.triage_agent import TriageAgent
from bughive.agents.log_analyst_agent import LogAnalystAgent
from bughive.agents.repo_navigator_agent import RepoNavigatorAgent
from bughive.agents.reproducer_agent import ReproducerAgent
from bughive.agents.dependency_analyst_agent import DependencyAnalystAgent
from bughive.agents.fix_planner_agent import FixPlannerAgent
from bughive.agents.patch_generator_agent import PatchGeneratorAgent
from bughive.agents.reviewer_agent import ReviewerCriticAgent

AGENT_REGISTRY = {
    "triage": TriageAgent, "log_analyst": LogAnalystAgent,
    "repo_navigator": RepoNavigatorAgent, "reproducer": ReproducerAgent,
    "dependency_analyst": DependencyAnalystAgent, "fix_planner": FixPlannerAgent,
    "patch_generator": PatchGeneratorAgent, "reviewer": ReviewerCriticAgent,
}
