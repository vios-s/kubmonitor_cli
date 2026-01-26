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


def get_gpu_info(ns, use_mock=False, mock_data=None):
    """Get GPU information from cluster nodes and pods."""
    if use_mock:
        return {
            'nodes': [
                {'name': 'gpu-node-01', 'gpu_type': 'H100-80GB', 'gpu_count': 8, 'allocated': 4},
                {'name': 'gpu-node-02', 'gpu_type': 'H100-80GB', 'gpu_count': 8, 'allocated': 0},
                {'name': 'gpu-node-03', 'gpu_type': 'A100-80GB', 'gpu_count': 8, 'allocated': 6},
                {'name': 'gpu-node-04', 'gpu_type': 'A100-80GB', 'gpu_count': 8, 'allocated': 2},
                {'name': 'gpu-node-05', 'gpu_type': 'A100-40GB', 'gpu_count': 4, 'allocated': 3},
            ],
            'total_gpus': 36,
            'allocated_gpus': 15,
            'gpu_types': ['H100-80GB', 'A100-80GB', 'A100-40GB'],
            'node_gpu_map': {
                'gpu-node-01': 'H100-80GB',
                'gpu-node-02': 'H100-80GB', 
                'gpu-node-03': 'A100-80GB',
                'gpu-node-04': 'A100-80GB',
                'gpu-node-05': 'A100-40GB',
            }
        }
    
    gpu_info = {
        'nodes': [],
        'total_gpus': 0,
        'allocated_gpus': 0,
        'gpu_types': set(),
        'node_gpu_map': {}  # Maps node name -> GPU type
    }
    
    # Get nodes with GPU capacity
    nodes_json = run_cmd("kubectl get nodes -o json")
    try:
        nodes = json.loads(nodes_json).get('items', [])
        for node in nodes:
            node_name = node['metadata']['name']
            labels = node['metadata'].get('labels', {})
            capacity = node.get('status', {}).get('capacity', {})
            allocatable = node.get('status', {}).get('allocatable', {})
            
            # Check for NVIDIA GPUs
            gpu_count = 0
            for key in capacity:
                if 'gpu' in key.lower():
                    try:
                        gpu_count = int(capacity[key])
                    except:
                        pass
                    break
            
            if gpu_count > 0:
                # Try to get GPU type from common label patterns
                gpu_type = 'GPU'
                gpu_label_keys = [
                    'nvidia.com/gpu.product',
                    'gpu.nvidia.com/product', 
                    'accelerator',
                    'nvidia.com/gpu.machine',
                    'node.kubernetes.io/instance-type'
                ]
                for label_key in gpu_label_keys:
                    if label_key in labels:
                        raw_type = labels[label_key].replace('-', ' ')
                        # Shorten common GPU names
                        gpu_type = _shorten_gpu_name(raw_type)
                        break
                
                gpu_info['nodes'].append({
                    'name': node_name,
                    'gpu_type': gpu_type,
                    'gpu_count': gpu_count,
                    'allocated': 0  # Will be updated from pod info
                })
                gpu_info['total_gpus'] += gpu_count
                gpu_info['gpu_types'].add(gpu_type)
                gpu_info['node_gpu_map'][node_name] = gpu_type
    except:
        pass
    
    # Get GPU allocation from pods
    pods_json = run_cmd(f"kubectl get pods --all-namespaces -o json")
    try:
        pods = json.loads(pods_json).get('items', [])
        for pod in pods:
            if pod['status'].get('phase') not in ['Running', 'Pending']:
                continue
            node_name = pod['spec'].get('nodeName', '')
            containers = pod['spec'].get('containers', [])
            for container in containers:
                resources = container.get('resources', {}).get('requests', {})
                for key, value in resources.items():
                    if 'gpu' in key.lower():
                        try:
                            gpu_req = int(value)
                            gpu_info['allocated_gpus'] += gpu_req
                            # Update node allocation
                            for node in gpu_info['nodes']:
                                if node['name'] == node_name:
                                    node['allocated'] += gpu_req
                        except (ValueError, TypeError):
                            pass
    except:
        pass
    
    gpu_info['gpu_types'] = list(gpu_info['gpu_types'])
    return gpu_info


def _shorten_gpu_name(name):
    """Shorten GPU names for display."""
    name = name.upper()
    # Common patterns to shorten
    if 'A100' in name:
        if '80G' in name:
            return 'A100-80GB'
        elif '40G' in name:
            return 'A100-40GB'
        return 'A100'
    elif 'H100' in name:
        if '80G' in name:
            return 'H100-80GB'
        return 'H100'
    elif 'V100' in name:
        if '32G' in name:
            return 'V100-32GB'
        elif '16G' in name:
            return 'V100-16GB'
        return 'V100'
    elif 'T4' in name:
        return 'T4'
    elif 'P100' in name:
        return 'P100'
    elif 'P40' in name:
        return 'P40'
    elif 'L40' in name:
        return 'L40S' if 'L40S' in name else 'L40'
    elif 'RTX' in name:
        # Extract RTX model number
        import re
        match = re.search(r'RTX\s*(\d+)', name)
        if match:
            return f'RTX {match.group(1)}'
        return 'RTX'
    # Return shortened version if too long
    if len(name) > 12:
        return name[:10] + '..'
    return name


def get_jobs_pods(ns, use_mock=False, mock_data=None, gpu_info=None):
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
    
    # Build node_gpu_map from gpu_info or mock
    node_gpu_map = {}
    if gpu_info:
        node_gpu_map = gpu_info.get('node_gpu_map', {})
    elif use_mock:
        # Fallback mock mapping should match get_gpu_info's mock GPU types
        node_gpu_map = {
            'gpu-node-01': 'H100-80GB',
            'gpu-node-02': 'A100-80GB',
            'gpu-node-03': 'A100-40GB',
        }

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

            # User and GPU info
            user = "Unknown"
            gpu_request = 0
            gpu_type_from_selector = None
            try:
                pod_spec = spec['template']['spec']
                containers = pod_spec['containers']
                img = containers[0]['image']
                parts = img.split('/')
                user = parts[0] if len(parts) > 1 else img.split(':')[0]
                
                # Get GPU requests
                for container in containers:
                    resources = container.get('resources', {}).get('requests', {})
                    for key, value in resources.items():
                        if 'gpu' in key.lower():
                            try:
                                gpu_request += int(value)
                            except (ValueError, TypeError):
                                pass
                
                # Get GPU type from nodeSelector (most reliable source)
                node_selector = pod_spec.get('nodeSelector', {})
                gpu_selector_keys = [
                    'nvidia.com/gpu.product',
                    'gpu.nvidia.com/product',
                    'accelerator',
                    'nvidia.com/gpu.machine',
                ]
                for key in gpu_selector_keys:
                    if key in node_selector:
                        gpu_type_from_selector = _shorten_gpu_name(node_selector[key])
                        break
            except:
                pass

            # Pods - track node and GPU type
            my_pods = []
            job_gpu_type = gpu_type_from_selector  # Prefer nodeSelector (available before scheduling)
            for pod in pods:
                if pod['metadata']['name'].startswith(name + "-"):
                    p_status = pod['status']['phase']
                    p_node = pod['spec'].get('nodeName', '')
                    my_pods.append({
                        'name': pod['metadata']['name'],
                        'status': p_status,
                        'node': p_node
                    })
                    # Fallback: get GPU type from node if not in nodeSelector
                    if gpu_request > 0 and not job_gpu_type and p_node and p_node in node_gpu_map:
                        job_gpu_type = node_gpu_map[p_node]

            jobs_data.append({
                'name': name,
                'status': status,
                'user': user,
                'completions': f"{succeeded}/{req}",
                'duration': duration,
                'pods': my_pods,
                'gpu': gpu_request,
                'gpu_type': job_gpu_type  # The actual GPU type being used
            })

    except Exception:
        pass

    return jobs_data


def get_pod_logs(ns, pod_name, tail_lines=100, use_mock=False):
    """Fetch logs for a specific pod."""
    if use_mock:
        # Generate mock log data
        mock_logs = []
        import random
        log_messages = [
            "INFO: Starting application...",
            "INFO: Loading configuration from /etc/config/app.yaml",
            "INFO: Connecting to database...",
            "INFO: Database connection established",
            "INFO: Initializing worker threads...",
            "DEBUG: Worker pool size: 4",
            "INFO: Processing batch 1/10",
            "INFO: Processing batch 2/10",
            "WARNING: High memory usage detected (85%)",
            "INFO: Processing batch 3/10",
            "INFO: Processing batch 4/10",
            "DEBUG: Cache hit ratio: 0.87",
            "INFO: Processing batch 5/10",
            "ERROR: Failed to process item #42: timeout",
            "INFO: Retrying item #42...",
            "INFO: Processing batch 6/10",
            "INFO: Processing batch 7/10",
            "INFO: Processing batch 8/10",
            "DEBUG: Checkpoint saved",
            "INFO: Processing batch 9/10",
            "INFO: Processing batch 10/10",
            "INFO: All batches completed successfully",
            "INFO: Cleaning up resources...",
            "INFO: Application finished",
        ]
        for i, msg in enumerate(log_messages[:tail_lines]):
            timestamp = f"2026-01-21T10:{i:02d}:00Z"
            mock_logs.append(f"{timestamp} {msg}")
        return "\n".join(mock_logs)
    
    cmd = f"kubectl -n {ns} logs {pod_name} --tail={tail_lines}"
    return run_cmd(cmd)


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


def build_row_index(jobs):
    """Build a flat list of all rows (jobs and pods) for selection tracking."""
    all_rows = []
    for job in jobs:
        if job['status'] == 'Completed':
            status_style = "green"
        elif job['status'] == 'Failed':
            status_style = "red"
        else:
            status_style = "yellow"
        
        # Format GPU display - show count and type if available
        gpu_count = job.get('gpu', 0)
        gpu_type = job.get('gpu_type')
        if gpu_count > 0:
            if gpu_type:
                gpu_display = f"{gpu_count}x {gpu_type}"
            else:
                gpu_display = str(gpu_count)
        else:
            gpu_display = "-"

        all_rows.append({
            'type': 'job',
            'name': job['name'],
            'display_name': f"[bold]{job['name']}[/]",
            'user': job['user'],
            'status': f"[{status_style}]{job['status']}[/]",
            'gpu': gpu_display,
            'completions': job['completions'],
            'duration': job['duration'],
            'pod_name': None  # Jobs don't have pod_name for log viewing
        })

        for i, pod_info in enumerate(job['pods']):
            # Handle both old format (string) and new format (dict)
            if isinstance(pod_info, dict):
                p_name = pod_info['name']
                p_status = pod_info['status']
            else:
                # Legacy string format: "pod-name (Status)"
                p_name = pod_info.split(' (')[0]
                p_status = pod_info.split(' (')[1].rstrip(')')

            is_last = (i == len(job['pods']) - 1)
            prefix = "└── " if is_last else "├── "

            p_status_style = "green" if p_status == 'Running' else "dim"

            all_rows.append({
                'type': 'pod',
                'name': p_name,
                'display_name': f"  {prefix}{p_name}",
                'user': "",
                'status': f"[{p_status_style}]{p_status}[/]",
                'gpu': "",
                'completions': "",
                'duration': "",
                'pod_name': p_name  # Actual pod name for log fetching
            })
    return all_rows


def generate_table(jobs, offset=0, max_rows=None, selected_index=0):
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_lines=False)
    table.add_column("Job / Pod Name", style="cyan", no_wrap=True)
    table.add_column("User", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("GPU", justify="center", style="yellow")
    table.add_column("Comp", justify="right")
    table.add_column("Duration", justify="right")

    all_rows = build_row_index(jobs)

    visible_rows = all_rows[offset:]
    if max_rows:
        visible_rows = visible_rows[:max_rows]

    for i, row in enumerate(visible_rows):
        actual_index = offset + i
        is_selected = (actual_index == selected_index)
        
        # Apply selection highlighting
        if is_selected:
            name_display = f"[reverse]{row['display_name']}[/reverse]"
            # Add indicator for pods that can show logs without breaking tree indentation
            if row['type'] == 'pod':
                name_display = f"[reverse]{row['display_name']} ▶[/reverse]"
        else:
            name_display = row['display_name']
        
        table.add_row(
            name_display,
            row['user'],
            row['status'],
            row['gpu'],
            row['completions'],
            row['duration']
        )

    return table, all_rows


def generate_cluster_resources(quota, gpu_info=None):
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")

    grid.add_row("[bold]CPU[/bold]", quota['cpu']['str'])
    grid.add_row("[bold]MEM[/bold]", quota['mem']['str'])
    grid.add_row("[bold]GPU[/bold]", quota['gpu']['str'])
    
    # Add detailed GPU info by type
    if gpu_info and gpu_info.get('nodes'):
        grid.add_row("", "")  # Spacer
        
        # Aggregate by GPU type
        gpu_by_type = {}
        for node in gpu_info['nodes']:
            gpu_type = node['gpu_type']
            if gpu_type not in gpu_by_type:
                gpu_by_type[gpu_type] = {'total': 0, 'allocated': 0}
            gpu_by_type[gpu_type]['total'] += node['gpu_count']
            gpu_by_type[gpu_type]['allocated'] += node['allocated']
        
        # Display each GPU type with usage
        for gpu_type, counts in gpu_by_type.items():
            used = counts['allocated']
            total = counts['total']
            # Color based on utilization
            if total > 0:
                pct = (used / total) * 100
                if pct >= 80:
                    color = "red"
                elif pct >= 50:
                    color = "yellow"
                else:
                    color = "green"
            else:
                color = "dim"
            grid.add_row(
                f"  [cyan]{gpu_type}[/cyan]",
                f"[{color}]{used}/{total}[/{color}]"
            )

    return Panel(grid, title="Cluster Quota", border_style="blue")


def generate_log_viewer(logs, pod_name, scroll_offset=0, max_lines=None):
    """Generate a log viewer panel for a specific pod."""
    lines = logs.split('\n') if logs else ["No logs available"]
    
    # Apply scroll offset
    visible_lines = lines[scroll_offset:]
    if max_lines:
        visible_lines = visible_lines[:max_lines]
    
    # Color-code log lines based on level
    formatted_lines = []
    for line in visible_lines:
        line_upper = line.upper()
        if 'ERROR' in line_upper:
            formatted_lines.append(f"[red]{line}[/red]")
        elif 'WARNING' in line_upper or 'WARN' in line_upper:
            formatted_lines.append(f"[yellow]{line}[/yellow]")
        elif 'DEBUG' in line_upper:
            formatted_lines.append(f"[dim]{line}[/dim]")
        elif 'INFO' in line_upper:
            formatted_lines.append(f"[green]{line}[/green]")
        else:
            formatted_lines.append(line)
    
    log_text = "\n".join(formatted_lines) if formatted_lines else "No logs available"
    
    # Create scroll indicator
    has_real_logs = bool(logs and logs.strip())
    if not has_real_logs:
        total_lines = 0
        scroll_info = " (0-0/0)"
    else:
        total_lines = len(lines)
        start_line = min(scroll_offset + 1, total_lines)
        end_line = min(scroll_offset + (max_lines or total_lines), total_lines)
        scroll_info = f" ({start_line}-{end_line}/{total_lines})"
    
    return Panel(
        log_text,
        title=f"Logs: {pod_name}{scroll_info}",
        subtitle="[dim]↑/↓ Scroll | ESC/Backspace Close | r Refresh[/dim]",
        border_style="cyan",
        expand=True
    )


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
    console.print("  [cyan]Enter[/cyan]          View logs for selected pod")
    console.print("  [cyan]ESC/Backspace[/cyan]  Close log viewer")
    console.print("  [cyan]r[/cyan]              Refresh logs (in log viewer)")
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
    layout["footer"].update(Panel(
        "[cyan]↑/↓[/cyan] Navigate  [cyan]Enter[/cyan] View Logs  [cyan]q[/cyan] Quit",
        style="dim"))

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
            selected_index = 0  # Track selected row
            
            # Log viewer state
            viewing_logs = False
            current_logs = ""
            current_pod_name = ""
            log_scroll_offset = 0

            quota = get_quota(args.namespace, use_mock=args.mock, mock_data=mock_data)
            gpu_info = get_gpu_info(args.namespace, use_mock=args.mock, mock_data=mock_data)
            jobs = get_jobs_pods(args.namespace, use_mock=args.mock,
                                 mock_data=mock_data, gpu_info=gpu_info)

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
                            else:
                                # Just ESC key (no bracket following)
                                key = 'escape'
                        elif char.lower() == 'q':
                            key = 'q'
                        elif char == '\n' or char == '\r':  # Enter key
                            key = 'enter'
                        elif char == '\x7f' or char == '\x08':  # Backspace
                            key = 'backspace'
                        elif char.lower() == 'r':
                            key = 'r'
                else:
                    while msvcrt.kbhit():
                        key_input = msvcrt.getch()
                        if key_input == b'\xe0':  # Extended key prefix on Windows
                            key_input = msvcrt.getch()
                            if key_input == b'H':  # Up arrow on Windows
                                key = 'up'
                            elif key_input == b'P':  # Down arrow on Windows
                                key = 'down'
                        elif key_input == b'H':  # Up arrow on Windows (alternate)
                            key = 'up'
                        elif key_input == b'P':  # Down arrow on Windows (alternate)
                            key = 'down'
                        elif key_input == b'\r':  # Enter key
                            key = 'enter'
                        elif key_input == b'\x1b':  # Escape key
                            key = 'escape'
                        elif key_input == b'\x08':  # Backspace
                            key = 'backspace'
                        else:
                            decoded = key_input.decode('utf-8', errors='ignore').lower()
                            if decoded == 'q':
                                key = 'q'
                            elif decoded == 'r':
                                key = 'r'

                # Handle quit
                if key == 'q' and not viewing_logs:
                    break

                cpu_total, cpu_per_core, mem, gpu = get_local_metrics()

                # Build row index for selection tracking
                all_rows = build_row_index(jobs)
                total_rows = len(all_rows)

                # Calculate max visible rows (approximate based on available height)
                # Account for:
                # header(3) + footer(3) + panel borders(2) + table header(2) = 10
                available_height = console.height - 10
                max_visible_rows = max(10, available_height)

                if viewing_logs:
                    # Log viewer mode
                    log_lines = current_logs.split('\n') if current_logs else []
                    max_log_scroll = max(0, len(log_lines) - max_visible_rows + 5)
                    
                    if key == 'escape' or key == 'backspace' or key == 'q':
                        viewing_logs = False
                        current_logs = ""
                        current_pod_name = ""
                        log_scroll_offset = 0
                    elif key == 'up':
                        log_scroll_offset = max(0, log_scroll_offset - 1)
                    elif key == 'down':
                        log_scroll_offset = min(max_log_scroll, log_scroll_offset + 1)
                    elif key == 'r':
                        # Manual refresh logs
                        current_logs = get_pod_logs(
                            args.namespace, current_pod_name,
                            tail_lines=500, use_mock=args.mock
                        )
                    
                    # Auto-refresh logs periodically
                    now = time.time()
                    if now - last_fetch > fetch_interval:
                        current_logs = get_pod_logs(
                            args.namespace, current_pod_name,
                            tail_lines=500, use_mock=args.mock
                        )
                        last_fetch = now
                    
                    # Update layout with log viewer
                    layout["cluster_resources"].update(generate_cluster_resources(quota, gpu_info))
                    layout["local_resources"].update(
                        generate_local_resources(cpu_total, cpu_per_core, mem, gpu))
                    layout["right"].update(generate_log_viewer(
                        current_logs, current_pod_name,
                        scroll_offset=log_scroll_offset,
                        max_lines=max_visible_rows
                    ))
                    layout["footer"].update(Panel(
                        f"[cyan]↑/↓[/cyan] Scroll  [cyan]r[/cyan] Refresh  [cyan]ESC/Backspace[/cyan] Close  [dim](auto-refresh {fetch_interval}s)[/dim]  Viewing: [bold]{current_pod_name}[/bold]",
                        style="dim"))
                else:
                    # Normal job/pod list mode
                    # Calculate max scroll position with buffer to ensure
                    # last job's pods are visible
                    max_scroll = max(0, total_rows - max_visible_rows + 3)

                    # Navigation
                    if key == 'up':
                        selected_index = max(0, selected_index - 1)
                        # Auto-scroll to keep selection visible
                        if selected_index < scroll_offset:
                            scroll_offset = selected_index
                    elif key == 'down':
                        selected_index = min(total_rows - 1, selected_index + 1)
                        # Auto-scroll to keep selection visible
                        if selected_index >= scroll_offset + max_visible_rows:
                            scroll_offset = selected_index - max_visible_rows + 1
                    elif key == 'enter':
                        # Open log viewer for selected pod
                        if total_rows > 0 and selected_index < len(all_rows):
                            selected_row = all_rows[selected_index]
                            if selected_row['type'] == 'pod' and selected_row['pod_name']:
                                viewing_logs = True
                                current_pod_name = selected_row['pod_name']
                                log_scroll_offset = 0
                                current_logs = get_pod_logs(
                                    args.namespace, current_pod_name,
                                    tail_lines=500, use_mock=args.mock
                                )

                    now = time.time()
                    if now - last_fetch > fetch_interval:
                        quota = get_quota(args.namespace, use_mock=args.mock,
                                          mock_data=mock_data)
                        gpu_info = get_gpu_info(args.namespace, use_mock=args.mock,
                                                mock_data=mock_data)
                        jobs = get_jobs_pods(args.namespace, use_mock=args.mock,
                                             mock_data=mock_data, gpu_info=gpu_info)
                        last_fetch = now

                    jobs_title = f"Jobs ({len(jobs)})"
                    
                    # Generate table with selection
                    table, _ = generate_table(
                        jobs, offset=scroll_offset,
                        max_rows=max_visible_rows, selected_index=selected_index
                    )

                    layout["cluster_resources"].update(generate_cluster_resources(quota, gpu_info))
                    layout["local_resources"].update(
                        generate_local_resources(cpu_total, cpu_per_core, mem, gpu))
                    layout["right"].update(Panel(table, title=jobs_title, border_style="green"))
                    layout["footer"].update(Panel(
                        "[cyan]↑/↓[/cyan] Navigate  [cyan]Enter[/cyan] View Logs  [cyan]q[/cyan] Quit",
                        style="dim"))

                time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        if old_settings and platform.system() != "Windows":
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("Exited.")


if __name__ == "__main__":
    main()
