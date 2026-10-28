from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.ao02_state_and_graph import PipelinePhase, ResourceType


class DTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SeverityStatus(StrEnum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class GridPosition(DTO):
    row: int = Field(ge=0)
    col: int = Field(ge=0)


class RackLayout(DTO):
    rack_id: str
    grid_position: GridPosition


class RackSpatialNode(RackLayout):
    status: SeverityStatus
    active_badge: ResourceType | None = None
    power_load_kw: float = Field(ge=0)
    max_power_kw: float = Field(gt=0)
    active_token_ids: list[str] = Field(default_factory=list)


class CoolingUnitNode(DTO):
    unit_id: str
    supply_temp_celsius: float
    fan_speed_rpm: float = Field(ge=0)
    status: SeverityStatus


class QueuedIncidentTokenDTO(DTO):
    token_id: str
    priority_number: int = Field(ge=0)
    rack_id: str
    tenant_id: str | None
    resource_type: ResourceType
    current_phase: PipelinePhase
    utilization_pct: float = Field(ge=0, le=100)
    lead_time_weeks: float | None = Field(default=None, ge=0)
    hop_count: int = Field(ge=0)


class BootstrapDTO(DTO):
    app_name: str
    milestone: Literal[1] = 1
    data_mode: Literal["reference-layout"] = "reference-layout"
    telemetry_available: Literal[False] = False
    resources: list[ResourceType]
    racks: list[RackLayout]
    cooling_units: list[str]


class HealthDTO(DTO):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
