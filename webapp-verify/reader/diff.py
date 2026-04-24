"""Structural diff between two parsed snapshots.

Uses LCS on uid-free signatures, then post-processes to detect 'changed'
nodes (same role+name, different attrs/url/value/flags) as ~ rather than +/-.
"""

from __future__ import annotations

from dataclasses import dataclass
from .parse import Node


@dataclass
class DiffOp:
    kind: str  # "=" | "+" | "-" | "~"
    a: Node | None = None  # original (for - and ~)
    b: Node | None = None  # new (for + and ~)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "a": self.a.to_dict() if self.a else None,
            "b": self.b.to_dict() if self.b else None,
        }


def diff_snapshots(a: list[Node], b: list[Node]) -> list[DiffOp]:
    a_sigs = [n.signature() for n in a]
    b_sigs = [n.signature() for n in b]
    ops_raw = _lcs_ops(a_sigs, b_sigs, a, b)
    return _merge_changes(ops_raw)


def _lcs_ops(
    a_sigs: list[tuple],
    b_sigs: list[tuple],
    a: list[Node],
    b: list[Node],
) -> list[DiffOp]:
    n, m = len(a_sigs), len(b_sigs)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a_sigs[i] == b_sigs[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    ops: list[DiffOp] = []
    i = j = 0
    while i < n and j < m:
        if a_sigs[i] == b_sigs[j]:
            ops.append(DiffOp("=", a=a[i], b=b[j]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            ops.append(DiffOp("-", a=a[i]))
            i += 1
        else:
            ops.append(DiffOp("+", b=b[j]))
            j += 1
    while i < n:
        ops.append(DiffOp("-", a=a[i]))
        i += 1
    while j < m:
        ops.append(DiffOp("+", b=b[j]))
        j += 1
    return ops


def _merge_changes(ops: list[DiffOp]) -> list[DiffOp]:
    """Detect - followed by + (or vice versa) at same depth with same ident,
    and collapse into ~."""
    out: list[DiffOp] = []
    i = 0
    while i < len(ops):
        op = ops[i]
        if op.kind == "-" and i + 1 < len(ops):
            for look in range(i + 1, min(i + 6, len(ops))):
                cand = ops[look]
                if (
                    cand.kind == "+"
                    and cand.b is not None
                    and op.a is not None
                    and cand.b.depth == op.a.depth
                    and cand.b.ident() == op.a.ident()
                ):
                    out.append(DiffOp("~", a=op.a, b=cand.b))
                    for k in range(i + 1, look):
                        out.append(ops[k])
                    i = look + 1
                    break
            else:
                out.append(op)
                i += 1
            continue
        out.append(op)
        i += 1
    return out


def interesting_ops(ops: list[DiffOp]) -> list[DiffOp]:
    return [o for o in ops if o.kind != "="]


def summarise_diff(ops: list[DiffOp]) -> dict:
    adds = sum(1 for o in ops if o.kind == "+")
    dels = sum(1 for o in ops if o.kind == "-")
    chgs = sum(1 for o in ops if o.kind == "~")
    unchanged = sum(1 for o in ops if o.kind == "=")
    return {"+": adds, "-": dels, "~": chgs, "=": unchanged}
