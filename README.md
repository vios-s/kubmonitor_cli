# KubMonitor CLI

A beautiful, nvitop-style Kubernetes monitor for your terminal.

## Installation

1.  Navigate to the directory:
    ```bash
    cd kubmonitor_cli
    ```
2.  Install the package:
    ```bash
    pip install .
    ```

## Usage

Run the tool with the target namespace:

```bash
kubmonitor <namespace>
```

Example:
```bash
kubmonitor eidf098ns
```

## shortcuts
- `q`: Quit

## Metrics
- **Cluster**: CPU, Memory, GPU quotas from Kubernetes.
- **Local**: Real-time CPU (per core) and Memory usage of the host machine.
