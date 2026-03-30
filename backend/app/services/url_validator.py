"""
URL validation and SSRF protection utilities.

PURPOSE: Validate URLs against an allowlist of trusted government/statistical
data sources, and perform general URL safety checks (scheme, private IP,
suspicious patterns) to prevent SSRF attacks from user-supplied URLs.

DEPENDS ON: (stdlib only — no app imports)
USED BY: routers/export.py (via ExportGenerator domain validation)
"""
import ipaddress
import logging
from urllib.parse import urlparse
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Allowlisted domains for MCP API calls
# These are trusted government and statistical data sources
ALLOWED_API_DOMAINS = [
    # Swiss Federal Statistics
    "api.bfs.admin.ch",
    "www.bfs.admin.ch",
    "bfs.admin.ch",
    # Eurostat
    "ec.europa.eu",
    "api.eurostat.ec.europa.eu",
    "data.europa.eu",
    "eurostat.ec.europa.eu",
    # EU Parliament
    "data.europarl.europa.eu",
    "europarl.europa.eu",
    # UK Parliament
    "api.parliament.uk",
    "parliament.uk",
    # German Bundestag
    "api.bundestag.de",
    "bundestag.de",
    # Swiss Open Data
    "opendata.swiss",
    "www.opendata.swiss",
    # Swiss Parliament
    "www.openparldata.ch",
    "openparldata.ch",
    "api.openparldata.ch",
    # World Bank
    "api.worldbank.org",
    # OECD
    "stats.oecd.org",
    # UN Data
    "data.un.org",
    # IMF
    "dataservices.imf.org",
]


def validate_api_url(url: str) -> bool:
    """
    Validate that API URL is from an allowed domain.

    Prevents SSRF attacks by:
    1. Requiring HTTPS
    2. Checking against allowlist
    3. Blocking private/internal IPs

    Args:
        url: The URL to validate

    Returns:
        True if valid

    Raises:
        HTTPException if URL is not allowed
    """
    try:
        parsed = urlparse(url)

        # Must be HTTPS
        if parsed.scheme != "https":
            logger.warning(f"URL validation failed - not HTTPS: {url}")
            raise HTTPException(
                status_code=400,
                detail="API URL must use HTTPS"
            )

        # Extract hostname
        hostname = parsed.netloc.lower()
        if not hostname:
            raise HTTPException(
                status_code=400,
                detail="Invalid URL - no hostname found"
            )

        # Remove port if present
        if ":" in hostname:
            hostname = hostname.split(":")[0]

        # Check against allowlist
        if hostname not in ALLOWED_API_DOMAINS:
            logger.warning(f"URL validation failed - domain not allowed: {hostname}")
            raise HTTPException(
                status_code=400,
                detail=f"API domain '{hostname}' is not in the allowed list. Contact support to add new data sources."
            )

        # Block internal/private IPs (defense in depth)
        try:
            # Try to resolve as IP
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                logger.warning(f"URL validation failed - private IP: {parsed.hostname}")
                raise HTTPException(
                    status_code=400,
                    detail="API URL cannot target private/internal addresses"
                )
        except ValueError:
            # hostname is not an IP address, which is expected and fine
            pass

        logger.info(f"URL validated successfully: {hostname}")
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid API URL: {str(e)}")


# Hostnames that are always blocked for general SSRF protection
_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"})

# Internal hostname suffixes to block
_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost")

# Cloud metadata IP (AWS, GCP instance metadata)
_METADATA_IP = "169.254.169.254"


def is_safe_external_url(url: str) -> bool:
    """
    Check whether a URL is safe to fetch (general SSRF protection).

    Unlike ``validate_api_url`` (which enforces a domain allowlist for
    Local Data scout APIs), this function only blocks obviously dangerous
    targets: private IPs, localhost variants, cloud metadata endpoints,
    and internal hostnames.

    Used by export_generator when fetching
    arbitrary external URLs found by the AI agent.

    Args:
        url: URL to check

    Returns:
        True if the URL appears safe to fetch, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.netloc or "").lower().split(":")[0]
        if not hostname:
            return False

        if hostname in _BLOCKED_HOSTS or hostname == _METADATA_IP:
            return False

        if any(hostname.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
            return False

        # Block private/internal/reserved IP addresses
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return False
        except ValueError:
            pass  # Not an IP address, which is expected

        return True
    except Exception:
        return False
