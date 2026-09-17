"""
education_state.py — State Management for Education Counselling ("Aarohi").
Maintains student profile slots in complete isolation from Real Estate state.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("education_state")

class EducationStateManager:
    """
    Dedicated State Manager for Education Counselling Voice Agent (Aarohi).
    Tracks captured student profile slots and ensures no repeated questions.
    """

    def __init__(self, json_path: Optional[str] = None):
        self.json_path = json_path
        self.current_node_id = "GREETING"
        self.student_profile: Dict[str, Any] = {
            "student_name": None,
            "current_qualification": None,
            "education_level": None,
            "percentage": None,
            "interests": None,
            "career_goal": None,
            "preferred_course": None,
            "preferred_specialization": None,
            "preferred_city": None,
            "preferred_country": None,
            "study_abroad": None,
            "budget": None,
            "entrance_exam": None,
            "phone": None,
            "counselling_requested": None
        }
        # Backward-compatible property alias for conversation_data
        self.conversation_data = self.student_profile
        self.schema = {"domain": "education", "agent_name": "Aarohi"}
        self._session_ended = False
        self.visited_nodes = set()

    def update_profile(self, new_entities: Dict[str, Any]) -> None:
        """
        Updates student profile slots with newly extracted entities.
        Retains already captured values (State Authority).
        """
        for key, value in new_entities.items():
            if value is not None and self.student_profile.get(key) is None:
                self.student_profile[key] = value
                logger.info("[EDUCATION STATE] Captured slot: %s = %s", key, value)

    def get_missing_slots(self) -> List[str]:
        """Returns list of uncollected critical student profile slots."""
        missing = []
        if not self.student_profile.get("current_qualification") and not self.student_profile.get("preferred_course"):
            missing.append("course_or_qualification")
        if not self.student_profile.get("preferred_city") and not self.student_profile.get("preferred_country") and self.student_profile.get("study_abroad") is None:
            missing.append("location_or_abroad")
        if not self.student_profile.get("budget"):
            missing.append("budget")
        if not self.student_profile.get("percentage") and not self.student_profile.get("entrance_exam"):
            missing.append("academic_score")
        return missing

    def get_next_question_goal(self) -> str:
        """Determines the single next conversation goal based on missing slots."""
        missing = self.get_missing_slots()
        if "course_or_qualification" in missing:
            return "Ask what course or qualification they are currently studying or planning to pursue."
        if "location_or_abroad" in missing:
            return "Ask if they prefer studying in India (which city) or studying abroad."
        if "budget" in missing:
            return "Ask their approximate budget or fee expectation."
        if "academic_score" in missing:
            return "Ask about their percentage score or entrance exam status."
        return "Offer to connect them with a expert human counsellor for detailed admission guidance."

    def reset_state(self, language: str = "en") -> None:
        """Resets session state for a new call."""
        self.current_node_id = "GREETING"
        for key in self.student_profile:
            self.student_profile[key] = None
        self._session_ended = False
        self.visited_nodes.clear()
