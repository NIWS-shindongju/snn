"""CLI tool to download Sentinel-2 products from Copernicus Data Space.

Usage:
    python scripts/download_sentinel2.py \\
        --bbox -55.0 -5.0 -50.0 -1.0 \\
        --start 2024-01-01 \\
        --end 2024-03-31 \\
        --max-products 3 \\
        --output-dir ./data/sentinel2
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from carbonsnn.config import get_settings
from carbonsnn.data.sentinel2 import SentinelDownloader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async(args: argparse.Namespace) -> None:
    """Async download implementation.

    Args:
        args: Parsed CLI arguments.
    """
    settings = get_settings()

    if not settings.copernicus_client_id or not settings.copernicus_client_secret:
        logger.error(
            "Copernicus credentials not configured. "
            "Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET in .env"
        )
        sys.exit(1)

    downloader = SentinelDownloader(
        output_dir=args.output_dir,
        max_cloud_cover=args.max_cloud_cover,
    )

    bbox = args.bbox  # [west, south, east, north]
    logger.info(
        "Searching for Sentinel-2 products: bbox=%s dates=%s–%s max_cloud=%.1f%%",
        bbox,
        args.start,
        args.end,
        args.max_cloud_cover,
    )

    # Search
    products = await downloader.search(
        bbox=bbox,
        start_date=args.start,
        end_date=args.end,
        max_results=args.max_products * 2,  # search more to filter by cloud cover
    )

    if not products:
        logger.warning("No products found matching criteria.")
        return

    logger.info("Found %d product(s):", len(products))
    for i, p in enumerate(products[: args.max_products]):
        logger.info(
            "  [%d] %s | %s | cloud=%.1f%% | %.1f MB",
            i + 1,
            p.name,
            p.sensing_date.strftime("%Y-%m-%d"),
            p.cloud_cover,
            p.size_mb,
        )

    if args.dry_run:
        logger.info("Dry run — no files downloaded.")
        return

    # Download
    downloaded: list[Path] = []
    for product in products[: args.max_products]:
        try:
            path = await downloader.download(product, dest_dir=args.output_dir)
            downloaded.append(path)
        except Exception as exc:
            logger.error("Failed to download %s: %s", product.name, exc)

    logger.info("Downloaded %d/%d products to %s", len(downloaded), args.max_products, args.output_dir)
    for path in downloaded:
        logger.info("  → %s (%d MB)", path.name, path.stat().st_size // 1_048_576)


def main() -> None:
    """Parse arguments and run download."""
    parser = argparse.ArgumentParser(description="Download Sentinel-2 L2A products from Copernicus")
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        required=True,
        help="Bounding box in EPSG:4326",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date (ISO-8601, e.g. 2024-01-01)",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End date (ISO-8601, e.g. 2024-03-31)",
    )
    parser.add_argument(
        "--max-products",
        type=int,
        default=3,
        help="Maximum number of products to download (default: 3)",
    )
    parser.add_argument(
        "--max-cloud-cover",
        type=float,
        default=20.0,
        help="Maximum cloud cover percentage (default: 20.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/sentinel2",
        help="Output directory for downloaded files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search only, do not download",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
