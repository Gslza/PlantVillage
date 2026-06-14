#!/usr/bin/env python3
"""
prepare_dataset.py

Script to clean, deduplicate, and split the Tomato Leaf classification dataset.
This script normalizes class names, filters corrupt files, removes duplicates,
performs a stratified split (Train/Val/Test), and generates detailed reports.

Compatible with Windows and Google Colab.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Union, Set

# Standard libraries check. PIL and scikit-learn are expected to be installed.
try:
    from PIL import Image
except ImportError:
    print("[ERROR] PIL (Pillow) is not installed. Please install it using: pip install Pillow")
    sys.exit(1)

try:
    from sklearn.model_selection import train_test_split
except ImportError:
    print("[ERROR] scikit-learn is not installed. Please install it using: pip install scikit-learn")
    sys.exit(1)


# Predefined class mapping
CLASS_MAPPING = {
    "Bacterial_spot227": "bacterial_spot",
    "Early_blight227": "early_blight",
    "healthy227": "healthy",
    "Late_blight227": "late_blight",
    "Leaf_Mold227": "leaf_mold",
    "Septoria_leaf_spot227": "septoria_leaf_spot",
    "Target_Spot227": "target_spot",
    "Tomato_mosaic_virus227": "tomato_mosaic_virus",
    "Tomato_Yellow_Leaf_Curl_Virus227": "tomato_yellow_leaf_curl_virus",
    "Two-spotted_spider_mite227": "two_spotted_spider_mite"
}

# Supported image file extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Prepare and split Tomato Leaves dataset.")
    parser.add_argument(
        "--source",
        type=str,
        default="Dataset of Tomato Leaves/plantvillage/Preprocessed data",
        help="Path to source dataset directory."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="dataset_clean",
        help="Path to output clean dataset directory."
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="Ratio of data for training split (default: 0.8)."
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Ratio of data for validation split (default: 0.1)."
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.1,
        help="Ratio of data for test split (default: 0.1)."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for data splitting (default: 42)."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate output directory if it exists."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the workflow without writing files to disk."
    )
    parser.add_argument(
        "--copy-workers",
        type=int,
        default=4,
        help="Number of threads to copy files in parallel (default: 4)."
    )
    return parser.parse_args()


def get_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def process_single_file(file_path: Path, source_class: str, target_class: str) -> dict:
    """Validate image integrity and calculate its SHA-256 hash."""
    is_corrupt = False
    error_msg = ""
    sha256_hash = ""

    try:
        # Check if file is empty
        if file_path.stat().st_size == 0:
            raise ValueError("File size is 0 bytes")

        # Compute SHA-256
        sha256_hash = get_sha256(file_path)

        # Verify image using Pillow
        with Image.open(file_path) as img:
            img.verify()

        # Load image data to catch truncation
        with Image.open(file_path) as img:
            img.load()

    except Exception as e:
        is_corrupt = True
        error_msg = str(e)

    return {
        "file_path": file_path,
        "source_class": source_class,
        "target_class": target_class,
        "is_corrupt": is_corrupt,
        "error_msg": error_msg,
        "sha256_hash": sha256_hash
    }


def scan_dataset(source_dir: Path, workers: int = 4) -> Tuple[List[dict], List[dict], List[dict]]:
    """Scan directory, verify image integrity, and identify duplicates."""
    # Find all class subdirectories
    class_dirs = [d for d in source_dir.iterdir() if d.is_dir() and d.name in CLASS_MAPPING]
    print(f"[INFO] Kelas ditemukan: {len(class_dirs)}")

    # Gather all file paths to scan
    all_file_tasks = []
    for class_dir in class_dirs:
        source_class = class_dir.name
        target_class = CLASS_MAPPING[source_class]
        for file_path in class_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                all_file_tasks.append((file_path, source_class, target_class))

    print("[INFO] Memeriksa validitas gambar...")
    processed_results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_file, path, src_cls, tgt_cls): path
            for path, src_cls, tgt_cls in all_file_tasks
        }
        for future in as_completed(futures):
            processed_results.append(future.result())

    print("[INFO] Memeriksa gambar duplikat...")
    # Sort alphabetically by path to ensure deterministic duplicate detection
    processed_results.sort(key=lambda x: x["file_path"])

    seen_hashes = {}
    valid_unique = []
    duplicates = []
    corrupt = []

    for item in processed_results:
        if item["is_corrupt"]:
            corrupt.append(item)
        else:
            h = item["sha256_hash"]
            if h in seen_hashes:
                item["is_duplicate"] = True
                item["duplicate_of"] = seen_hashes[h]
                duplicates.append(item)
            else:
                item["is_duplicate"] = False
                item["duplicate_of"] = None
                seen_hashes[h] = item["file_path"]
                valid_unique.append(item)

    return valid_unique, duplicates, corrupt


def perform_split(
    valid_files: List[dict],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Split clean dataset into stratified train, validation, and test subsets."""
    # Group files by target class
    paths = [item["file_path"] for item in valid_files]
    classes = [item["target_class"] for item in valid_files]

    # Validate ratio sum
    if not math.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError(
            f"Ratios must sum to 1.0 (train={train_ratio}, val={val_ratio}, test={test_ratio})"
        )

    # If any ratio is 0.0, handle splitting combinations
    if math.isclose(val_ratio + test_ratio, 0.0):
        # 100% Train
        train_idx = list(range(len(paths)))
        val_idx, test_idx = [], []
    elif math.isclose(train_ratio, 0.0):
        # 0% Train, split Val and Test
        train_idx = []
        if math.isclose(val_ratio, 0.0):
            val_idx = []
            test_idx = list(range(len(paths)))
        elif math.isclose(test_ratio, 0.0):
            val_idx = list(range(len(paths)))
            test_idx = []
        else:
            val_idx, test_idx = train_test_split(
                range(len(paths)),
                test_size=test_ratio / (val_ratio + test_ratio),
                random_state=seed,
                stratify=classes
            )
    else:
        # Standard Train/Val/Test or Train/Val or Train/Test
        val_test_ratio = val_ratio + test_ratio
        train_idx, temp_idx = train_test_split(
            range(len(paths)),
            test_size=val_test_ratio,
            random_state=seed,
            stratify=classes
        )

        temp_classes = [classes[i] for i in temp_idx]
        if math.isclose(test_ratio, 0.0):
            val_idx = temp_idx
            test_idx = []
        elif math.isclose(val_ratio, 0.0):
            val_idx = []
            test_idx = temp_idx
        else:
            val_val, test_val = train_test_split(
                temp_idx,
                test_size=test_ratio / val_test_ratio,
                random_state=seed,
                stratify=temp_classes
            )
            val_idx = val_val
            test_idx = test_val

    # Map back indices to file dict structures
    train_split = [valid_files[i] for i in train_idx]
    val_split = [valid_files[i] for i in val_idx]
    test_split = [valid_files[i] for i in test_idx]

    return train_split, val_split, test_split


def validate_split_manifests(
    train_files: List[dict],
    val_files: List[dict],
    test_files: List[dict],
    expected_total: int,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float
) -> None:
    """Verify that split constraints are met and issue warnings if class counts are low."""
    # 1. Check if splits are not empty if they are expected to have files
    if train_ratio > 0.0 and not train_files:
        raise ValueError("Train split is empty despite non-zero ratio.")
    if val_ratio > 0.0 and not val_files:
        raise ValueError("Validation split is empty despite non-zero ratio.")
    if test_ratio > 0.0 and not test_files:
        raise ValueError("Test split is empty despite non-zero ratio.")

    # 2. Assert no overlap of hashes between splits
    train_hashes = {item["sha256_hash"] for item in train_files}
    val_hashes = {item["sha256_hash"] for item in val_files}
    test_hashes = {item["sha256_hash"] for item in test_files}

    overlap_tr_val = train_hashes.intersection(val_hashes)
    overlap_tr_te = train_hashes.intersection(test_hashes)
    overlap_val_te = val_hashes.intersection(test_hashes)

    if overlap_tr_val:
        raise ValueError(f"leakage detected! Overlap between Train and Validation: {len(overlap_tr_val)} files.")
    if overlap_tr_te:
        raise ValueError(f"leakage detected! Overlap between Train and Test: {len(overlap_tr_te)} files.")
    if overlap_val_te:
        raise ValueError(f"leakage detected! Overlap between Validation and Test: {len(overlap_val_te)} files.")

    # 3. Check total counts match
    total_split = len(train_files) + len(val_files) + len(test_files)
    if total_split != expected_total:
        raise ValueError(
            f"Split elements sum ({total_split}) does not match total valid images ({expected_total})!"
        )

    # 4. Warn if total images per class is very low
    all_assigned_files = train_files + val_files + test_files
    class_counts = Counter(item["target_class"] for item in all_assigned_files)
    for target_class, count in class_counts.items():
        if count < 20:
            print(
                f"[WARNING] Kelas '{target_class}' hanya memiliki total {count} gambar valid. "
                "Jumlah ini mungkin terlalu sedikit untuk pelatihan model yang optimal."
            )


def write_reports(
    output_dir: Path,
    valid_unique: List[dict],
    duplicates: List[dict],
    corrupt: List[dict],
    train_split: List[dict],
    val_split: List[dict],
    test_split: List[dict],
    manifest_tasks: List[Tuple[Path, Path, str, str, str]],
    working_dir: Path
) -> None:
    """Generate final CSV/JSON reports detailing dataset quality and layout."""
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Helper function to get POSIX relative path string
    def get_rel_str(path: Path) -> str:
        try:
            return path.relative_to(working_dir).as_posix()
        except ValueError:
            return path.as_posix()

    # 1. corrupt_files.csv
    corrupt_file_path = reports_dir / "corrupt_files.csv"
    with open(corrupt_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "class_name", "error_message"])
        for item in corrupt:
            writer.writerow([get_rel_str(item["file_path"]), item["target_class"], item["error_msg"]])

    # 2. duplicate_files.csv
    duplicate_file_path = reports_dir / "duplicate_files.csv"
    with open(duplicate_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["duplicate_file", "original_file", "sha256_hash", "class_name"])
        for item in duplicates:
            orig = get_rel_str(item["duplicate_of"]) if item["duplicate_of"] else ""
            writer.writerow([
                get_rel_str(item["file_path"]),
                orig,
                item["sha256_hash"],
                item["target_class"]
            ])

    # 3. class_mapping.json
    class_mapping_path = reports_dir / "class_mapping.json"
    with open(class_mapping_path, "w", encoding="utf-8") as f:
        json.dump(CLASS_MAPPING, f, indent=2)

    # 4. split_manifest.csv
    split_manifest_path = reports_dir / "split_manifest.csv"
    with open(split_manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["original_path", "output_path", "class_name", "split", "sha256_hash"])
        for src, dest, cls_name, split_name, h_val in manifest_tasks:
            writer.writerow([
                get_rel_str(src),
                get_rel_str(dest),
                cls_name,
                split_name,
                h_val
            ])

    # 5. dataset_summary.csv
    # Calculate counts per class
    # Source names are raw folder names, let's map them to normalized keys
    class_stats = {tgt: {
        "original": 0, "valid": 0, "duplicate": 0, "corrupt": 0,
        "train": 0, "val": 0, "test": 0
    } for tgt in CLASS_MAPPING.values()}

    # Parse counts from corrupt, duplicates, and split datasets
    for item in corrupt:
        class_stats[item["target_class"]]["corrupt"] += 1
        class_stats[item["target_class"]]["original"] += 1

    for item in duplicates:
        class_stats[item["target_class"]]["duplicate"] += 1
        class_stats[item["target_class"]]["original"] += 1

    for item in train_split:
        class_stats[item["target_class"]]["train"] += 1
        class_stats[item["target_class"]]["valid"] += 1
        class_stats[item["target_class"]]["original"] += 1

    for item in val_split:
        class_stats[item["target_class"]]["val"] += 1
        class_stats[item["target_class"]]["valid"] += 1
        class_stats[item["target_class"]]["original"] += 1

    for item in test_split:
        class_stats[item["target_class"]]["test"] += 1
        class_stats[item["target_class"]]["valid"] += 1
        class_stats[item["target_class"]]["original"] += 1

    summary_file_path = reports_dir / "dataset_summary.csv"
    with open(summary_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "class_name", "original_count", "valid_count", "duplicate_count",
            "corrupt_count", "train_count", "validation_count", "test_count"
        ])
        for cls_name in sorted(CLASS_MAPPING.values()):
            s = class_stats[cls_name]
            writer.writerow([
                cls_name, s["original"], s["valid"], s["duplicate"],
                s["corrupt"], s["train"], s["val"], s["test"]
            ])


def print_distribution_table(
    train_split: List[dict],
    val_split: List[dict],
    test_split: List[dict]
) -> None:
    """Print the final class split distribution summary in a nicely aligned table."""
    # Count splits per class
    train_counts = Counter(item["target_class"] for item in train_split)
    val_counts = Counter(item["target_class"] for item in val_split)
    test_counts = Counter(item["target_class"] for item in test_split)

    # Print Table
    header = f"\n{'Class':<35}{'Train':<8}{'Validation':<12}{'Test':<8}{'Total':<8}"
    print(header)
    print("-" * len(header))

    total_train = 0
    total_val = 0
    total_test = 0
    total_all = 0

    for cls in sorted(CLASS_MAPPING.values()):
        tr = train_counts.get(cls, 0)
        val = val_counts.get(cls, 0)
        te = test_counts.get(cls, 0)
        tot = tr + val + te

        total_train += tr
        total_val += val
        total_test += te
        total_all += tot

        print(f"{cls:<35}{tr:<8}{val:<12}{te:<8}{tot:<8}")

    print("-" * len(header))
    print(f"{'Total':<35}{total_train:<8}{total_val:<12}{total_test:<8}{total_all:<8}\n")

    # Display class percentage distributions
    if total_all > 0:
        print("Distribusi persentase kelas dalam dataset:")
        for cls in sorted(CLASS_MAPPING.values()):
            tr = train_counts.get(cls, 0)
            val = val_counts.get(cls, 0)
            te = test_counts.get(cls, 0)
            tot = tr + val + te
            pct = (tot / total_all) * 100
            print(f" - {cls:<35} : {pct:6.2f}%")
        print()


def execute_copy_command(task: Tuple[Path, Path]) -> None:
    """Execute copying of a single file from source to target."""
    src, dest = task
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def main() -> None:
    args = parse_arguments()

    working_dir = Path.cwd()
    source_dir = Path(args.source)
    output_dir = Path(args.output)

    # Validate inputs
    if not source_dir.exists():
        print(f"[ERROR] Source folder '{source_dir}' does not exist.")
        sys.exit(1)

    if not source_dir.is_dir():
        print(f"[ERROR] Source path '{source_dir}' is not a directory.")
        sys.exit(1)

    # Handle overwrite condition
    if output_dir.exists() and not args.dry_run:
        if args.overwrite:
            print(f"[INFO] Menghapus folder output lama: {output_dir}")
            shutil.rmtree(output_dir)
        else:
            print(
                f"[ERROR] Output folder '{output_dir}' already exists. "
                "Use --overwrite to delete and recreate it."
            )
            sys.exit(1)

    print("[INFO] Membaca dataset...")
    # 1. Scan and clean dataset
    valid_unique, duplicates, corrupt = scan_dataset(source_dir, workers=8)

    # 2. Print scanned summary info
    print(f"[INFO] Scan complete. Valid & Unique: {len(valid_unique)}, Duplicates: {len(duplicates)}, Corrupt: {len(corrupt)}")

    # 3. Perform split
    print("[INFO] Membagi dataset...")
    try:
        train_split, val_split, test_split = perform_split(
            valid_files=valid_unique,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed
        )
    except Exception as e:
        print(f"[ERROR] Failed splitting dataset: {e}")
        sys.exit(1)

    # 4. Run post-split validation checks
    try:
        validate_split_manifests(
            train_files=train_split,
            val_files=val_split,
            test_files=test_split,
            expected_total=len(valid_unique),
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio
        )
    except Exception as e:
        print(f"[ERROR] Post-split validation failed: {e}")
        sys.exit(1)

    # 5. Generate copying task map and manifest entries
    copy_tasks = []  # List[Tuple[src_path, dest_path]]
    manifest_tasks = []  # List[Tuple[src_path, dest_path, class_name, split, hash]]

    # Define a helper mapping of splits
    split_configs = [
        ("train", train_split),
        ("validation", val_split),
        ("test", test_split)
    ]

    for split_name, split_files in split_configs:
        # Group files by class to assign sequential indexing
        class_groups = {}
        for item in split_files:
            cls = item["target_class"]
            class_groups.setdefault(cls, []).append(item)

        # Generate copy routes
        for class_name, files_in_class in class_groups.items():
            # Sort files alphabetically to ensure deterministic renaming sequence
            files_in_class.sort(key=lambda x: x["file_path"])

            for idx, item in enumerate(files_in_class, start=1):
                src_path = item["file_path"]
                suffix = src_path.suffix.lower()
                new_filename = f"{class_name}_{idx:06d}{suffix}"
                dest_path = output_dir / split_name / class_name / new_filename

                copy_tasks.append((src_path, dest_path))
                manifest_tasks.append((
                    src_path,
                    dest_path,
                    class_name,
                    split_name,
                    item["sha256_hash"]
                ))

    # 6. Copy Files
    if args.dry_run:
        print("[INFO] [DRY RUN] Skipping file copies and directory creations.")
    else:
        # Copying Train
        if args.train_ratio > 0:
            print("[INFO] Menyalin gambar train...")
            train_tasks = [(src, dest) for src, dest in copy_tasks if "/train/" in dest.as_posix()]
            with ThreadPoolExecutor(max_workers=args.copy_workers) as executor:
                list(executor.map(execute_copy_command, train_tasks))

        # Copying Validation
        if args.val_ratio > 0:
            print("[INFO] Menyalin gambar validation...")
            val_tasks = [(src, dest) for src, dest in copy_tasks if "/validation/" in dest.as_posix()]
            with ThreadPoolExecutor(max_workers=args.copy_workers) as executor:
                list(executor.map(execute_copy_command, val_tasks))

        # Copying Test
        if args.test_ratio > 0:
            print("[INFO] Menyalin gambar test...")
            test_tasks = [(src, dest) for src, dest in copy_tasks if "/test/" in dest.as_posix()]
            with ThreadPoolExecutor(max_workers=args.copy_workers) as executor:
                list(executor.map(execute_copy_command, test_tasks))

        # Write reports
        print("[INFO] Menulis laporan...")
        try:
            write_reports(
                output_dir=output_dir,
                valid_unique=valid_unique,
                duplicates=duplicates,
                corrupt=corrupt,
                train_split=train_split,
                val_split=val_split,
                test_split=test_split,
                manifest_tasks=manifest_tasks,
                working_dir=working_dir
            )
        except Exception as e:
            print(f"[ERROR] Failed writing reports: {e}")
            sys.exit(1)

    print("[SUCCESS] Dataset berhasil dirapikan.")

    # 7. Print final tabular report and details
    print_distribution_table(train_split, val_split, test_split)


if __name__ == "__main__":
    main()
