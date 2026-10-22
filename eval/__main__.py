"""
Evaluation CLI.

  uv run python -m eval run [--pipelines ocr-claude,claude-vision] [--runs 3] [--images 01.jpg,02.png]
  uv run python -m eval report [RUN_FILE]

`run` calls the pipelines and saves raw results to eval/runs/, then prints the report.
`report` re-scores a saved run (the latest by default) without API calls and rewrites eval/REPORT.md.
"""
import argparse
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from time import perf_counter

from image_to_json.model import MODEL
from eval.dataset import load_labels, image_paths
from eval.pipelines import PIPELINES
from eval.report import render, write_report

RUNS_DIRECTORY = Path(__file__).parent.resolve() / 'runs'


def run_one(pipeline: str, path: Path, run: int) -> dict:
    start = perf_counter()
    entry = {"pipeline": pipeline, "image": path.name, "run": run, "error": None, "result": None}
    try:
        entry["result"] = PIPELINES[pipeline](path.read_bytes()).model_dump(mode="json")
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    entry["seconds"] = round(perf_counter() - start, 2)
    return entry


def command_run(args) -> None:
    pipelines = args.pipelines.split(',')
    unknown = [p for p in pipelines if p not in PIPELINES]
    if unknown:
        sys.exit(f"unknown pipeline(s): {', '.join(unknown)}. available: {', '.join(PIPELINES)}")
    paths = image_paths(args.images.split(',') if args.images else None)
    jobs = [(p, path, r) for path in paths for p in pipelines for r in range(1, args.runs + 1)]
    print(f"{len(jobs)} extractions: {len(paths)} invoices x {len(pipelines)} pipelines x {args.runs} runs")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, *job) for job in jobs]
        for done, future in enumerate(as_completed(futures), 1):
            entry = future.result()
            results.append(entry)
            status = "error" if entry["error"] else ("ok" if entry["result"]["success"] else "failed validation")
            print(f"[{done}/{len(jobs)}] {entry['pipeline']:<14} {entry['image']:<18} run {entry['run']}  "
                  f"{entry['seconds']:>5.1f}s  {status}")

    run = {"created": datetime.now().isoformat(timespec='seconds'), "model": MODEL, "pipelines": pipelines,
           "runs": args.runs, "images": [p.name for p in paths], "results": results}
    RUNS_DIRECTORY.mkdir(exist_ok=True)
    run_file = RUNS_DIRECTORY / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    run_file.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\nsaved {run_file}\n")
    report(run_file, write=not args.no_write)


def report(run_file: Path, write: bool = True) -> None:
    run = json.loads(run_file.read_text(encoding='utf-8'))
    labels = load_labels()
    print(render(run, labels))
    if write:
        print(f"wrote {write_report(run, labels, run_file.name)}")


def command_report(args) -> None:
    if args.run_file:
        run_file = Path(args.run_file)
    else:
        runs = sorted(RUNS_DIRECTORY.glob('*.json'))
        if not runs:
            sys.exit("no saved runs in eval/runs/. start with: python -m eval run")
        run_file = runs[-1]
    report(run_file, write=not args.no_write)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m eval", description="Evaluate invoice extraction pipelines")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run pipelines on the dataset and report")
    run_parser.add_argument("--pipelines", default=",".join(PIPELINES), help=f"comma separated: {', '.join(PIPELINES)}")
    run_parser.add_argument("--runs", type=int, default=3, help="runs per invoice, for consistency (default 3)")
    run_parser.add_argument("--images", help="comma separated image names (default: all)")
    run_parser.add_argument("--workers", type=int, default=4, help="parallel extractions (default 4)")
    run_parser.add_argument("--no-write", action="store_true", help="don't rewrite eval/REPORT.md")
    run_parser.set_defaults(func=command_run)

    report_parser = sub.add_parser("report", help="re-score a saved run without API calls")
    report_parser.add_argument("run_file", nargs="?", help="run JSON (default: latest in eval/runs/)")
    report_parser.add_argument("--no-write", action="store_true", help="don't rewrite eval/REPORT.md")
    report_parser.set_defaults(func=command_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
