"""download_sentinel2.py: Download Sentinel-2 L2A products from Copernicus.

Credentials are loaded from COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET
environment variables (not SPIKEEO_ prefixed — these are Copernicus-specific).

Usage:
    COPERNICUS_CLIENT_ID=xxx COPERNICUS_CLIENT_SECRET=yyy \\
    python scripts/download_sentinel2.py \\
        --bbox -60 -10 -50 0 \\
        --start 2024-01-01 --end 2024-03-31 \\
        --output ./data/sentinel2/
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


async def download(
    bbox: list[float],
    start_date: str,
    end_date: str,
    output_dir: str,
    max_products: int = 3,
) -> None:
    """Search and download Sentinel-2 products.

    Args:
        bbox: [west, south, east, north] bounding box.
        start_date: ISO-8601 start date.
        end_date: ISO-8601 end date.
        output_dir: Output directory for downloads.
        max_products: Maximum number of products to download.
    """
    client_id = os.environ.get("COPERNICUS_CLIENT_ID", "")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.error(
            "Copernicus credentials not set. "
            "Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET environment variables."
        )
        return

    # Use the existing sentinel2 downloader from carbonsnn (kept for compatibility)
    # or implement a direct httpx-based downloader here.
    logger.info("Searching Copernicus for products: bbox=%s dates=%s to %s", bbox, start_date, end_date)
    logger.info("Output directory: %s", output_dir)
    logger.info("Note: Implement SentinelDownloader here for actual downloads.")


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Download Sentinel-2 products")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), required=True)
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="./data/sentinel2/")
    parser.add_argument("--max-products", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(download(
        bbox=args.bbox,
        start_date=args.start,
        end_date=args.end,
        output_dir=args.output,
        max_products=args.max_products,
    ))


if __name__ == "__main__":
    main()
