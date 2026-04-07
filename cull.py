import argparse
import csv
import os
import shutil
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import imagehash
import numpy as np
import rawpy
from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".dng",
    ".rw2",
    ".orf",
}

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".rw2", ".orf"}


@dataclass
class PhotoInfo:
    file_name: str
    path: str
    width: int
    height: int
    blur_score: float
    brightness: float
    hash_value: imagehash.ImageHash
    quality_score: float
    rejection_reasons: List[str]
    duplicate_of: Optional[str] = None


def iter_image_files(source_dir: str) -> Iterable[str]:
    for name in sorted(os.listdir(source_dir)):
        path = os.path.join(source_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            yield path


def load_image_rgb(path: str) -> np.ndarray:
    ext = os.path.splitext(path)[1].lower()
    if ext in RAW_EXTENSIONS:
        with rawpy.imread(path) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False)
        return rgb

    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def compute_blur_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_quality_score(blur_score: float, brightness: float, width: int, height: int) -> float:
    blur_component = min(1.0, blur_score / 300.0)
    exposure_component = 1.0 - min(1.0, abs(brightness - 128.0) / 128.0)
    resolution_component = min(1.0, (width * height) / 12_000_000.0)
    return (0.55 * blur_component) + (0.35 * exposure_component) + (0.10 * resolution_component)


def analyze_image(
    path: str,
    blur_threshold: float,
    min_pixels: int,
    underexposed_threshold: float,
    overexposed_threshold: float,
) -> PhotoInfo:
    rgb = load_image_rgb(path)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape

    blur_score = compute_blur_score(gray)
    brightness = float(np.mean(gray))
    hash_value = imagehash.phash(Image.fromarray(rgb))
    quality_score = compute_quality_score(blur_score, brightness, width, height)

    reasons: List[str] = []
    if blur_score < blur_threshold:
        reasons.append("blurry")
    if width * height < min_pixels:
        reasons.append("low_resolution")
    if brightness < underexposed_threshold:
        reasons.append("underexposed")
    if brightness > overexposed_threshold:
        reasons.append("overexposed")

    return PhotoInfo(
        file_name=os.path.basename(path),
        path=path,
        width=width,
        height=height,
        blur_score=blur_score,
        brightness=brightness,
        hash_value=hash_value,
        quality_score=quality_score,
        rejection_reasons=reasons,
    )


def copy_or_move(src: str, dst: str, move_files: bool) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if move_files:
        shutil.move(src, dst)
    else:
        shutil.copy2(src, dst)


def choose_winner(a: PhotoInfo, b: PhotoInfo) -> Tuple[PhotoInfo, PhotoInfo]:
    if b.quality_score > a.quality_score:
        return b, a
    return a, b


def write_report(report_path: str, rows: List[dict]) -> None:
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    fieldnames = [
        "file_name",
        "decision",
        "reason",
        "duplicate_of",
        "blur_score",
        "brightness",
        "resolution",
        "quality_score",
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def file_day_key(path: str) -> str:
    # Group by file modified day as a practical fallback across formats.
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def apply_daily_top_n(
    winners: List[PhotoInfo],
    top_per_day: int,
    culled_dir: str,
    rejected_dir: str,
    report_by_name: Dict[str, dict],
) -> Tuple[List[PhotoInfo], List[PhotoInfo]]:
    if top_per_day <= 0:
        return winners, []

    grouped: Dict[str, List[PhotoInfo]] = {}
    for info in winners:
        grouped.setdefault(file_day_key(info.path), []).append(info)

    kept: List[PhotoInfo] = []
    demoted: List[PhotoInfo] = []

    for day, photos in grouped.items():
        ranked = sorted(photos, key=lambda p: p.quality_score, reverse=True)
        day_kept = ranked[:top_per_day]
        day_demoted = ranked[top_per_day:]
        kept.extend(day_kept)

        for info in day_kept:
            report_by_name[info.file_name] = {
                "file_name": info.file_name,
                "decision": "keep",
                "reason": f"top_{top_per_day}_for_day:{day}",
                "duplicate_of": "",
                "blur_score": f"{info.blur_score:.2f}",
                "brightness": f"{info.brightness:.2f}",
                "resolution": f"{info.width}x{info.height}",
                "quality_score": f"{info.quality_score:.4f}",
            }

        for info in day_demoted:
            demoted.append(info)
            culled_path = os.path.join(culled_dir, info.file_name)
            rejected_path = os.path.join(rejected_dir, info.file_name)
            if os.path.exists(culled_path):
                shutil.move(culled_path, rejected_path)
            report_by_name[info.file_name] = {
                "file_name": info.file_name,
                "decision": "reject",
                "reason": f"daily_ranking_excess:{day}",
                "duplicate_of": "",
                "blur_score": f"{info.blur_score:.2f}",
                "brightness": f"{info.brightness:.2f}",
                "resolution": f"{info.width}x{info.height}",
                "quality_score": f"{info.quality_score:.4f}",
            }

    return kept, demoted


def run_culling(
    source_dir: str,
    culled_dir: str,
    rejected_dir: str,
    report_path: str,
    duplicate_threshold: int,
    blur_threshold: float,
    min_pixels: int,
    underexposed_threshold: float,
    overexposed_threshold: float,
    top_per_day: int,
    move_files: bool,
) -> None:
    os.makedirs(culled_dir, exist_ok=True)
    os.makedirs(rejected_dir, exist_ok=True)

    winners: List[PhotoInfo] = []
    rejected: List[PhotoInfo] = []
    report_by_name: Dict[str, dict] = {}

    for path in iter_image_files(source_dir):
        try:
            info = analyze_image(
                path,
                blur_threshold=blur_threshold,
                min_pixels=min_pixels,
                underexposed_threshold=underexposed_threshold,
                overexposed_threshold=overexposed_threshold,
            )
        except Exception as exc:
            report_by_name[os.path.basename(path)] = {
                "file_name": os.path.basename(path),
                "decision": "reject",
                "reason": f"read_error:{exc}",
                "duplicate_of": "",
                "blur_score": "",
                "brightness": "",
                "resolution": "",
                "quality_score": "",
            }
            copy_or_move(path, os.path.join(rejected_dir, os.path.basename(path)), move_files)
            continue

        if info.rejection_reasons:
            rejected.append(info)
            copy_or_move(path, os.path.join(rejected_dir, info.file_name), move_files)
            report_by_name[info.file_name] = {
                "file_name": info.file_name,
                "decision": "reject",
                "reason": ";".join(info.rejection_reasons),
                "duplicate_of": "",
                "blur_score": f"{info.blur_score:.2f}",
                "brightness": f"{info.brightness:.2f}",
                "resolution": f"{info.width}x{info.height}",
                "quality_score": f"{info.quality_score:.4f}",
            }
            continue

        duplicate_index: Optional[int] = None
        for idx, existing in enumerate(winners):
            if abs(existing.hash_value - info.hash_value) <= duplicate_threshold:
                duplicate_index = idx
                break

        if duplicate_index is None:
            winners.append(info)
            copy_or_move(path, os.path.join(culled_dir, info.file_name), move_files)
            report_by_name[info.file_name] = {
                "file_name": info.file_name,
                "decision": "keep",
                "reason": "best_candidate",
                "duplicate_of": "",
                "blur_score": f"{info.blur_score:.2f}",
                "brightness": f"{info.brightness:.2f}",
                "resolution": f"{info.width}x{info.height}",
                "quality_score": f"{info.quality_score:.4f}",
            }
            continue

        current_winner = winners[duplicate_index]
        new_winner, loser = choose_winner(current_winner, info)
        winners[duplicate_index] = new_winner

        loser.duplicate_of = new_winner.file_name
        rejected.append(loser)

        if loser is current_winner:
            old_winner_path = os.path.join(culled_dir, current_winner.file_name)
            if os.path.exists(old_winner_path):
                copy_or_move(old_winner_path, os.path.join(rejected_dir, current_winner.file_name), True)
            copy_or_move(path, os.path.join(culled_dir, info.file_name), move_files)
        else:
            copy_or_move(path, os.path.join(rejected_dir, info.file_name), move_files)

        report_by_name[loser.file_name] = {
            "file_name": loser.file_name,
            "decision": "reject",
            "reason": "near_duplicate",
            "duplicate_of": new_winner.file_name,
            "blur_score": f"{loser.blur_score:.2f}",
            "brightness": f"{loser.brightness:.2f}",
            "resolution": f"{loser.width}x{loser.height}",
            "quality_score": f"{loser.quality_score:.4f}",
        }

    winners, demoted = apply_daily_top_n(
        winners=winners,
        top_per_day=top_per_day,
        culled_dir=culled_dir,
        rejected_dir=rejected_dir,
        report_by_name=report_by_name,
    )
    rejected.extend(demoted)

    report_rows = [report_by_name[name] for name in sorted(report_by_name)]
    write_report(report_path, report_rows)

    print(
        f"Done. kept={len(winners)} rejected={len(rejected)} report={report_path} "
        f"mode={'move' if move_files else 'copy'}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-cull images by quality and near-duplicate detection.")
    parser.add_argument("--source", default="RAW", help="Input folder containing photos.")
    parser.add_argument("--culled", default="CULLED", help="Folder where best candidates are placed.")
    parser.add_argument("--rejected", default="REJECTED", help="Folder where bad/redundant images are placed.")
    parser.add_argument("--report", default="cull_report.csv", help="CSV report with keep/reject reasons.")
    parser.add_argument("--duplicate-threshold", type=int, default=7, help="pHash distance cutoff for near duplicates.")
    parser.add_argument("--blur-threshold", type=float, default=85.0, help="Minimum Laplacian variance to avoid blur rejection.")
    parser.add_argument("--min-pixels", type=int, default=1_000_000, help="Minimum pixel count before resolution rejection.")
    parser.add_argument("--underexposed", type=float, default=30.0, help="Reject if average brightness is below this value.")
    parser.add_argument("--overexposed", type=float, default=225.0, help="Reject if average brightness is above this value.")
    parser.add_argument("--top-per-day", type=int, default=0, help="Keep only top N by quality score per day after dedupe (0 disables).")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying them.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_culling(
        source_dir=args.source,
        culled_dir=args.culled,
        rejected_dir=args.rejected,
        report_path=args.report,
        duplicate_threshold=args.duplicate_threshold,
        blur_threshold=args.blur_threshold,
        min_pixels=args.min_pixels,
        underexposed_threshold=args.underexposed,
        overexposed_threshold=args.overexposed,
        top_per_day=args.top_per_day,
        move_files=args.move,
    )


if __name__ == "__main__":
    main()