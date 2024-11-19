import os
import re
from detect_secrets.plugins.base import RegexBasedDetector


class AdafruitKeyDetector(RegexBasedDetector):
    """Scans for Adafruit keys."""

    @property
    def secret_type(self) -> str:
        return "Adafruit API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:adafruit)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9_-]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class AdobeSecretDetector(RegexBasedDetector):
    """Scans for Adobe client keys."""

    @property
    def secret_type(self) -> str:
        return "Adobe Client Keys"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Adobe Client ID (OAuth Web)
            re.compile(
                r"""(?i)(?:adobe)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Adobe Client Secret
            re.compile(r"(?i)\b((p8e-)[a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"),
        ]


class AgeSecretKeyDetector(RegexBasedDetector):
    """Scans for Age secret keys."""

    @property
    def secret_type(self) -> str:
        return "Age Secret Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(r"""AGE-SECRET-KEY-1[QPZRY9X8GF2TVDW0S3JN54KHCE6MUA7L]{58}"""),
        ]


class AirtableApiKeyDetector(RegexBasedDetector):
    """Scans for Airtable API keys."""

    @property
    def secret_type(self) -> str:
        return "Airtable API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:airtable)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{17})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class AlgoliaApiKeyDetector(RegexBasedDetector):
    """Scans for Algolia API keys."""

    @property
    def secret_type(self) -> str:
        return "Algolia API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(r"""(?i)\b((LTAI)[a-z0-9]{20})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
        ]


class AlibabaSecretDetector(RegexBasedDetector):
    """Scans for Alibaba AccessKey IDs and Secret Keys."""

    @property
    def secret_type(self) -> str:
        return "Alibaba Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Alibaba AccessKey ID
            re.compile(r"""(?i)\b((LTAI)[a-z0-9]{20})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
            # For Alibaba Secret Key
            re.compile(
                r"""(?i)(?:alibaba)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{30})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class AsanaSecretDetector(RegexBasedDetector):
    """Scans for Asana Client IDs and Client Secrets."""

    @property
    def secret_type(self) -> str:
        return "Asana Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Asana Client ID
            re.compile(
                r"""(?i)(?:asana)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9]{16})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # For Asana Client Secret
            re.compile(
                r"""(?i)(?:asana)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class AtlassianApiTokenDetector(RegexBasedDetector):
    """Scans for Atlassian API tokens."""

    @property
    def secret_type(self) -> str:
        return "Atlassian API token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Atlassian API token
            re.compile(
                r"""(?i)(?:atlassian|confluence|jira)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{24})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class AuthressAccessKeyDetector(RegexBasedDetector):
    """Scans for Authress Service Client Access Keys."""

    @property
    def secret_type(self) -> str:
        return "Authress Service Client Access Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Authress Service Client Access Key
            re.compile(
                r"""(?i)\b((?:sc|ext|scauth|authress)_[a-z0-9]{5,30}\.[a-z0-9]{4,6}\.acc[_-][a-z0-9-]{10,32}\.[a-z0-9+/_=-]{30,120})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class BeamerApiTokenDetector(RegexBasedDetector):
    """Scans for Beamer API tokens."""

    @property
    def secret_type(self) -> str:
        return "Beamer API token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Beamer API token
            re.compile(
                r"""(?i)(?:beamer)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(b_[a-z0-9=_\-]{44})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class BitbucketDetector(RegexBasedDetector):
    """Scans for Bitbucket Client ID and Client Secret."""

    @property
    def secret_type(self) -> str:
        return "Bitbucket Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Bitbucket Client ID
            re.compile(
                r"""(?i)(?:bitbucket)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # For Bitbucket Client Secret
            re.compile(
                r"""(?i)(?:bitbucket)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class BittrexDetector(RegexBasedDetector):
    """Scans for Bittrex Access Key and Secret Key."""

    @property
    def secret_type(self) -> str:
        return "Bittrex Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Bittrex Access Key
            re.compile(
                r"""(?i)(?:bittrex)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # For Bittrex Secret Key
            re.compile(
                r"""(?i)(?:bittrex)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class ClojarsApiTokenDetector(RegexBasedDetector):
    """Scans for Clojars API tokens."""

    @property
    def secret_type(self) -> str:
        return "Clojars API token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Clojars API token
            re.compile(r"(?i)(CLOJARS_)[a-z0-9]{60}"),
        ]


class CodecovAccessTokenDetector(RegexBasedDetector):
    """Scans for Codecov Access Token."""

    @property
    def secret_type(self) -> str:
        return "Codecov Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Codecov Access Token
            re.compile(
                r"""(?i)(?:codecov)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class CoinbaseAccessTokenDetector(RegexBasedDetector):
    """Scans for Coinbase Access Token."""

    @property
    def secret_type(self) -> str:
        return "Coinbase Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Coinbase Access Token
            re.compile(
                r"""(?i)(?:coinbase)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9_-]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class ConfluentDetector(RegexBasedDetector):
    """Scans for Confluent Access Token and Confluent Secret Key."""

    @property
    def secret_type(self) -> str:
        return "Confluent Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # For Confluent Access Token
            re.compile(
                r"""(?i)(?:confluent)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{16})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # For Confluent Secret Key
            re.compile(
                r"""(?i)(?:confluent)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class ContentfulApiTokenDetector(RegexBasedDetector):
    """Scans for Contentful delivery API token."""

    @property
    def secret_type(self) -> str:
        return "Contentful API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:contentful)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{43})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DatabricksApiTokenDetector(RegexBasedDetector):
    """Scans for Databricks API token."""

    @property
    def secret_type(self) -> str:
        return "Databricks API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(r"""(?i)\b(dapi[a-h0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
        ]


class DatadogAccessTokenDetector(RegexBasedDetector):
    """Scans for Datadog Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Datadog Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:datadog)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DefinedNetworkingApiTokenDetector(RegexBasedDetector):
    """Scans for Defined Networking API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Defined Networking API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:dnkey)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(dnkey-[a-z0-9=_\-]{26}-[a-z0-9=_\-]{52})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DigitaloceanDetector(RegexBasedDetector):
    """Scans for various DigitalOcean Tokens."""

    @property
    def secret_type(self) -> str:
        return "DigitalOcean Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # OAuth Access Token
            re.compile(r"""(?i)\b(doo_v1_[a-f0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
            # Personal Access Token
            re.compile(r"""(?i)\b(dop_v1_[a-f0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
            # OAuth Refresh Token
            re.compile(r"""(?i)\b(dor_v1_[a-f0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""),
        ]


class DiscordDetector(RegexBasedDetector):
    """Scans for various Discord Client Tokens."""

    @property
    def secret_type(self) -> str:
        return "Discord Client Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Discord API key
            re.compile(
                r"""(?i)(?:discord)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Discord client ID
            re.compile(
                r"""(?i)(?:discord)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9]{18})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Discord client secret
            re.compile(
                r"""(?i)(?:discord)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DopplerApiTokenDetector(RegexBasedDetector):
    """Scans for Doppler API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Doppler API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Doppler API token
            re.compile(r"""(?i)dp\.pt\.[a-z0-9]{43}"""),
        ]


class DroneciAccessTokenDetector(RegexBasedDetector):
    """Scans for Droneci Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Droneci Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Droneci Access Token
            re.compile(
                r"""(?i)(?:droneci)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DropboxDetector(RegexBasedDetector):
    """Scans for various Dropbox Tokens."""

    @property
    def secret_type(self) -> str:
        return "Dropbox Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Dropbox API secret
            re.compile(
                r"""(?i)(?:dropbox)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{15})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Dropbox long-lived API token
            re.compile(
                r"""(?i)(?:dropbox)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{11}(AAAAAAAAAA)[a-z0-9\-_=]{43})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Dropbox short-lived API token
            re.compile(
                r"""(?i)(?:dropbox)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(sl\.[a-z0-9\-=_]{135})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class DuffelApiTokenDetector(RegexBasedDetector):
    """Scans for Duffel API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Duffel API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Duffel API Token
            re.compile(r"""(?i)duffel_(test|live)_[a-z0-9_\-=]{43}"""),
        ]


class DynatraceApiTokenDetector(RegexBasedDetector):
    """Scans for Dynatrace API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Dynatrace API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Dynatrace API Token
            re.compile(r"""(?i)dt0c01\.[a-z0-9]{24}\.[a-z0-9]{64}"""),
        ]


class EasyPostDetector(RegexBasedDetector):
    """Scans for various EasyPost Tokens."""

    @property
    def secret_type(self) -> str:
        return "EasyPost Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # EasyPost API token
            re.compile(r"""(?i)\bEZAK[a-z0-9]{54}"""),
            # EasyPost test API token
            re.compile(r"""(?i)\bEZTK[a-z0-9]{54}"""),
        ]


class EtsyAccessTokenDetector(RegexBasedDetector):
    """Scans for Etsy Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Etsy Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Etsy Access Token
            re.compile(
                r"""(?i)(?:etsy)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{24})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FacebookAccessTokenDetector(RegexBasedDetector):
    """Scans for Facebook Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Facebook Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Facebook Access Token
            re.compile(
                r"""(?i)(?:facebook)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FastlyApiKeyDetector(RegexBasedDetector):
    """Scans for Fastly API keys."""

    @property
    def secret_type(self) -> str:
        return "Fastly API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Fastly API key
            re.compile(
                r"""(?i)(?:fastly)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FinicityDetector(RegexBasedDetector):
    """Scans for Finicity API tokens and Client Secrets."""

    @property
    def secret_type(self) -> str:
        return "Finicity Credentials"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Finicity API token
            re.compile(
                r"""(?i)(?:finicity)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Finicity Client Secret
            re.compile(
                r"""(?i)(?:finicity)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{20})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FinnhubAccessTokenDetector(RegexBasedDetector):
    """Scans for Finnhub Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Finnhub Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Finnhub Access Token
            re.compile(
                r"""(?i)(?:finnhub)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{20})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FlickrAccessTokenDetector(RegexBasedDetector):
    """Scans for Flickr Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Flickr Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Flickr Access Token
            re.compile(
                r"""(?i)(?:flickr)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class FlutterwaveDetector(RegexBasedDetector):
    """Scans for Flutterwave API Keys."""

    @property
    def secret_type(self) -> str:
        return "Flutterwave API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Flutterwave Encryption Key
            re.compile(r"""(?i)FLWSECK_TEST-[a-h0-9]{12}"""),
            # Flutterwave Public Key
            re.compile(r"""(?i)FLWPUBK_TEST-[a-h0-9]{32}-X"""),
            # Flutterwave Secret Key
            re.compile(r"""(?i)FLWSECK_TEST-[a-h0-9]{32}-X"""),
        ]


class FrameIoApiTokenDetector(RegexBasedDetector):
    """Scans for Frame.io API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Frame.io API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Frame.io API token
            re.compile(r"""(?i)fio-u-[a-z0-9\-_=]{64}"""),
        ]


class FreshbooksAccessTokenDetector(RegexBasedDetector):
    """Scans for Freshbooks Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Freshbooks Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Freshbooks Access Token
            re.compile(
                r"""(?i)(?:freshbooks)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class GCPApiKeyDetector(RegexBasedDetector):
    """Scans for GCP API keys."""

    @property
    def secret_type(self) -> str:
        return "GCP API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # GCP API Key
            re.compile(
                r"""(?i)\b(AIza[0-9A-Za-z\\-_]{35})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class GitHubTokenCustomDetector(RegexBasedDetector):
    """Scans for GitHub tokens."""

    @property
    def secret_type(self) -> str:
        return "GitHub Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # GitHub App/Personal Access/OAuth Access/Refresh Token
            # ref. https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/
            re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}"),
            # GitHub Fine-Grained Personal Access Token
            re.compile(r"github_pat_[0-9a-zA-Z_]{82}"),
            re.compile(r"gho_[0-9a-zA-Z]{36}"),
        ]


class GitLabDetector(RegexBasedDetector):
    """Scans for GitLab Secrets."""

    @property
    def secret_type(self) -> str:
        return "GitLab Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # GitLab Personal Access Token
            re.compile(r"""glpat-[0-9a-zA-Z\-\_]{20}"""),
            # GitLab Pipeline Trigger Token
            re.compile(r"""glptt-[0-9a-f]{40}"""),
            # GitLab Runner Registration Token
            re.compile(r"""GR1348941[0-9a-zA-Z\-\_]{20}"""),
        ]


class GitterAccessTokenDetector(RegexBasedDetector):
    """Scans for Gitter Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Gitter Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Gitter Access Token
            re.compile(
                r"""(?i)(?:gitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9_-]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class GoCardlessApiTokenDetector(RegexBasedDetector):
    """Scans for GoCardless API Tokens."""

    @property
    def secret_type(self) -> str:
        return "GoCardless API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # GoCardless API token
            re.compile(
                r"""(?:gocardless)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(live_[a-z0-9\-_=]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)""",
                re.IGNORECASE,
            ),
        ]


class GrafanaDetector(RegexBasedDetector):
    """Scans for Grafana Secrets."""

    @property
    def secret_type(self) -> str:
        return "Grafana Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Grafana API key or Grafana Cloud API key
            re.compile(
                r"""(?i)\b(eyJrIjoi[A-Za-z0-9]{70,400}={0,2})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Grafana Cloud API token
            re.compile(
                r"""(?i)\b(glc_[A-Za-z0-9+/]{32,400}={0,2})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Grafana Service Account token
            re.compile(
                r"""(?i)\b(glsa_[A-Za-z0-9]{32}_[A-Fa-f0-9]{8})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class HashiCorpTFApiTokenDetector(RegexBasedDetector):
    """Scans for HashiCorp Terraform User/Org API Tokens."""

    @property
    def secret_type(self) -> str:
        return "HashiCorp Terraform API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # HashiCorp Terraform user/org API token
            re.compile(r"""(?i)[a-z0-9]{14}\.atlasv1\.[a-z0-9\-_=]{60,70}"""),
        ]


class HerokuApiKeyDetector(RegexBasedDetector):
    """Scans for Heroku API Keys."""

    @property
    def secret_type(self) -> str:
        return "Heroku API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:heroku)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class HubSpotApiTokenDetector(RegexBasedDetector):
    """Scans for HubSpot API Tokens."""

    @property
    def secret_type(self) -> str:
        return "HubSpot API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # HubSpot API Token
            re.compile(
                r"""(?i)(?:hubspot)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class HuggingFaceDetector(RegexBasedDetector):
    """Scans for Hugging Face Tokens."""

    @property
    def secret_type(self) -> str:
        return "Hugging Face Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Hugging Face Access token
            re.compile(r"""(?:^|[\\'"` >=:])(hf_[a-zA-Z]{34})(?:$|[\\'"` <])"""),
            # Hugging Face Organization API token
            re.compile(
                r"""(?:^|[\\'"` >=:\(,)])(api_org_[a-zA-Z]{34})(?:$|[\\'"` <\),])"""
            ),
        ]


class IntercomApiTokenDetector(RegexBasedDetector):
    """Scans for Intercom API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Intercom API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:intercom)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{60})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class JFrogDetector(RegexBasedDetector):
    """Scans for JFrog-related secrets."""

    @property
    def secret_type(self) -> str:
        return "JFrog Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # JFrog API Key
            re.compile(
                r"""(?i)(?:jfrog|artifactory|bintray|xray)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{73})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # JFrog Identity Token
            re.compile(
                r"""(?i)(?:jfrog|artifactory|bintray|xray)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class JWTBase64Detector(RegexBasedDetector):
    """Scans for Base64-encoded JSON Web Tokens."""

    @property
    def secret_type(self) -> str:
        return "Base64-encoded JSON Web Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Base64-encoded JSON Web Token
            re.compile(
                r"""\bZXlK(?:(?P<alg>aGJHY2lPaU)|(?P<apu>aGNIVWlPaU)|(?P<apv>aGNIWWlPaU)|(?P<aud>aGRXUWlPaU)|(?P<b64>aU5qUWlP)|(?P<crit>amNtbDBJanBi)|(?P<cty>amRIa2lPaU)|(?P<epk>bGNHc2lPbn)|(?P<enc>bGJtTWlPaU)|(?P<jku>cWEzVWlPaU)|(?P<jwk>cWQyc2lPb)|(?P<iss>cGMzTWlPaU)|(?P<iv>cGRpSTZJ)|(?P<kid>cmFXUWlP)|(?P<key_ops>clpYbGZiM0J6SWpwY)|(?P<kty>cmRIa2lPaUp)|(?P<nonce>dWIyNWpaU0k2)|(?P<p2c>d01tTWlP)|(?P<p2s>d01uTWlPaU)|(?P<ppt>d2NIUWlPaU)|(?P<sub>emRXSWlPaU)|(?P<svt>emRuUWlP)|(?P<tag>MFlXY2lPaU)|(?P<typ>MGVYQWlPaUp)|(?P<url>MWNtd2l)|(?P<use>MWMyVWlPaUp)|(?P<ver>MlpYSWlPaU)|(?P<version>MlpYSnphVzl1SWpv)|(?P<x>NElqb2)|(?P<x5c>NE5XTWlP)|(?P<x5t>NE5YUWlPaU)|(?P<x5ts256>NE5YUWpVekkxTmlJNkl)|(?P<x5u>NE5YVWlPaU)|(?P<zip>NmFYQWlPaU))[a-zA-Z0-9\/\\_+\-\r\n]{40,}={0,2}"""
            ),
        ]


class KrakenAccessTokenDetector(RegexBasedDetector):
    """Scans for Kraken Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Kraken Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Kraken Access Token
            re.compile(
                r"""(?i)(?:kraken)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9\/=_\+\-]{80,90})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class KucoinDetector(RegexBasedDetector):
    """Scans for Kucoin Access Tokens and Secret Keys."""

    @property
    def secret_type(self) -> str:
        return "Kucoin Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Kucoin Access Token
            re.compile(
                r"""(?i)(?:kucoin)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{24})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Kucoin Secret Key
            re.compile(
                r"""(?i)(?:kucoin)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class LaunchdarklyAccessTokenDetector(RegexBasedDetector):
    """Scans for Launchdarkly Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Launchdarkly Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:launchdarkly)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class LinearDetector(RegexBasedDetector):
    """Scans for Linear secrets."""

    @property
    def secret_type(self) -> str:
        return "Linear Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Linear API Token
            re.compile(r"""(?i)lin_api_[a-z0-9]{40}"""),
            # Linear Client Secret
            re.compile(
                r"""(?i)(?:linear)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class LinkedInDetector(RegexBasedDetector):
    """Scans for LinkedIn secrets."""

    @property
    def secret_type(self) -> str:
        return "LinkedIn Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # LinkedIn Client ID
            re.compile(
                r"""(?i)(?:linkedin|linked-in)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{14})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # LinkedIn Client secret
            re.compile(
                r"""(?i)(?:linkedin|linked-in)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{16})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class LobDetector(RegexBasedDetector):
    """Scans for Lob secrets."""

    @property
    def secret_type(self) -> str:
        return "Lob Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Lob API Key
            re.compile(
                r"""(?i)(?:lob)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}((live|test)_[a-f0-9]{35})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Lob Publishable API Key
            re.compile(
                r"""(?i)(?:lob)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}((test|live)_pub_[a-f0-9]{31})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class MailgunDetector(RegexBasedDetector):
    """Scans for Mailgun secrets."""

    @property
    def secret_type(self) -> str:
        return "Mailgun Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Mailgun Private API Token
            re.compile(
                r"""(?i)(?:mailgun)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(key-[a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Mailgun Public Validation Key
            re.compile(
                r"""(?i)(?:mailgun)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(pubkey-[a-f0-9]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Mailgun Webhook Signing Key
            re.compile(
                r"""(?i)(?:mailgun)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-h0-9]{32}-[a-h0-9]{8}-[a-h0-9]{8})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class MapBoxApiTokenDetector(RegexBasedDetector):
    """Scans for MapBox API tokens."""

    @property
    def secret_type(self) -> str:
        return "MapBox API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # MapBox API Token
            re.compile(
                r"""(?i)(?:mapbox)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(pk\.[a-z0-9]{60}\.[a-z0-9]{22})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class MattermostAccessTokenDetector(RegexBasedDetector):
    """Scans for Mattermost Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Mattermost Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Mattermost Access Token
            re.compile(
                r"""(?i)(?:mattermost)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{26})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class MessageBirdDetector(RegexBasedDetector):
    """Scans for MessageBird secrets."""

    @property
    def secret_type(self) -> str:
        return "MessageBird Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # MessageBird API Token
            re.compile(
                r"""(?i)(?:messagebird|message-bird|message_bird)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{25})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # MessageBird Client ID
            re.compile(
                r"""(?i)(?:messagebird|message-bird|message_bird)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class MicrosoftTeamsWebhookDetector(RegexBasedDetector):
    """Scans for Microsoft Teams Webhook URLs."""

    @property
    def secret_type(self) -> str:
        return "Microsoft Teams Webhook"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Microsoft Teams Webhook
            re.compile(
                r"""https:\/\/[a-z0-9]+\.webhook\.office\.com\/webhookb2\/[a-z0-9]{8}-([a-z0-9]{4}-){3}[a-z0-9]{12}@[a-z0-9]{8}-([a-z0-9]{4}-){3}[a-z0-9]{12}\/IncomingWebhook\/[a-z0-9]{32}\/[a-z0-9]{8}-([a-z0-9]{4}-){3}[a-z0-9]{12}"""
            ),
        ]


class NetlifyAccessTokenDetector(RegexBasedDetector):
    """Scans for Netlify Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Netlify Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Netlify Access Token
            re.compile(
                r"""(?i)(?:netlify)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{40,46})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class NewRelicDetector(RegexBasedDetector):
    """Scans for New Relic API tokens and keys."""

    @property
    def secret_type(self) -> str:
        return "New Relic API Secrets"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # New Relic ingest browser API token
            re.compile(
                r"""(?i)(?:new-relic|newrelic|new_relic)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(NRJS-[a-f0-9]{19})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # New Relic user API ID
            re.compile(
                r"""(?i)(?:new-relic|newrelic|new_relic)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # New Relic user API Key
            re.compile(
                r"""(?i)(?:new-relic|newrelic|new_relic)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(NRAK-[a-z0-9]{27})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class NYTimesAccessTokenDetector(RegexBasedDetector):
    """Scans for New York Times Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "New York Times Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:nytimes|new-york-times,|newyorktimes)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{32})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class OktaAccessTokenDetector(RegexBasedDetector):
    """Scans for Okta Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Okta Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:okta)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9=_\-]{42})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class OpenAIApiKeyDetector(RegexBasedDetector):
    """Scans for OpenAI API Keys."""

    @property
    def secret_type(self) -> str:
        return "OpenAI API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)\b(sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class PlanetScaleDetector(RegexBasedDetector):
    """Scans for PlanetScale API Tokens."""

    @property
    def secret_type(self) -> str:
        return "PlanetScale API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # the PlanetScale API token
            re.compile(
                r"""(?i)\b(pscale_tkn_[a-z0-9=\-_\.]{32,64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # the PlanetScale OAuth token
            re.compile(
                r"""(?i)\b(pscale_oauth_[a-z0-9=\-_\.]{32,64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # the PlanetScale password
            re.compile(
                r"""(?i)\b(pscale_pw_[a-z0-9=\-_\.]{32,64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class PostmanApiTokenDetector(RegexBasedDetector):
    """Scans for Postman API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Postman API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)\b(PMAK-[a-f0-9]{24}-[a-f0-9]{34})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class PrefectApiTokenDetector(RegexBasedDetector):
    """Scans for Prefect API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Prefect API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [re.compile(r"""(?i)\b(pnu_[a-z0-9]{36})(?:['|\"|\n|\r|\s|\x60|;]|$)""")]


class PulumiApiTokenDetector(RegexBasedDetector):
    """Scans for Pulumi API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Pulumi API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [re.compile(r"""(?i)\b(pul-[a-f0-9]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)""")]


class PyPiUploadTokenDetector(RegexBasedDetector):
    """Scans for PyPI Upload Tokens."""

    @property
    def secret_type(self) -> str:
        return "PyPI Upload Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [re.compile(r"""pypi-AgEIcHlwaS5vcmc[A-Za-z0-9\-_]{50,1000}""")]


class RapidApiAccessTokenDetector(RegexBasedDetector):
    """Scans for RapidAPI Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "RapidAPI Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:rapidapi)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9_-]{50})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class ReadmeApiTokenDetector(RegexBasedDetector):
    """Scans for Readme API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Readme API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(r"""(?i)\b(rdme_[a-z0-9]{70})(?:['|\"|\n|\r|\s|\x60|;]|$)""")
        ]


class RubygemsApiTokenDetector(RegexBasedDetector):
    """Scans for Rubygem API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Rubygem API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(r"""(?i)\b(rubygems_[a-f0-9]{48})(?:['|\"|\n|\r|\s|\x60|;]|$)""")
        ]


class ScalingoApiTokenDetector(RegexBasedDetector):
    """Scans for Scalingo API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Scalingo API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [re.compile(r"""\btk-us-[a-zA-Z0-9-_]{48}\b""")]


class SendbirdDetector(RegexBasedDetector):
    """Scans for Sendbird Access IDs and Tokens."""

    @property
    def secret_type(self) -> str:
        return "Sendbird Credential"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Sendbird Access ID
            re.compile(
                r"""(?i)(?:sendbird)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Sendbird Access Token
            re.compile(
                r"""(?i)(?:sendbird)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class SendGridApiTokenDetector(RegexBasedDetector):
    """Scans for SendGrid API Tokens."""

    @property
    def secret_type(self) -> str:
        return "SendGrid API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)\b(SG\.[a-z0-9=_\-\.]{66})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class SendinBlueApiTokenDetector(RegexBasedDetector):
    """Scans for SendinBlue API Tokens."""

    @property
    def secret_type(self) -> str:
        return "SendinBlue API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)\b(xkeysib-[a-f0-9]{64}-[a-z0-9]{16})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class SentryAccessTokenDetector(RegexBasedDetector):
    """Scans for Sentry Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Sentry Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:sentry)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class ShippoApiTokenDetector(RegexBasedDetector):
    """Scans for Shippo API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Shippo API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)\b(shippo_(live|test)_[a-f0-9]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


"""
This plugin searches for Shopify Access Tokens, Custom Access Tokens,
Private App Access Tokens, and Shared Secrets.
"""


class ShopifyDetector(RegexBasedDetector):
    """Scans for Shopify Access Tokens, Custom Access Tokens, Private App Access Tokens,
    and Shared Secrets.
    """

    @property
    def secret_type(self) -> str:
        return "Shopify Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Shopify access token
            re.compile(r"""shpat_[a-fA-F0-9]{32}"""),
            # Shopify custom access token
            re.compile(r"""shpca_[a-fA-F0-9]{32}"""),
            # Shopify private app access token
            re.compile(r"""shppa_[a-fA-F0-9]{32}"""),
            # Shopify shared secret
            re.compile(r"""shpss_[a-fA-F0-9]{32}"""),
        ]


class SidekiqDetector(RegexBasedDetector):
    """Scans for Sidekiq secrets and sensitive URLs."""

    @property
    def secret_type(self) -> str:
        return "Sidekiq Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Sidekiq Secret
            re.compile(
                r"""(?i)(?:BUNDLE_ENTERPRISE__CONTRIBSYS__COM|BUNDLE_GEMS__CONTRIBSYS__COM)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-f0-9]{8}:[a-f0-9]{8})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Sidekiq Sensitive URL
            re.compile(
                r"""(?i)\b(http(?:s??):\/\/)([a-f0-9]{8}:[a-f0-9]{8})@(?:gems.contribsys.com|enterprise.contribsys.com)(?:[\/|\#|\?|:]|$)"""
            ),
        ]


class SlackDetector(RegexBasedDetector):
    """Scans for Slack tokens and webhooks."""

    @property
    def secret_type(self) -> str:
        return "Slack Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Slack App-level token
            re.compile(r"""(?i)(xapp-\d-[A-Z0-9]+-\d+-[a-z0-9]+)"""),
            # Slack Bot token
            re.compile(r"""(xoxb-[0-9]{10,13}\-[0-9]{10,13}[a-zA-Z0-9-]*)"""),
            # Slack Configuration access token and refresh token
            re.compile(r"""(?i)(xoxe.xox[bp]-\d-[A-Z0-9]{163,166})"""),
            re.compile(r"""(?i)(xoxe-\d-[A-Z0-9]{146})"""),
            # Slack Legacy bot token and token
            re.compile(r"""(xoxb-[0-9]{8,14}\-[a-zA-Z0-9]{18,26})"""),
            re.compile(r"""(xox[os]-\d+-\d+-\d+-[a-fA-F\d]+)"""),
            # Slack Legacy Workspace token
            re.compile(r"""(xox[ar]-(?:\d-)?[0-9a-zA-Z]{8,48})"""),
            # Slack User token and enterprise token
            re.compile(r"""(xox[pe](?:-[0-9]{10,13}){3}-[a-zA-Z0-9-]{28,34})"""),
            # Slack Webhook URL
            re.compile(
                r"""(https?:\/\/)?hooks.slack.com\/(services|workflows)\/[A-Za-z0-9+\/]{43,46}"""
            ),
        ]


class SnykApiTokenDetector(RegexBasedDetector):
    """Scans for Snyk API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Snyk API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:snyk)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class SquarespaceAccessTokenDetector(RegexBasedDetector):
    """Scans for Squarespace Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Squarespace Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:squarespace)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class SumoLogicDetector(RegexBasedDetector):
    """Scans for SumoLogic Access ID and Access Token."""

    @property
    def secret_type(self) -> str:
        return "SumoLogic"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i:(?:sumo)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3})(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(su[a-zA-Z0-9]{12})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            re.compile(
                r"""(?i)(?:sumo)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{64})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class TelegramBotApiTokenDetector(RegexBasedDetector):
    """Scans for Telegram Bot API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Telegram Bot API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:^|[^0-9])([0-9]{5,16}:A[a-zA-Z0-9_\-]{34})(?:$|[^a-zA-Z0-9_\-])"""
            )
        ]


class TravisCiAccessTokenDetector(RegexBasedDetector):
    """Scans for Travis CI Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Travis CI Access Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:travis)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{22})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class TwitchApiTokenDetector(RegexBasedDetector):
    """Scans for Twitch API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Twitch API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:twitch)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{30})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class TwitterDetector(RegexBasedDetector):
    """Scans for Twitter Access Secrets, Access Tokens, API Keys, API Secrets, and Bearer Tokens."""

    @property
    def secret_type(self) -> str:
        return "Twitter Secret"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Twitter Access Secret
            re.compile(
                r"""(?i)(?:twitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{45})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Twitter Access Token
            re.compile(
                r"""(?i)(?:twitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([0-9]{15,25}-[a-zA-Z0-9]{20,40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Twitter API Key
            re.compile(
                r"""(?i)(?:twitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{25})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Twitter API Secret
            re.compile(
                r"""(?i)(?:twitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{50})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Twitter Bearer Token
            re.compile(
                r"""(?i)(?:twitter)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(A{22}[a-zA-Z0-9%]{80,100})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class TypeformApiTokenDetector(RegexBasedDetector):
    """Scans for Typeform API Tokens."""

    @property
    def secret_type(self) -> str:
        return "Typeform API Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:typeform)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(tfp_[a-z0-9\-_\.=]{59})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


class VaultDetector(RegexBasedDetector):
    """Scans for Vault Batch Tokens and Vault Service Tokens."""

    @property
    def secret_type(self) -> str:
        return "Vault Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Vault Batch Token
            re.compile(
                r"""(?i)\b(hvb\.[a-z0-9_-]{138,212})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Vault Service Token
            re.compile(
                r"""(?i)\b(hvs\.[a-z0-9_-]{90,100})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class WandbAPIKeyDetector(RegexBasedDetector):
    """Scans for Weights and Biases API Keys."""

    @property
    def secret_type(self) -> str:
        return "Weights and Biases API Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [re.compile(r"\b[a-f0-9]{40}\b", re.IGNORECASE)]


class YandexDetector(RegexBasedDetector):
    """Scans for Yandex Access Tokens, API Keys, and AWS Access Tokens."""

    @property
    def secret_type(self) -> str:
        return "Yandex Token"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            # Yandex Access Token
            re.compile(
                r"""(?i)(?:yandex)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(t1\.[A-Z0-9a-z_-]+[=]{0,2}\.[A-Z0-9a-z_-]{86}[=]{0,2})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Yandex API Key
            re.compile(
                r"""(?i)(?:yandex)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(AQVN[A-Za-z0-9_\-]{35,38})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
            # Yandex AWS Access Token
            re.compile(
                r"""(?i)(?:yandex)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}(YC[a-zA-Z0-9_\-]{38})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            ),
        ]


class ZendeskSecretKeyDetector(RegexBasedDetector):
    """Scans for Zendesk Secret Keys."""

    @property
    def secret_type(self) -> str:
        return "Zendesk Secret Key"

    @property
    def denylist(self) -> list[re.Pattern]:
        return [
            re.compile(
                r"""(?i)(?:zendesk)(?:[0-9a-z\-_\t .]{0,20})(?:[\s|']|[\s|"]){0,3}(?:=|>|:{1,3}=|\|\|:|<=|=>|:|\?=)(?:'|\"|\s|=|\x60){0,5}([a-z0-9]{40})(?:['|\"|\n|\r|\s|\x60|;]|$)"""
            )
        ]


_custom_plugins_path = "file://" + os.path.abspath(__file__)

ALL_PLUGINS = {
    "plugins_used": [
        {"name": "SoftlayerDetector"},
        {"name": "StripeDetector"},
        {"name": "NpmDetector"},
        {"name": "IbmCosHmacDetector"},
        {"name": "DiscordBotTokenDetector"},
        {"name": "BasicAuthDetector"},
        {"name": "AzureStorageKeyDetector"},
        {"name": "ArtifactoryDetector"},
        {"name": "AWSKeyDetector"},
        {"name": "CloudantDetector"},
        {"name": "IbmCloudIamDetector"},
        {"name": "JwtTokenDetector"},
        {"name": "MailchimpDetector"},
        {"name": "SquareOAuthDetector"},
        {"name": "PrivateKeyDetector"},
        {"name": "TwilioKeyDetector"},
        {"name": "AdafruitKeyDetector", "path": _custom_plugins_path},
        {"name": "AdobeSecretDetector", "path": _custom_plugins_path},
        {"name": "AgeSecretKeyDetector", "path": _custom_plugins_path},
        {"name": "AirtableApiKeyDetector", "path": _custom_plugins_path},
        {"name": "AlgoliaApiKeyDetector", "path": _custom_plugins_path},
        {"name": "AlibabaSecretDetector", "path": _custom_plugins_path},
        {"name": "AsanaSecretDetector", "path": _custom_plugins_path},
        {"name": "AtlassianApiTokenDetector", "path": _custom_plugins_path},
        {"name": "AuthressAccessKeyDetector", "path": _custom_plugins_path},
        {"name": "BittrexDetector", "path": _custom_plugins_path},
        {"name": "BitbucketDetector", "path": _custom_plugins_path},
        {"name": "BeamerApiTokenDetector", "path": _custom_plugins_path},
        {"name": "ClojarsApiTokenDetector", "path": _custom_plugins_path},
        {"name": "CodecovAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "CoinbaseAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "ConfluentDetector", "path": _custom_plugins_path},
        {"name": "ContentfulApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DatabricksApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DatadogAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "DefinedNetworkingApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DigitaloceanDetector", "path": _custom_plugins_path},
        {"name": "DopplerApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DroneciAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "DuffelApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DynatraceApiTokenDetector", "path": _custom_plugins_path},
        {"name": "DiscordDetector", "path": _custom_plugins_path},
        {"name": "DropboxDetector", "path": _custom_plugins_path},
        {"name": "EasyPostDetector", "path": _custom_plugins_path},
        {"name": "EtsyAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "FacebookAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "FastlyApiKeyDetector", "path": _custom_plugins_path},
        {"name": "FinicityDetector", "path": _custom_plugins_path},
        {"name": "FinnhubAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "FlickrAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "FlutterwaveDetector", "path": _custom_plugins_path},
        {"name": "FrameIoApiTokenDetector", "path": _custom_plugins_path},
        {"name": "FreshbooksAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "GCPApiKeyDetector", "path": _custom_plugins_path},
        {"name": "GitHubTokenCustomDetector", "path": _custom_plugins_path},
        {"name": "GitLabDetector", "path": _custom_plugins_path},
        {"name": "GitterAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "GoCardlessApiTokenDetector", "path": _custom_plugins_path},
        {"name": "GrafanaDetector", "path": _custom_plugins_path},
        {"name": "HashiCorpTFApiTokenDetector", "path": _custom_plugins_path},
        {"name": "HerokuApiKeyDetector", "path": _custom_plugins_path},
        {"name": "HubSpotApiTokenDetector", "path": _custom_plugins_path},
        {"name": "HuggingFaceDetector", "path": _custom_plugins_path},
        {"name": "IntercomApiTokenDetector", "path": _custom_plugins_path},
        {"name": "JFrogDetector", "path": _custom_plugins_path},
        {"name": "JWTBase64Detector", "path": _custom_plugins_path},
        {"name": "KrakenAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "KucoinDetector", "path": _custom_plugins_path},
        {"name": "LaunchdarklyAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "LinearDetector", "path": _custom_plugins_path},
        {"name": "LinkedInDetector", "path": _custom_plugins_path},
        {"name": "LobDetector", "path": _custom_plugins_path},
        {"name": "MailgunDetector", "path": _custom_plugins_path},
        {"name": "MapBoxApiTokenDetector", "path": _custom_plugins_path},
        {"name": "MattermostAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "MessageBirdDetector", "path": _custom_plugins_path},
        {"name": "MicrosoftTeamsWebhookDetector", "path": _custom_plugins_path},
        {"name": "NetlifyAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "NewRelicDetector", "path": _custom_plugins_path},
        {"name": "NYTimesAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "OktaAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "OpenAIApiKeyDetector", "path": _custom_plugins_path},
        {"name": "PlanetScaleDetector", "path": _custom_plugins_path},
        {"name": "PostmanApiTokenDetector", "path": _custom_plugins_path},
        {"name": "PrefectApiTokenDetector", "path": _custom_plugins_path},
        {"name": "PulumiApiTokenDetector", "path": _custom_plugins_path},
        {"name": "PyPiUploadTokenDetector", "path": _custom_plugins_path},
        {"name": "RapidApiAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "ReadmeApiTokenDetector", "path": _custom_plugins_path},
        {"name": "RubygemsApiTokenDetector", "path": _custom_plugins_path},
        {"name": "ScalingoApiTokenDetector", "path": _custom_plugins_path},
        {"name": "SendbirdDetector", "path": _custom_plugins_path},
        {"name": "SendGridApiTokenDetector", "path": _custom_plugins_path},
        {"name": "SendinBlueApiTokenDetector", "path": _custom_plugins_path},
        {"name": "SentryAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "ShippoApiTokenDetector", "path": _custom_plugins_path},
        {"name": "ShopifyDetector", "path": _custom_plugins_path},
        {"name": "SidekiqDetector", "path": _custom_plugins_path},
        {"name": "SlackDetector", "path": _custom_plugins_path},
        {"name": "SnykApiTokenDetector", "path": _custom_plugins_path},
        {"name": "SquarespaceAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "SumoLogicDetector", "path": _custom_plugins_path},
        {"name": "TelegramBotApiTokenDetector", "path": _custom_plugins_path},
        {"name": "TravisCiAccessTokenDetector", "path": _custom_plugins_path},
        {"name": "TwitchApiTokenDetector", "path": _custom_plugins_path},
        {"name": "TwitterDetector", "path": _custom_plugins_path},
        {"name": "TypeformApiTokenDetector", "path": _custom_plugins_path},
        {"name": "VaultDetector", "path": _custom_plugins_path},
        {"name": "WandbAPIKeyDetector", "path": _custom_plugins_path},
        {"name": "YandexDetector", "path": _custom_plugins_path},
        {"name": "ZendeskSecretKeyDetector", "path": _custom_plugins_path},
        {"name": "Base64HighEntropyString", "limit": 4.5},
        {"name": "HexHighEntropyString", "limit": 3.0},
    ]
}
