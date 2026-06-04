#!/usr/bin/env python3
"""Benchmark and profile ``import weave`` and ``weave.init()``.

Why this exists
---------------
Cold start of the Weave SDK has two phases:

* ``import weave`` — pure CPU/code cost. Fully deterministic and reproducible
  offline, so it is the real optimization target.
* ``weave.init()`` — network bound (W&B auth, ``server_info``,
  ``ensure_project_exists``). Its *code* cost is tiny; we measure it via the
  offline "disabled" path (``WEAVE_DISABLED=true``) so the number is
  reproducible without credentials or a server.

The script produces three things:

1. Timing stats for cold ``import weave`` and offline ``init()`` (subprocess,
   N iterations, warmup discarded).
2. A per-module import-time breakdown from ``python -X importtime``, aggregated
   by top-level package and by individual module (exclusive "self" time).
3. Flame graphs, when the tools are installed:
     * pyinstrument -> HTML + text call-stack flame graph (pure Python, always
       works).
     * py-spy -> SVG flame graph (best effort; may need elevated perms on macOS).
     * an ``-X importtime`` log saved for ``tuna`` (interactive import icicle).

Run it inside the project venv so ``import weave`` resolves to this checkout:

    source .venv/bin/activate
    python scripts/benchmarks/import_init_profile.py

Common flags:

    python scripts/benchmarks/import_init_profile.py --iterations 10
    python scripts/benchmarks/import_init_profile.py --no-flame   # timing only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# --- Constants ---------------------------------------------------------------

DEFAULT_ITERATIONS = 8
WARMUP_RUNS = 1  # discarded so the filesystem cache is warm before we measure
DEFAULT_OUT_DIR = Path(__file__).parent / ".artifacts"
SUBPROCESS_TIMEOUT_S = 120
PYSPY_RATE_HZ = 1000
PYINSTRUMENT_INTERVAL_S = 0.0001
IMPORTTIME_TOP_MODULES = 30
IMPORTTIME_TOP_PACKAGES = 25
US_PER_S = 1_000_000

# HTML flame graph (icicle) layout.
INDENT_UNIT = 2  # spaces per nesting level in -X importtime output
FLAME_WIDTH_PX = 1600
FLAME_ROW_PX = 22
FLAME_MIN_FRAC = 0.001  # prune subtrees below 0.1% of total to keep the SVG small
FLAME_LABEL_MIN_PX = 38  # only draw a text label on boxes at least this wide

# Project to init with. The offline (disabled) path never contacts the network,
# so the value is arbitrary but must be well-formed (``entity/project``).
OFFLINE_PROJECT = "offline/import-init-profile"
DISABLED_ENV = {"WEAVE_DISABLED": "true"}

# Driver executed under the profilers: import + offline init in one process.
FLAME_DRIVER = """\
import weave

weave.init({project!r})
"""

# Time just the import, printing the elapsed seconds. Interpreter startup is
# excluded because the clock starts after the interpreter is already running.
IMPORT_TIMER = """\
import time

_t0 = time.perf_counter()
import weave
print(time.perf_counter() - _t0)
"""

# Time import + offline init separately, printing "import,init".
INIT_TIMER = """\
import time

_t0 = time.perf_counter()
import weave
_t1 = time.perf_counter()
weave.init({project!r})
_t2 = time.perf_counter()
print(f"{{_t1 - _t0}},{{_t2 - _t1}}")
"""

IMPORTTIME_LINE_RE = re.compile(r"^import time:\s*([\d]+)\s*\|\s*([\d]+)\s*\|(.*)$")


# --- Data types --------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Stats:
    """Summary statistics for a list of timing samples, in seconds."""

    mean: float
    median: float
    std_dev: float
    minimum: float
    maximum: float
    n: int

    @classmethod
    def from_samples(cls, samples: list[float]) -> Stats:
        if not samples:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0)
        return cls(
            mean=statistics.mean(samples),
            median=statistics.median(samples),
            std_dev=statistics.stdev(samples) if len(samples) > 1 else 0.0,
            minimum=min(samples),
            maximum=max(samples),
            n=len(samples),
        )


@dataclass(slots=True, frozen=True)
class ModuleImport:
    """One module's import cost, in microseconds, from ``-X importtime``."""

    name: str
    self_us: int
    cumulative_us: int


@dataclass(slots=True)
class TreeNode:
    """A node in the reconstructed import tree (for the flame graph)."""

    name: str
    self_us: int
    cumulative_us: int
    depth: int
    children: list[TreeNode]


# --- Subprocess helpers ------------------------------------------------------


def _run_python(code: str, *, extra_env: dict[str, str] | None = None) -> str:
    """Run ``code`` in a fresh interpreter and return its stdout (stripped)."""
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subprocess failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def measure_import(iterations: int) -> Stats:
    """Cold ``import weave`` time over ``iterations`` fresh processes."""
    samples: list[float] = []
    for i in range(iterations + WARMUP_RUNS):
        elapsed = float(_run_python(IMPORT_TIMER))
        if i >= WARMUP_RUNS:
            samples.append(elapsed)
        print(f"  import run {i + 1}/{iterations + WARMUP_RUNS}: {elapsed:.3f}s")
    return Stats.from_samples(samples)


def measure_init(iterations: int) -> tuple[Stats, Stats]:
    """Offline (disabled) ``init()`` code cost over fresh processes.

    Returns ``(import_stats, init_stats)``. The import number here is a
    cross-check against :func:`measure_import`; the init number is the
    network-free code cost of ``weave.init()``.
    """
    import_samples: list[float] = []
    init_samples: list[float] = []
    code = INIT_TIMER.format(project=OFFLINE_PROJECT)
    for i in range(iterations + WARMUP_RUNS):
        out = _run_python(code, extra_env=DISABLED_ENV)
        import_s, init_s = (float(x) for x in out.split(","))
        if i >= WARMUP_RUNS:
            import_samples.append(import_s)
            init_samples.append(init_s)
        print(
            f"  init run {i + 1}/{iterations + WARMUP_RUNS}: "
            f"import {import_s:.3f}s, init(disabled) {init_s:.4f}s"
        )
    return Stats.from_samples(import_samples), Stats.from_samples(init_samples)


# --- importtime parsing ------------------------------------------------------


def capture_importtime() -> str:
    """Return the raw ``python -X importtime -c 'import weave'`` log (stderr)."""
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import weave"],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"importtime run failed:\n{proc.stdout.strip()}")
    return proc.stderr


def parse_importtime(log: str) -> list[ModuleImport]:
    """Parse an ``-X importtime`` log into per-module costs."""
    modules: list[ModuleImport] = []
    for line in log.splitlines():
        match = IMPORTTIME_LINE_RE.match(line)
        if not match:
            continue
        self_field, cumulative_field, name_field = match.groups()
        if self_field == "self":  # header row
            continue
        modules.append(
            ModuleImport(
                name=name_field.strip(),
                self_us=int(self_field),
                cumulative_us=int(cumulative_field),
            )
        )
    return modules


def aggregate_by_package(modules: list[ModuleImport]) -> list[tuple[str, int]]:
    """Sum exclusive self-time by top-level package, sorted descending."""
    totals: dict[str, int] = defaultdict(int)
    for module in modules:
        top = module.name.split(".", 1)[0]
        totals[top] += module.self_us
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def parse_importtime_tree(log: str) -> list[TreeNode]:
    """Reconstruct the import tree from an ``-X importtime`` log.

    importtime prints in post-order: a module's line appears *after* every
    module it imported, and an importer is indented less than its imports.
    Walking the lines in order with a stack therefore re-creates the tree —
    when a shallower line appears, the deeper lines sitting on the stack are
    exactly its direct children (their own descendants were already attached).
    """
    stack: list[TreeNode] = []
    for line in log.splitlines():
        match = IMPORTTIME_LINE_RE.match(line)
        if not match:
            continue
        self_field, cumulative_field, name_field = match.groups()
        if self_field == "self":  # header row (won't match \d+ anyway)
            continue
        depth = (len(name_field) - len(name_field.lstrip(" "))) // INDENT_UNIT
        children: list[TreeNode] = []
        while stack and stack[-1].depth > depth:
            children.append(stack.pop())
        children.reverse()  # restore import order
        stack.append(
            TreeNode(
                name=name_field.strip(),
                self_us=int(self_field),
                cumulative_us=int(cumulative_field),
                depth=depth,
                children=children,
            )
        )
    return stack  # whatever remains are the outermost (top-level) imports


def _hue_for(name: str) -> int:
    """Stable hue (0-359) per top-level package, so siblings are colored alike."""
    top = name.split(".", 1)[0]
    acc = 0
    for char in top:
        acc = (acc * 31 + ord(char)) % 360
    return acc


def render_flamegraph_html(roots: list[TreeNode], out_path: Path) -> None:
    """Render the import tree as a self-contained HTML icicle (flame graph).

    Box width is proportional to cumulative import time, so the widest boxes are
    the most expensive imports. Gaps under a box are that module's own self-time.
    Faithful to ``-X importtime`` numbers (no sampling distortion).
    """
    total_us = sum(node.cumulative_us for node in roots) or 1
    boxes: list[str] = []
    max_depth = 0

    def emit(node: TreeNode, x_frac: float, depth: int) -> None:
        nonlocal max_depth
        frac = node.cumulative_us / total_us
        if frac < FLAME_MIN_FRAC:
            return
        max_depth = max(max_depth, depth)
        x_px = x_frac * FLAME_WIDTH_PX
        w_px = frac * FLAME_WIDTH_PX
        ms = node.cumulative_us / 1000
        self_ms = node.self_us / 1000
        tip = (
            f"{node.name} — {ms:.1f}ms cumulative, {self_ms:.1f}ms self "
            f"({frac * 100:.1f}% of import)"
        )
        label = node.name if w_px >= FLAME_LABEL_MIN_PX else ""
        boxes.append(
            f'<div class="b" style="left:{x_px:.1f}px;top:{depth * FLAME_ROW_PX}px;'
            f"width:{max(w_px - 1, 0):.1f}px;background:hsl({_hue_for(node.name)},"
            f'60%,62%)" title="{tip}">{label}</div>'
        )
        child_x = x_frac
        for child in node.children:
            emit(child, child_x, depth + 1)
            child_x += child.cumulative_us / total_us

    child_x = 0.0
    for root in roots:
        emit(root, child_x, 0)
        child_x += root.cumulative_us / total_us

    height = (max_depth + 1) * FLAME_ROW_PX + 4
    total_s = total_us / US_PER_S
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>import weave — import-time flame graph</title>
<style>
 body {{ font:12px -apple-system,Segoe UI,Roboto,sans-serif; margin:16px; background:#fafafa; }}
 h1 {{ font-size:15px; }} .sub {{ color:#666; margin-bottom:12px; }}
 #fg {{ position:relative; width:{FLAME_WIDTH_PX}px; height:{height}px; }}
 .b {{ position:absolute; height:{FLAME_ROW_PX - 1}px; overflow:hidden;
       white-space:nowrap; box-sizing:border-box; padding:0 3px; line-height:{FLAME_ROW_PX - 1}px;
       border-radius:2px; color:#111; cursor:default; }}
 .b:hover {{ outline:1px solid #000; }}
</style></head><body>
<h1><code>import weave</code> — import-time flame graph</h1>
<div class="sub">Width &prop; cumulative import time. Total {total_s:.3f}s.
Built from <code>python -X importtime</code> (faithful; no sampling distortion).
Subtrees below {FLAME_MIN_FRAC * 100:.1f}% pruned. Hover a box for details.</div>
<div id="fg">{"".join(boxes)}</div>
</body></html>"""
    out_path.write_text(html, encoding="utf-8")


# --- Output formatting -------------------------------------------------------


def _fmt_s(seconds: float) -> str:
    return f"{seconds:.3f}s"


def _bar(fraction: float, width: int = 24) -> str:
    filled = round(fraction * width)
    return "#" * filled + "." * (width - filled)


def print_timing_section(import_stats: Stats, init_stats: Stats) -> None:
    print("\n" + "=" * 72)
    print("TIMING (fresh subprocess; warmup discarded)")
    print("=" * 72)
    header = f"{'phase':<22}{'mean':>9}{'median':>9}{'min':>9}{'max':>9}{'stdev':>9}"
    print(header)
    print("-" * len(header))
    for label, stats in (
        ("import weave", import_stats),
        ("init() [disabled]", init_stats),
    ):
        print(
            f"{label:<22}"
            f"{_fmt_s(stats.mean):>9}"
            f"{_fmt_s(stats.median):>9}"
            f"{_fmt_s(stats.minimum):>9}"
            f"{_fmt_s(stats.maximum):>9}"
            f"{_fmt_s(stats.std_dev):>9}"
        )
    print(
        "\nNote: init() here is the offline WEAVE_DISABLED path (no network)."
        "\nReal init() adds W&B auth + server_info + ensure_project_exists RTTs."
    )


def print_importtime_section(modules: list[ModuleImport]) -> None:
    total_self_us = sum(m.self_us for m in modules)
    total_s = total_self_us / US_PER_S
    print("\n" + "=" * 72)
    print(
        f"IMPORT BREAKDOWN  (total self-time {total_s:.3f}s across "
        f"{len(modules)} modules)"
    )
    print("=" * 72)

    packages = aggregate_by_package(modules)
    print(f"\nTop {IMPORTTIME_TOP_PACKAGES} top-level packages by exclusive self-time:")
    print(f"{'package':<28}{'self':>9}{'% total':>9}  share")
    print("-" * 72)
    for name, self_us in packages[:IMPORTTIME_TOP_PACKAGES]:
        frac = self_us / total_self_us if total_self_us else 0.0
        print(f"{name:<28}{self_us / US_PER_S:>8.3f}s{frac * 100:>8.1f}%  {_bar(frac)}")

    by_self = sorted(modules, key=lambda m: m.self_us, reverse=True)
    print(f"\nTop {IMPORTTIME_TOP_MODULES} individual modules by exclusive self-time:")
    print(f"{'module':<52}{'self':>9}{'% total':>9}")
    print("-" * 72)
    for module in by_self[:IMPORTTIME_TOP_MODULES]:
        frac = module.self_us / total_self_us if total_self_us else 0.0
        print(f"{module.name:<52}{module.self_us / US_PER_S:>8.3f}s{frac * 100:>8.1f}%")


# --- Flame graph generation --------------------------------------------------


def generate_pyinstrument(out_dir: Path) -> Path | None:
    """Profile import + offline init with pyinstrument; write HTML + text."""
    try:
        import pyinstrument  # noqa: F401
    except ImportError:
        print("  [skip] pyinstrument not installed (uv pip install pyinstrument)")
        return None

    html_path = out_dir / "flame_pyinstrument.html"
    text_path = out_dir / "flame_pyinstrument.txt"
    driver = (
        "from pyinstrument import Profiler\n"
        f"_p = Profiler(interval={PYINSTRUMENT_INTERVAL_S})\n"
        "_p.start()\n"
        "import weave\n"
        f"weave.init({OFFLINE_PROJECT!r})\n"
        "_p.stop()\n"
        f"open({str(html_path)!r}, 'w', encoding='utf-8').write(_p.output_html())\n"
        f"open({str(text_path)!r}, 'w', encoding='utf-8').write("
        "_p.output_text(unicode=True, color=False, show_all=True))\n"
    )
    _run_python(driver, extra_env=DISABLED_ENV)
    print(f"  [ok] pyinstrument HTML -> {html_path}")
    print(f"  [ok] pyinstrument text -> {text_path}")
    return html_path


def generate_pyspy(out_dir: Path) -> Path | None:
    """Record an SVG flame graph with py-spy (best effort)."""
    pyspy = shutil.which("py-spy")
    if not pyspy:
        print("  [skip] py-spy not on PATH (uv tool install py-spy)")
        return None

    svg_path = out_dir / "flame_pyspy.svg"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, dir=out_dir, encoding="utf-8"
    ) as driver_file:
        driver_file.write(FLAME_DRIVER.format(project=OFFLINE_PROJECT))
        driver_path = driver_file.name

    env = {**os.environ, **DISABLED_ENV}
    cmd = [
        pyspy,
        "record",
        "--rate",
        str(PYSPY_RATE_HZ),
        "--output",
        str(svg_path),
        "--",
        sys.executable,
        driver_path,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        env=env,
        check=False,
    )
    Path(driver_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        print("  [skip] py-spy failed (on macOS it often needs sudo):")
        print("         " + proc.stderr.strip().replace("\n", "\n         "))
        return None
    print(f"  [ok] py-spy SVG -> {svg_path}")
    return svg_path


# --- Main --------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"timing iterations per phase (default {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="directory for flame graph + importtime artifacts",
    )
    parser.add_argument(
        "--no-flame",
        action="store_true",
        help="skip flame graph generation (timing + breakdown only)",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Python:    {sys.version.split()[0]}  ({sys.executable})")
    print(f"Artifacts: {args.out_dir}")

    print(f"\nMeasuring cold `import weave` x{args.iterations} ...")
    import_stats = measure_import(args.iterations)
    print(f"\nMeasuring offline `init()` x{args.iterations} ...")
    init_import_stats, init_stats = measure_init(args.iterations)

    print("\nCapturing `python -X importtime -c 'import weave'` ...")
    importtime_log = capture_importtime()
    log_path = args.out_dir / "importtime.log"
    log_path.write_text(importtime_log)
    modules = parse_importtime(importtime_log)

    print_timing_section(import_stats, init_stats)
    print_importtime_section(modules)

    if not args.no_flame:
        print("\n" + "=" * 72)
        print("FLAME GRAPHS")
        print("=" * 72)
        # Faithful import-time flame graph from importtime (no external tools).
        flame_path = args.out_dir / "flame_importtime.html"
        render_flamegraph_html(parse_importtime_tree(importtime_log), flame_path)
        print(f"  [ok] importtime flame graph -> {flame_path}")
        # Call-stack flame graphs from optional profilers.
        generate_pyinstrument(args.out_dir)
        generate_pyspy(args.out_dir)
        print(f"  [ok] importtime log -> {log_path}")
        print(f"        view as an icicle graph with:  tuna {log_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
