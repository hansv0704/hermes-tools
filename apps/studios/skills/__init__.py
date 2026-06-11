"""
Alice Game Studio — Skills 模組
每個 skill 對應 CCGS 中的一個 SKILL.md
Phase 1-6 完整移植
"""

# Phase 1
from .start_skill import (
    detect_project_state,
    ONBOARDING_QUESTION,
    get_path_A, get_path_B, get_path_C, get_path_D,
    REVIEW_MODE_QUESTION,
    StartSession, get_session
)

# Phase 2
from .map_systems_skill import map_systems_skill, MAP_PHASES
from .design_system_skill import design_system_skill, GDD_SECTIONS
from .design_review_skill import design_review_skill
from .review_all_gdds_skill import review_all_gdds_skill
from .consistency_check_skill import consistency_check_skill

# Phase 3
from .create_architecture_skill import CreateArchitectureSkill
from .architecture_decision_skill import ArchitectureDecisionSkill
from .architecture_review_skill import ArchitectureReviewSkill
from .create_control_manifest_skill import CreateControlManifestSkill
from .art_bible_skill import ArtBibleSkill

# Phase 4
from .asset_spec_skill import asset_spec_skill, ASSET_CATEGORIES
from .ux_design_skill import ux_design_skill, UX_SECTIONS
from .ux_review_skill import ux_review_skill, HEURISTICS, GAME_HEURISTICS
from .prototype_skill import prototype_skill, PROTOTYPE_TYPES
from .create_epics_skill import create_epics_skill
from .create_stories_skill import create_stories_skill
from .sprint_plan_skill import sprint_plan_skill
from .gate_check_skill import gate_check_skill, GATE_CHECKS
from .vertical_slice_skill import vertical_slice_skill, VERTICAL_SLICE_PHASES, SLICE_TYPES

# Phase 5
from .code_review_skill import code_review_bp
from .story_complete_skill import story_complete_bp
from .sprint_retro_skill import sprint_retro_bp
from .implement_skill import implement_bp
from .test_design_skill import test_design_bp
from .playtest_skill import playtest_bp
from .issue_write_skill import issue_write_bp

# Phase 6
from .profiling_skill import ProfilingSkill
from .balance_tuning_skill import BalanceTuningSkill
from .asset_audit_skill import AssetAuditSkill
from .accessibility_review_skill import AccessibilityReviewSkill
from .polish_pass_skill import PolishPassSkill

__all__ = [
    # Phase 1
    "detect_project_state", "ONBOARDING_QUESTION",
    "get_path_A", "get_path_B", "get_path_C", "get_path_D",
    "REVIEW_MODE_QUESTION", "StartSession", "get_session",
    # Phase 2
    "map_systems_skill", "MAP_PHASES",
    "design_system_skill", "GDD_SECTIONS",
    "design_review_skill",
    "review_all_gdds_skill",
    "consistency_check_skill",
    # Phase 3
    "CreateArchitectureSkill", "ArchitectureDecisionSkill",
    "ArchitectureReviewSkill", "CreateControlManifestSkill", "ArtBibleSkill",
    # Phase 4
    "asset_spec_skill", "ASSET_CATEGORIES",
    "ux_design_skill", "UX_SECTIONS",
    "ux_review_skill", "HEURISTICS", "GAME_HEURISTICS",
    "prototype_skill", "PROTOTYPE_TYPES",
    "create_epics_skill", "create_stories_skill",
    "sprint_plan_skill", "gate_check_skill",
    "vertical_slice_skill", "VERTICAL_SLICE_PHASES", "SLICE_TYPES",
    # Phase 5
    "code_review_bp", "story_complete_bp", "sprint_retro_bp",
    "implement_bp", "test_design_bp", "playtest_bp", "issue_write_bp",
    # Phase 6
    "ProfilingSkill", "BalanceTuningSkill", "AssetAuditSkill",
    "AccessibilityReviewSkill", "PolishPassSkill",
]
