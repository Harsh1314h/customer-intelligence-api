from pathlib import Path
from urllib.parse import urlparse


def sync_artifacts(artifact_uri: str | None, model_dir: Path) -> None:
    if not artifact_uri:
        return

    model_dir.mkdir(parents=True, exist_ok=True)

    if artifact_uri.startswith("gs://"):
        _sync_gcs(artifact_uri, model_dir)
        return

    if artifact_uri.startswith("s3://"):
        _sync_s3(artifact_uri, model_dir)
        return

    source = Path(artifact_uri)
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Model artifact directory not found: {artifact_uri}")

    for artifact_path in source.iterdir():
        if artifact_path.is_file():
            (model_dir / artifact_path.name).write_bytes(artifact_path.read_bytes())


def _sync_gcs(artifact_uri: str, model_dir: Path) -> None:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("Install google-cloud-storage to load gs:// model artifacts.") from exc

    parsed = urlparse(artifact_uri)
    bucket_name = parsed.netloc
    prefix = parsed.path.lstrip("/")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for blob in client.list_blobs(bucket, prefix=prefix):
        if blob.name.endswith("/"):
            continue
        destination = model_dir / Path(blob.name).name
        blob.download_to_filename(destination)


def _sync_s3(artifact_uri: str, model_dir: Path) -> None:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Install boto3 to load s3:// model artifacts.") from exc

    parsed = urlparse(artifact_uri)
    bucket_name = parsed.netloc
    prefix = parsed.path.lstrip("/")

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            destination = model_dir / Path(key).name
            client.download_file(bucket_name, key, str(destination))
