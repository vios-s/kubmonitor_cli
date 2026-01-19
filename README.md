<div align="center">

![KubMonitor Logo](assets/logo.svg)

# KubMonitor CLI

**A beautiful, nvitop-style Kubernetes monitor for your terminal.**

[![PyPI Version](https://img.shields.io/pypi/v/kubmonitor-cli?style=flat-square&color=blue)](https://pypi.org/project/kubmonitor-cli/)
[![Python Version](https://img.shields.io/pypi/pyversions/kubmonitor-cli?style=flat-square)](https://pypi.org/project/kubmonitor-cli/)
[![License](https://img.shields.io/github/license/vios-s/kubmonitor_cli?style=flat-square)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/vios-s/kubmonitor_cli/release.yml?style=flat-square)](https://github.com/vios-s/kubmonitor-cli/actions)

</div>

---

## ✨ Overview

**KubMonitor** provides a real-time, high-fidelity dashboard for your Kubernetes clusters directly in your terminal. Inspired by tools like `nvitop` and `btop`, it combines cluster quotas with local machine metrics in a slick, responsive TUI (Terminal User Interface).

![KubMonitor Demo](assets/screenshot.png)

## 🚀 Features

- **📊 Real-time Dashboard**: Live updates of CPU, Memory, and GPU usage.
- **☸️ Namespace Scoped**: Monitor specific Kubernetes namespaces with ease.
- **💻 Hybrid Metrics**: View both K8s Cluster Quotas and Local Machine stats side-by-side.
- **⚡ Reactive TUI**: Built with `Refreshed` layouts using [Rich](https://github.com/Textualize/rich).
- **🖥️ Cross-Platform**: Works seamlessly on Linux, macOS, and Windows.

## 📦 Installation

Install via pip:

```bash
pip install kubmonitor-cli
```

Or install from source:

```bash
git clone https://github.com/vios-s/kubmonitor-cli.git
cd kubmonitor-cli
pip install .
```

## 🎮 Usage

Simply run the command followed by the target namespace:

```bash
kubmonitor <namespace>
```

**Example:**

```bash
kubmonitor eidf098ns
```

### Mock Mode (Testing/Debug)

For testing or debugging purposes without requiring access to a Kubernetes cluster, you can use the `--mock` flag to run KubMonitor with simulated data:

```bash
kubmonitor <namespace> --mock
```

**Example:**

```bash
kubmonitor test-namespace --mock
```

This will generate realistic mock data including:
- Simulated resource quotas (CPU, Memory, GPU)
- Mock Kubernetes jobs with various states (running, completed, failed)
- Mock pods with realistic resource usage patterns
- Generated timestamps and durations


### Keyboard Shortcuts

| Key | Description |
| :---: | :--- |
| `↑` / `↓` | **Navigate** up and down |
| `q` | **Quit** the application |
| `Ctrl+C` | Force Exit |

## 🛠️ Technology Stack

- **[Rich](https://github.com/Textualize/rich)**: For beautiful terminal formatting and layout.
- **[Psutil](https://github.com/giampaolo/psutil)**: For retrieving local system metrics.
- **Kubectl**: Under the hood, it uses your local `kubectl` configuration to fetch cluster data.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Made with ❤️ by yyx</sub>
</div>
