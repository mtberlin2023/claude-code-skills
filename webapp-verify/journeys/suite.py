"""Journey suite — run N journeys against one target sequentially.

Substrate for v1.0 P2 (site health matrix). A site.yaml names a target
plus a list of journey files; suite runner loads + validates each journey
(reusing journeys.loader), runs them via run_journey under a shared
artefacts root, and writes a combined suite-result.json next to the
per-journey run dirs.

site.yaml shape (v0.3):

    schema: webwitness/site/v0.3
    label: undavos production            # optional, display only
    target: https://undavos.com/         # required — applied to every journey
    journeys:                            # required, non-empty
      - file: journeys/acceptance-undavos-fresh.json
      - file: journeys/templates/keyboard-only-navigation.json
        persona: returning               # optional override of journey.persona

Paths in `file:` resolve relative to the yaml file's parent dir.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from verify import (  # noqa: E402
    ensure_artefacts_dir,
    new_run_id,
    write_artefact_json,
)

from .loader import (  # noqa: E402
    JourneyRefusedError,
    load_journey,
    load_personas,
)
from .runner import run_journey  # noqa: E402

SUITE_SCHEMA = "webwitness/site/v0.3"


class SuiteRefusedError(ValueError):
    """Raised when a site.yaml fails validation."""


def load_suite(path: Path, allow_high_entropy: bool = False) -> dict:
    """Load + validate a site.yaml. Returns a resolved suite dict:

        {
          "schema": "...",
          "label": str | None,
          "target": str,
          "_yaml_path": Path,
          "journeys": [
            {
              "file": str (as written),
              "_path": Path (resolved),
              "persona_override": str | None,
              "_journey": dict (already loaded + validated),
            },
            ...
          ],
        }

    Each journey is loaded via journeys.loader.load_journey AFTER applying
    the suite-level target override and any per-row persona override, so
    invalid suites fail loudly at load time, not mid-run.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SuiteRefusedError(f"cannot read suite at {path}: {e}") from e

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        raise SuiteRefusedError(f"suite is not valid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise SuiteRefusedError("suite must be a YAML mapping at top level")

    schema = raw.get("schema")
    if schema is not None and schema != SUITE_SCHEMA:
        raise SuiteRefusedError(
            f"suite schema mismatch: got {schema!r}, expected {SUITE_SCHEMA!r}"
        )

    target = raw.get("target")
    if not isinstance(target, str) or not target.strip():
        raise SuiteRefusedError("suite missing required field 'target' (URL string)")

    label = raw.get("label")
    if label is not None and not isinstance(label, str):
        raise SuiteRefusedError("'label' must be a string if present")

    journeys_raw = raw.get("journeys")
    if not isinstance(journeys_raw, list) or not journeys_raw:
        raise SuiteRefusedError(
            "suite missing required field 'journeys' (non-empty list)"
        )

    personas = load_personas()
    yaml_dir = path.parent

    resolved_rows: list[dict] = []
    for i, row in enumerate(journeys_raw):
        if not isinstance(row, dict):
            raise SuiteRefusedError(
                f"journeys[{i}] must be a mapping with at least a 'file' key"
            )
        f = row.get("file")
        if not isinstance(f, str) or not f.strip():
            raise SuiteRefusedError(
                f"journeys[{i}] missing required 'file' (string path)"
            )
        jp = (yaml_dir / f).resolve()
        if not jp.is_file():
            raise SuiteRefusedError(
                f"journeys[{i}].file not found: {jp}"
            )

        persona_override = row.get("persona")
        if persona_override is not None:
            if not isinstance(persona_override, str):
                raise SuiteRefusedError(
                    f"journeys[{i}].persona must be a string if present"
                )
            if persona_override not in personas:
                raise SuiteRefusedError(
                    f"journeys[{i}].persona '{persona_override}' not in personas.json. "
                    f"Known: {sorted(personas)}"
                )

        try:
            j_doc = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise SuiteRefusedError(
                f"journeys[{i}] cannot read/parse {jp}: {e}"
            ) from e
        if not isinstance(j_doc, dict):
            raise SuiteRefusedError(
                f"journeys[{i}] {jp} is not a JSON object at top level"
            )

        # Apply suite-level overrides BEFORE validation, then write a
        # patched temp dict that load_journey can validate as a normal
        # journey.json. We don't write the patch back to disk.
        j_doc["target"] = target
        if persona_override is not None:
            j_doc["persona"] = persona_override

        # load_journey takes a path. To keep validation single-sourced
        # we round-trip the patched dict through a tempfile rather than
        # duplicating the loader contract here.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(j_doc, tf, ensure_ascii=False)
            scratch = Path(tf.name)
        try:
            try:
                journey = load_journey(scratch, allow_high_entropy=allow_high_entropy)
            except JourneyRefusedError as e:
                raise SuiteRefusedError(
                    f"journeys[{i}] ({f}) failed validation after suite overrides: {e}"
                ) from e
        finally:
            try:
                scratch.unlink()
            except OSError:
                pass

        resolved_rows.append({
            "file": f,
            "_path": jp,
            "persona_override": persona_override,
            "_journey": journey,
        })

    return {
        "schema": SUITE_SCHEMA,
        "label": label,
        "target": target,
        "_yaml_path": path,
        "journeys": resolved_rows,
    }


def run_suite(suite: dict, suite_id: str | None = None) -> dict:
    """Run every journey in a resolved suite sequentially and return a
    suite-result dict. Per-journey artefacts land under
    ARTEFACTS_ROOT/suite-<suite_id>/<journey_run_id>/."""
    if suite_id is None:
        suite_id = new_run_id()

    suite_dir = ensure_artefacts_dir(f"suite-{suite_id}")
    write_artefact_json(suite_dir, "suite.json", {
        "schema": suite["schema"],
        "label": suite.get("label"),
        "target": suite["target"],
        "yaml_path": str(suite["_yaml_path"]),
        "journeys": [
            {
                "file": row["file"],
                "path": str(row["_path"]),
                "persona": row["_journey"]["persona"],
                "persona_override": row["persona_override"],
                "intent": row["_journey"]["intent"],
            }
            for row in suite["journeys"]
        ],
    })

    rows_out: list[dict] = []
    verdict_summary = {"PASS": 0, "FAIL": 0, "UNCLEAR": 0}
    suite_start = time.perf_counter()

    for row in suite["journeys"]:
        journey = row["_journey"]
        run_id = new_run_id()
        # Make sure run_ids don't collide when journeys run in the same
        # second. new_run_id is ISO-second resolution; if the previous
        # row already used this id, append a suffix.
        existing = {p.name for p in suite_dir.iterdir() if p.is_dir()}
        if run_id in existing:
            n = 2
            while f"{run_id}-{n}" in existing:
                n += 1
            run_id = f"{run_id}-{n}"

        result = run_journey(journey, run_id=run_id, artefacts_root=suite_dir)
        verdict = result.get("verdict", "FAIL")
        verdict_summary[verdict] = verdict_summary.get(verdict, 0) + 1
        rows_out.append({
            "file": row["file"],
            "persona": journey["persona"],
            "persona_override": row["persona_override"],
            "intent": journey["intent"],
            "run_id": result["run_id"],
            "verdict": verdict,
            "matcher": result.get("matcher"),
            "iterations": result.get("iterations"),
            "clicks_used": result.get("clicks_used"),
            "dead_ends": result.get("dead_ends"),
            "duration_ms": result.get("duration_ms"),
            "error": result.get("error"),
            "artefacts_dir": result.get("artefacts_dir"),
        })

    suite_result = {
        "suite_id": suite_id,
        "site": {
            "label": suite.get("label"),
            "target": suite["target"],
        },
        "journeys": rows_out,
        "verdict_summary": verdict_summary,
        "duration_ms": int((time.perf_counter() - suite_start) * 1000),
        "artefacts_dir": str(suite_dir),
        "_suite": True,
    }
    write_artefact_json(suite_dir, "suite-result.json", suite_result)
    return suite_result
