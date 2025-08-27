import os, yaml
from typing import List, Dict, Any, Optional

class PSPRecommendations:
    def __init__(self, config_path: str = "config/partners.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.providers: Dict[str, Dict[str, Any]] = self.cfg.get("providers", {})
        self.disclosure = self.cfg.get("disclosure", {})

    def list_visible(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        items = []
        for pid, p in self.providers.items():
            if not p.get("visible", True):
                continue
            if category and p.get("category") != category:
                continue
            p2 = dict(p)
            p2["id"] = pid
            items.append(p2)
        return items

    def choose_for_context(
        self,
        *,
        match_listed: bool,
        violation_risk: float,
        needs_entity: bool,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Minimal, honest rules:
        - If MATCH listed => show PSP (durango, paymentcloud)
        - If violation_risk >= 0.7 => show legal
        - If needs_entity => show formation
        """
        picks: List[Dict[str, Any]] = []

        if match_listed:
            picks += self._pick_category("psp", limit=2)

        if violation_risk is not None and violation_risk >= 0.7:
            picks += self._pick_category("legal", limit=1)

        if needs_entity:
            picks += self._pick_category("formation", limit=1)

        # Deduplicate in order
        seen, unique = set(), []
        for p in picks:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            unique.append(p)
        return unique[:limit]

    def disclosure_short(self) -> str:
        return self.disclosure.get("short", "Independent recommendations. No affiliate relationship.")

    def _pick_category(self, category: str, limit: int = 1) -> List[Dict[str, Any]]:
        return [p for p in self.list_visible(category)][:limit]
