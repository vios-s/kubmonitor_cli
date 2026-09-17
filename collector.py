"""One-shot usage snapshot: kubectl -> SQLite.

Run periodically (cron / systemd timer):

    kubmonitor collect --config /path/to/project.yaml

Each run upserts every Job (and bare Pod) currently visible in the
namespace into the workloads table, snapshots the resource quota, and —
if enabled — samples real GPU utilization by exec'ing nvidia-smi inside
running GPU pods. Runs are stateless and idempotent; a missed run only
widens the sampling gap, Job start/completion times come from the API
objects themselves.
"""

import json
import re
import subprocess

import usagedb
from monitor import run_cmd, _shorten_gpu_name, parse_quantity
from mock_data import generate_mock_data

GPU_SELECTOR_KEYS = [
    "nvidia.com/gpu.product",
    "gpu.nvidia.com/product",
    "accelerator",
    "nvidia.com/gpu.machine",
]


def _labels_of(obj):
    return (obj.get("metadata", {}) or {}).get("labels", {}) or {}


def _pod_template_labels(job):
    tpl = job.get("spec", {}).get("template", {})
    return (tpl.get("metadata", {}) or {}).get("labels", {}) or {}


def _name_tokens_contains(name, account):
    """True if `account` appears as a '-'-bounded token run of `name`
    (underscores in accounts compared against '-' in names)."""
    norm = account.replace("_", "-").lower()
    return f"-{norm}-" in f"-{name.lower()}-"


def _images_of(pod_spec):
    """All container images, comma-joined (or None). Persisted so that
    retroactive re-attribution sees the same hints live attribution did,
    including multi-container pods."""
    images = [c["image"] for c in pod_spec.get("containers", []) or []
              if c.get("image")]
    return ",".join(images) if images else None


def _image_hints(pod_spec):
    """Possible account tokens hiding in container image references.

    Docker Hub style (`alice/train:2.1`) puts the account in the first
    path segment; private-registry style (host contains a dot) often
    carries the username in the tag (ECIR convention `cuda-eidf:<user>`).
    """
    hints = []
    for container in pod_spec.get("containers", []) or []:
        img = container.get("image", "") or ""
        parts = img.split("/")
        if len(parts) > 1 and "." not in parts[0]:
            hints.append(parts[0])
        tag = img.rsplit(":", 1)[1] if ":" in img else ""
        if tag and tag != "latest" and not tag[0].isdigit():
            hints.append(tag)
    return hints


def resolve_account(name, label_sets, prefix, name_map, image_hints=()):
    """Return (account_or_None, attribution).

    name_map maps a matchable token (account or alias) to the canonical
    account it attributes to; a plain set/list of accounts also works.
    Image hints only count when they match a declared token — a random
    Docker Hub account never becomes an attribution on its own.
    """
    if not isinstance(name_map, dict):
        name_map = {token: token for token in name_map}
    owner_keys = ([f"{prefix}/owner"] if prefix else []) + ["owner"]
    for key in owner_keys:
        for labels in label_sets:
            if labels.get(key):
                return labels[key], "label"
    for token in sorted(name_map, key=len, reverse=True):
        if _name_tokens_contains(name, token):
            return name_map[token], "name"
    lowered = {token.lower(): account for token, account in name_map.items()}
    for hint in image_hints:
        if hint.lower() in lowered:
            return lowered[hint.lower()], "image"
    return None, "none"


def _label_value(label_sets, prefix, name):
    """First non-empty value of `name` across label_sets, prefix first."""
    keys = ([f"{prefix}/{name}"] if prefix else []) + [name]
    for key in keys:
        for labels in label_sets:
            if labels.get(key):
                return labels[key]
    return None


def _purpose_of(label_sets, prefix):
    return _label_value(label_sets, prefix, "purpose")


def _research_project_of(label_sets, prefix):
    """The `project` label — the owner's research project (docs/LABELS.md).

    Not the allocation code: that is `cfg.project`, the scope key. A
    workload with no such label stays NULL rather than inheriting the
    allocation, so reports can tell "unlabelled" from a real project.
    """
    return _label_value(label_sets, prefix, "project")


def _pod_spec_requests(pod_spec):
    """Sum (gpu, cpu_cores, mem_gb) requests across containers."""
    gpu, cpu, mem = 0, 0.0, 0.0
    for container in pod_spec.get("containers", []):
        requests = (container.get("resources", {}) or {}).get("requests", {}) or {}
        for key, value in requests.items():
            if "gpu" in key.lower():
                try:
                    gpu += int(value)
                except (ValueError, TypeError):
                    pass
            elif key == "cpu":
                cpu += parse_quantity(value)
            elif key == "memory":
                mem += parse_quantity(value) / 2**30
    return gpu, cpu, mem


def _gpu_model_from_selector(pod_spec):
    selector = pod_spec.get("nodeSelector", {}) or {}
    for key in GPU_SELECTOR_KEYS:
        if key in selector:
            return _shorten_gpu_name(selector[key])
    return None


def _fetch_json_items(cmd, strict=False):
    """Run a `kubectl ... -o json` command and return its item list.

    kubectl always prints a JSON List (even when empty), so no output or
    unparsable output means the command itself failed. With strict=True
    that raises — a cron collector must record such a run as failed
    rather than as "success, 0 workloads".
    """
    out = run_cmd(cmd)
    try:
        return json.loads(out).get("items", [])
    except (ValueError, AttributeError):
        if strict:
            raise RuntimeError(f"kubectl gave no parsable output: {cmd}")
        return []


def _node_gpu_map(kubectl):
    node_map = {}
    for node in _fetch_json_items(f"{kubectl} get nodes -o json"):
        labels = _labels_of(node)
        capacity = node.get("status", {}).get("capacity", {}) or {}
        has_gpu = any("gpu" in k.lower() for k in capacity)
        if not has_gpu:
            continue
        gpu_type = "GPU"
        for key in GPU_SELECTOR_KEYS + ["node.kubernetes.io/instance-type"]:
            if key in labels:
                gpu_type = _shorten_gpu_name(labels[key])
                break
        node_map[node["metadata"]["name"]] = gpu_type
    return node_map


def _job_phase(job):
    status = job.get("status", {}) or {}
    required = job.get("spec", {}).get("completions", 1) or 1
    if status.get("succeeded", 0) >= required:
        return "Succeeded"
    if status.get("failed", 0) > 0 and not status.get("active", 0):
        return "Failed"
    if status.get("active", 0) > 0:
        return "Running"
    return "Pending"


def _pod_completion_time(pod):
    """Latest container termination time of a finished pod, if any."""
    times = []
    for cs in pod.get("status", {}).get("containerStatuses", []) or []:
        terminated = (cs.get("state", {}) or {}).get("terminated") or {}
        if terminated.get("finishedAt"):
            times.append(terminated["finishedAt"])
    return max(times) if times else None


def _uid_of(obj, cfg, kind):
    meta = obj.get("metadata", {}) or {}
    return meta.get("uid") or f"{cfg.namespace}/{kind}/{meta.get('name', '?')}"


def _sample_pod_gpus(cfg, pod, account, ts, conn, workload_uid=None):
    """Exec nvidia-smi inside a running GPU pod; ignore all failures."""
    pod_name = pod["metadata"]["name"]
    cmd = cfg.kubectl(
        f"-n {cfg.namespace} exec {pod_name} -- nvidia-smi "
        f"--query-gpu=index,utilization.gpu,memory.used,memory.total "
        f"--format=csv,noheader,nounits")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return 0
    if result.returncode != 0:
        return 0
    count = 0
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            idx, util, mem_used, mem_total = (int(parts[0]), float(parts[1]),
                                              float(parts[2]), float(parts[3]))
        except ValueError:
            continue
        usagedb.add_util_sample(
            conn, ts, cfg.project, _uid_of(pod, cfg, "Pod"), pod_name,
            account, idx, util, mem_used, mem_total,
            workload_uid=workload_uid)
        count += 1
    return count


def _snapshot_quota(cfg, conn, ts, use_mock, mock_data):
    if use_mock:
        for res, entry in (mock_data.get("quota") or {}).items():
            m = re.match(r"^\s*([\d.]+\w*)\s*/\s*([\d.]+\w*)\s*$",
                         entry.get("str", ""))
            if m:
                usagedb.add_quota_snapshot(
                    conn, ts, cfg.project, res,
                    parse_quantity(m.group(1)), parse_quantity(m.group(2)))
        return
    items = _fetch_json_items(
        cfg.kubectl(f"-n {cfg.namespace} get resourcequota -o json"))
    for rq in items:
        status = rq.get("status", {}) or {}
        hard, used = status.get("hard", {}) or {}, status.get("used", {}) or {}
        for key, hard_val in hard.items():
            if key.startswith("limits."):
                continue
            if key in ("requests.cpu", "cpu"):
                res = "cpu"
            elif key in ("requests.memory", "memory"):
                res = "mem"
            elif "gpu" in key:
                res = "gpu"
            else:
                continue
            usagedb.add_quota_snapshot(
                conn, ts, cfg.project, res,
                parse_quantity(used.get(key, 0)), parse_quantity(hard_val))


def _mark_deleted(conn, cfg, current_uids):
    """Freeze rows for workloads that vanished before finishing.

    A job deleted while Running never gets a completionTime, so its row
    would claim "Running" forever. Marking it 'Deleted' keeps reports
    honest; GPU-hour accounting is unaffected either way because accrual
    already stops at last_seen.
    """
    rows = conn.execute(
        "SELECT uid FROM workloads WHERE project = ? "
        "AND phase IN ('Running', 'Pending', 'Unknown')",
        (cfg.project,)).fetchall()
    gone = [r["uid"] for r in rows if r["uid"] not in current_uids]
    if gone:
        conn.executemany(
            "UPDATE workloads SET phase = 'Deleted' WHERE uid = ?",
            [(uid,) for uid in gone])
    return len(gone)


def _reattribute_unknown(conn, cfg, name_map):
    """Retry attribution for historical rows that have none.

    Workloads deleted from the cluster are never re-observed, so an
    account/alias added to the members file *after* they were recorded
    would otherwise stay unattributed forever. Re-running the name/image
    matching against the current members map lets history heal itself.
    Rows fixed by hand (attribution='manual') are never touched.
    """
    if not name_map:
        return 0
    healed = 0
    rows = conn.execute(
        "SELECT uid, name, image FROM workloads "
        "WHERE project = ? AND attribution = 'none'",
        (cfg.project,)).fetchall()
    for row in rows:
        hints = ()
        if row["image"]:
            hints = _image_hints({"containers": [
                {"image": img} for img in row["image"].split(",")]})
        account, attribution = resolve_account(
            row["name"], [{}], cfg.label_prefix, name_map, hints)
        if account:
            conn.execute(
                "UPDATE workloads SET account = ?, attribution = ? "
                "WHERE uid = ?", (account, attribution, row["uid"]))
            healed += 1
    return healed


def collect(cfg, use_mock=False, verbose=False):
    """Run one collection cycle. Returns (n_jobs, n_pods) recorded."""
    conn = usagedb.open_db(cfg.db)
    ts = usagedb.utcnow_iso()
    members = cfg.load_members() if cfg.members_file else None
    name_map = members.name_match_map() if members else {}
    kubectl = cfg.kubectl("").strip()

    try:
        if use_mock:
            mock_data = generate_mock_data()
            jobs = mock_data["jobs"]["items"]
            pods = mock_data["pods"]["items"]
            node_map = mock_data.get("node_gpu_map", {})
        else:
            mock_data = None
            jobs = _fetch_json_items(
                cfg.kubectl(f"-n {cfg.namespace} get jobs -o json"),
                strict=True)
            pods = _fetch_json_items(
                cfg.kubectl(f"-n {cfg.namespace} get pods -o json"),
                strict=True)
            # Nodes may be RBAC-restricted; missing GPU models must not
            # abort the whole collection.
            node_map = _node_gpu_map(kubectl)

        # Index pods by owning job (ownerReferences first, name prefix as
        # fallback for sources that lack them, e.g. mock data).
        job_names = {j["metadata"]["name"] for j in jobs}
        pods_by_job, bare_pods = {}, []
        for pod in pods:
            owner_job = None
            for ref in (pod.get("metadata", {}).get("ownerReferences") or []):
                if ref.get("kind") == "Job" and ref.get("name") in job_names:
                    owner_job = ref["name"]
                    break
            if owner_job is None:
                for jn in job_names:
                    if pod["metadata"]["name"].startswith(jn + "-"):
                        owner_job = jn
                        break
            if owner_job:
                pods_by_job.setdefault(owner_job, []).append(pod)
            else:
                bare_pods.append(pod)

        gpu_pods_to_sample = []  # (pod, account, owning workload uid)
        current_uids = set()     # everything seen in this snapshot

        for job in jobs:
            name = job["metadata"]["name"]
            pod_spec = job.get("spec", {}).get("template", {}).get("spec", {}) or {}
            label_sets = [_labels_of(job), _pod_template_labels(job)]
            account, attribution = resolve_account(
                name, label_sets, cfg.label_prefix, name_map,
                image_hints=_image_hints(pod_spec))
            gpu, cpu, mem_gb = _pod_spec_requests(pod_spec)
            gpu_model = _gpu_model_from_selector(pod_spec)
            job_uid = _uid_of(job, cfg, "Job")
            current_uids.add(job_uid)
            node = None
            for pod in pods_by_job.get(name, []):
                node = pod.get("spec", {}).get("nodeName") or node
                if gpu > 0 and not gpu_model and node in node_map:
                    gpu_model = node_map[node]
                if (gpu > 0 and
                        pod.get("status", {}).get("phase") == "Running"):
                    gpu_pods_to_sample.append((pod, account, job_uid))
            status = job.get("status", {}) or {}
            usagedb.upsert_workload(conn, {
                "uid": job_uid,
                "project": cfg.project, "namespace": cfg.namespace,
                "kind": "Job", "name": name,
                "account": account, "attribution": attribution,
                "purpose": _purpose_of(label_sets, cfg.label_prefix),
                "research_project": _research_project_of(
                    label_sets, cfg.label_prefix),
                "gpu_count": gpu, "gpu_model": gpu_model,
                "image": _images_of(pod_spec),
                "cpu_request": cpu, "mem_request_gb": mem_gb,
                "node": node,
                "created_at": job.get("metadata", {}).get("creationTimestamp"),
                "started_at": status.get("startTime"),
                "completed_at": status.get("completionTime"),
                "phase": _job_phase(job),
            })

        for pod in bare_pods:
            name = pod["metadata"]["name"]
            pod_spec = pod.get("spec", {}) or {}
            label_sets = [_labels_of(pod)]
            account, attribution = resolve_account(
                name, label_sets, cfg.label_prefix, name_map,
                image_hints=_image_hints(pod_spec))
            gpu, cpu, mem_gb = _pod_spec_requests(pod_spec)
            node = pod_spec.get("nodeName")
            gpu_model = _gpu_model_from_selector(pod_spec)
            if gpu > 0 and not gpu_model and node in node_map:
                gpu_model = node_map[node]
            phase = pod.get("status", {}).get("phase", "Unknown")
            pod_uid = _uid_of(pod, cfg, "Pod")
            current_uids.add(pod_uid)
            if gpu > 0 and phase == "Running":
                gpu_pods_to_sample.append((pod, account, pod_uid))
            usagedb.upsert_workload(conn, {
                "uid": pod_uid,
                "project": cfg.project, "namespace": cfg.namespace,
                "kind": "Pod", "name": name,
                "account": account, "attribution": attribution,
                "purpose": _purpose_of(label_sets, cfg.label_prefix),
                "research_project": _research_project_of(
                    label_sets, cfg.label_prefix),
                "gpu_count": gpu, "gpu_model": gpu_model,
                "image": _images_of(pod_spec),
                "cpu_request": cpu, "mem_request_gb": mem_gb,
                "node": node,
                "created_at": pod.get("metadata", {}).get("creationTimestamp"),
                "started_at": pod.get("status", {}).get("startTime"),
                "completed_at": _pod_completion_time(pod),
                "phase": phase,
            })

        _snapshot_quota(cfg, conn, ts, use_mock, mock_data)

        deleted = _mark_deleted(conn, cfg, current_uids)
        healed = _reattribute_unknown(conn, cfg, name_map)

        samples = 0
        if cfg.sample_gpu_util and not use_mock:
            for pod, account, wl_uid in gpu_pods_to_sample:
                samples += _sample_pod_gpus(cfg, pod, account, ts, conn,
                                            workload_uid=wl_uid)

        usagedb.add_collect_run(conn, ts, cfg.project, True,
                                len(pods), len(jobs),
                                f"util_samples={samples} healed={healed} "
                                f"deleted={deleted}")
        conn.commit()
        if verbose:
            print(f"[{ts}] {cfg.project}: {len(jobs)} jobs, "
                  f"{len(pods)} pods, {samples} GPU util samples, "
                  f"{healed} re-attributed, {deleted} marked Deleted")
        return len(jobs), len(pods)
    except Exception as exc:
        conn.rollback()
        usagedb.add_collect_run(conn, ts, cfg.project, False, None, None,
                                f"error: {exc}")
        conn.commit()
        raise
    finally:
        conn.close()
