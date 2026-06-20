"""Typed project configuration."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class FetchConfig(BaseModel):
    start_date: date = date(2023, 1, 1)
    end_date: date | None = None
    timeout_seconds: float = Field(default=30, gt=0)
    max_retries: int = Field(default=4, ge=0)
    page_size: int = Field(default=1000, ge=1, le=1000)


class PathsConfig(BaseModel):
    raw: Path = Path("data/raw")
    interim: Path = Path("data/interim")
    processed: Path = Path("data/processed")
    figures: Path = Path("reports/figures")
    tables: Path = Path("reports/tables")

    def resolve(self, root: Path) -> PathsConfig:
        values = {
            name: value if value.is_absolute() else root / value
            for name, value in self.model_dump().items()
        }
        return PathsConfig(**values)


class ProjectConfig(BaseModel):
    project_name: str
    source: str = "kalshi"
    series_id: str = "KXHIGHNY"
    category: str = "Weather"
    candle_interval_minutes: int = 60
    forecast_horizons_hours: list[int] = [24, 12, 6, 1]
    efficiency_horizons_hours: list[int] = [1, 6]
    max_staleness_hours: float = 2
    minimum_training_events: int = 60
    calibration_bins: int = 10
    bootstrap_iterations: int = 1000
    random_seed: int = 20260619
    fetch: FetchConfig = FetchConfig()
    paths: PathsConfig = PathsConfig()
    root: Path = Path(".")

    @model_validator(mode="after")
    def validate_research_parameters(self) -> ProjectConfig:
        if self.source != "kalshi":
            raise ValueError("The MVP supports source='kalshi' only")
        if self.candle_interval_minutes not in {1, 60, 1440}:
            raise ValueError("Kalshi candle interval must be 1, 60, or 1440 minutes")
        if not self.forecast_horizons_hours or min(self.forecast_horizons_hours) <= 0:
            raise ValueError("Forecast horizons must be positive")
        return self

    def ensure_output_directories(self) -> None:
        for path in self.paths.model_dump().values():
            Path(path).mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path = "config/mvp.yaml") -> ProjectConfig:
    """Load YAML and resolve data/report paths relative to the repository root."""
    config_path = Path(path).resolve()
    payload = yaml.safe_load(config_path.read_text())
    root = config_path.parent.parent
    payload["root"] = root
    config = ProjectConfig.model_validate(payload)
    config.paths = config.paths.resolve(root)
    return config
