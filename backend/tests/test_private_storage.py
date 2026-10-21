from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import InvalidCSV


def test_private_object_digest_and_key(settings):
    storage = PrivateStorage(settings)
    organization, dataset = uuid4(), uuid4()
    content = b"synthetic fixture"
    expected = {"Bucket": settings.s3_bucket, "Key": storage.key(organization, dataset)}
    with Stubber(storage.client) as stub:
        stub.add_response(
            "get_object", {"Body": StreamingBody(BytesIO(content), len(content))}, expected
        )
        with storage.read(organization, dataset, len(content), sha256(content).hexdigest()) as file:
            assert file.read() == content
    assert storage.key(uuid4(), dataset) != storage.key(organization, dataset)
    storage.close()


@pytest.mark.parametrize("size,digest", [(1, "a" * 64), (3, "a" * 64), (10, "a" * 64)])
def test_corrupt_object_refused(settings, size, digest):
    storage = PrivateStorage(settings)
    with Stubber(storage.client) as stub:
        stub.add_response("get_object", {"Body": StreamingBody(BytesIO(b"abc"), 3)})
        with pytest.raises(InvalidCSV, match="OBJECT_INTEGRITY_FAILED"):
            with storage.read(uuid4(), uuid4(), size, digest):
                pytest.fail("Corrupt object was exposed")
    storage.close()


@pytest.mark.parametrize("operation", ["get_object", "put_object", "delete_object"])
def test_outages_have_no_provider_details(settings, operation):
    storage = PrivateStorage(settings)
    with Stubber(storage.client) as stub:
        stub.add_client_error(operation, "ServiceUnavailable", "PRIVATE_PROVIDER_MARKER", 503)
        with pytest.raises(StorageUnavailable) as exc:
            if operation == "put_object":
                storage.put(uuid4(), uuid4(), BytesIO(b"abc"), 3)
            elif operation == "delete_object":
                storage.delete(uuid4(), uuid4())
            else:
                with storage.read(uuid4(), uuid4(), 3, "a" * 64):
                    pytest.fail("Unavailable object was exposed")
        assert "PRIVATE_PROVIDER_MARKER" not in str(exc.value)
    storage.close()


def test_missing_object_is_permanent(settings):
    storage = PrivateStorage(settings)
    with Stubber(storage.client) as stub:
        stub.add_client_error("get_object", "NoSuchKey", "private object name", 404)
        with pytest.raises(InvalidCSV, match="OBJECT_MISSING"):
            with storage.read(uuid4(), uuid4(), 3, "a" * 64):
                pytest.fail("Missing object was exposed")
    storage.close()
