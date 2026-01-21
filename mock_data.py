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
        if job_info.get("gpu", 0) > 0:
            resources = {
                "requests": {
                    "nvidia.com/gpu": str(job_info["gpu"])
                },
                "limits": {
                    "nvidia.com/gpu": str(job_info["gpu"])
                }
            }
        
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
                    "spec": {
                        "containers": [
                            {
                                "image": job_info["image"],
                                "resources": resources
                            }
                        ]
                    }
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

        for _ in range(num_pods):
            pods_items.append({
                "metadata": {
                    "name": f"{job_info['name']}-{_generate_pod_suffix()}"
                },
                "status": {
                    "phase": phase
                }
            })

    return pods_items


def _generate_quota():
    return {
        "cpu": {
            "used": 8,
            "limit": 16,
            "str": "8 / 16"
        },
        "mem": {
            "used": 32,
            "limit": 64,
            "str": "32Gi / 64Gi"
        },
        "gpu": {
            "used": 2,
            "limit": 4,
            "str": "2 / 4"
        }
    }


def generate_mock_data():
    now = datetime.now(timezone.utc)

    jobs_data = _generate_jobs_data(now)
    jobs_items = _build_jobs_items(jobs_data)
    pods_items = _generate_pods_items(jobs_data)

    return {
        "quota": _generate_quota(),
        "jobs": {
            "items": jobs_items
        },
        "pods": {
            "items": pods_items
        }
    }
