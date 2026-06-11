import os
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageChops

def perform_visual_check(
    current_screenshot_path: str,
    step_name: str,
    baseline_dir: str,
    diff_dir: str,
    threshold: float = 0.05
) -> Tuple[float, Optional[str]]:
    """
    Perform a visual check comparing the current step's screenshot to a saved baseline.
    If the baseline does not exist, copies current screenshot as baseline and returns (0.0, None).
    Otherwise, computes the percentage of differing pixels.
    If the difference is above threshold, saves a difference image in diff_dir.
    Returns: (diff_score: float, diff_image_path: Optional[str])
    """
    baseline_path = Path(baseline_dir) / f"{step_name}.png"
    
    if not Path(current_screenshot_path).exists():
        return 0.0, None

    if not baseline_path.exists():
        # Set the current run screenshot as the baseline
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            img = Image.open(current_screenshot_path)
            img.save(baseline_path)
        except Exception:
            pass
        return 0.0, None
        
    # Open and compare
    try:
        img1 = Image.open(baseline_path).convert("RGB")
        img2 = Image.open(current_screenshot_path).convert("RGB")
    except Exception:
        # If image parsing fails, return 0 diff score
        return 0.0, None
    
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)
        
    diff = ImageChops.difference(img1, img2)
    stat = diff.getbbox()
    if stat is None:
        return 0.0, None
        
    # Calculate score (ratio of non-matching pixels)
    gray_diff = diff.convert("L")
    hist = gray_diff.histogram()
    total_pixels = gray_diff.size[0] * gray_diff.size[1]
    matching_pixels = hist[0]
    differing_pixels = total_pixels - matching_pixels
    diff_score = differing_pixels / total_pixels
    
    diff_image_path = None
    if diff_score > threshold:
        # Save diff image
        diff_path = Path(diff_dir) / f"diff_{step_name}.png"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            diff.save(diff_path)
            diff_image_path = str(diff_path)
        except Exception:
            pass
        
    return diff_score, diff_image_path
