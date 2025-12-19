"""
ParameterPlan Dataclass - Complete parameter plan for one generation.

This dataclass stores all parameters that AD-Agent computes for a single
animation cleanup generation, including model selection, CFG, Denoise,
ControlNet settings, and metadata.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParameterPlan:
    """Complete parameter plan for one generation."""
    
    # Model
    model_name: str
    
    # Core SD parameters
    cfg: float
    denoise: float
    steps: int
    sampler: str = "euler"
    scheduler: str = "simple"
    
    # ControlNet parameters
    lineart_strength: float = 1.0
    lineart_end: float = 0.9
    canny_strength: float = 0.8
    canny_end: float = 0.6
    
    # Metadata
    reasoning: str = ""
    warnings: List[str] = field(default_factory=list)
    conflicts_fixed: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure lists are initialized."""
        if self.warnings is None:
            self.warnings = []
        if self.conflicts_fixed is None:
            self.conflicts_fixed = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "model_name": self.model_name,
            "cfg": self.cfg,
            "denoise": self.denoise,
            "steps": self.steps,
            "sampler": self.sampler,
            "scheduler": self.scheduler,
            "lineart_strength": self.lineart_strength,
            "lineart_end": self.lineart_end,
            "canny_strength": self.canny_strength,
            "canny_end": self.canny_end,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "conflicts_fixed": self.conflicts_fixed,
        }

