import uuid
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_s3_client():
    # boto3 is synchronous; every call through this client is wrapped in
    # run_in_threadpool below so it never blocks the event loop.
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


@lru_cache
def get_s3_public_client():
    # Used ONLY for signing presigned GET URLs. A SigV4 signature covers the
    # host, so a URL signed against the internal Docker hostname would fail
    # to validate if simply string-rewritten to a browser-reachable host —
    # this client signs against the public endpoint from the start instead.
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_public_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


async def ensure_bucket_exists() -> None:
    client = get_s3_client()

    def _ensure() -> None:
        try:
            client.head_bucket(Bucket=settings.s3_bucket_name)
        except ClientError:
            client.create_bucket(Bucket=settings.s3_bucket_name)

    await run_in_threadpool(_ensure)


def object_key_for(user_id: uuid.UUID, extension: str) -> str:
    """Unguessable, per-user key — a fresh random uuid, not derived from any
    sequential or otherwise-predictable id."""
    return f"receipts/{user_id}/{uuid.uuid4()}.{extension.lstrip('.')}"


async def put_object(key: str, data: bytes, content_type: str) -> None:
    client = get_s3_client()
    await run_in_threadpool(
        client.put_object,
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def get_object(key: str) -> bytes:
    """Reads an object's bytes back — used by the async worker to fetch the
    original file it needs to render/extract, since the job payload carries
    only the object key, never the file bytes themselves."""
    client = get_s3_client()

    def _get() -> bytes:
        response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
        return response["Body"].read()

    return await run_in_threadpool(_get)


async def presigned_get_url(key: str, expires_in: int = 300) -> str:
    """Short-lived signed URL, browser-reachable. Callers are responsible for
    verifying the requester owns the object (in practice: only ever called
    with a key read back from a row that was already fetched through RLS)."""
    client = get_s3_public_client()
    return await run_in_threadpool(
        client.generate_presigned_url,
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )


async def delete_object(key: str) -> None:
    client = get_s3_client()
    await run_in_threadpool(client.delete_object, Bucket=settings.s3_bucket_name, Key=key)
