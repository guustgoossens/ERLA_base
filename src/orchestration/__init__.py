"""Orchestration module for the recursive research agent system.

This module provides the 4-layer recursive research agent:
- Layer 1: InnerLoop - Atomic search-summarize-validate unit
- Layer 2: IterationLoop - Depth expansion via citation traversal
- Layer 3: MasterAgent - Orchestrator with tool-based control
- Layer 4: Big Loop 2 - Hypothesis-seeded recursive exploration
"""

from .overseer import Overseer
from .models import (
    BranchStatus,
    InnerLoopMode,
    ValidatedSummary,
    ResearchHypothesis,
    IterationResult,
    Branch,
    LoopState,
    LoopStatus,
    BranchSplitResult,
)
from .inner_loop import InnerLoop
from .iteration_loop import IterationLoop
from .master_agent import MasterAgent, ResearchSession
from .branch_manager import BranchManager
from .state_store import StateStore
from .tools import (
    ToolType,
    ToolDefinition,
    ToolCall,
    ToolResult,
    ToolExecutor,
    get_tool_schema,
    get_tool_descriptions,
    TOOL_DEFINITIONS,
)

__all__ = [
    # Original
    "Overseer",
    # Models
    "BranchStatus",
    "InnerLoopMode",
    "ValidatedSummary",
    "ResearchHypothesis",
    "IterationResult",
    "Branch",
    "LoopState",
    "LoopStatus",
    "BranchSplitResult",
    # Layer 1
    "InnerLoop",
    # Layer 2
    "IterationLoop",
    # Layer 3
    "MasterAgent",
    "ResearchSession",
    # Branch Management
    "BranchManager",
    "StateStore",
    # Tools
    "ToolType",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "ToolExecutor",
    "get_tool_schema",
    "get_tool_descriptions",
    "TOOL_DEFINITIONS",
]
