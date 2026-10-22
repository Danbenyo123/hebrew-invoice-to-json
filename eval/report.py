"""Turn a saved run into comparison tables for the terminal and eval/REPORT.md."""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from image_to_json.schemas import Invoice
from eval.dataset import Label
from eval.scoring import OUTCOMES, CORRECT, FIELD_WEIGHTS, score_invoice, weighted_score, consistency

REPORT_PATH = Path(__file__).parent.resolve() / 'REPORT.md'


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _avg(values) -> float | None:
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def _entries(run: dict) -> dict:
    """results grouped as {pipeline: {image: [entry, ...]}}, with invoices parsed"""
    grouped = defaultdict(lambda: defaultdict(list))
    for entry in run["results"]:
        result = entry.get("result") or {}
        invoice = result.get("invoice")
        grouped[entry["pipeline"]][entry["image"]].append({
            **entry,
            "invoice": Invoice.model_validate(invoice) if invoice else None,
            "success": result.get("success", False),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
        })
    return grouped


def summarize(run: dict, labels: dict[str, Label]) -> dict:
    summary = {"pipelines": {}, "images": defaultdict(dict), "fields": defaultdict(dict)}
    for pipeline, images in _entries(run).items():
        stats = {"scores": [], "unverified_scores": [], "outcomes": Counter(), "consistency": [],
                 "honest": 0, "expected_failures": 0, "unexpected_failures": 0, "errors": 0,
                 "seconds": [], "input_tokens": [], "output_tokens": []}
        field_outcomes = defaultdict(Counter)
        for image, entries in images.items():
            label = labels.get(image)
            image_scores = []
            for e in entries:
                stats["seconds"].append(e["seconds"])
                stats["input_tokens"].append(e["input_tokens"])
                stats["output_tokens"].append(e["output_tokens"])
                if e["error"]:
                    stats["errors"] += 1
                if label is None:
                    continue
                if label.expect_failure:
                    stats["expected_failures"] += 1
                    stats["honest"] += int(not e["success"] and not e["error"])
                elif not e["success"]:
                    stats["unexpected_failures"] += 1
                results = score_invoice(label.invoice, e["invoice"])
                image_scores.append(weighted_score(results))
                if label.verified:
                    stats["outcomes"].update(r.outcome for r in results)
                    for r in results:
                        field_outcomes[r.field][r.outcome] += 1
            if label is not None:
                stats["scores" if label.verified else "unverified_scores"] += image_scores
            stats["consistency"].append(consistency([e["invoice"] for e in entries]))
            summary["images"][image][pipeline] = {
                "score": _avg(image_scores),
                "consistency": consistency([e["invoice"] for e in entries]),
                "label": "—" if label is None else ("verified" if label.verified else "draft"),
                "failed": sum(1 for e in entries if not e["success"]),
                "runs": len(entries),
            }
        for field, counts in field_outcomes.items():
            summary["fields"][field][pipeline] = counts[CORRECT] / sum(counts.values())
        summary["pipelines"][pipeline] = stats
    return summary


def _table(headers: list[str], rows: list[list[str]], markdown: bool) -> str:
    if markdown:
        lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
        return "\n".join(lines)
    widths = [max(len(str(c)) for c in col) for col in zip(headers, *rows)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    return "\n".join([fmt.format(*headers), fmt.format(*("-" * w for w in widths))] + [fmt.format(*r) for r in rows])


def render(run: dict, labels: dict[str, Label], markdown: bool = False) -> str:
    summary = summarize(run, labels)
    pipelines = list(summary["pipelines"])
    out = []

    rows = []
    for name, s in summary["pipelines"].items():
        counted = sum(s["outcomes"].values()) or 1
        rows.append([
            name,
            _pct(_avg(s["scores"])),
            _pct(_avg(s["unverified_scores"])),
            *(f"{s['outcomes'][o]} ({s['outcomes'][o] / counted * 100:.0f}%)" for o in OUTCOMES),
            f"{s['honest']}/{s['expected_failures']}",
            str(s["unexpected_failures"]),
            _pct(_avg(s["consistency"])),
            f"{_avg(s['seconds']) or 0:.1f}s",
            f"{_avg(s['input_tokens']) or 0:,.0f} / {_avg(s['output_tokens']) or 0:,.0f}",
        ])
    out += ["Summary" if not markdown else "## Summary", "",
            _table(["pipeline", "score (verified)", "score (draft labels)", "correct", "missed", "wrong",
                    "hallucinated", "honest failures", "unexpected failures", "consistency", "avg time",
                    "avg tokens in / out"], rows, markdown), ""]

    rows = [[field, *(_pct(summary["fields"][field].get(p)) for p in pipelines)]
            for field in sorted(summary["fields"], key=lambda f: (-FIELD_WEIGHTS.get(f.split('.')[0], 1), f))]
    out += ["Accuracy per field (verified labels)" if not markdown else "## Accuracy per field (verified labels)", "",
            _table(["field", *pipelines], rows, markdown), ""]

    rows = []
    for image in sorted(summary["images"]):
        per = summary["images"][image]
        any_p = next(iter(per.values()))
        rows.append([image, any_p["label"],
                     *(f"{_pct(per[p]['score'])} · {_pct(per[p]['consistency'])} · {per[p]['failed']}/{per[p]['runs']} failed"
                       if p in per else "—" for p in pipelines)])
    out += ["Per image (score · consistency · failed validation)" if not markdown
            else "## Per image (score · consistency · failed validation)", "",
            _table(["image", "label", *pipelines], rows, markdown), ""]
    return "\n".join(out)


def public_run(run: dict, labels: dict[str, Label]) -> dict:
    """the run without images whose labels are private"""
    private = {name for name, label in labels.items() if label.private}
    return {**run, "images": [i for i in run["images"] if i not in private],
            "results": [r for r in run["results"] if r["image"] not in private]}


def write_report(run: dict, labels: dict[str, Label], run_name: str) -> Path:
    run = public_run(run, labels)
    header = f"""# Evaluation report

Run `{run_name}` · model `{run['model']}` · {run['runs']} run(s) per invoice · {len(run['images'])} invoices

**How to read it**
- **score**: weighted share of correct fields per invoice, averaged over invoices and runs. Weights: invoice number, total and line items ×3; date, VAT, before-VAT and supplier ID ×2; other fields ×1. Fields empty in both the label and the extraction aren't counted.
- **missed / wrong / hallucinated**: a labeled value left empty / a different value / a value invented where the label is empty.
- **honest failures**: on invoices that should fail validation (blank template, missing total), how often the pipeline failed instead of inventing data.
- **consistency**: for repeated runs on the same invoice, the share of runs agreeing on each field.
- **draft labels** were written from the images and are not yet human-verified, so they are reported separately.

"""
    REPORT_PATH.write_text(header + render(run, labels, markdown=True), encoding='utf-8')
    return REPORT_PATH
