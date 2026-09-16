from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.storage.azure_recordings import AzureRecordingStore


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING",
                       "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=ZmFrZS1rZXk=;EndpointSuffix=core.windows.net")
    service = MagicMock()
    service.account_name = "testaccount"
    service.get_container_client.return_value.get_container_properties.return_value = {"public_access": None}
    blob = MagicMock()
    def get_blob(container, name, snapshot=None):
        blob.url = f"https://testaccount.blob.core.windows.net/{container}/{name}" + (f"?snapshot={snapshot}" if snapshot else "")
        return blob
    service.get_blob_client.side_effect = get_blob
    monkeypatch.setattr("cognitive_os.infrastructure.storage.azure_recordings.BlobServiceClient.from_connection_string",
                        lambda *args, **kwargs: service)
    store = AzureRecordingStore(Settings(_env_file=None))
    recording = SimpleNamespace(id=uuid4(), blob_key="org/session/video.mp4", blob_snapshot="snapshot1",
                                 size_bytes=100, media_type="video/mp4", content_sha256="a" * 64)
    return store, recording, blob, service


def test_sas_is_scoped_and_snapshot_read_only(azure):
    store, recording, blob, service = azure
    upload = store.transfer(recording, write=True)
    permissions = parse_qs(urlparse(upload["url"]).query)["sp"][0]
    assert "w" in permissions and "r" not in permissions and "d" not in permissions
    playback = store.transfer(recording)
    query = parse_qs(urlparse(playback["url"]).query)
    assert query["sp"] == ["r"] and query["snapshot"] == ["snapshot1"]
    assert query["rscd"] == ["inline"] and query["rsct"] == ["video/mp4"]
    assert playback["headers"] == {} and playback["method"] == "GET"
    service.get_container_client.return_value.get_container_properties.return_value = {"public_access": "blob"}
    with pytest.raises(ApplicationError):
        store.transfer(recording)


def test_freeze_checks_size_and_etag(azure):
    store, recording, blob, _ = azure
    blob.get_blob_properties.return_value = SimpleNamespace(size=99, blob_type="BlockBlob", etag="e1",
                                                           content_settings=SimpleNamespace(content_type="video/mp4"))
    with pytest.raises(ApplicationError):
        store.freeze(recording)
    blob.get_blob_properties.return_value.size = 100
    blob.create_snapshot.return_value = {"snapshot": "frozen"}
    assert store.freeze(recording) == "frozen"
    assert blob.create_snapshot.call_args.kwargs["etag"] == "e1"


def test_resumable_blocks_require_complete_manifest(azure):
    store, recording, blob, _ = azure
    blob.get_block_list.return_value = ([], [])
    status = store.upload_status(recording)
    assert status["blocks"][0]["uploaded"] is False
    with pytest.raises(ApplicationError):
        store.commit_blocks(recording)
    expected = status["blocks"][0]
    blob.get_block_list.return_value = ([], [SimpleNamespace(id=expected["id"], size=100)])
    assert store.upload_status(recording)["blocks"][0]["uploaded"] is True
