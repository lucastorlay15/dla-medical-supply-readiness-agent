from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict


@dataclass(frozen=True)
class ScaleProfile:
    customers: int
    items: int
    suppliers: int
    active_items_per_customer: int
    history_days: int
    orders: int
    supplier_events: int


SCALE_PROFILES: Dict[str, ScaleProfile] = {
    # Fast smoke test for development.
    "tiny": ScaleProfile(
        customers=20,
        items=120,
        suppliers=30,
        active_items_per_customer=45,
        history_days=180,
        orders=25_000,
        supplier_events=8,
    ),
    # Recommended interview/demo profile: millions of Delta rows, but still practical.
    "demo": ScaleProfile(
        customers=120,
        items=500,
        suppliers=120,
        active_items_per_customer=100,
        history_days=540,
        orders=500_000,
        supplier_events=30,
    ),
    # Optional stress profile. Use only if workspace capacity/cost is acceptable.
    "large": ScaleProfile(
        customers=300,
        items=1_000,
        suppliers=300,
        active_items_per_customer=200,
        history_days=730,
        orders=3_000_000,
        supplier_events=80,
    ),
}


@dataclass(frozen=True)
class GenerationConfig:
    catalog_name: str
    schema_name: str
    as_of_date: date
    scale_name: str = "demo"
    seed: int = 42

    @property
    def profile(self) -> ScaleProfile:
        if self.scale_name not in SCALE_PROFILES:
            raise ValueError(
                f"Unknown scale '{self.scale_name}'. Choose one of {sorted(SCALE_PROFILES)}."
            )
        return SCALE_PROFILES[self.scale_name]

    @property
    def start_date(self) -> date:
        return self.as_of_date - timedelta(days=self.profile.history_days - 1)

    def table_name(self, table: str) -> str:
        return f"{self.catalog_name}.{self.schema_name}.{table}"
