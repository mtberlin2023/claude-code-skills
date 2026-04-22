#!/usr/bin/env python3
"""
Expert Usage Audit — analyses Claude Code JSONL session logs
to score expert maturity level (L0–L5) per session and per domain.

No user input required. Runs entirely against local JSONL data.

Usage:
    python3 expert-audit.py [--project=PROJECT_DIR_NAME] [--json] [--recent N]

The scoring rubric is internal. The output shows levels and coverage,
not the detection criteria.
"""

import json
import glob
import os
import re
import sys
import argparse
from collections import defaultdict
from pathlib import Path


# ── Domain taxonomy (internal — maps expert filenames to domains) ──────────

DOMAIN_MAP = {
    "Technical": [
        "technical-architect", "mobile-architect", "lead-developer",
        "technical-architecture"
    ],
    "UX & Design": [
        "ux-director", "ux-frontier", "journey-architect", "brand-designer",
        "accessibility-expert", "brand-book", "ux-manual"
    ],
    "Legal": [
        "legal-counsel", "legal-reviewer", "legal-adversary",
        "legal-playbook", "legal-process"
    ],
    "Content": [
        "publishing-director", "content-strategist", "marketing-strategist",
        "technical-writer", "seo-expert", "audio-producer", "course-architect",
        "content-playbook", "course-design-playbook", "documentation-playbook"
    ],
    "Strategy": [
        "strategic-advisor", "poc-expert", "creative-ideator", "davos-expert",
        "landscape-researcher", "product-manager", "founder-in-residence",
        "conference-curator"
    ],
    "Quality": ["qa-lead", "security-reviewer"],
    "Meta/System": [
        "expert-coach", "calibration-analyst", "expert-system-architect",
        "learning-designer", "expert-operating-system", "expert-protocol",
        "expert-onboarding", "development-tracker"
    ],
    "Art": ["art-director", "art-forensics", "art-critic", "digital-artist"],
    "Production": [
        "music-video-director", "casting-agent", "location-scout",
        "production-designer", "stylist", "colourist", "dop",
        "prompt-director", "editor", "music-producer", "music-lyricist",
        "music-architect", "music-ar"
    ],
    "Research": [
        "qual-research-lead", "research-synthesist", "research-analyst",
        "conference-scout", "expert-architect", "case-study-hunter",
        "landscape-analyst"
    ],
}

DOMAIN_ORDER = [
    "Technical", "UX & Design", "Legal", "Content", "Strategy",
    "Quality", "Meta/System", "Art", "Production", "Research"
]

EXPERT_SKILL_KEYWORDS = [
    "expert", "calibrat", "360", "coach", "drill", "review-session"
]

META_EXPERT_KEYWORDS = [
    "coach", "calibrat", "system-architect", "learning-designer"
]

EXPERT_FRAMING_RE = re.compile(
    r"(you are|act as|you're now|speaking as|I am)\s+"
    r"(a |an |the )?"
    r"(expert|specialist|advisor|counsel|architect|director|coach|"
    r"analyst|designer|strategist|producer|reviewer|scout|critic)",
    re.I,
)

MT_CODE_RE = re.compile(r"MT-[A-Z]{2}\d{2}")


# ── Session scoring ───────────────────────────────────────────────────────

def score_session(filepath):
    """Analyse one JSONL session file and return signal dict + computed level."""
    signals = {
        "has_persona_read": False,
        "has_memory_read": False,
        "has_notepad_read": False,
        "has_playbook_read": False,
        "has_kp_read": False,
        "has_focus_group": False,
        "has_meta_expert": False,
        "has_cross_expert": False,
        "has_expert_skill": False,
        "has_inline_framing": False,
        "has_mt_code": False,
        "has_feedforward": False,
        "has_compliance": False,
        "persona_count": 0,
    }

    personas = set()
    domains_hit = set()
    timestamp = None

    with open(filepath) as fh:
        for line in fh:
            try:
                obj = json.loads(line.strip())
            except (json.JSONDecodeError, ValueError):
                continue

            ts = obj.get("timestamp")
            if ts and not timestamp:
                timestamp = ts[:10]

            msg = obj.get("message", {})
            content = msg.get("content", [])

            # ── scan text content ──
            texts = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))

            for text in texts:
                if EXPERT_FRAMING_RE.search(text):
                    signals["has_inline_framing"] = True
                if MT_CODE_RE.search(text):
                    signals["has_mt_code"] = True
                if "feedforward" in text.lower():
                    signals["has_feedforward"] = True
                if "compliance" in text.lower() and "register" in text.lower():
                    signals["has_compliance"] = True

            # ── scan tool_use blocks ──
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue

                    name = block.get("name", "")
                    inp = block.get("input", {})

                    if name == "Read":
                        fp = inp.get("file_path", "")
                        fn = fp.split("/")[-1]
                        stem = fn.replace(".md", "").replace(".memory", "").replace(".notepad", "")

                        if "experts/" in fp:
                            if ".memory" in fn:
                                signals["has_memory_read"] = True
                            elif ".notepad" in fn:
                                signals["has_notepad_read"] = True
                            elif any(x in fn for x in ("playbook", "guide", "manual")):
                                signals["has_playbook_read"] = True
                            elif "knowledge-pack" in fp:
                                signals["has_kp_read"] = True
                            elif fn.endswith(".md") and not fn.startswith(("EXPERT", "AGENT")):
                                signals["has_persona_read"] = True
                                personas.add(fn)
                                if any(m in fn for m in META_EXPERT_KEYWORDS):
                                    signals["has_meta_expert"] = True

                            # domain detection
                            for domain, patterns in DOMAIN_MAP.items():
                                if any(p in stem for p in patterns):
                                    domains_hit.add(domain)
                                    break

                        elif "focus-group" in fp:
                            signals["has_focus_group"] = True
                            domains_hit.add("Research")
                        elif "compliance-register" in fp:
                            signals["has_compliance"] = True

                    elif name == "Skill":
                        sk = inp.get("skill", "")
                        if any(e in sk for e in EXPERT_SKILL_KEYWORDS):
                            signals["has_expert_skill"] = True
                            domains_hit.add("Meta/System")
                        if "focus-group" in sk:
                            signals["has_focus_group"] = True
                            domains_hit.add("Research")

    signals["persona_count"] = len(personas)
    signals["has_cross_expert"] = len(personas) >= 2

    # ── compute level ──
    level = 0
    if signals["has_inline_framing"]:
        level = max(level, 1)
    if signals["has_mt_code"] and level == 0:
        level = 1
    if signals["has_persona_read"] or signals["has_memory_read"]:
        level = max(level, 2)
    if signals["has_playbook_read"] or signals["has_kp_read"]:
        level = max(level, 3)
    if signals["has_expert_skill"] or signals["has_compliance"]:
        level = max(level, 4)
    if signals["has_meta_expert"] and signals["has_cross_expert"]:
        level = max(level, 4)
    if signals["has_feedforward"] or (signals["has_meta_expert"] and signals["has_expert_skill"]):
        level = max(level, 5)

    return {
        "timestamp": timestamp,
        "level": level,
        "domains": sorted(domains_hit),
        "persona_count": signals["persona_count"],
        **signals,
    }


# ── Roster scanning (available vs. invoked) ──────────────────────────────

def scan_roster(session_dir):
    """Scan the working directory for expert persona files on disk.

    Walks up from the session_dir project path to find an experts/ directory,
    then maps each persona file to a domain. Returns dict of domain -> set of
    filenames that *exist* on disk (available), independent of invocation.
    """
    available = defaultdict(set)

    # Try to find the repo root from the project dir name
    # e.g. -Users-markturrell-Documents-SuperMark -> /Users/markturrell/Documents/SuperMark
    dir_name = Path(session_dir).name
    repo_path = "/" + dir_name.lstrip("-").replace("-", "/")

    # Common expert directory patterns
    candidates = [
        Path(repo_path) / "_shared" / "experts",
        Path(repo_path) / "experts",
        Path(repo_path) / ".experts",
    ]

    expert_dir = None
    for c in candidates:
        if c.is_dir():
            expert_dir = c
            break

    if not expert_dir:
        return available

    for f in expert_dir.glob("*.md"):
        fn = f.name
        # Skip non-persona files
        if fn.startswith(("EXPERT", "AGENT", "INDEX", "README")):
            continue
        if ".memory" in fn or ".notepad" in fn:
            continue
        if any(x in fn for x in ("register", "protocol", "system", "operating",
                                   "onboarding", "checklist", "blueprint",
                                   "360", "store", "suite", "log", "health")):
            continue

        stem = fn.replace(".md", "")
        for domain, patterns in DOMAIN_MAP.items():
            if any(p in stem for p in patterns):
                available[domain].add(fn)
                break

    # Also check for memory files (indicates L2+ infrastructure exists)
    memory_count = len(list(expert_dir.glob("*.memory*.md")))
    notepad_count = len(list(expert_dir.glob("*.notepad.md")))

    return available, memory_count, notepad_count


# ── Report generation ─────────────────────────────────────────────────────

def generate_report(results, session_dir, as_json=False):
    total = len(results)
    if total == 0:
        print("No sessions found.")
        return

    # ── level distribution ──
    level_dist = defaultdict(int)
    for r in results:
        level_dist[r["level"]] += 1

    # ── domain coverage (invoked) ──
    domain_sessions = defaultdict(set)
    for i, r in enumerate(results):
        for d in r["domains"]:
            domain_sessions[d].add(i)

    # ── roster scan (available) ──
    roster_result = scan_roster(session_dir)
    if isinstance(roster_result, tuple):
        roster_available, memory_count, notepad_count = roster_result
    else:
        roster_available, memory_count, notepad_count = roster_result, 0, 0

    # ── overall stats ──
    max_level = max(r["level"] for r in results)
    avg_level = sum(r["level"] for r in results) / total
    l2_plus = sum(1 for r in results if r["level"] >= 2)

    if as_json:
        report = {
            "total_sessions": total,
            "overall": {
                "peak_level": max_level,
                "average_level": round(avg_level, 2),
                "l2_plus_sessions": l2_plus,
                "l2_plus_pct": round(l2_plus * 100 / total, 1),
            },
            "level_distribution": {
                f"L{l}": {"count": level_dist[l], "pct": round(level_dist[l] * 100 / total, 1)}
                for l in range(6)
            },
            "domain_coverage": {},
            "roster": {
                "memory_files": memory_count,
                "notepad_files": notepad_count,
            },
        }
        for d in DOMAIN_ORDER:
            invoked = len(domain_sessions.get(d, set()))
            available = len(roster_available.get(d, set()))
            report["domain_coverage"][d] = {
                "available": available,
                "invoked_sessions": invoked,
                "invoked_pct": round(invoked * 100 / total, 1),
                "status": "active" if invoked > 0 else ("unused" if available > 0 else "gap"),
            }
        # recent 30
        recent = results[-30:]
        recent_dist = defaultdict(int)
        for r in recent:
            recent_dist[r["level"]] += 1
        report["recent_30"] = {
            f"L{l}": recent_dist[l] for l in range(6)
        }
        print(json.dumps(report, indent=2))
        return

    # ── text report ──
    print("=" * 60)
    print("  EXPERT USAGE AUDIT")
    print("=" * 60)
    print()

    print(f"  Sessions analysed: {total}")
    print(f"  Peak maturity:     L{max_level}")
    print(f"  Average level:     L{avg_level:.1f}")
    print(f"  L2+ sessions:      {l2_plus} ({l2_plus * 100 // total}%)")
    print()

    # ── roster summary ──
    total_available = sum(len(v) for v in roster_available.values())
    if total_available > 0:
        print(f"  ROSTER ON DISK")
        print(f"  " + "-" * 44)
        print(f"  Persona files:  {total_available}")
        print(f"  Memory files:   {memory_count}")
        print(f"  Notepad files:  {notepad_count}")
        print()

    # ── level histogram ──
    print("  MATURITY DISTRIBUTION")
    print("  " + "-" * 44)
    bar_max = max(level_dist.values()) if level_dist else 1
    for l in range(6):
        count = level_dist[l]
        pct = count * 100 // total
        bar_len = int(count / bar_max * 30) if bar_max else 0
        bar = "\u2588" * bar_len
        labels = ["None", "Inline hint", "Persistent persona",
                   "Method-equipped", "Calibrated", "Operating system"]
        print(f"  L{l} {labels[l]:20s} {count:3d} ({pct:2d}%) {bar}")
    print()

    # ── domain heat map (available vs invoked) ──
    print("  DOMAIN COVERAGE (available / invoked)")
    print("  " + "-" * 56)
    for d in DOMAIN_ORDER:
        invoked = len(domain_sessions.get(d, set()))
        available = len(roster_available.get(d, set()))
        pct = invoked * 100 // total if total else 0

        if invoked == 0 and available == 0:
            status = "GAP"
        elif invoked == 0 and available > 0:
            status = "UNUSED"
        elif invoked <= 3:
            status = "L1"
        elif invoked <= 10:
            status = "L2"
        elif invoked <= 20:
            status = "L3"
        elif invoked <= 40:
            status = "L4"
        else:
            status = "L5"

        bar_len = min(invoked, 30)
        bar = "\u2588" * (bar_len // 2)
        avail_str = f"{available:2d} avail" if available > 0 else "      "
        print(f"  {d:15s} {status:6s}  {avail_str} | {invoked:3d} invoked ({pct:2d}%) {bar}")
    print()

    # ── recent trend ──
    recent = results[-30:]
    recent_dist = defaultdict(int)
    for r in recent:
        recent_dist[r["level"]] += 1
    print("  RECENT 30 SESSIONS")
    print("  " + "-" * 44)
    for l in range(6):
        count = recent_dist[l]
        bar = "\u2588" * count
        print(f"  L{l}: {count:2d}  {bar}")
    print()
    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Expert Usage Audit")
    parser.add_argument(
        "--project", default=None,
        help="Project directory name (e.g. -Users-markturrell-Documents-SuperMark)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--recent", type=int, default=0, help="Only analyse last N sessions")
    args = parser.parse_args()

    base = Path.home() / ".claude" / "projects"

    if args.project:
        session_dir = base / args.project
    else:
        # Auto-detect: pick the directory with the most JSONL files
        candidates = [d for d in base.iterdir() if d.is_dir()]
        if not candidates:
            print("No project directories found in ~/.claude/projects/")
            sys.exit(1)
        session_dir = max(candidates, key=lambda d: len(list(d.glob("*.jsonl"))))
        print(f"  Auto-detected project: {session_dir.name}")
        print()

    files = sorted(session_dir.glob("*.jsonl"))
    if not files:
        print(f"No JSONL files found in {session_dir}")
        sys.exit(1)

    if args.recent:
        files = files[-args.recent:]

    results = []
    for f in files:
        results.append(score_session(str(f)))

    generate_report(results, str(session_dir), as_json=args.json)

    # When outputting JSON (likely piped to a file), print next-step guidance to stderr
    # so it appears in the terminal even when stdout is redirected.
    if args.json:
        print(file=sys.stderr)
        print("  ✓ Audit complete — {} sessions analysed.".format(len(results)), file=sys.stderr)
        print("  ✓ Results written to ai-obs-report.json", file=sys.stderr)
        print(file=sys.stderr)
        print("  Next: go back to the AI Observability Dashboard in your browser", file=sys.stderr)
        print("        and drop ai-obs-report.json into the upload area.", file=sys.stderr)
        print(file=sys.stderr)


if __name__ == "__main__":
    main()
