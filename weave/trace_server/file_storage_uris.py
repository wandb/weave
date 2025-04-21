"""
This module contains the classes and utilities for working with file storage URIs.

A URI has specific form and structure and therefore we need to parse and validate them.
Each storage type (S3, GCS, Azure) has its own URI format and validation rules.
"""

from urllib.parse import ParseResult, urlparse


class URIParseError(ValueError):
    """Raised when a storage URI cannot be parsed or is invalid."""

    pass


class FileStorageURI:
    """Base class for all file storage URIs.

    This class provides the interface and common functionality for handling
    different types of storage URIs (S3, GCS, Azure). Each subclass implements
    specific parsing and validation rules for its storage type.

    Attributes:
        scheme (str): The URI scheme (e.g., 's3', 'gs', 'az')
        path (str): The path component of the URI
    """

    scheme: str
    path: str

    @classmethod
    def _from_parse_result(cls, parsed_uri: ParseResult) -> "FileStorageURI":
        """Create a storage URI instance from a parsed URI.

        Args:
            parsed_uri: A ParseResult instance from urlparse

        Returns:
            A new instance of the appropriate FileStorageURI subclass

        Raises:
            URIParseError: If the URI is invalid for the storage type
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _to_parse_result(self) -> ParseResult:
        """Convert the storage URI to a ParseResult.

        Returns:
            ParseResult containing the components of the URI
        """
        raise NotImplementedError("Subclasses must implement this method")

    def has_path(self) -> bool:
        return self.path != ""

    def with_path(self, path: str) -> "FileStorageURI":
        copied = self.parse_uri_str(self.to_uri_str())
        copied.path = path
        return copied

    def to_uri_str(self) -> str:
        return self._to_parse_result().geturl()

    @classmethod
    def parse_uri_str(cls, uri: str) -> "FileStorageURI":
        parsed_uri = urlparse(uri)
        scheme = parsed_uri.scheme

        # Get all subclasses of FileStorageURI
        candidate_classes = cls.__subclasses__()
        if cls != FileStorageURI:
            candidate_classes.append(cls)
        for candidate_class in candidate_classes:
            if candidate_class.scheme == scheme:
                return candidate_class._from_parse_result(parsed_uri)
        raise URIParseError(f"No matching scheme for file storage URI: {uri}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_uri_str()})"


class S3FileStorageURI(FileStorageURI):
    """Amazon S3 storage URI handler.

    Format: s3://<bucket>/<path>
    Example: s3://my-bucket/path/to/object

    Attributes:
        scheme (str): Always 's3'
        bucket (str): The S3 bucket name
        path (str): The object key/path within the bucket
    """

    scheme = "s3"
    bucket: str

    def __init__(self, bucket: str, path: str):
        self.bucket = bucket.strip("/")
        if self.bucket == "":
            raise URIParseError("Bucket cannot be empty")
        self.path = path.strip("/")

    @classmethod
    def _from_parse_result(cls, parsed_uri: ParseResult) -> "S3FileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(
                f"Incorrect scheme for S3 file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.params != "":
            raise URIParseError(
                f"Invalid params for S3 file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.query != "":
            raise URIParseError(
                f"Invalid query for S3 file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.fragment != "":
            raise URIParseError(
                f"Invalid fragment for S3 file storage URI: {parsed_uri.geturl()}"
            )
        return cls(parsed_uri.netloc, parsed_uri.path)

    def _to_parse_result(self) -> ParseResult:
        return ParseResult(
            scheme=self.scheme,
            netloc=self.bucket,
            path=self.path,
            params="",
            query="",
            fragment="",
        )


class GCSFileStorageURI(FileStorageURI):
    """Google Cloud Storage URI handler.

    Format: gs://<bucket>/<path>
    Example: gs://my-bucket/path/to/object

    Attributes:
        scheme (str): Always 'gs'
        bucket (str): The GCS bucket name
        path (str): The object path within the bucket
    """

    scheme = "gs"
    bucket: str

    def __init__(self, bucket: str, path: str):
        self.bucket = bucket.strip("/")
        if self.bucket == "":
            raise URIParseError("Bucket cannot be empty")
        self.path = path.strip("/")

    @classmethod
    def _from_parse_result(cls, parsed_uri: ParseResult) -> "GCSFileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(
                f"Incorrect scheme for GCS file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.params != "":
            raise URIParseError(
                f"Invalid params for GCS file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.query != "":
            raise URIParseError(
                f"Invalid query for GCS file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.fragment != "":
            raise URIParseError(
                f"Invalid fragment for GCS file storage URI: {parsed_uri.geturl()}"
            )
        return cls(parsed_uri.netloc, parsed_uri.path)

    def _to_parse_result(self) -> ParseResult:
        return ParseResult(
            scheme=self.scheme,
            netloc=self.bucket,
            path=self.path,
            params="",
            query="",
            fragment="",
        )


class AzureFileStorageURI(FileStorageURI):
    """Azure Blob Storage URI handler.

    Format: az://<account>/<container>/<path>
    Example: az://myaccount/mycontainer/path/to/blob

    The account is stored in the netloc component, while container and path
    are stored in the path component of the URI.
    """

    scheme = "az"
    account: str
    container: str

    def __init__(self, account: str, container: str, path: str):
        self.account = account.strip("/")
        if self.account == "":
            raise URIParseError("Account cannot be empty")
        self.container = container.strip("/")
        if self.container == "":
            raise URIParseError("Container cannot be empty")
        self.path = path.strip("/")

    @classmethod
    def _from_parse_result(cls, parsed_uri: ParseResult) -> "AzureFileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(
                f"Incorrect scheme for Azure file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.params != "":
            raise URIParseError(
                f"Invalid params for Azure file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.query != "":
            raise URIParseError(
                f"Invalid query for Azure file storage URI: {parsed_uri.geturl()}"
            )
        if parsed_uri.fragment != "":
            raise URIParseError(
                f"Invalid fragment for Azure file storage URI: {parsed_uri.geturl()}"
            )

        # Split the path into container and path
        path = parsed_uri.path.strip("/")
        if path == "":
            raise URIParseError(
                f"Invalid path for Azure file storage URI - must include container name: {parsed_uri.geturl()}"
            )
        path_parts = path.split("/", 1)
        account = parsed_uri.netloc
        container = path_parts[0]
        path = path_parts[1] if len(path_parts) > 1 else ""
        return cls(account, container, path)

    def _to_parse_result(self) -> ParseResult:
        path = self.container
        if self.path != "":
            path += "/" + self.path
        return ParseResult(
            scheme=self.scheme,
            netloc=self.account,
            path=path,
            params="",
            query="",
            fragment="",
        )
