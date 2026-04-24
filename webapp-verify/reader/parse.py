"""Parse webwitness a11y snapshot text into a list of structured nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict


@dataclass
class Node:
    depth: int
    uid: str
    role: str
    name: str | None = None
    url: str | None = None
    value: str | None = None
    level: str | None = None
    flags: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def signature(self) -> tuple:
        """Uid-free structural key. Used as LCS element."""
        return (
            self.depth,
            self.role,
            self.name or "",
            self.url or "",
            self.value or "",
            self.level or "",
            tuple(sorted(self.flags)),
            tuple(sorted(self.attrs.items())),
        )

    def ident(self) -> tuple:
        """Weaker key — same node across snapshots if (depth, role, name) match.
        Used to detect 'changed' nodes after LCS finds them as delete+insert."""
        return (self.role, self.name or "")

    def render(self) -> str:
        """Human-readable one-line render (no uid)."""
        parts = [self.role]
        if self.name is not None:
            parts.append(f'"{self.name}"')
        if self.level:
            parts.append(f'level={self.level}')
        for k, v in self.attrs.items():
            parts.append(f'{k}="{v}"')
        if self.url:
            parts.append(f'url="{self.url}"')
        if self.value is not None:
            parts.append(f'value="{self.value}"')
        parts.extend(self.flags)
        return "  " * self.depth + " ".join(parts)


_HEADER_RE = re.compile(r'^##\s+')
_LINE_RE = re.compile(r'^(?P<indent> *)uid=(?P<uid>\S+)\s+(?P<rest>.+)$')


def parse_snapshot_text(text: str) -> list[Node]:
    nodes: list[Node] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if _HEADER_RE.match(raw.strip()):
            continue
        m = _LINE_RE.match(raw)
        if not m:
            continue
        indent = m.group('indent')
        depth = len(indent) // 2
        uid = m.group('uid')
        rest = m.group('rest')
        nodes.append(_parse_rest(rest, depth, uid))
    return nodes


def parse_snapshot_json(snapshot_json: dict) -> list[Node]:
    """Takes the raw MCP snapshot response shape {content: [{type, text}]}."""
    try:
        text = snapshot_json["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return []
    return parse_snapshot_text(text)


def snapshot_url(snapshot_json: dict) -> str | None:
    nodes = parse_snapshot_json(snapshot_json)
    for n in nodes:
        if n.depth == 0 and n.role == "RootWebArea":
            return n.url
    return None


def snapshot_busy(snapshot_json: dict) -> bool:
    nodes = parse_snapshot_json(snapshot_json)
    for n in nodes:
        if n.depth == 0 and n.role == "RootWebArea":
            return "busy" in n.flags
    return False


def _parse_rest(rest: str, depth: int, uid: str) -> Node:
    tokens = _tokenize(rest)
    if not tokens:
        return Node(depth=depth, uid=uid, role="unknown")
    role = tokens[0]
    idx = 1
    name = None
    if idx < len(tokens) and tokens[idx].startswith('"'):
        name = _strip_quotes(tokens[idx])
        idx += 1
    url = None
    value = None
    level = None
    flags: list[str] = []
    attrs: dict[str, str] = {}
    while idx < len(tokens):
        tok = tokens[idx]
        idx += 1
        if '=' in tok:
            k, _, v = tok.partition('=')
            v = _strip_quotes(v)
            if k == "url":
                url = v
            elif k == "value":
                value = v
            elif k == "level":
                level = v
            else:
                attrs[k] = v
        else:
            flags.append(tok)
    return Node(
        depth=depth, uid=uid, role=role, name=name,
        url=url, value=value, level=level, flags=flags, attrs=attrs,
    )


def _tokenize(s: str) -> list[str]:
    """Split on whitespace, respecting double-quoted substrings.
    Handles: role "name with spaces" key="quoted val" bareflag."""
    tokens: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        if s[i] == '"':
            i += 1
            while i < n and s[i] != '"':
                if s[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                i += 1
            if i < n:
                i += 1
            tokens.append(s[start:i])
            continue
        while i < n and not s[i].isspace():
            if s[i] == '=' and i + 1 < n and s[i + 1] == '"':
                i += 2
                while i < n and s[i] != '"':
                    if s[i] == '\\' and i + 1 < n:
                        i += 2
                        continue
                    i += 1
                if i < n:
                    i += 1
                continue
            i += 1
        tokens.append(s[start:i])
    return tokens


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s
