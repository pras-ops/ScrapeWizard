import re
from typing import Dict, List, Any, Tuple, Optional
from scrapewizard.engine.fingerprint import ElementFingerprint, normalize_text
from scrapewizard.core.logging import log

class SelfHealingEngine:
    """
    Deterministic offline self-healing engine.
    Compares candidate elements against an element's saved fingerprint to find the best match.
    """
    def __init__(self, confidence_threshold: float = 0.85, ambiguity_margin: float = 0.10):
        self.confidence_threshold = confidence_threshold
        self.ambiguity_margin = ambiguity_margin

    def score_candidate(self, fingerprint: ElementFingerprint, cand: Dict[str, Any]) -> float:
        """Score a single candidate element against the saved fingerprint (Max 1.0)."""
        # Tier 2: Attributes & Text (Weight: 0.50)
        attr_score = 0.0
        orig_attrs = fingerprint.attributes or {}
        cand_attrs = cand.get("attributes") or {}
        
        # Compare matching attribute keys and values
        common_keys = set(orig_attrs.keys()) & set(cand_attrs.keys())
        if orig_attrs and cand_attrs:
            match_count = sum(1 for k in common_keys if str(orig_attrs[k]) == str(cand_attrs[k]))
            attr_score = match_count / max(len(orig_attrs), len(cand_attrs))
        elif not orig_attrs and not cand_attrs:
            attr_score = 1.0

        # Strong ID/TestID match overrides generic attribute score
        if orig_attrs.get("id") and orig_attrs.get("id") == cand_attrs.get("id"):
            attr_score = max(attr_score, 0.95)
        for test_key in ["data-testid", "data-test", "data-qa"]:
            if orig_attrs.get(test_key) and orig_attrs.get(test_key) == cand_attrs.get(test_key):
                attr_score = max(attr_score, 0.95)

        # Text matching
        orig_text = normalize_text(fingerprint.text)
        cand_text = normalize_text(cand.get("text"))
        text_score = 0.0
        if orig_text and cand_text:
            if orig_text == cand_text:
                text_score = 1.0
            elif orig_text in cand_text or cand_text in orig_text:
                text_score = 0.5
        elif not orig_text and not cand_text:
            text_score = 1.0

        tier2_score = (attr_score * 0.6) + (text_score * 0.4)

        # Tier 3: Structural Context (Weight: 0.25)
        parent_score = 0.0
        orig_parent = fingerprint.context.get("parent") or {}
        cand_parent = cand.get("context", {}).get("parent") or {}
        
        if orig_parent and cand_parent:
            if orig_parent.get("tag") == cand_parent.get("tag"):
                parent_score += 0.4
            # Class overlap
            orig_p_classes = set(orig_parent.get("classes") or [])
            cand_p_classes = set(cand_parent.get("classes") or [])
            if orig_p_classes and cand_p_classes:
                overlap = orig_p_classes & cand_p_classes
                parent_score += 0.6 * (len(overlap) / max(len(orig_p_classes), len(cand_p_classes)))
            elif not orig_p_classes and not cand_p_classes:
                parent_score += 0.6
        elif not orig_parent and not cand_parent:
            parent_score = 1.0

        # Siblings tag overlap
        sibling_score = 0.0
        orig_siblings = fingerprint.siblings or []
        cand_siblings = cand.get("context", {}).get("siblings") or []
        orig_sib_tags = [s.get("tag") for s in orig_siblings if s.get("tag")]
        cand_sib_tags = [s.get("tag") for s in cand_siblings if s.get("tag")]
        if orig_sib_tags and cand_sib_tags:
            common_sibs = set(orig_sib_tags) & set(cand_sib_tags)
            sibling_score = len(common_sibs) / max(len(orig_sib_tags), len(cand_sib_tags))
        elif not orig_sib_tags and not cand_sib_tags:
            sibling_score = 1.0

        tier3_score = (parent_score * 0.7) + (sibling_score * 0.3)

        # Tier 4: Geometry / Visual (Weight: 0.25)
        orig_geom = fingerprint.geometry or {}
        cand_geom = cand.get("geometry") or {}
        
        # Distance in viewport coordinates
        dx = abs(orig_geom.get("x_pct", 0.0) - cand_geom.get("x_pct", 0.0))
        dy = abs(orig_geom.get("y_pct", 0.0) - cand_geom.get("y_pct", 0.0))
        dist = (dx**2 + dy**2)**0.5
        coord_score = max(0.0, 1.0 - (dist * 2.0))
        
        # Size matching
        dw = abs(orig_geom.get("w", 0.0) - cand_geom.get("w", 0.0))
        dh = abs(orig_geom.get("h", 0.0) - cand_geom.get("h", 0.0))
        denom = (orig_geom.get("w", 1.0) + orig_geom.get("h", 1.0) + 1.0)
        size_score = max(0.0, 1.0 - ((dw + dh) / denom))

        tier4_score = (coord_score * 0.5) + (size_score * 0.5)

        # Overall weighted similarity score
        overall = (tier2_score * 0.5) + (tier3_score * 0.25) + (tier4_score * 0.25)

        # Exact ID or TestID match is a highly specific signal that can survive structural/visual changes
        if orig_attrs.get("id") and orig_attrs.get("id") == cand_attrs.get("id"):
            overall = max(overall, 0.90)
        for test_key in ["data-testid", "data-test", "data-qa"]:
            if orig_attrs.get(test_key) and orig_attrs.get(test_key) == cand_attrs.get(test_key):
                overall = max(overall, 0.90)
                
        return overall

async def attempt_self_healing(page, fingerprint_dict: Optional[Dict[str, Any]], confidence_threshold: float = 0.85) -> Optional[Any]:
    """
    Attempt to locate element on page using visual/context self-healing.
    Collects candidates of same tag name, scores them, checks for ambiguity, and returns located Element if matched.
    """
    if not fingerprint_dict:
        return None

    fingerprint = ElementFingerprint.from_dict(fingerprint_dict)
    tag = fingerprint.tag or "*"

    # Evaluate candidate collection script on the page
    try:
        candidates = await page.evaluate("""
            (tagQuery) => {
                const elements = Array.from(document.querySelectorAll(tagQuery));
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                
                return elements.map((el, index) => {
                    const rect = el.getBoundingClientRect();
                    const parent = el.parentElement;
                    const parentInfo = parent ? {
                        tag: parent.tagName.toLowerCase(),
                        classes: Array.from(parent.classList),
                        text_head: parent.innerText ? parent.innerText.substring(0, 30).trim() : ""
                    } : null;

                    const siblings = [];
                    if (parent) {
                        let sibCurrent = parent.firstElementChild;
                        while (sibCurrent) {
                            if (sibCurrent !== el) {
                                siblings.push({
                                    tag: sibCurrent.tagName.toLowerCase()
                                });
                            }
                            sibCurrent = sibCurrent.nextElementSibling;
                        }
                    }
                    
                    const tempId = 'heal-' + index + '-' + Math.random().toString(36).substring(2, 7);
                    el.setAttribute('data-sw-heal-id', tempId);

                    return {
                        heal_id: tempId,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText ? el.innerText.trim() : "",
                        attributes: Array.from(el.attributes).reduce((acc, a) => {
                            if (a.name !== 'data-sw-heal-id') {
                                acc[a.name] = a.value;
                            }
                            return acc;
                        }, {}),
                        geometry: {
                            x_pct: parseFloat((rect.left / (viewportWidth || 1)).toFixed(4)),
                            y_pct: parseFloat((rect.top / (viewportHeight || 1)).toFixed(4)),
                            w: rect.width,
                            h: rect.height
                        },
                        context: {
                            parent: parentInfo,
                            siblings: siblings,
                            child_count: el.children.length
                        }
                    };
                });
            }
        """, tag)
    except Exception as e:
        log(f"Self-healing: failed to evaluate candidate extraction: {e}", level="error")
        return None

    engine = SelfHealingEngine(confidence_threshold=confidence_threshold)
    scored_candidates = []

    for c in candidates:
        score = engine.score_candidate(fingerprint, c)
        if score >= confidence_threshold:
            scored_candidates.append((score, c))

    # Clean attributes from all candidates except the chosen target (handled below)
    async def clean_all_except(chosen_id: Optional[str] = None):
        await page.evaluate("""
            (chosenId) => {
                document.querySelectorAll('[data-sw-heal-id]').forEach(el => {
                    if (el.getAttribute('data-sw-heal-id') !== chosenId) {
                        el.removeAttribute('data-sw-heal-id');
                    }
                });
            }
        """, chosen_id)

    if not scored_candidates:
        await clean_all_except(None)
        log("Self-healing: no candidate met confidence threshold.")
        return None

    # Sort descending
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_score, top_cand = scored_candidates[0]

    # Verify ambiguity: top score must exceed second score by margin
    if len(scored_candidates) > 1:
        second_score, second_cand = scored_candidates[1]
        if (top_score - second_score) < engine.ambiguity_margin:
            await clean_all_except(None)
            log(f"Self-healing: ambiguous match. Top candidate: {top_score:.3f}, second candidate: {second_score:.3f}", level="warning")
            return None

    # Resolve matched element
    heal_id = top_cand["heal_id"]
    await clean_all_except(heal_id)
    
    # Locate element
    loc = page.locator(f"[data-sw-heal-id='{heal_id}']")
        
    log(f"Self-healing: successfully resolved element of tag <{tag}> with confidence {top_score:.3f}")
    return loc.first
