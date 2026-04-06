"""Sentinel-2 scene fetcher for EUDR parcel change detection.

Uses Copernicus Data Space Ecosystem (CDSE) OData API to search and download
Sentinel-2 L2A products covering a parcel's bounding box.

If Copernicus credentials are not configured, falls back to a mock mode
that generates synthetic GeoTIFF data for development/demo purposes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from tracecheck.config import settings

logger = logging.getLogger(__name__)

# Sentinel-2 L2A band order used throughout the pipeline
# (matches spikeeo/io/vegetation.py ALL_BANDS)
BAND_ORDER = ["B02", "B03", "B04", "B08", "B05", "B06", "B07", "B8A", "B11", "B12"]
NUM_BANDS = len(BAND_ORDER)


@dataclass
class SceneInfo:
    """Metadata about a fetched satellite scene."""

    scene_id: str
    acquisition_date: str  # YYYY-MM-DD
    cloud_coverage: float  # 0–100
    file_path: Path
    is_mock: bool = False


class SentinelFetcher:
    """Fetch Sentinel-2 scenes for EUDR parcel analysis.

    For each parcel we need:
    - A 'before' scene: taken BEFORE the EUDR cutoff date (default 2020-12-31)
    - An 'after' scene: taken AFTER the cutoff (most recent available)

    Args:
        data_dir: Root directory for cached data.
    """

    CDSE_ODATA_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path(settings.data_dir) / "sentinel2"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._mock_mode = not (settings.copernicus_client_id and settings.copernicus_client_secret)
        if self._mock_mode:
            logger.warning(
                "Copernicus credentials not set — running in MOCK mode. "
                "Set TRACECHECK_COPERNICUS_CLIENT_ID and TRACECHECK_COPERNICUS_CLIENT_SECRET "
                "for real satellite data."
            )

    def fetch_for_parcel(
        self,
        parcel_id: str,
        bbox: tuple[float, float, float, float],  # (minx, miny, maxx, maxy)
        cutoff_date: str = "2020-12-31",
    ) -> tuple[Path, Path, SceneInfo, SceneInfo]:
        """Fetch before/after Sentinel-2 scenes for a parcel.

        Args:
            parcel_id: UUID used for caching.
            bbox: (minx, miny, maxx, maxy) bounding box.
            cutoff_date: EUDR reference date (default 2020-12-31).

        Returns:
            Tuple of (before_tif, after_tif, before_info, after_info).
        """
        parcel_dir = self.data_dir / parcel_id
        parcel_dir.mkdir(parents=True, exist_ok=True)

        if self._mock_mode:
            return self._fetch_mock(parcel_id, parcel_dir, bbox, cutoff_date)

        return self._fetch_real(parcel_id, parcel_dir, bbox, cutoff_date)

    # ─────────────────────────────────────────────────────────────────────────
    # Mock mode (development / demo)
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_mock(
        self,
        parcel_id: str,
        parcel_dir: Path,
        bbox: tuple[float, float, float, float],
        cutoff_date: str,
    ) -> tuple[Path, Path, SceneInfo, SceneInfo]:
        """Generate synthetic GeoTIFF data for testing without real credentials."""
        before_path = parcel_dir / "before.tif"
        after_path = parcel_dir / "after.tif"

        # Parse cutoff for metadata
        co = datetime.strptime(cutoff_date, "%Y-%m-%d")
        before_date = (co - timedelta(days=180)).strftime("%Y-%m-%d")
        after_date = datetime.now().strftime("%Y-%m-%d")

        if not before_path.exists():
            _write_mock_geotiff(before_path, bbox, cloud_fraction=0.05, vegetation_ndvi=0.6)
        if not after_path.exists():
            # Slightly lower NDVI after cutoff to simulate minimal change
            _write_mock_geotiff(after_path, bbox, cloud_fraction=0.05, vegetation_ndvi=0.58)

        before_info = SceneInfo(
            scene_id=f"MOCK-{parcel_id[:8]}-BEFORE",
            acquisition_date=before_date,
            cloud_coverage=5.0,
            file_path=before_path,
            is_mock=True,
        )
        after_info = SceneInfo(
            scene_id=f"MOCK-{parcel_id[:8]}-AFTER",
            acquisition_date=after_date,
            cloud_coverage=5.0,
            file_path=after_path,
            is_mock=True,
        )
        return before_path, after_path, before_info, after_info

    # ─────────────────────────────────────────────────────────────────────────
    # Real Copernicus mode
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_real(
        self,
        parcel_id: str,
        parcel_dir: Path,
        bbox: tuple[float, float, float, float],
        cutoff_date: str,
    ) -> tuple[Path, Path, SceneInfo, SceneInfo]:
        """Download actual Sentinel-2 L2A scenes from CDSE."""
        import httpx

        token = self._get_access_token()

        # Search for before scene (6 months before cutoff)
        co = datetime.strptime(cutoff_date, "%Y-%m-%d")
        before_start = (co - timedelta(days=180)).strftime("%Y-%m-%d")
        before_end = cutoff_date

        # Search for after scene (last 12 months)
        after_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        after_end = datetime.now().strftime("%Y-%m-%d")

        before_product = self._search_best_product(token, bbox, before_start, before_end)
        after_product = self._search_best_product(token, bbox, after_start, after_end)

        if not before_product or not after_product:
            logger.warning("No Sentinel-2 products found for parcel %s, falling back to mock", parcel_id)
            return self._fetch_mock(parcel_id, parcel_dir, bbox, cutoff_date)

        before_path = self._download_bands(token, before_product, parcel_dir / "before.tif", bbox)
        after_path = self._download_bands(token, after_product, parcel_dir / "after.tif", bbox)

        before_info = SceneInfo(
            scene_id=before_product["Id"],
            acquisition_date=before_product.get("ContentDate", {}).get("Start", "")[:10],
            cloud_coverage=float(before_product.get("CloudCover", 0)),
            file_path=before_path,
        )
        after_info = SceneInfo(
            scene_id=after_product["Id"],
            acquisition_date=after_product.get("ContentDate", {}).get("Start", "")[:10],
            cloud_coverage=float(after_product.get("CloudCover", 0)),
            file_path=after_path,
        )
        return before_path, after_path, before_info, after_info

    def _get_access_token(self) -> str:
        import httpx

        resp = httpx.post(
            self.CDSE_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.copernicus_client_id,
                "client_secret": settings.copernicus_client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _search_best_product(
        self,
        token: str,
        bbox: tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        max_cloud: float = 20.0,
    ) -> dict[str, Any] | None:
        """Search CDSE OData for the lowest-cloud Sentinel-2 L2A product."""
        import httpx

        minx, miny, maxx, maxy = bbox
        wkt = f"POLYGON(({minx} {miny},{maxx} {miny},{maxx} {maxy},{minx} {maxy},{minx} {miny}))"

        params = {
            "$filter": (
                f"Collection/Name eq 'SENTINEL-2' "
                f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
                f"and att/OData.CSC.DoubleAttribute/Value le {max_cloud}) "
                f"and OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') "
                f"and ContentDate/Start ge {start_date}T00:00:00.000Z "
                f"and ContentDate/Start le {end_date}T23:59:59.000Z"
            ),
            "$orderby": "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover') asc",
            "$top": "1",
        }

        resp = httpx.get(
            f"{self.CDSE_ODATA_BASE}/Products",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
        return items[0] if items else None

    def _download_bands(
        self,
        token: str,
        product: dict[str, Any],
        output_path: Path,
        bbox: tuple[float, float, float, float],
    ) -> Path:
        """Download and crop a Sentinel-2 product to the parcel bbox."""
        if output_path.exists():
            logger.debug("Cache hit: %s", output_path)
            return output_path

        import httpx

        product_id = product["Id"]
        url = f"{self.CDSE_ODATA_BASE}/Products({product_id})/$value"

        # For MVP: download the full product zip and extract relevant bands
        # This is a simplified approach — production would use COG/STAC endpoints
        import tempfile, zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "product.zip"
            with httpx.stream(
                "GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=300
            ) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            with zipfile.ZipFile(zip_path) as zf:
                # Find B02, B04, B08, B8A, B11, B12 band files
                band_files = self._extract_bands(zf, Path(tmpdir))
                self._stack_and_crop_bands(band_files, output_path, bbox)

        return output_path

    def _extract_bands(self, zf, extract_dir: Path) -> dict[str, Path]:
        """Extract required band files from a Sentinel-2 zip archive."""
        required = {"B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"}
        band_files: dict[str, Path] = {}
        for name in zf.namelist():
            for band in required:
                # Match patterns like IMG_DATA/R10m/T_B02_10m.jp2
                if f"_{band}_" in name and name.endswith(".jp2"):
                    dest = extract_dir / f"{band}.jp2"
                    zf.extract(name, str(extract_dir))
                    extracted = extract_dir / name
                    extracted.rename(dest)
                    band_files[band] = dest
                    break
        return band_files

    def _stack_and_crop_bands(
        self, band_files: dict[str, Path], output_path: Path, bbox: tuple
    ) -> None:
        """Stack individual band files into a single multi-band GeoTIFF."""
        import rasterio
        from rasterio.merge import merge
        from rasterio.transform import from_bounds

        arrays = []
        meta = None
        for band_name in BAND_ORDER:
            if band_name not in band_files:
                continue
            with rasterio.open(band_files[band_name]) as src:
                if meta is None:
                    meta = src.meta.copy()
                # Resample all bands to 10m (B02 resolution)
                from rasterio.enums import Resampling
                data = src.read(
                    1,
                    out_shape=(512, 512),
                    resampling=Resampling.bilinear,
                )
                arrays.append(data)

        if not arrays or meta is None:
            raise RuntimeError("Could not extract required bands from product")

        stacked = np.stack(arrays, axis=0)
        meta.update(count=len(arrays), dtype="float32", nodata=0)
        with rasterio.open(output_path, "w", **meta) as dst:
            dst.write(stacked.astype(np.float32))

        logger.info("Saved stacked bands to %s", output_path)


# ─────────────────────────────────────────────────────────────────────────────
# Mock GeoTIFF writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_mock_geotiff(
    path: Path,
    bbox: tuple[float, float, float, float],
    cloud_fraction: float = 0.05,
    vegetation_ndvi: float = 0.6,
    size: int = 128,
) -> None:
    """Write a synthetic 10-band Sentinel-2-like GeoTIFF for testing."""
    try:
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.crs import CRS
    except ImportError:
        # Fallback: write a simple numpy array as npy
        np.save(str(path).replace(".tif", ".npy"), np.random.rand(NUM_BANDS, size, size))
        return

    rng = np.random.default_rng(seed=hash(str(path)) % (2**32))
    # Approximate Sentinel-2 reflectance values (0–10000 DN scale)
    # B02 (Blue), B03 (Green), B04 (Red), B08 (NIR), ...
    base_refl = {
        "B02": 0.08, "B03": 0.10, "B04": 0.07,
        "B08": 0.35,  # NIR
        "B05": 0.20, "B06": 0.28, "B07": 0.32, "B8A": 0.34,
        "B11": 0.15, "B12": 0.08,
    }

    # Adjust NIR/Red ratio to match target NDVI
    # NDVI = (NIR - Red) / (NIR + Red) = veg_ndvi
    # With Red = 0.07: NIR = Red * (1 + NDVI) / (1 - NDVI)
    red = base_refl["B04"]
    nir = red * (1 + vegetation_ndvi) / max(1 - vegetation_ndvi, 1e-5)
    nir = min(nir, 0.8)
    base_refl["B08"] = nir
    base_refl["B8A"] = nir * 0.95

    arrays = []
    for band in BAND_ORDER:
        base = base_refl.get(band, 0.10)
        noise = rng.normal(0, 0.01, (size, size))
        band_data = (np.full((size, size), base) + noise).clip(0, 1)
        # Add cloud pixels
        if cloud_fraction > 0:
            cloud_mask = rng.random((size, size)) < cloud_fraction
            band_data[cloud_mask] = rng.uniform(0.3, 0.9, cloud_mask.sum())
        arrays.append((band_data * 10_000).astype(np.float32))

    stacked = np.stack(arrays, axis=0)  # (10, H, W)
    transform = from_bounds(*bbox, width=size, height=size)

    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=size, width=size,
        count=NUM_BANDS,
        dtype="float32",
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=0,
    ) as dst:
        dst.write(stacked)

    logger.debug("Mock GeoTIFF written: %s (NDVI≈%.2f, cloud=%.0f%%)", path, vegetation_ndvi, cloud_fraction * 100)
