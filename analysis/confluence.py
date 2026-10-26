"""
Confluence Engine (REDESIGNED)
Only H4 Bias + H1 OB/FVG + M15 CRT are required.
M30 / M5 / M1 layers are optional / disabled.
"""

from typing import Dict, List, Optional
import pandas as pd

from config import MIN_CONFLUENCE_SCORE, REQUIRED_LAYERS
from utils.logger import get_logger

from analysis.layer1_h4_bias import analyze_h4
from analysis.layer2_h1_ob_fvg import analyze_h1_ob_fvg
from analysis.layer4_m15_crt import analyze_m15_crt

# Optional imports kept for future use but not required
try:
    from analysis.layer3_m30_msnr import analyze_m30_msnr
    from analysis.layer5_m5_mss import analyze_m5_mss
    from analysis.layer6_m1_entry import analyze_m1_entry
except ImportError:
    pass

logger = get_logger(__name__)


def run_full_analysis(
    pair: str,
    dataframes: Dict[str, pd.DataFrame]
) -> Dict:
    """
    Run the three required layers (H4, H1, M15) and compute confluence.
    """
    logger.info("=" * 60)
    logger.info("Starting HTF analysis (H4 + H1 + M15) for %s", pair)
    logger.info("=" * 60)

    results = {
        "pair": pair,
        "confluence_score": 0,
        "confluence_passed": False,
        "direction": None,
        "layers": {},
        "layer_results": [],
    }

    # ── Layer 1: H4 Market Structure ────────────────────────────────────────
    h4_result = analyze_h4(pair, dataframes.get("H4"))
    results["layers"]["h4_bias"] = h4_result
    results["layer_results"].append({
        "layer": 1,
        "name": "H4 Bias",
        "valid": h4_result.get("valid", False),
        "direction": h4_result.get("bias", "neutral"),
    })

    if not h4_result.get("valid", False):
        logger.info("Layer 1 FAILED — H4 bias is neutral or low confidence")
        return _finalize_results(results)

    direction = h4_result["bias"]
    results["direction"] = direction
    results["confluence_score"] += 1
    logger.info("Layer 1 PASSED — H4 bias: %s (confidence=%.2f)",
                direction, h4_result.get("confidence", 0))

    # ── Layer 2: H1 Order Block + FVG ───────────────────────────────────────
    h1_result = analyze_h1_ob_fvg(pair, dataframes.get("H1"), direction)
    results["layers"]["h1_ob_fvg"] = h1_result
    results["layer_results"].append({
        "layer": 2,
        "name": "H1 OB/FVG",
        "valid": h1_result.get("valid", False),
    })

    if h1_result.get("valid", False):
        results["confluence_score"] += 1
        logger.info("Layer 2 PASSED — H1 OB/FVG aligned")
    else:
        logger.info("Layer 2 FAILED — No valid OB/FVG")
        return _finalize_results(results)

    # ── Layer 3 (original Layer 4): M15 CRT ────────────────────────────────
    m15_result = analyze_m15_crt(pair, dataframes.get("M15"), direction)
    results["layers"]["m15_crt"] = m15_result
    results["layer_results"].append({
        "layer": 3,
        "name": "M15 CRT",
        "valid": m15_result.get("valid", False),
    })

    if m15_result.get("valid", False):
        results["confluence_score"] += 1
        logger.info("Layer 3 PASSED — M15 CRT setup found")
    else:
        logger.info("Layer 3 FAILED — No M15 CRT setup")

    return _finalize_results(results)


def _finalize_results(results: Dict) -> Dict:
    """Apply final confluence rule: all 3 required layers must pass."""
    score = results["confluence_score"]
    results["confluence_passed"] = score >= MIN_CONFLUENCE_SCORE

    if results["confluence_passed"]:
        logger.info("CONFLUENCE PASSED — %d/%d required layers", score, MIN_CONFLUENCE_SCORE)
    else:
        logger.info("CONFLUENCE FAILED — only %d/%d layers passed", score, MIN_CONFLUENCE_SCORE)

    return results
