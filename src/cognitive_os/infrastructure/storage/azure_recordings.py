from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import base64
import hashlib
import math

from azure.core import MatchConditions
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas,BlobBlock

from cognitive_os.domain.errors import ApplicationError


class AzureRecordingStore:
    block_size = 4 * 1024 * 1024
    def __init__(self, settings):
        secret = settings.azure_storage_connection_string
        if not secret or not secret.get_secret_value().strip():
            raise ApplicationError(503, "Recording storage is not configured")
        connection_string = secret.get_secret_value()
        fields = dict(part.split("=", 1) for part in connection_string.split(";") if "=" in part)
        self.account_key = fields.get("AccountKey")
        if not self.account_key:
            raise ApplicationError(503, "Recording storage requires an account key connection string")
        try:
            self.service = BlobServiceClient.from_connection_string(
                connection_string, connection_timeout=10, read_timeout=30, retry_total=1)
        except ValueError:
            raise ApplicationError(503, "Recording storage configuration is invalid") from None
        self.container = settings.azure_storage_container

    def ensure_private(self):
        properties = self.service.get_container_client(self.container).get_container_properties()
        if properties.get("public_access"):
            raise ApplicationError(503, "Recording container must be private")

    def transfer(self, recording, *, write=False):
        self.ensure_private()
        expiry = datetime.now(UTC) + timedelta(minutes=60)
        snapshot = None if write else recording.blob_snapshot
        token = generate_blob_sas(
            account_name=self.service.account_name, container_name=self.container,
            blob_name=recording.blob_key, account_key=self.account_key,
            permission=BlobSasPermissions(create=write, write=write, read=not write),
            expiry=expiry, start=datetime.now(UTC) - timedelta(minutes=1),
            protocol="https", snapshot=snapshot,
            **({} if write else {"content_disposition": "inline", "content_type": recording.media_type}))
        blob = self.service.get_blob_client(self.container, recording.blob_key, snapshot=snapshot)
        return {"url": blob.url + ("&" if "?" in blob.url else "?") + token,
                "expires_at": expiry, "method": "PUT" if write else "GET",
                "headers": {"x-ms-blob-type": "BlockBlob", "Content-Type": recording.media_type}
                if write else {}}

    def freeze(self, recording):
        self.ensure_private()
        blob = self.service.get_blob_client(self.container, recording.blob_key)
        props = blob.get_blob_properties()
        if props.size != recording.size_bytes or props.blob_type != "BlockBlob":
            raise ApplicationError(409, "Uploaded video size or blob type does not match reservation")
        media_type = (props.content_settings.content_type or "").split(";", 1)[0].lower()
        if media_type != recording.media_type:
            raise ApplicationError(409, "Uploaded video content type does not match reservation")
        # Freeze the exact validated object: a still-valid upload SAS cannot mutate the analyzed snapshot.
        return blob.create_snapshot(etag=props.etag, match_condition=MatchConditions.IfNotModified)["snapshot"]

    def download(self, recording, target):
        blob = self.service.get_blob_client(self.container, recording.blob_key,
                                             snapshot=recording.blob_snapshot)
        if blob.get_blob_properties().size != recording.size_bytes:
            raise ValueError("Recording size changed")
        total = 0
        digest = hashlib.sha256()
        with target.open("wb") as output:
            for chunk in blob.download_blob(max_concurrency=1).chunks():
                total += len(chunk)
                if total > recording.size_bytes:
                    raise ValueError("Recording exceeds reserved size")
                output.write(chunk)
                digest.update(chunk)
        if total != recording.size_bytes:
            raise ValueError("Incomplete recording")
        if recording.content_sha256 and digest.hexdigest() != recording.content_sha256:
            raise ValueError("Recording content hash mismatch")

    def upload_status(self, recording):
        blob = self.service.get_blob_client(
            self.container,
            recording.blob_key,
        )

        try:
            committed, uncommitted = blob.get_block_list(
                block_list_type="all"
            )
        except ResourceNotFoundError:
            committed, uncommitted = [], []

        present = {
            item.id: item.size
            for item in [*committed, *uncommitted]
        }

        blocks = []

        total_blocks = math.ceil(
            recording.size_bytes / self.block_size
        )

        for index in range(total_blocks):
            raw_block_id = (
                f"{recording.id.hex}:{index:08d}"
            )

            encoded_block_id = base64.b64encode(
                raw_block_id.encode()
            ).decode()

            expected = min(
                self.block_size,
                recording.size_bytes
                - index * self.block_size,
            )

            blocks.append({
                "index": index,
                "id": encoded_block_id,
                "raw_id": raw_block_id,
                "size_bytes": expected,
                "uploaded": present.get(raw_block_id) == expected,
            })

        return {
            "recording_id": str(recording.id),
            "block_size_bytes": self.block_size,
            "content_sha256": recording.content_sha256,
            "blocks": blocks,
        }

    def commit_blocks(self, recording):
        if not recording.content_sha256:
            raise ApplicationError(
                409,
                "Resumable uploads require content_sha256 in the reservation"
            )

        status = self.upload_status(recording)

        missing_blocks = [
            block
            for block in status["blocks"]
            if not block["uploaded"]
        ]

        if missing_blocks:
            raise ApplicationError(
                409,
                f"Missing blocks: {[b['id'] for b in missing_blocks]}"
            )

        blob = self.service.get_blob_client(
            self.container,
            recording.blob_key
        )

        block_list = [
            BlobBlock(
                block_id=f"{recording.id.hex}:{block['index']:08d}"
            )
            for block in status["blocks"]
        ]

        blob.commit_block_list(
            block_list,
            content_settings=ContentSettings(
                content_type=recording.media_type
            ),
        )

        return self.freeze(recording)

    def close(self):
        self.service.close()


@contextmanager
def recording_store(settings):
    store = None
    try:
        store = AzureRecordingStore(settings)
        yield store
    except AzureError:
        raise ApplicationError(503, "Recording storage unavailable or upload incomplete") from None
    finally:
        if store is not     None:
            store.close()
