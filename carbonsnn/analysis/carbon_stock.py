"""IPCC Tier-2 carbon stock estimation from land cover classification.

Estimates Above-Ground Biomass (AGB) and Below-Ground Biomass (BGB)
carbon stocks from classified pixel arrays, with uncertainty ranges.
"""

import logging
from dataclasses import dataclass

import numpy as np

from carbonsnn.config import get_settings
from carbonsnn.models.carbon_snn import CarbonLandCoverConfig

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Result dataclasses
# ──────────────────────────────────────────────────────────

@dataclass
class CarbonStockResult:
    """Total carbon stock estimate for a classified scene.

    Attributes:
        total_agb_mg: Total above-ground biomass carbon (Mg C).
        total_bgb_mg: Total below-ground biomass carbon (Mg C).
        total_carbon_mg: Sum of AGB and BGB (Mg C).
        area_ha: Total analysed area (ha).
        carbon_density_mg_ha: Mean carbon density (Mg C/ha).
        uncertainty_low: Lower bound of uncertainty range (Mg C).
        uncertainty_high: Upper bound of uncertainty range (Mg C).
        class_breakdown: Per-class area (ha) and carbon (Mg C).
        climate_zone: Detected climate zone ('tropical'/'temperate'/'boreal').
    """

    total_agb_mg: float
    total_bgb_mg: float
    total_carbon_mg: float
    area_ha: float
    carbon_density_mg_ha: float
    uncertainty_low: float
    uncertainty_high: float
    class_breakdown: dict[str, dict[str, float]]
    climate_zone: str


@dataclass
class CarbonChangeImpact:
    """Carbon impact of a deforestation event.

    Attributes:
        area_ha: Deforested area (ha).
        carbon_lost_mg: Estimated carbon released (Mg C).
        co2_equivalent_mg: CO2-equivalent (Mg CO2e = C × 3.667).
        uncertainty_low: Lower uncertainty bound.
        uncertainty_high: Upper uncertainty bound.
        climate_zone: Climate zone of the affected area.
    """

    area_ha: float
    carbon_lost_mg: float
    co2_equivalent_mg: float
    uncertainty_low: float
    uncertainty_high: float
    climate_zone: str


# ──────────────────────────────────────────────────────────
# Estimator
# ──────────────────────────────────────────────────────────

class CarbonStockEstimator:
    """Estimate carbon stocks using IPCC Tier-2 default factors.

    Args:
        config: Land cover configuration with carbon density tables.
        pixel_size_m: Ground sampling distance (default 10 m).
        uncertainty_pct: Fractional uncertainty (default 20 %).
    """

    C_TO_CO2: float = 3.667   # Molecular mass ratio CO2/C

    def __init__(
        self,
        config: CarbonLandCoverConfig | None = None,
        pixel_size_m: float = 10.0,
        uncertainty_pct: float = 0.20,
    ) -> None:
        settings = get_settings()
        self.config = config or CarbonLandCoverConfig()
        self.pixel_size_m = pixel_size_m
        self.uncertainty_pct = uncertainty_pct
        self._ha_per_pixel = (pixel_size_m / 100.0) ** 2  # 10 m → 0.01 ha

    # ── Climate zone detection ────────────────────────────────

    def detect_climate_zone(self, latitude: float) -> str:
        """Infer IPCC climate zone from latitude.

        Args:
            latitude: Decimal latitude of the scene centroid.

        Returns:
            'tropical' | 'temperate' | 'boreal'
        """
        abs_lat = abs(latitude)
        if abs_lat <= 23.5:
            return "tropical"
        if abs_lat <= 60.0:
            return "temperate"
        return "boreal"

    # ── Core estimation ───────────────────────────────────────

    def estimate_total_stock(
        self,
        class_map: np.ndarray,
        latitude: float = 0.0,
    ) -> CarbonStockResult:
        """Estimate total carbon stock from a classified pixel map.

        Args:
            class_map: Integer array (H, W) with land cover class indices.
            latitude: Scene centroid latitude for climate zone detection.

        Returns:
            CarbonStockResult with total and per-class breakdowns.
        """
        climate_zone = self.detect_climate_zone(latitude)
        logger.info("Estimating carbon stock | zone=%s", climate_zone)

        total_agb = 0.0
        total_bgb = 0.0
        breakdown: dict[str, dict[str, float]] = {}

        for cls_idx, cls_name in enumerate(self.config.class_names):
            pixel_count = int(np.sum(class_map == cls_idx))
            area_ha = pixel_count * self._ha_per_pixel
            agb_density = self.config.carbon_density_agb[cls_idx]
            bgb_density = self.config.carbon_density_bgb[cls_idx]

            agb_stock = area_ha * agb_density
            bgb_stock = area_ha * bgb_density

            total_agb += agb_stock
            total_bgb += bgb_stock

            breakdown[cls_name] = {
                "area_ha": round(area_ha, 4),
                "agb_mg_c": round(agb_stock, 4),
                "bgb_mg_c": round(bgb_stock, 4),
                "total_carbon_mg_c": round(agb_stock + bgb_stock, 4),
            }

        total_carbon = total_agb + total_bgb
        total_area = float(class_map.size) * self._ha_per_pixel
        density = total_carbon / max(total_area, 1e-6)

        return CarbonStockResult(
            total_agb_mg=round(total_agb, 4),
            total_bgb_mg=round(total_bgb, 4),
            total_carbon_mg=round(total_carbon, 4),
            area_ha=round(total_area, 4),
            carbon_density_mg_ha=round(density, 4),
            uncertainty_low=round(total_carbon * (1 - self.uncertainty_pct), 4),
            uncertainty_high=round(total_carbon * (1 + self.uncertainty_pct), 4),
            class_breakdown=breakdown,
            climate_zone=climate_zone,
        )

    def estimate_change_impact(
        self,
        area_ha: float,
        from_class: int,
        to_class: int,
        latitude: float = 0.0,
    ) -> CarbonChangeImpact:
        """Estimate carbon released by land cover conversion.

        Args:
            area_ha: Area converted (ha).
            from_class: Source land cover class index.
            to_class: Destination land cover class index.
            latitude: Scene latitude for climate zone.

        Returns:
            CarbonChangeImpact with CO2-equivalent emission estimate.
        """
        climate_zone = self.detect_climate_zone(latitude)
        from_carbon = self.config.total_carbon(from_class) * area_ha
        to_carbon = self.config.total_carbon(to_class) * area_ha
        carbon_lost = max(0.0, from_carbon - to_carbon)
        co2_eq = carbon_lost * self.C_TO_CO2

        logger.info(
            "Carbon change: %.2f ha %s→%s, lost=%.2f Mg C, CO2e=%.2f Mg",
            area_ha,
            self.config.class_names[from_class],
            self.config.class_names[to_class],
            carbon_lost,
            co2_eq,
        )
        return CarbonChangeImpact(
            area_ha=round(area_ha, 4),
            carbon_lost_mg=round(carbon_lost, 4),
            co2_equivalent_mg=round(co2_eq, 4),
            uncertainty_low=round(carbon_lost * (1 - self.uncertainty_pct), 4),
            uncertainty_high=round(carbon_lost * (1 + self.uncertainty_pct), 4),
            climate_zone=climate_zone,
        )

    def uncertainty_range(
        self, central_estimate: float, method: str = "ipcc_tier2"
    ) -> tuple[float, float]:
        """Return (low, high) uncertainty bounds.

        Args:
            central_estimate: Central value (Mg C or Mg CO2e).
            method: Uncertainty method ('ipcc_tier2' = ±20%).

        Returns:
            Tuple (low, high).
        """
        pct = self.uncertainty_pct if method == "ipcc_tier2" else 0.30
        return (
            round(central_estimate * (1 - pct), 4),
            round(central_estimate * (1 + pct), 4),
        )
