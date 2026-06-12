import analyzerDiff
import analyzerCore
import analyzerUI

from argparse import ArgumentParser
import os
from datetime import datetime
import json

def generate_report_filenames(args, mode):
    os.makedirs("reports", exist_ok=True)

    exp_part = "-".join(map(str, args.experiments))
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if args.report_name:
        base = args.report_name
    else:
        base = f"analysis_{mode}_exp{exp_part}_{timestamp}"

    return base

def save_json_report(report, path):
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

def get_args():
    parser = ArgumentParser(description="Analyzer")

    # Database
    parser.add_argument(
        "-db", "--database",
        type=str,
        default="central.db",
        help="Database path (default: central.db)"
    )

    # Experiments
    parser.add_argument(
        "-exp", "--experiments",
        type=str,
        required=True,
        help="Comma-separated experiment ids (e.g. 1,2,3)"
    )

    # Modes (mutually exclusive logic handled manually)
    parser.add_argument(
        "--across-browsers",
        action="store_true",
        help="Compare across browsers (default mode)"
    )

    parser.add_argument(
        "--across-versions",
        action="store_true",
        help="Compare across versions (same browser across experiments)"
    )

    # Optional report name
    parser.add_argument(
        "--report-name",
        type=str,
        default=None,
        help="Custom base name for report files (without extension)"
    )

    args = parser.parse_args()

    # Experiments parsing
    try:
        args.experiments = [int(x.strip()) for x in args.experiments.split(",") if x.strip()]
    except ValueError:
        raise ValueError("Invalid --experiments format. Use comma-separated integers (e.g. 1,2,3)")

    # Mode validation
    if args.across_browsers and args.across_versions:
        raise ValueError("Cannot use both --across-browsers and --across-versions at the same time.")

    if not args.across_browsers and not args.across_versions:
        args.across_browsers = True  # default mode

    return args

if __name__ == "__main__":
    args = get_args()
    print(args)
    mode = "versions" if args.across_versions else "browsers"
    base_filename = generate_report_filenames(args, mode)
    detailed_report_path = os.path.join("reports", f"{base_filename}.json")
    
    report_output, simplified_input = analyzerDiff.analyze(args.database, args.experiments, mode=mode)

    simplified_report, simplified_stats = analyzerCore.build_simplified_report(simplified_input)
    report_output["metrics"]["simplification_metrics"] = simplified_stats
    
    save_json_report(report=report_output, path=detailed_report_path)
    print(f"[+] JSON report written to: {detailed_report_path}")
    
    simplified_report_path = os.path.join("reports", f"{base_filename}.html")
    analyzerUI.generate_behavior_report_html(all_browser_sections=simplified_report, output_path=simplified_report_path)
    