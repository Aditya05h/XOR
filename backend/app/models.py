from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from app.core.ao02_state_and_graph import ResourceType, PipelinePhase, GateDecision

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, validate_assignment=True)

class TelemetryWindowSummary(Model):
    window_start: AwareDatetime
    window_end: AwareDatetime
    rack_id: str
    tenant_id: str | None
    resource_type: ResourceType
    current_utilization_pct: float = Field(ge=0, le=100)
    safety_margin_pct: float = Field(ge=0, le=100)
    hard_capacity_limit: float = Field(gt=0)
    unit: str
    raw_series_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    @model_validator(mode='after')
    def ordered(self):
        if self.window_end < self.window_start: raise ValueError('window end precedes start')
        return self

class CapacityForecast(Model):
    predicted_exhaustion_date: AwareDatetime | None = None
    lead_time_weeks: float | None = Field(default=None, ge=0)
    confidence_interval_days: tuple[float, float] | None = None
    forecast_confidence_score: float | None = Field(default=None, ge=0, le=1)
    is_transient_spike: bool = False
    regime_change_detected: bool = False
    regime_change_description: str | None = None
    @model_validator(mode='after')
    def interval(self):
        if self.confidence_interval_days and not 0 <= self.confidence_interval_days[0] <= self.confidence_interval_days[1]:
            raise ValueError('invalid confidence interval')
        return self

class RCADiagnosis(Model):
    root_cause_summary: str
    attributed_tenant_id: str | None = None
    driving_workload_signature: str | None = None
    correlated_signals: list[str] = Field(default_factory=list)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    investigation_notes: str

class RemediationOption(Model):
    option_id: str
    title: str
    recommended_action: str
    simulated_post_action_utilization_pct: float = Field(ge=0, le=100)
    projected_lead_time_extension_weeks: float = Field(ge=0)
    simulation_assumptions: str = Field(min_length=1)
    mutates_live_facility_controls: Literal[False] = False

class RiskEvaluation(Model):
    risk_score: float = Field(ge=0, le=1)
    blast_radius_summary: str
    sla_impact_assessment: str
    gate_decision: GateDecision
    selected_option_id: str

class AuditTrailRecord(Model):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_id: str
    phase: PipelinePhase
    actor: str
    telemetry_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision_summary: str
    model_configuration_id: str

class IncidentToken(Model):
    token_id: str = Field(default_factory=lambda: str(uuid4()))
    priority_number: int = Field(ge=1, le=100)
    rack_id: str
    tenant_id: str | None
    resource_type: ResourceType
    current_phase: PipelinePhase = PipelinePhase.RESOURCE_MONITORING
    hop_count: int = Field(default=0, ge=0)
    max_allowed_hops: int = Field(default=8, ge=1, le=100)
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class HeapIncidentEnvelope(Model):
    token: IncidentToken
    telemetry: TelemetryWindowSummary
    forecast: CapacityForecast = Field(default_factory=CapacityForecast)
    rca: RCADiagnosis | None = None
    remediation_options: list[RemediationOption] = Field(default_factory=list)
    risk_evaluation: RiskEvaluation | None = None
    human_approved: bool | None = None
    operator_notes: str = ''
    audit_trail: list[AuditTrailRecord] = Field(default_factory=list)
    @model_validator(mode='after')
    def consistent(self):
        if any(getattr(self.token,k) != getattr(self.telemetry,k) for k in ('rack_id','tenant_id','resource_type')):
            raise ValueError('token and telemetry scope differ')
        if self.risk_evaluation and self.risk_evaluation.selected_option_id not in {o.option_id for o in self.remediation_options}:
            raise ValueError('selected remediation option does not exist')
        return self
