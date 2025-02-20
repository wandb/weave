import pytest

from weave.trace_server.file_storage_uris import (
    AzureFileStorageURI,
    FileStorageURI,
    GCSFileStorageURI,
    S3FileStorageURI,
    URIParseError,
)


@pytest.mark.parametrize(
    "uri,expected_class",
    [
        ("s3://bucket/path", S3FileStorageURI),
        ("gcs://bucket/path", GCSFileStorageURI),
        ("az://account/container/path", AzureFileStorageURI),
    ],
)
def test_parse_uri_str(uri: str, expected_class):
    """Test that URIs are parsed into the correct class type."""
    parsed = FileStorageURI.parse_uri_str(uri)
    assert isinstance(parsed, expected_class)
    assert parsed.to_uri_str() == uri


@pytest.mark.parametrize(
    "uri,expected_attrs",
    [
        (
            "s3://my-bucket/path/to/object",
            {"bucket": "my-bucket", "path": "path/to/object"},
        ),
        (
            "gcs://my-bucket/path/to/object",
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
    ],
)
def test_uri_attributes(uri: str, expected_attrs: dict):
    """Test that parsed URIs have correct attribute values."""
    parsed = FileStorageURI.parse_uri_str(uri)
    for attr, value in expected_attrs.items():
        assert getattr(parsed, attr) == value


@pytest.mark.parametrize(
    "uri",
    [
        "invalid://bucket/path",
        "s3://",
        "s3:///",
        "gcs://",
        "gcs:///",
        "az://account",
        "az://account/",
        "az:///container/path",
    ],
)
def test_invalid_uris(uri: str):
    """Test that invalid URIs raise appropriate errors."""
    with pytest.raises(URIParseError):
        FileStorageURI.parse_uri_str(uri)


def test_with_path():
    """Test modifying URI paths."""
    uri = S3FileStorageURI("bucket", "original/path")
    new_uri = uri.with_path("new/path")

    assert isinstance(new_uri, S3FileStorageURI)
    assert new_uri.bucket == "bucket"
    assert new_uri.path == "new/path"
    assert new_uri.to_uri_str() == "s3://bucket/new/path"


@pytest.mark.parametrize(
    "uri",
    [
        ("s3://bucket/path?query"),
        ("s3://bucket/path#fragment"),
        ("az://account/container/path#fragment"),
    ],
)
def test_uri_with_extra_components(uri: str):
    """Test that URIs with params, query, or fragments are rejected."""
    with pytest.raises(URIParseError):
        FileStorageURI.parse_uri_str(uri)


@pytest.mark.parametrize(
    "storage_class,constructor_args,expected_uri",
    [
        (S3FileStorageURI, ("bucket", ""), "s3://bucket"),
        (S3FileStorageURI, ("bucket", "path"), "s3://bucket/path"),
        (GCSFileStorageURI, ("bucket", ""), "gcs://bucket"),
        (GCSFileStorageURI, ("bucket", "path"), "gcs://bucket/path"),
        (AzureFileStorageURI, ("account", "container", ""), "az://account/container"),
        (
            AzureFileStorageURI,
            ("account", "container", "path"),
            "az://account/container/path",
        ),
    ],
)
def test_empty_paths(storage_class, constructor_args, expected_uri):
    """Test handling of empty paths for all storage types."""
    uri = storage_class(*constructor_args)
    assert uri.to_uri_str() == expected_uri
    # Test round trip
    parsed = FileStorageURI.parse_uri_str(expected_uri)
    assert parsed.to_uri_str() == expected_uri


@pytest.mark.parametrize(
    "storage_class,constructor_args,new_path,expected_uri",
    [
        (
            S3FileStorageURI,
            ("bucket", "old/path"),
            "new/path",
            "s3://bucket/new/path",
        ),
        (
            GCSFileStorageURI,
            ("bucket", "old/path"),
            "new/path",
            "gcs://bucket/new/path",
        ),
        (
            AzureFileStorageURI,
            ("account", "container", "old/path"),
            "new/path",
            "az://account/container/new/path",
        ),
    ],
)
def test_with_path_all_types(storage_class, constructor_args, new_path, expected_uri):
    """Test with_path for all storage types."""
    uri = storage_class(*constructor_args)
    new_uri = uri.with_path(new_path)
    assert new_uri.to_uri_str() == expected_uri
    # Ensure original URI is unchanged
    assert uri.path != new_path


@pytest.mark.parametrize(
    "storage_class,bad_args",
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
    "original_uri",
    [
        "s3://bucket/simple/path",
        "s3://bucket/path/with/many/segments",
        "s3://bucket/path/with/trailing/slash/",
        "gcs://bucket/simple/path",
        "gcs://bucket/path/with/many/segments",
        "gcs://bucket/path/with/trailing/slash/",
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


def test_parse_uri_str_from_subclass():
    """Test parsing URI string directly from a storage class."""
    uri = "s3://bucket/path"
    parsed = S3FileStorageURI.parse_uri_str(uri)
    assert isinstance(parsed, S3FileStorageURI)
    assert parsed.to_uri_str() == uri


def test_azure_container_path_parsing():
    """Test Azure URI parsing edge cases with container and path."""
    # Just container, no path
    uri = "az://account/container"
    parsed = FileStorageURI.parse_uri_str(uri)
    assert parsed.container == "container"
    assert parsed.path == ""

    # Container with path
    uri = "az://account/container/path"
    parsed = FileStorageURI.parse_uri_str(uri)
    assert parsed.container == "container"
    assert parsed.path == "path"
