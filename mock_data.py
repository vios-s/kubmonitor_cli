from datetime import datetime, timedelta, timezone
import random
import string


def _time_ago(now, hours=0, minutes=0):
    dt = now - timedelta(hours=hours, minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_jobs_data(now):
    jobs_data = [
        # Running jobs
        {
            "name": "ml-training-bert-large",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=2),
            "image": "alice/pytorch:2.1",
            "gpu": 2,
        },
        {
            "name": "hyperparameter-tuning-job",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=5, minutes=15),
            "image": "david/optuna:3.4",
            "gpu": 1,
        },
        {
            "name": "image-preprocessing-batch",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, minutes=40),
            "image": "frank/opencv:4.8",
            "gpu": 0,
        },
        {
            "name": "distributed-training-resnet",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=7, minutes=30),
            "image": "bob/horovod:0.28",
            "gpu": 4,
        },
        {
            "name": "feature-extraction-pipeline",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=2, minutes=30),
            "image": "eve/sklearn:1.3",
            "gpu": 0,
        },
        {
            "name": "model-serving-warmup",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, minutes=15),
            "image": "carol/triton:23.10",
            "gpu": 1,
        },
        {
            "name": "batch-prediction-service",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=3),
            "image": "david/tensorflow:2.14",
            "gpu": 2,
        },
        {
            "name": "recommendation-engine-train",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, minutes=30),
            "image": "frank/lightgbm:4.1",
            "gpu": 0,
        },
        {
            "name": "speech-recognition-train",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=3, minutes=45),
            "image": "iris/whisper:large-v3",
            "gpu": 2,
        },
        {
            "name": "time-series-forecasting",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=5),
            "image": "jack/prophet:1.1",
            "gpu": 0,
        },
        {
            "name": "semantic-search-indexing",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=7, minutes=15),
            "image": "leo/elasticsearch:8.11",
            "gpu": 0,
        },
        {
            "name": "document-embedding-job",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=9, minutes=30),
            "image": "nancy/sentence-transformers:2.2",
            "gpu": 1,
        },
        {
            "name": "reinforcement-learning-agent",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=10, minutes=45),
            "image": "peter/stable-baselines3:2.2",
            "gpu": 2,
        },
        {
            "name": "anomaly-detection-pipeline",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=13, minutes=15),
            "image": "rachel/isolation-forest:1.3",
            "gpu": 0,
        },
        {
            "name": "clickstream-analytics",
            "active": 1, "succeeded": 0, "failed": 0,
            "startTime": _time_ago(now, hours=15),
            "image": "tina/flink:1.18",
            "gpu": 0,
        },
        # Completed jobs
        {
            "name": "inference-api-deployment",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=3, minutes=30),
            "completionTime": _time_ago(now, hours=2, minutes=45),
            "image": "charlie/fastapi:0.104",
            "gpu": 1,
        },
        {
            "name": "model-evaluation-suite",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=6, minutes=30),
            "completionTime": _time_ago(now, hours=6),
            "image": "emily/mlflow:2.8",
            "gpu": 0,
        },
        {
            "name": "nlp-sentiment-analysis",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=9),
            "completionTime": _time_ago(now, hours=8, minutes=15),
            "image": "henry/transformers:4.35",
            "gpu": 1,
        },
        {
            "name": "database-backup-export",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=11, minutes=30),
            "completionTime": _time_ago(now, hours=11),
            "image": "ivan/pgdump:16",
            "gpu": 0,
        },
        {
            "name": "log-aggregation-batch",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=13, minutes=30),
            "completionTime": _time_ago(now, hours=12, minutes=38),
            "image": "judy/logstash:8.11",
            "gpu": 0,
        },
        {
            "name": "text-classification-job",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=1, minutes=30),
            "completionTime": _time_ago(now, minutes=48),
            "image": "grace/bert-base:1.0",
            "gpu": 1,
        },
        {
            "name": "object-detection-yolo",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=6, minutes=30),
            "completionTime": _time_ago(now, hours=5, minutes=5),
            "image": "karen/yolov8:2.0",
            "gpu": 2,
        },
        {
            "name": "ab-testing-analysis",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=10, minutes=30),
            "completionTime": _time_ago(now, hours=10, minutes=12),
            "image": "oscar/scipy:1.11",
            "gpu": 0,
        },
        {
            "name": "data-lake-sync",
            "active": 0, "succeeded": 1, "failed": 0,
            "startTime": _time_ago(now, hours=12),
            "completionTime": _time_ago(now, hours=11, minutes=8),
            "image": "quinn/delta-lake:3.0",
            "gpu": 0,
        },
        # Failed jobs
        {
            "name": "data-processing-pipeline",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=4, minutes=30),
            "completionTime": _time_ago(now, hours=4, minutes=15),
            "image": "emily/spark:3.5",
            "gpu": 0,
        },
        {
            "name": "video-encoding-job",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=10, minutes=30),
            "completionTime": _time_ago(now, hours=10, minutes=25),
            "image": "grace/ffmpeg:6.0",
            "gpu": 1,
        },
        {
            "name": "etl-customer-data",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=8, minutes=30),
            "completionTime": _time_ago(now, hours=8, minutes=27),
            "image": "ivan/airflow:2.7",
            "gpu": 0,
        },
        {
            "name": "fraud-detection-model",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=2, minutes=15),
            "completionTime": _time_ago(now, hours=2, minutes=10),
            "image": "henry/catboost:1.2",
            "gpu": 1,
        },
        {
            "name": "graph-neural-network",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=8),
            "completionTime": _time_ago(now, hours=7, minutes=55),
            "image": "maria/pytorch-geometric:2.4",
            "gpu": 2,
        },
        {
            "name": "multilingual-translation",
            "active": 0, "succeeded": 0, "failed": 1,
            "startTime": _time_ago(now, hours=14, minutes=30),
            "completionTime": _time_ago(now, hours=14, minutes=22),
            "image": "steve/marian-mt:3.1",
            "gpu": 1,
        },
    ]

    return jobs_data


def _build_jobs_items(jobs_data):
    jobs_items = []
    for job_info in jobs_data:
        # Build resources with GPU if specified
        resources = {}
        node_selector = {}
        gpu_count = job_info.get("gpu", 0)

        if gpu_count > 0:
            resources = {
                "requests": {
                    "cpu": "20",
                    "memory": "128Gi",
                    "nvidia.com/gpu": str(gpu_count)
                },
                "limits": {
                    "cpu": "20",
                    "memory": "128Gi",
                    "nvidia.com/gpu": str(gpu_count)
                }
            }
            # Assign GPU type based on job requirements (like real jobs do)
            if gpu_count >= 4:
                node_selector = {"nvidia.com/gpu.product": "NVIDIA-H100-80GB-HBM3"}
            elif gpu_count >= 2:
                node_selector = {"nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB"}
            else:
                node_selector = {"nvidia.com/gpu.product": "NVIDIA-A100-SXM4-40GB"}

        pod_spec = {
            "containers": [
                {
                    "image": job_info["image"],
                    "resources": resources
                }
            ]
        }
        if node_selector:
            pod_spec["nodeSelector"] = node_selector

        job = {
            "metadata": {"name": job_info["name"]},
            "status": {
                "active": job_info["active"],
                "succeeded": job_info["succeeded"],
                "failed": job_info["failed"],
                "startTime": job_info["startTime"],
            },
            "spec": {
                "completions": 1,
                "template": {
                    "spec": pod_spec
                }
            }
        }

        if "completionTime" in job_info:
            job["status"]["completionTime"] = job_info["completionTime"]

        jobs_items.append(job)

    return jobs_items


def _generate_pod_suffix():
    # random suffix like "5k9w2"
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))


def _generate_pods_items(jobs_data):
    pods_items = []
    # GPU node assignment based on job GPU requirements
    gpu_nodes = ['gpu-node-01', 'gpu-node-02', 'gpu-node-03']

    for job_info in jobs_data:
        # ~60% get 1 pod, ~30% get 2 pods, ~10% get 3 pods
        rand = random.random()
        num_pods = 1 if rand < 0.60 else 2 if rand < 0.90 else 3

        if job_info["active"] > 0:
            phase = "Running"
        elif job_info["succeeded"] > 0:
            phase = "Succeeded"
        else:
            phase = "Failed"

        # Assign node based on GPU requirements
        gpu_req = job_info.get("gpu", 0)
        if gpu_req > 0:
            # Assign to a GPU node (prefer A100 for larger jobs)
            if gpu_req >= 4:
                node_name = 'gpu-node-01'  # A100
            elif gpu_req >= 2:
                # A100 or V100
                node_name = random.choice(['gpu-node-01', 'gpu-node-03'])
            else:
                node_name = random.choice(gpu_nodes)
        else:
            node_name = f"cpu-node-{random.randint(1, 5):02d}"

        for _ in range(num_pods):
            pods_items.append({
                "metadata": {
                    "name": f"{job_info['name']}-{_generate_pod_suffix()}"
                },
                "spec": {
                    "nodeName": node_name
                },
                "status": {
                    "phase": phase
                }
            })

    return pods_items


def _generate_gpu_info():
    """Generate mock GPU information matching typical HPC cluster."""
    nodes = [
        {'name': 'gpu-node-01', 'gpu_type': 'H100-80GB',
         'gpu_count': 8, 'allocated': 4},
        {'name': 'gpu-node-02', 'gpu_type': 'H100-80GB',
         'gpu_count': 8, 'allocated': 0},
        {'name': 'gpu-node-03', 'gpu_type': 'A100-80GB',
         'gpu_count': 8, 'allocated': 6},
        {'name': 'gpu-node-04', 'gpu_type': 'A100-80GB',
         'gpu_count': 8, 'allocated': 2},
        {'name': 'gpu-node-05', 'gpu_type': 'A100-40GB',
         'gpu_count': 4, 'allocated': 3},
    ]

    node_gpu_map = {
        'gpu-node-01': 'H100-80GB',
        'gpu-node-02': 'H100-80GB',
        'gpu-node-03': 'A100-80GB',
        'gpu-node-04': 'A100-80GB',
        'gpu-node-05': 'A100-40GB',
    }

    # Calculate totals dynamically
    total_gpus = sum(n['gpu_count'] for n in nodes)
    allocated_gpus = sum(n['allocated'] for n in nodes)
    gpu_types = sorted(list(set(n['gpu_type'] for n in nodes)))

    return {
        'nodes': nodes,
        'total_gpus': total_gpus,
        'allocated_gpus': allocated_gpus,
        'gpu_types': gpu_types,
        'node_gpu_map': node_gpu_map
    }


def _generate_mock_logs(tail_lines=100):
    """Generate mock log data."""
    mock_logs = []
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

    # Repeat messages if needed to fill tail_lines
    while len(log_messages) < tail_lines:
        log_messages.extend(log_messages)

    for i, msg in enumerate(log_messages[:tail_lines]):
        timestamp = f"2026-01-21T10:{i:02d}:00Z"
        mock_logs.append(f"{timestamp} {msg}")
    return "\n".join(mock_logs)


def _generate_quota():
    # Helper to calculate expected usage from current jobs/nodes
    # For simplicity in mock, we'll align this with the GPU info
    # GPU: 15 used (from nodes allocated), 36 total
    return {
        "cpu": {
            "used": 48,
            "limit": 96,
            "str": "48 / 96"
        },
        "mem": {
            "used": 256,
            "limit": 512,
            "str": "256Gi / 512Gi"
        },
        "gpu": {
            "used": 15,
            "limit": 36,
            "str": "15 / 36"
        }
    }


def generate_mock_data():
    now = datetime.now(timezone.utc)

    jobs_data = _generate_jobs_data(now)
    jobs_items = _build_jobs_items(jobs_data)
    pods_items = _generate_pods_items(jobs_data)
    gpu_info = _generate_gpu_info()
    mock_logs = _generate_mock_logs(500)

    return {
        "quota": _generate_quota(),
        "jobs": {
            "items": jobs_items
        },
        "pods": {
            "items": pods_items
        },
        "gpu_info": gpu_info,
        "logs": mock_logs,
        "node_gpu_map": gpu_info['node_gpu_map']  # Convenience top-level access
    }
