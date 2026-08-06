"""Print a readable summary of a trained model bundle.

Usage:

    python -m scripts.inspect_metadata
    python -m scripts.inspect_metadata --model-dir models --json
"""

import argparse
import json
from pathlib import Path

from app.ml.registry import REQUIRED_ARTIFACTS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect trained model artifacts and metadata.")
    parser.add_argument("--model-dir", default="models", help="Directory holding the trained artifacts.")
    parser.add_argument("--json", action="store_true", help="Print raw metadata.json instead of a summary.")
    return parser.parse_args()


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} GB"


def print_metrics(title: str, metrics: dict) -> None:
    print(title)
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"    {name:<20} {value:.4f}")
        else:
            print(f"    {name:<20} {value:,}" if isinstance(value, int) else f"    {name:<20} {value}")


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir)

    if not model_dir.exists():
        raise SystemExit(
            f"Model directory not found: {model_dir.resolve()}\n"
            "Run `python -m scripts.train --transactions <dataset>` first, "
            "or pass --model-dir."
        )

    metadata_path = model_dir / "metadata.json"
    if not metadata_path.exists():
        raise SystemExit(f"No metadata.json in {model_dir.resolve()}. The bundle is incomplete.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if args.json:
        print(json.dumps(metadata, indent=2))
        return

    print(f"Model bundle: {model_dir.resolve()}")
    print()
    print(f"  version      {metadata.get('model_version', 'unknown')}")
    print(f"  created_at   {metadata.get('created_at', 'unknown')}")
    print(f"  demo_mode    {metadata.get('demo_mode', False)}")

    features = metadata.get("feature_columns") or []
    if features:
        print(f"  features     {len(features)}: {', '.join(features)}")

    churn_training = metadata.get("churn_training") or {}
    if churn_training:
        print()
        print("  Churn training:")
        for key in ("strategy", "prediction_window_days", "min_history_days", "snapshots", "rows", "customers"):
            if key in churn_training:
                value = churn_training[key]
                print(f"    {key:<24} {value:,}" if isinstance(value, int) else f"    {key:<24} {value}")

    metrics = metadata.get("metrics") or {}
    if metrics:
        print()
        print("  Metrics:")
        for group, values in metrics.items():
            if isinstance(values, dict):
                print_metrics(f"  {group}:", values)

    print()
    print("  Artifacts:")
    missing = []
    for label, filename in REQUIRED_ARTIFACTS.items():
        path = model_dir / filename
        if path.exists():
            print(f"    [ok]      {label:<12} {filename:<22} {human_size(path.stat().st_size):>10}")
        else:
            missing.append(filename)
            print(f"    [MISSING] {label:<12} {filename}")

    print()
    if missing:
        raise SystemExit(f"Incomplete bundle: {len(missing)} artifact(s) missing. The API will not start.")
    print("Bundle is complete.")


if __name__ == "__main__":
    main()
