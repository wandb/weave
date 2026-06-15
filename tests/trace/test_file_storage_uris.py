import pytest

from weave.trace_server.file_storage_uris import (
    AzureFileStorageURI,
    FileStorageURI,
    GCSFileStorageURI,
    S3FileStorageURI,
    URIParseError,
)


@pytest.mark.parametrize(
    ("uri", "expected_class"),
    [
        ("s3://bucket/path", S3FileStorageURI),
        ("gs://bucket/path", GCSFileStorageURI),
        ("az://account/container/path", AzureFileStorageURI),
    ],
)
def test_parse_uri_str(uri: str, expected_class):
    """Test that URIs are parsed into the correct class type and round-trip."""
    parsed = FileStorageURI.parse_uri_str(uri)
    assert isinstance(parsed, expected_class)
    assert parsed.to_uri_str() == uri


def test_parse_uri_str_from_subclass():
    """Test parsing URI string directly from a storage class."""
    uri = "s3://bucket/path"
    parsed = S3FileStorageURI.parse_uri_str(uri)
    assert isinstance(parsed, S3FileStorageURI)
    assert parsed.to_uri_str() == uri


@pytest.mark.parametrize(
    "uri",
    [
        "invalid://blah",
        "invalid://blah/blah",
        "invalid://bucket/path",
        "s3://",
        "s3:///",
        "s3:///path",
        "gs://",
        "gs:///",
        "gs:///path",
        "az://",
        "az://container",
        "az:///container",
        "az://account",
        "az://account/",
        "az:///container/path",
        "s3://bucket/path?query",
        "s3://bucket/path#fragment",
        "az://account/container/path#fragment",
    ],
)
def test_parse_uri_str_failure(uri: str):
    """Malformed schemes, missing components, and query/fragment extras all raise."""
    with pytest.raises(URIParseError):
        FileStorageURI.parse_uri_str(uri)


@pytest.mark.parametrize(
    ("uri", "expected_attrs"),
    [
        (
            "s3://my-bucket/path/to/object",
            {"bucket": "my-bucket", "path": "path/to/object"},
        ),
        (
            "gs://my-bucket/path/to/object",
            {"bucket": "my-bucket", "path": "path/to/object"},
        ),
        (
            "az://myaccount/mycontainer/path/to/blob",
            {
                "account": "myaccount",
                "container": "mycontainer",
                "path": "path/to/blob",
            },
        ),
        (
            "az://account/container",
            {"account": "account", "container": "container", "path": ""},
        ),
        (
            "az://account/container/path",
            {"account": "account", "container": "container", "path": "path"},
        ),
    ],
)
def test_uri_attributes(uri: str, expected_attrs: dict):
    """Test that parsed URIs have correct attribute values, including no-path Azure."""
    parsed = FileStorageURI.parse_uri_str(uri)
    for attr, value in expected_attrs.items():
        assert getattr(parsed, attr) == value


@pytest.mark.parametrize(
    ("storage_class", "constructor_args", "expected_uri"),
    [
        (S3FileStorageURI, ("bucket", ""), "s3://bucket"),
        (S3FileStorageURI, ("bucket", "path"), "s3://bucket/path"),
        (GCSFileStorageURI, ("bucket", ""), "gs://bucket"),
        (GCSFileStorageURI, ("bucket", "path"), "gs://bucket/path"),
        (AzureFileStorageURI, ("account", "container", ""), "az://account/container"),
        (
            AzureFileStorageURI,
            ("account", "container", "path"),
            "az://account/container/path",
        ),
    ],
)
def test_empty_paths(storage_class, constructor_args, expected_uri):
    """Test handling of empty paths for all storage types, with round trip."""
    uri = storage_class(*constructor_args)
    assert uri.to_uri_str() == expected_uri
    parsed = FileStorageURI.parse_uri_str(expected_uri)
    assert parsed.to_uri_str() == expected_uri


@pytest.mark.parametrize(
    ("storage_class", "constructor_args", "new_path", "expected_class", "expected_uri"),
    [
        (
            S3FileStorageURI,
            ("bucket", "old/path"),
            "new/path",
            S3FileStorageURI,
            "s3://bucket/new/path",
        ),
        (
            GCSFileStorageURI,
            ("bucket", "old/path"),
            "new/path",
            GCSFileStorageURI,
            "gs://bucket/new/path",
        ),
        (
            AzureFileStorageURI,
            ("account", "container", "old/path"),
            "new/path",
            AzureFileStorageURI,
            "az://account/container/new/path",
        ),
    ],
)
def test_with_path_all_types(
    storage_class, constructor_args, new_path, expected_class, expected_uri
):
    """Test with_path returns the right subclass and leaves the original unchanged."""
    uri = storage_class(*constructor_args)
    new_uri = uri.with_path(new_path)
    assert isinstance(new_uri, expected_class)
    assert new_uri.path == new_path
    assert new_uri.to_uri_str() == expected_uri
    assert uri.path != new_path


@pytest.mark.parametrize(
    ("storage_class", "bad_args"),
    [
        (S3FileStorageURI, ("", "path")),  # Empty bucket
        (GCSFileStorageURI, ("", "path")),  # Empty bucket
        (AzureFileStorageURI, ("", "container", "path")),  # Empty account
        (AzureFileStorageURI, ("account", "", "path")),  # Empty container
    ],
)
def test_empty_required_components(storage_class, bad_args):
    """Test that empty required components (bucket, account, container) raise errors."""
    with pytest.raises(URIParseError):
        storage_class(*bad_args)


@pytest.mark.parametrize(
    ("original_uri"),
    [
        "s3://bucket/simple/path",
        "s3://bucket/path/with/many/segments",
        "s3://bucket/path/with/trailing/slash/",
        "gs://bucket/simple/path",
        "gs://bucket/path/with/many/segments",
        "gs://bucket/path/with/trailing/slash/",
        "az://account/container/simple/path",
        "az://account/container/path/with/many/segments",
        "az://account/container/path/with/trailing/slash/",
    ],
)
def test_roundtrip_all_types(original_uri):
    """Test round-trip parsing and serialization for all URI types with various paths."""
    parsed = FileStorageURI.parse_uri_str(original_uri)
    regenerated = parsed.to_uri_str()
    # Parse again to ensure stability
    reparsed = FileStorageURI.parse_uri_str(regenerated)

    assert reparsed.to_uri_str() == regenerated
    # The regenerated URI should be normalized
    assert not regenerated.endswith("/")
    assert "//" not in regenerated[5:]  # Skip scheme://
