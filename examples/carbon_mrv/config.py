"""CarbonLandCoverConfig: IPCC Tier-2 land cover and carbon density parameters."""

from dataclasses import dataclass, field


@dataclass
class CarbonLandCoverConfig:
    """IPCC Tier-2 land cover classes with carbon density and display colours.

    Attributes:
        class_names: Ordered list of 11 land cover names.
        carbon_density_agb: Above-ground biomass carbon (Mg C/ha) per class.
        carbon_density_bgb: Below-ground biomass carbon (Mg C/ha) per class.
        hex_colors: HEX display colours for map rendering.
    """

    class_names: list[str] = field(default_factory=lambda: [
        "Tropical Forest", "Temperate Forest", "Boreal Forest",
        "Shrubland", "Grassland", "Cropland", "Wetland",
        "Settlement", "Bare Land", "Water Body", "Permanent Snow/Ice",
    ])

    carbon_density_agb: list[float] = field(default_factory=lambda: [
        200.0, 120.0, 80.0, 18.0, 3.5, 5.0, 50.0, 0.0, 0.0, 0.0, 0.0,
    ])

    carbon_density_bgb: list[float] = field(default_factory=lambda: [
        52.0, 31.2, 20.8, 4.7, 0.9, 1.3, 13.0, 0.0, 0.0, 0.0, 0.0,
    ])

    hex_colors: list[str] = field(default_factory=lambda: [
        "#1A6B1A", "#4CA64C", "#8FBC8F", "#D2B48C", "#98FB98",
        "#FFD700", "#4169E1", "#FF4500", "#D2691E", "#00BFFF", "#E0E0E0",
    ])

    @property
    def num_classes(self) -> int:
        """Return number of land cover classes."""
        return len(self.class_names)

    def total_carbon(self, class_idx: int) -> float:
        """Return total carbon density (AGB + BGB) for a class.

        Args:
            class_idx: Land cover class index.

        Returns:
            Total carbon density in Mg C/ha.
        """
        return self.carbon_density_agb[class_idx] + self.carbon_density_bgb[class_idx]
