"""Write a short Markdown summary of a context-coverage run.

Used by .github/workflows/context-coverage.yml to fill $GITHUB_STEP_SUMMARY.
Stdlib only. Reads the collector's JSON (and optionally an earlier run's JSON)
and prints Markdown to stdout.

  context_coverage_summary.py coverage-data.json [--compare previous.json]
"""
import argparse
import json


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_ratio(v):
    return "-" if v is None else f"{v:,.0f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--compare", help="an earlier coverage-data.json")
    args = ap.parse_args()

    doc = load(args.data)
    repos = [r for r in doc.get("repos", []) if r.get("in_scope")]
    prev = {}
    if args.compare:
        prev = {r["name"]: r for r in load(args.compare).get("repos", [])}

    src = doc.get("source", {})
    with_ctx = [r for r in repos if r.get("has_context")]
    stale = [r for r in repos if r.get("freshness") == "stale"]
    errored = [r for r in doc.get("repos", []) if r.get("errors")]

    out = ["## Context coverage", ""]
    out.append(f"- Source: `{src.get('mode')}` {src.get('org') or src.get('path') or ''}".rstrip())
    out.append(f"- Generated: {doc.get('generated_at')}")
    out.append(f"- Repos analyzed: **{len(repos)}** of {len(doc.get('repos', []))} scanned")
    out.append(f"- With any agent context: **{len(with_ctx)}**, without: **{len(repos) - len(with_ctx)}**")
    out.append(f"- Stale context: **{len(stale)}**")
    if errored:
        out.append(f"- Repos with scan errors (partial data): {len(errored)}")
    if args.compare:
        out.append(f"- Compared against the run from {load(args.compare).get('generated_at')}")
    out += ["", "| Repo | Context lines | LOC per context line | Freshness |"
            + (" Change in context lines |" if prev else ""),
            "|---|---:|---:|---|" + ("---:|" if prev else "")]
    for r in sorted(repos, key=lambda r: (r.get("total_context_lines") or 0)):
        row = (f"| {r['name']} | {r.get('total_context_lines') or 0:,} | "
               f"{fmt_ratio(r.get('loc_per_context_line'))} | {r.get('freshness') or '-'} |")
        if prev:
            p = prev.get(r["name"])
            if p is None:
                row += " new |"
            else:
                d = (r.get("total_context_lines") or 0) - (p.get("total_context_lines") or 0)
                row += f" {d:+,} |"
        out.append(row)
    out += ["", "Open the `context-coverage-report.html` file in this run's artifact for the full "
            "report (things to check, per-repo detail, folder trees)."]
    print("\n".join(out))


if __name__ == "__main__":
    main()
