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

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return ""

def get_quota(ns):
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
        if in_table and line.strip().startswith('----'): continue
        if in_table and not line.strip(): break
        
        if in_table:
            parts = line.split()
            if len(parts) >= 3:
                res = parts[0]
                used = parts[1]
                limit = parts[2]
                
                if res.startswith('limits.'): continue 
                
                key = None
                if res in ['requests.cpu', 'cpu']: key = 'cpu'
                elif res in ['requests.memory', 'memory']: key = 'mem'
                elif 'gpu' in res: key = 'gpu'
                
                if key:
                    data[key]['str'] = f"{used} / {limit}"
                    try:
                        if limit.isdigit() and int(limit) > 0:
                            data[key]['percent'] = (int(used) / int(limit)) * 100
                    except:
                        pass
                        
    return data

def get_jobs_pods(ns):
    jobs_json = run_cmd(f"kubectl -n {ns} get jobs -o json")
    pods_json = run_cmd(f"kubectl -n {ns} get pods -o json")
    
    jobs_data = []
    try:
        j = json.loads(jobs_json)
        p = json.loads(pods_json).get('items', [])
        
        for job in j.get('items', []):
            name = job['metadata']['name']
            status_obj = job.get('status', {})
            spec = job.get('spec', {})
            
            # Status Logic
            status = 'Unknown'
            active = status_obj.get('active', 0)
            succeeded = status_obj.get('succeeded', 0)
            failed = status_obj.get('failed', 0)
            req = spec.get('completions', 1)
            
            if succeeded >= req: status = 'Completed'
            elif active > 0: status = 'Running'
            elif failed > 0: status = 'Failed'
            else: status = 'Pending'
            
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
                    mins = int(diff.total_seconds() / 60)
                    duration = f"{mins}m"
                    if not 'completionTime' in status_obj:
                        duration += " (Run)"
                except Exception as e:
                    pass

            # User
            user = "Unknown"
            try:
                img = spec['template']['spec']['containers'][0]['image']
                parts = img.split('/')
                user = parts[0] if len(parts) > 1 else img.split(':')[0]
            except: pass
            
            # Pods
            my_pods = []
            for pod in p:
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
            
    except Exception as e:
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
        res = subprocess.run("nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader", shell=True, capture_output=True, text=True)
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
    for _ in range(4): cores_grid.add_column(justify="center", ratio=1)
    
    row_cells = []
    for i, p in enumerate(cpu_per_core):
        color = "green" if p < 50 else "yellow" if p < 80 else "red"
        row_cells.append(f"C{i}: [{color}]{p:.0f}%[/]")
        if len(row_cells) == 4:
            cores_grid.add_row(*row_cells)
            row_cells = []
    if row_cells:
        while len(row_cells) < 4: row_cells.append("")
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

def generate_table(jobs):
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_lines=False)
    table.add_column("Job / Pod Name", style="cyan", no_wrap=True)
    table.add_column("User", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Comp", justify="right")
    table.add_column("Duration", justify="right")
    
    for job in jobs:
        status_style = "green" if job['status'] == 'Completed' else "red" if job['status'] == 'Failed' else "yellow"
        
        table.add_row(
            f"[bold]{job['name']}[/]", 
            job['user'], 
            f"[{status_style}]{job['status']}[/]", 
            job['completions'],
            job['duration']
        )
        
        for i, pod_str in enumerate(job['pods']):
            p_name = pod_str.split(' (')[0]
            p_status = pod_str.split(' (')[1].rstrip(')')
            
            is_last = (i == len(job['pods']) - 1)
            prefix = "└── " if is_last else "├── "
            
            p_status_style = "green" if p_status == 'Running' else "dim"
            
            table.add_row(
                f"  {prefix}{p_name}", 
                "", 
                f"[{p_status_style}]{p_status}[/]", 
                "", 
                ""
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

def main():
    parser = argparse.ArgumentParser(description="Kubernetes Monitor (nvitop style)")
    parser.add_argument("namespace", help="Kubernetes Namespace")
    args = parser.parse_args()
    
    console = Console()
    layout = make_layout()
    
    layout["header"].update(Panel(f"Kubernetes Monitor - Namespace: [bold green]{args.namespace}[/]", style="white on blue"))
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
            
            quota = get_quota(args.namespace)
            jobs = get_jobs_pods(args.namespace)
            
            while True:
                # Input Handling
                key = None
                if platform.system() != "Windows":
                    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1)
                else:
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8').lower()
                
                if key and key.lower() == 'q':
                    break
                
                now = time.time()
                if now - last_fetch > fetch_interval:
                    quota = get_quota(args.namespace)
                    jobs = get_jobs_pods(args.namespace)
                    last_fetch = now
                
                cpu_total, cpu_per_core, mem, gpu = get_local_metrics()
                
                layout["cluster_resources"].update(generate_cluster_resources(quota))
                layout["local_resources"].update(generate_local_resources(cpu_total, cpu_per_core, mem, gpu))
                layout["right"].update(Panel(generate_table(jobs), title=f"Jobs ({len(jobs)})", border_style="green"))
                
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        pass
    finally:
        if old_settings and platform.system() != "Windows":
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("Exited.")

if __name__ == "__main__":
    main()
