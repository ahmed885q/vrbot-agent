"""
VRBOT Ultra Agent — AI-powered task orchestration layer.

Sits on top of the existing 54 tasks, adding:
- VisionAI: screenshot analysis (YOLO fast path + API fallback)
- MetaBrain: priority-based agent selection
- 6 specialist agents: gather, hunt, build, daily, tribe, defense
- Self-learning via SmartRetry + Supabase cloud memory
"""

from ultra_agent.coordinator import UltraCoordinator
from ultra_agent.meta_brain import MetaBrain

__all__ = ["UltraCoordinator", "MetaBrain"]
