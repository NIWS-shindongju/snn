"""Copernicus Data Space Ecosystem Sentinel-2 downloader.

Uses OAuth2 client credentials flow and the OData v1 catalogue API.
Implements async HTTP with httpx, automatic token refresh, retry logic,
and on-disk caching to avoid redundant downloads.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from carbonsnn.config import get_settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────

@dataclass
class Sentinel2Product:
    """Metadata for a single Sentinel-2 product in the catalogue.

    Attributes:
        product_id: Unique product identifier.
        name: Product filename (SAFE directory name).
        sensing_date: Acquisition date/time.
        cloud_cover: Scene cloud cover percentage.
        bbox: Bounding box [west, south, east, north].
        download_url: Direct download URL.
        size_mb: Approximate compressed product size.
    """

    product_id: str
    name: str
    sensing_date: datetime
    cloud_cover: float
    bbox: list[float]
    download_url: str
    size_mb: float = 0.0


@dataclass
class TokenCache:
    """In-memory OAuth2 token cache.

    Attributes:
        access_token: Bearer token string.
        expires_at: UNIX timestamp when the token expires.
    """

    access_token: str = ""
    expires_at: float = 0.0

    @property
    def is_valid(self) -> bool:
        """True if the token is non-empty and not expired (5 s buffer)."""
        return bool(self.access_token) and time.time() < self.expires_at - 5


# ──────────────────────────────────────────────────────────
# Downloader
# ──────────────────────────────────────────────────────────

class SentinelDownloader:
    """Download Sentinel-2 L2A products from Copernicus Data Space.

    Args:
        client_id: OAuth2 client ID (defaults to env var).
        client_secret: OAuth2 client secret (defaults to env var).
        output_dir: Directory to save downloaded files.
        max_cloud_cover: Maximum allowed cloud cover percentage.
        cache_dir: Directory for caching search results.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        output_dir: str | Path | None = None,
        max_cloud_cover: float = 20.0,
        cache_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.client_id = client_id or settings.copernicus_client_id
        self.client_secret = client_secret or settings.copernicus_client_secret
        self.token_url = settings.copernicus_token_url
        self.search_url = settings.copernicus_search_url
        self.download_url = settings.copernicus_download_url
        self.output_dir = Path(output_dir or settings.data_dir)
        self.max_cloud_cover = max_cloud_cover
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._token_cache = TokenCache()

    # ── Authentication ────────────────────────────────────────

    async def _get_token(self) -> str:
        """Retrieve (or refresh) the OAuth2 bearer token.

        Returns:
            Valid access token string.

        Raises:
            RuntimeError: If the token request fails.
        """
        if self._token_cache.is_valid:
            return self._token_cache.access_token

        logger.debug("Requesting new Copernicus OAuth2 token")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Token request failed: {response.status_code} {response.text}"
                )
            data = response.json()
            self._token_cache.access_token = data["access_token"]
            self._token_cache.expires_at = time.time() + data.get("expires_in", 3600)
            logger.info("OAuth2 token acquired, expires in %ds", data.get("expires_in", 3600))
            return self._token_cache.access_token

    # ── Search ────────────────────────────────────────────────

    def _cache_key(self, bbox: list[float], start: str, end: str) -> str:
        """Generate a deterministic cache filename for a search query."""
        raw = f"{bbox}_{start}_{end}_{self.max_cloud_cover}"
        return hashlib.md5(raw.encode()).hexdigest()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def search(
        self,
        bbox: list[float],
        start_date: str,
        end_date: str,
        max_results: int = 10,
    ) -> list[Sentinel2Product]:
        """Search the Copernicus catalogue for Sentinel-2 L2A products.

        Args:
            bbox: [west, south, east, north] bounding box in EPSG:4326.
            start_date: ISO-8601 start date string (e.g. '2024-01-01').
            end_date: ISO-8601 end date string (e.g. '2024-03-31').
            max_results: Maximum number of products to return.

        Returns:
            List of Sentinel2Product ordered by cloud cover ascending.
        """
        cache_key = self._cache_key(bbox, start_date, end_date)
        cache_file = self.cache_dir / f"search_{cache_key}.json"

        if cache_file.exists():
            logger.debug("Search cache hit: %s", cache_file)
            with cache_file.open() as fh:
                raw = json.load(fh)
            return [self._parse_product(p) for p in raw]

        token = await self._get_token()
        west, south, east, north = bbox
        geo_filter = (
            f"POLYGON(({west} {south},{east} {south},"
            f"{east} {north},{west} {north},{west} {south}))"
        )

        query = (
            f"{self.search_url}/Products?"
            f"$filter=Collection/Name eq 'SENTINEL-2' "
            f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
            f"and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') "
            f"and ContentDate/Start ge {start_date}T00:00:00.000Z "
            f"and ContentDate/Start le {end_date}T23:59:59.000Z "
            f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/OData.CSC.DoubleAttribute/Value le {self.max_cloud_cover}) "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;{geo_filter}')"
            f"&$orderby=Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover') asc"
            f"&$top={max_results}"
        )

        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=60
        ) as client:
            response = await client.get(query)
            response.raise_for_status()
            items: list[dict[str, Any]] = response.json().get("value", [])

        with cache_file.open("w") as fh:
            json.dump(items, fh)

        products = [self._parse_product(p) for p in items]
        logger.info("Found %d products for bbox=%s dates=%s–%s", len(products), bbox, start_date, end_date)
        return products

    def _parse_product(self, raw: dict[str, Any]) -> Sentinel2Product:
        """Parse a raw OData product entry into a Sentinel2Product."""
        attrs: dict[str, Any] = {a["Name"]: a.get("Value") for a in raw.get("Attributes", [])}
        return Sentinel2Product(
            product_id=raw.get("Id", ""),
            name=raw.get("Name", ""),
            sensing_date=datetime.fromisoformat(
                raw.get("ContentDate", {}).get("Start", "1970-01-01T00:00:00Z").rstrip("Z")
            ),
            cloud_cover=float(attrs.get("cloudCover", 100.0)),
            bbox=raw.get("Footprint", {}).get("coordinates", [[]])[0][:4] if raw.get("Footprint") else [],
            download_url=f"{self.download_url}/Products({raw.get('Id', '')}/$value",
            size_mb=float(raw.get("ContentLength", 0)) / 1_048_576,
        )

    # ── Download ──────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=5, max=60),
    )
    async def download(
        self, product: Sentinel2Product, dest_dir: str | Path | None = None
    ) -> Path:
        """Download a Sentinel-2 product to disk.

        Args:
            product: Product metadata from :meth:`search`.
            dest_dir: Override destination directory.

        Returns:
            Path to the downloaded file.

        Raises:
            httpx.HTTPError: On download failure after retries.
        """
        dest = Path(dest_dir or self.output_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out_path = dest / f"{product.name}.zip"

        if out_path.exists():
            logger.info("Product already cached: %s", out_path)
            return out_path

        token = await self._get_token()
        logger.info("Downloading %s (%.1f MB) → %s", product.name, product.size_mb, out_path)

        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=600, follow_redirects=True
        ) as client:
            async with client.stream("GET", product.download_url) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with out_path.open("wb") as fh:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        fh.write(chunk)
                        downloaded += len(chunk)

        logger.info("Download complete: %s (%d bytes)", out_path, downloaded)
        return out_path

    async def search_and_download(
        self,
        bbox: list[float],
        start_date: str,
        end_date: str,
        max_products: int = 3,
    ) -> list[Path]:
        """Convenience method: search then download top products.

        Args:
            bbox: Bounding box [west, south, east, north].
            start_date: ISO-8601 start date.
            end_date: ISO-8601 end date.
            max_products: Maximum products to download.

        Returns:
            List of downloaded file paths.
        """
        products = await self.search(bbox, start_date, end_date, max_results=max_products)
        if not products:
            logger.warning("No Sentinel-2 products found for the given criteria.")
            return []

        tasks = [self.download(p) for p in products[:max_products]]
        paths = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [p for p in paths if isinstance(p, Path)]
        logger.info("Downloaded %d/%d products", len(valid), len(products))
        return valid
