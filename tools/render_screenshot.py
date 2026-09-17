#!/usr/bin/env python3
"""Regenerate the README screenshots from the current code.

    python3 tools/render_screenshot.py

Writes assets/screenshot.svg (job list) and assets/screenshot-users.svg
(the per-user GPU view).

Why this exists: the README teaser used to be a hand-taken terminal
screenshot, so it silently went stale every time the UI changed — new
key bindings and the per-user view were invisible in it for releases.
This drives the same `generate_*` functions the live TUI calls, so the
image cannot drift from what the code actually prints. Re-run it in any
PR that changes the layout.

Mock data is deliberate: a frame of a real namespace would put every
colleague's account name in a public README.

SVG rather than PNG: it stays sharp at any zoom, is ~60 KB instead of
1.2 MB, and GitHub already renders assets/logo.svg in this README.
"""
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from rich.console import Console       # noqa: E402
from rich.panel import Panel           # noqa: E402

import monitor as m                    # noqa: E402
from version import __version__        # noqa: E402

WIDTH, HEIGHT = 200, 34
NAMESPACE = "eidf105ns"

# Pinned so the image is reproducible: generate_local_resources reads this
# machine's psutil counters, which would otherwise make every regeneration
# a diff.
LOCAL = (37.4, [44.0, 21.0, 63.0, 12.0, 58.0, 30.0, 9.0, 71.0], 61.2, "N/A")

KEYS_JOBS = ("[cyan]↑/↓[/cyan] Navigate  [cyan]Enter[/cyan] Logs"
             "  [cyan]d[/cyan] Describe  [cyan]u[/cyan] Users"
             "  [cyan]q[/cyan] Quit")
KEYS_USERS = KEYS_JOBS.replace("[cyan]u[/cyan] Users", "[cyan]u[/cyan] Jobs")


def frame(view):
    """Build one full-screen frame exactly as the main loop would."""
    # mock_data invents pod-name suffixes and node placements with `random`,
    # so an unseeded run changes the job table every time and the committed
    # asset would churn on every regeneration.
    random.seed(0)
    mock = m.generate_mock_data()
    pods = m.get_pods_list(NAMESPACE, use_mock=True, mock_data=mock)
    quota = m.get_quota(NAMESPACE, use_mock=True, mock_data=mock)
    gpu_info = m.get_gpu_info(NAMESPACE, pods=pods, use_mock=True,
                              mock_data=mock)
    jobs = m.get_jobs_pods(NAMESPACE, pods=pods, use_mock=True,
                           mock_data=mock, gpu_info=gpu_info)

    layout = m.make_layout()
    layout["header"].update(Panel(
        f"Kubernetes Monitor - Namespace: [bold green]{NAMESPACE}[/] ",
        style="white on blue"))
    layout["cluster_resources"].update(
        m.generate_cluster_resources(quota, gpu_info))
    layout["local_resources"].update(m.generate_local_resources(*LOCAL))

    if view == "users":
        layout["right"].update(m.generate_user_summary(jobs))
        layout["footer"].update(Panel(KEYS_USERS, style="dim"))
    else:
        table, _ = m.generate_table(jobs, offset=0, max_rows=HEIGHT - 12,
                                    selected_index=0)
        layout["right"].update(Panel(table, title=f"Jobs ({len(jobs)})",
                                     border_style="green"))
        layout["footer"].update(Panel(KEYS_JOBS, style="dim"))
    return layout


def main():
    for view, name in (("jobs", "screenshot.svg"),
                       ("users", "screenshot-users.svg")):
        # Render to devnull, not console.capture(): capture() diverts the
        # segments that record=True is supposed to collect, and save_svg then
        # writes an almost-empty file.
        with open(os.devnull, "w") as sink:
            console = Console(record=True, width=WIDTH, height=HEIGHT,
                              theme=m.build_theme("monokai"),
                              force_terminal=True, file=sink)
            console.print(frame(view))
        out = os.path.join(REPO, "assets", name)
        # Without a fixed unique_id, Rich invents a random one per run and
        # prefixes every CSS class with it — so re-rendering an unchanged UI
        # would still produce a ~250-line diff.
        console.save_svg(out, title=f"kubmonitor {__version__}",
                         unique_id=f"kubmonitor-{view}")
        print(f"wrote {os.path.relpath(out, REPO)} "
              f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
