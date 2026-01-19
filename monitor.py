import sys
import json
import time
import subprocess
import argparse
import platform

if platform.system() != "Windows":
    import select
    import tty
    import termios
else:
    import msvcrt
import psutil
from datetime import datetime
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich import box
from mock_data import generate_mock_data
from version import __version__


def format_duration(total_seconds):
    if total_seconds < 60:
        return f"{int(total_seconds)}s"
    elif total_seconds < 3600:  # < 1 hour
        minutes = int(total_seconds / 60)
        return f"{minutes}m"
    elif total_seconds < 86400:  # < 1 day
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    elif total_seconds < 604800:  # < 1 week
        days = int(total_seconds / 86400)
        hours = int((total_seconds % 86400) / 3600)
        return f"{days}d {hours}h" if hours > 0 else f"{days}d"
    else:  # >= 1 week
        weeks = int(total_seconds / 604800)
        days = int((total_seconds % 604800) / 86400)
        return f"{weeks}w {days}d" if days > 0 else f"{weeks}w"


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return ""


def get_quota(ns, use_mock=False, mock_data=None):
    if use_mock and mock_data:
        return mock_data['quota']

    output = run_cmd(f"kubectl -n {ns} describe resourcequota")
    data = {
        'cpu': {'used': 0, 'limit': 0, 'str': '0/0'},
        'mem': {'used': 0, 'limit': 0, 'str': '0/0'},
        'gpu': {'used': 0, 'limit': 0, 'str': '0/0'}
    }

    lines = output.split('\n')
    in_table = False
    for line in lines:
        if line.strip().startswith('Resource'):
            in_table = True
            continue
        if in_table and line.strip().startswith('----'):
            continue
        if in_table and not line.strip():
            break

        if in_table:
            parts = line.split()
            if len(parts) >= 3:
                res = parts[0]
                used = parts[1]
                limit = parts[2]

                if res.startswith('limits.'):
                    continue

                key = None
                if res in ['requests.cpu', 'cpu']:
                    key = 'cpu'
                elif res in ['requests.memory', 'memory']:
                    key = 'mem'
                elif 'gpu' in res:
                    key = 'gpu'

                if key:
                    data[key]['str'] = f"{used} / {limit}"
                    try:
                        if limit.isdigit() and int(limit) > 0:
                            data[key]['percent'] = (int(used) / int(limit)) * 100
                    except:
                        pass

    return data


def get_jobs_pods(ns, use_mock=False, mock_data=None):
    if use_mock and mock_data:
        jobs = mock_data['jobs']['items']
        pods = mock_data['pods']['items']
    else:
        jobs_json = run_cmd(f"kubectl -n {ns} get jobs -o json")
        pods_json = run_cmd(f"kubectl -n {ns} get pods -o json")

        try:
            j = json.loads(jobs_json)
            jobs = j.get('items', [])
            p = json.loads(pods_json)
            pods = p.get('items', [])
        except Exception:
            jobs = []
            pods = []

    jobs_data = []
    try:
        for job in jobs:
            name = job['metadata']['name']
            status_obj = job.get('status', {})
            spec = job.get('spec', {})

            # Status Logic
            active = status_obj.get('active', 0)
            succeeded = status_obj.get('succeeded', 0)
            failed = status_obj.get('failed', 0)
            req = spec.get('completions', 1)

            if succeeded >= req:
                status = 'Completed'
            elif active > 0:
                status = 'Running'
            elif failed > 0:
                status = 'Failed'
            else:
                status = 'Pending'

            # Duration
            duration = "-"
            if 'startTime' in status_obj:
                try:
                    start_str = status_obj['startTime']
                    start_str = start_str.replace('Z', '+00:00')
                    start = datetime.fromisoformat(start_str)

                    end = datetime.now(start.tzinfo)
                    if 'completionTime' in status_obj:
                        end_str = status_obj['completionTime'].replace('Z', '+00:00')
                        end = datetime.fromisoformat(end_str)

                    diff = end - start
                    total_seconds = diff.total_seconds()
                    duration = format_duration(total_seconds)
                    if 'completionTime' not in status_obj:
                        duration += " (Run)"
                except Exception:
                    pass

            # User
            user = "Unknown"
            try:
                img = spec['template']['spec']['containers'][0]['image']
                parts = img.split('/')
                user = parts[0] if len(parts) > 1 else img.split(':')[0]
            except:
                pass

            # Pods
            my_pods = []
            for pod in pods:
                if pod['metadata']['name'].startswith(name + "-"):
                    p_status = pod['status']['phase']
                    my_pods.append(f"{pod['metadata']['name']} ({p_status})")

            jobs_data.append({
                'name': name,
                'status': status,
                'user': user,
                'completions': f"{succeeded}/{req}",
                'duration': duration,
                'pods': my_pods
            })

    except Exception:
        pass

    return jobs_data


def get_local_metrics():
    # CPU
    cpu_total = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)

    # Mem
    mem = psutil.virtual_memory().percent
    # GPU (Try nvidia-smi)
    gpu = "N/A"
    try:
        cmd = "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            gpu = res.stdout.strip()
    except:
        pass

    return cpu_total, cpu_per_core, mem, gpu


def generate_local_resources(cpu_total, cpu_per_core, mem, gpu):
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")

    # Overview
    grid.add_row("[bold]Total CPU[/]", f"{cpu_total}%")
    grid.add_row("[bold]Memory[/]", f"{mem}%")
    grid.add_row("[bold]GPU[/]", str(gpu))

    # Per Core details
    cores_grid = Table.grid(expand=True, padding=(0, 1))
    for _ in range(4):
        cores_grid.add_column(justify="center", ratio=1)

    row_cells = []
    for i, p in enumerate(cpu_per_core):
        color = "green" if p < 50 else "yellow" if p < 80 else "red"
        row_cells.append(f"C{i}: [{color}]{p:.0f}%[/]")
        if len(row_cells) == 4:
            cores_grid.add_row(*row_cells)
            row_cells = []
    if row_cells:
        while len(row_cells) < 4:
            row_cells.append("")
        cores_grid.add_row(*row_cells)

    layout = Table.grid(expand=True)
    layout.add_row(grid)
    layout.add_row(Panel(cores_grid, title="Cores", border_style="dim", box=box.SIMPLE))

    return Panel(layout, title="Local Machine", border_style="magenta")


def make_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=3)
    )
    layout["left"].split(
        Layout(name="cluster_resources", ratio=1),
        Layout(name="local_resources", ratio=1)
    )
    return layout


def generate_table(jobs, offset=0, max_rows=None):
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_lines=False)
    table.add_column("Job / Pod Name", style="cyan", no_wrap=True)
    table.add_column("User", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Comp", justify="right")
    table.add_column("Duration", justify="right")

    all_rows = []
    for job in jobs:
        if job['status'] == 'Completed':
            status_style = "green"
        elif job['status'] == 'Failed':
            status_style = "red"
        else:
            status_style = "yellow"

        all_rows.append({
            'type': 'job',
            'name': f"[bold]{job['name']}[/]",
            'user': job['user'],
            'status': f"[{status_style}]{job['status']}[/]",
            'completions': job['completions'],
            'duration': job['duration']
        })

        for i, pod_str in enumerate(job['pods']):
            p_name = pod_str.split(' (')[0]
            p_status = pod_str.split(' (')[1].rstrip(')')

            is_last = (i == len(job['pods']) - 1)
            prefix = "└── " if is_last else "├── "

            p_status_style = "green" if p_status == 'Running' else "dim"

            all_rows.append({
                'type': 'pod',
                'name': f"  {prefix}{p_name}",
                'user': "",
                'status': f"[{p_status_style}]{p_status}[/]",
                'completions': "",
                'duration': ""
            })

    visible_rows = all_rows[offset:]
    if max_rows:
        visible_rows = visible_rows[:max_rows]

    for row in visible_rows:
        table.add_row(
            row['name'],
            row['user'],
            row['status'],
            row['completions'],
            row['duration']
        )

    return table


def generate_cluster_resources(quota):
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")

    grid.add_row("CPU", quota['cpu']['str'])
    grid.add_row("MEM", quota['mem']['str'])
    grid.add_row("GPU", quota['gpu']['str'])

    return Panel(grid, title="Cluster Quota", border_style="blue")


def print_help():
    console = Console(force_terminal=True, legacy_windows=False)

    console.print(
        "\n[bold cyan]kubmonitor[/bold cyan] - Real-time Kubernetes "
        "dashboard combining cluster quotas and local metrics.\n",
        highlight=False
    )

    console.print("[bold yellow]Usage:[/bold yellow]")
    console.print(
        "  [green]kubmonitor[/green] [cyan][[/cyan][dim]NAMESPACE[/dim]"
        "[cyan]][/cyan] [cyan][[/cyan][magenta]--mock[/magenta][cyan]][/cyan] "
        "[cyan][[/cyan][magenta]--help[/magenta][cyan]][/cyan] "
        "[cyan][[/cyan][magenta]--version[/magenta][cyan]][/cyan]\n"
    )

    console.print("[bold yellow]Positional Arguments:[/bold yellow]")
    console.print("  [cyan]NAMESPACE[/cyan]      Kubernetes namespace to monitor.")
    console.print(
        "                 [dim]Note: Cannot be used with --mock flag.[/dim]\n"
    )

    console.print("[bold yellow]Options:[/bold yellow]")
    console.print("  [magenta]-h, --help[/magenta]     Show this help message.")
    console.print(
        "  [magenta]--mock[/magenta]         Use mock data instead of "
        "querying the actual Kubernetes cluster."
    )
    console.print("                 Useful for testing and development.")
    console.print(
        "                 [dim]When using --mock, the namespace argument "
        "is ignored.[/dim]"
    )
    console.print(
        "  [magenta]-V, --version[/magenta]  Show kubmonitor's version "
        "number.\n"
    )

    console.print("[bold yellow]Examples:[/bold yellow]")
    console.print("  [dim]# Monitor the default namespace[/dim]")
    console.print("  [green]kubmonitor[/green]\n")
    console.print("  [dim]# Monitor a specific namespace[/dim]")
    console.print("  [green]kubmonitor[/green] [cyan]my-namespace[/cyan]\n")
    console.print("  [dim]# Use mock data for testing (no namespace needed)[/dim]")
    console.print("  [green]kubmonitor[/green] [magenta]--mock[/magenta]\n")

    console.print("[bold yellow]Keyboard Shortcuts:[/bold yellow]")
    console.print("  [cyan]↑/↓[/cyan]            Navigate up and down")
    console.print("  [cyan]q[/cyan]              Quit the application")
    console.print("  [cyan]Ctrl+C[/cyan]         Force exit\n")

    console.print(
        "[dim]For more information, visit: "
        "https://github.com/vios-s/kubmonitor_cli[/dim]\n"
    )


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(prog='kubmonitor', add_help=False)
    parser.add_argument('namespace', nargs='?', default='default')
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--version', '-V', action='version',
                        version=f'kubmonitor {__version__}')

    args = parser.parse_args()

    if args.mock and args.namespace != 'default':
        console = Console()
        console.print(
            "\n[bold red]Error:[/bold red] Cannot specify a namespace when "
            "using [magenta]--mock[/magenta] flag.\n"
        )
        console.print(
            "[dim]Mock mode uses generated test data and doesn't connect "
            "to a real cluster.[/dim]\n"
        )
        console.print("[yellow]Usage:[/yellow]")
        console.print(
            "  [green]kubmonitor --mock[/green]"
            "         [dim]# Use mock data[/dim]"
        )
        console.print(
            "  [green]kubmonitor my-namespace[/green]"
            "   [dim]# Monitor real namespace[/dim]\n"
        )
        sys.exit(1)

    mock_data = None
    if args.mock:
        mock_data = generate_mock_data()
        if not mock_data:
            print("Failed to load mock data. Exiting.")
            return

    console = Console()
    layout = make_layout()

    mode_str = "[bold yellow]MOCK MODE[/]" if args.mock else ""
    layout["header"].update(Panel(
        f"Kubernetes Monitor - Namespace: [bold green]{args.namespace}[/] {mode_str}",
        style="white on blue"))
    layout["footer"].update(Panel("Press 'q' or Ctrl+C to exit", style="dim"))

    old_settings = None
    if platform.system() != "Windows":
        old_settings = termios.tcgetattr(sys.stdin)

    try:
        if platform.system() != "Windows":
            tty.setcbreak(sys.stdin.fileno())

        with Live(layout, refresh_per_second=4, screen=True):
            last_fetch = 0
            fetch_interval = 2
            scroll_offset = 0

            quota = get_quota(args.namespace, use_mock=args.mock, mock_data=mock_data)
            jobs = get_jobs_pods(args.namespace, use_mock=args.mock,
                                 mock_data=mock_data)

            while True:
                # Input Handling - process all buffered input and use last nav key
                key = None
                if platform.system() != "Windows":
                    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        char = sys.stdin.read(1)
                        if char == '\x1b':  # Escape sequence start
                            next1 = sys.stdin.read(1)
                            if next1 == '[':
                                next2 = sys.stdin.read(1)
                                if next2 == 'A':  # Up arrow on Unix/Linux
                                    key = 'up'
                                elif next2 == 'B':  # Down arrow on Unix/Linux
                                    key = 'down'
                        elif char.lower() == 'q':
                            key = 'q'
                else:
                    while msvcrt.kbhit():
                        key_input = msvcrt.getch()
                        if key_input == b'H':  # Up arrow on Windows
                            key = 'up'
                        elif key_input == b'P':  # Down arrow on Windows
                            key = 'down'
                        else:
                            decoded = key_input.decode('utf-8', errors='ignore').lower()
                            if decoded == 'q':
                                key = 'q'

                if key == 'q':
                    break

                cpu_total, cpu_per_core, mem, gpu = get_local_metrics()

                # Calculate total rows needed for all jobs (1 row/job + 1 row/pod)
                total_rows = sum(1 + len(job['pods']) for job in jobs)

                # Calculate max visible rows (approximate based on available height)
                # Account for:
                # header(3) + footer(3) + panel borders(2) + table header(2) = 10
                available_height = console.height - 10
                max_visible_rows = max(10, available_height)

                # Calculate max scroll position with buffer to ensure
                # last job's pods are visible
                max_scroll = max(0, total_rows - max_visible_rows + 3)

                # Navigation
                if key == 'up':
                    scroll_offset = max(0, scroll_offset - 1)
                elif key == 'down':
                    scroll_offset = min(max_scroll, scroll_offset + 1)

                now = time.time()
                if now - last_fetch > fetch_interval:
                    quota = get_quota(args.namespace, use_mock=args.mock,
                                      mock_data=mock_data)
                    jobs = get_jobs_pods(args.namespace, use_mock=args.mock,
                                         mock_data=mock_data)
                    last_fetch = now

                jobs_title = f"Jobs ({len(jobs)})"

                layout["cluster_resources"].update(generate_cluster_resources(quota))
                layout["local_resources"].update(
                    generate_local_resources(cpu_total, cpu_per_core, mem, gpu))
                layout["right"].update(Panel(generate_table(
                    jobs, offset=scroll_offset, max_rows=max_visible_rows),
                    title=jobs_title, border_style="green"))

                time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        if old_settings and platform.system() != "Windows":
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("Exited.")


if __name__ == "__main__":
    main()
