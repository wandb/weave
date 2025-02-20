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
        scheme (str): The URI scheme (e.g., 's3', 'gcs', 'az')
        path (str): The path component of the URI
    """

    scheme: str
    path: str

    def __str__(self) -> str:
        """Return the string representation of the URI.
        
        Returns:
            str: The complete URI as a string
        """
        return self.to_uri_str()

    def __repr__(self) -> str:
        """Return a detailed string representation of the URI.
        
        Returns:
            str: A detailed representation including the class name and URI
        """
        return f"{self.__class__.__name__}('{self.to_uri_str()}')"

    def __eq__(self, other: object) -> bool:
        """Compare two URIs for equality.
        
        URIs are considered equal if they resolve to the same canonical form,
        regardless of trailing slashes or other normalizable differences.
        
        Args:
            other: Another object to compare with
            
        Returns:
            bool: True if the URIs are equal, False otherwise
        """
        if not isinstance(other, FileStorageURI):
            return NotImplemented
        return self.to_uri_str() == other.to_uri_str()

    def __hash__(self) -> int:
        """Generate a hash value for the URI.
        
        The hash is based on the canonical string form of the URI to ensure
        consistent behavior with __eq__.
        
        Returns:
            int: Hash value of the URI
        """
        return hash(self.to_uri_str())

    @classmethod
    def from_parse_result(cls, parsed_uri: ParseResult) -> "FileStorageURI":
        """Create a storage URI instance from a parsed URI.
        
        Args:
            parsed_uri: A ParseResult instance from urlparse
            
        Returns:
            A new instance of the appropriate FileStorageURI subclass
            
        Raises:
            URIParseError: If the URI is invalid for the storage type
        """
        raise NotImplementedError("Subclasses must implement this method")

    def to_parse_result(self) -> ParseResult:
        """Convert the storage URI to a ParseResult.
        
        Returns:
            ParseResult containing the components of the URI
        """
        raise NotImplementedError("Subclasses must implement this method")


    def with_path(self, path: str) -> "FileStorageURI":
        copied = self.parse_uri_str(self.to_uri_str())
        copied.path = path
        return copied


    def to_uri_str(self) -> str:
        return self.to_parse_result().geturl()

    @classmethod
    def parse_uri_str(cls, uri: str) -> "FileStorageURI":
        parsed_uri = urlparse(uri)
        scheme = parsed_uri.scheme

        # Get all subclasses of FileStorageURI
        candidate_classes = cls.__subclasses__()
        for candidate_class in candidate_classes:
            if candidate_class.scheme == scheme:
                return candidate_class.from_parse_result(parsed_uri)
        raise URIParseError(f"No matching scheme for file storage URI: {uri}")


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
        self.path = path.strip("/")

    @classmethod
    def from_parse_result(cls, parsed_uri: ParseResult) -> "S3FileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(f"Incorrect scheme for S3 file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.params != "":
            raise URIParseError(f"Invalid params for S3 file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.query != "":
            raise URIParseError(f"Invalid query for S3 file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.fragment != "":
            raise URIParseError(f"Invalid fragment for S3 file storage URI: {parsed_uri.geturl()}")
        return cls(parsed_uri.netloc, parsed_uri.path)

    def to_parse_result(self) -> ParseResult:
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
    
    Format: gcs://<bucket>/<path>
    Example: gcs://my-bucket/path/to/object
    
    Attributes:
        scheme (str): Always 'gcs'
        bucket (str): The GCS bucket name
        path (str): The object path within the bucket
    """

    scheme = "gcs"
    bucket: str

    def __init__(self, bucket: str, path: str):
        self.bucket = bucket.strip("/")
        self.path = path.strip("/")

    @classmethod
    def from_parse_result(cls, parsed_uri: ParseResult) -> "GCSFileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(f"Incorrect scheme for GCS file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.params != "":
            raise URIParseError(f"Invalid params for GCS file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.query != "":
            raise URIParseError(f"Invalid query for GCS file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.fragment != "":
            raise URIParseError(f"Invalid fragment for GCS file storage URI: {parsed_uri.geturl()}")
        return cls(parsed_uri.netloc, parsed_uri.path)

    def to_parse_result(self) -> ParseResult:
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
        self.container = container.strip("/")
        self.path = path.strip("/")

    @classmethod
    def from_parse_result(cls, parsed_uri: ParseResult) -> "AzureFileStorageURI":
        if parsed_uri.scheme != cls.scheme:
            raise URIParseError(f"Incorrect scheme for Azure file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.params != "":
            raise URIParseError(f"Invalid params for Azure file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.query != "":
            raise URIParseError(f"Invalid query for Azure file storage URI: {parsed_uri.geturl()}")
        if parsed_uri.fragment != "":
            raise URIParseError(f"Invalid fragment for Azure file storage URI: {parsed_uri.geturl()}")

        # Split the path into container and path
        path = parsed_uri.path.strip("/")
        if path == '':
            raise URIParseError(f"Invalid path for Azure file storage URI - must include container name: {parsed_uri.geturl()}")
        path_parts = path.split("/", 1)
        account = parsed_uri.netloc
        container = path_parts[0]
        path = path_parts[1] if len(path_parts) > 1 else ""
        return cls(account, container, path)

    def to_parse_result(self) -> ParseResult:
        return ParseResult(
            scheme=self.scheme,
            netloc=self.account,
            path="/".join([self.container, self.path]),
            params="",
            query="",
            fragment="",
        )
