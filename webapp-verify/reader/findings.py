"""Apply rules.json over parsed snapshots and flow to produce auto-findings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from .parse import Node

RULES_PATH = Path(__file__).parent / "rules.json"


@dataclass
class Finding:
    rule_id: str
    severity: str
    description: str
    snapshot_index: int | None
    step_index: int | None
    node_repr: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def load_rules() -> list[dict]:
    with RULES_PATH.open() as f:
        return json.load(f)["rules"]


def run_rules(
    flow: dict,
    snapshots: list[tuple[int, list[Node]]],
    final_snapshot_nodes: list[Node] | None,
) -> list[Finding]:
    """
    flow: flow.json dict
    snapshots: list of (step_index, parsed_nodes) for every take_snapshot step
    final_snapshot_nodes: parsed final-snapshot.json (or None)
    """
    rules = load_rules()
    findings: list[Finding] = []
    for rule in rules:
        scope = rule.get("applies_to")
        if scope == "image":
            findings.extend(_check_image_rule(rule, snapshots))
        elif scope == "button":
            findings.extend(_check_button_rule(rule, snapshots))
        elif scope == "tree":
            findings.extend(_check_tree_rule(rule, snapshots, final_snapshot_nodes))
        elif scope == "run":
            findings.extend(_check_run_rule(rule, flow, snapshots))
    return findings


def _check_image_rule(rule: dict, snapshots) -> list[Finding]:
    out: list[Finding] = []
    patterns = [re.compile(p) for p in rule.get("match_any", [])]
    match_empty = rule.get("match_empty_name", False)
    seen_signatures = set()
    for step_idx, nodes in snapshots:
        for n in nodes:
            if n.role != "image":
                continue
            sig = (n.role, n.name or "", n.url or "")
            if sig in seen_signatures:
                continue
            hit = False
            if match_empty and (not n.name):
                hit = True
            elif patterns and n.name:
                hit = any(p.search(n.name) for p in patterns)
            if hit:
                seen_signatures.add(sig)
                out.append(Finding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    description=rule["description"],
                    snapshot_index=_first_snapshot_idx(snapshots, n),
                    step_index=step_idx,
                    node_repr=n.render().strip(),
                ))
    return out


def _check_button_rule(rule: dict, snapshots) -> list[Finding]:
    out: list[Finding] = []
    patterns = [re.compile(p) for p in rule.get("match_any_name", [])]
    seen_names = set()
    for step_idx, nodes in snapshots:
        for n in nodes:
            if n.role != "button":
                continue
            if not n.name or n.name in seen_names:
                continue
            if any(p.search(n.name) for p in patterns):
                seen_names.add(n.name)
                out.append(Finding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    description=rule["description"],
                    snapshot_index=None,
                    step_index=step_idx,
                    node_repr=n.render().strip(),
                ))
    return out


def _check_tree_rule(rule: dict, snapshots, final_snapshot_nodes) -> list[Finding]:
    check = rule.get("check")
    out: list[Finding] = []
    if check == "no_h1":
        pool = snapshots[:1]
        if pool:
            _, nodes = pool[0]
            if not any(n.role == "heading" and n.level == "1" for n in nodes):
                out.append(Finding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    description=rule["description"],
                    snapshot_index=0,
                    step_index=None,
                    node_repr=None,
                ))
    elif check == "h1_below_statictext":
        pool = snapshots[:1]
        min_run = rule.get("min_statictext_run", 3)
        if pool:
            _, nodes = pool[0]
            finding = _h1_below_run(nodes, min_run)
            if finding:
                out.append(Finding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    description=rule["description"],
                    snapshot_index=0,
                    step_index=None,
                    node_repr=finding,
                ))
    elif check == "final_busy":
        if final_snapshot_nodes:
            for n in final_snapshot_nodes:
                if n.depth == 0 and n.role == "RootWebArea" and "busy" in n.flags:
                    out.append(Finding(
                        rule_id=rule["id"],
                        severity=rule["severity"],
                        description=rule["description"],
                        snapshot_index=None,
                        step_index=None,
                        node_repr=n.render().strip(),
                    ))
                    break
    return out


def _check_run_rule(rule: dict, flow: dict, snapshots) -> list[Finding]:
    check = rule.get("check")
    out: list[Finding] = []
    if check == "url_unchanged_after_click":
        steps = flow.get("steps", [])
        snap_by_step = {idx: nodes for idx, nodes in snapshots}
        for i, step in enumerate(steps):
            if step.get("tool") != "click":
                continue
            pre_idx = _nearest_snapshot_before(snap_by_step, i)
            post_idx = _nearest_snapshot_after(snap_by_step, i)
            if pre_idx is None or post_idx is None:
                continue
            pre_url = _root_url(snap_by_step[pre_idx])
            post_url = _root_url(snap_by_step[post_idx])
            if pre_url and post_url and pre_url == post_url:
                out.append(Finding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    description=rule["description"],
                    snapshot_index=post_idx,
                    step_index=i,
                    node_repr=f"click step {i + 1} → URL unchanged ({pre_url})",
                ))
    return out


def _h1_below_run(nodes: list[Node], min_run: int) -> str | None:
    streak = 0
    last_depth = None
    for n in nodes:
        if n.role == "heading" and n.level == "1":
            if streak >= min_run:
                return n.render().strip()
            streak = 0
            last_depth = None
            continue
        if n.role == "StaticText":
            if last_depth is None or n.depth == last_depth:
                streak += 1
                last_depth = n.depth
                continue
        streak = 0
        last_depth = None
    return None


def _root_url(nodes: list[Node]) -> str | None:
    for n in nodes:
        if n.depth == 0 and n.role == "RootWebArea":
            return n.url
    return None


def _nearest_snapshot_before(snap_by_step: dict, step_idx: int) -> int | None:
    candidates = [i for i in snap_by_step.keys() if i < step_idx]
    return max(candidates) if candidates else None


def _nearest_snapshot_after(snap_by_step: dict, step_idx: int) -> int | None:
    candidates = [i for i in snap_by_step.keys() if i > step_idx]
    return min(candidates) if candidates else None


def _first_snapshot_idx(snapshots, target_node: Node) -> int | None:
    for idx, (_step, nodes) in enumerate(snapshots):
        for n in nodes:
            if n.role == target_node.role and n.name == target_node.name:
                return idx
    return None
