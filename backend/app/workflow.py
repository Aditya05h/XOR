"""Executable six-phase LangGraph workflow with durable SQLite human interrupts."""
from contextlib import contextmanager
from typing import TypedDict, Literal
from uuid import uuid4
import json
import time
from math import sqrt
from statistics import mean
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from app.models import HeapIncidentEnvelope, RCADiagnosis, RemediationOption, RiskEvaluation, AuditTrailRecord
from app.core.ao02_state_and_graph import PipelinePhase as Phase, GateDecision
from app.providers import ExplanationProvider
from app.forecasting import MODEL_ID

class AO02AgentState(TypedDict, total=False):
    active_token_id: str
    current_phase: str
    hop_count: int
    should_halt: bool
    halt_reason: str | None
    awaiting_human_verification: bool
    deferred: bool

class WorkflowBusy(ValueError): pass

class WorkflowEngine:
    def __init__(self, heap, settings=None):
        self.heap = heap
        self.provider = ExplanationProvider()
        self.checkpoint_path = heap.path + '.checkpoints.sqlite3'
        with heap.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS workflow_leases (token TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)')

    @contextmanager
    def _lease(self, token):
        owner = str(uuid4())
        with self.heap.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM workflow_leases WHERE expires < ?', (time.time(),))
            try: db.execute('INSERT INTO workflow_leases VALUES (?,?,?)', (token, owner, time.time()+120))
            except Exception as exc: raise WorkflowBusy('Incident workflow is already processing') from exc
        try: yield
        finally:
            with self.heap.connection() as db: db.execute('DELETE FROM workflow_leases WHERE token=? AND owner=?', (token,owner))

    def _save(self, token, phase, actor, summary, mutate=None, terminal=False, increment=True):
        with self.heap.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT envelope,active FROM incidents WHERE id=?', (token,)).fetchone()
            if not row: raise KeyError(token)
            env = HeapIncidentEnvelope.model_validate_json(row[0])
            if not row[1]: return env
            if env.token.current_phase == Phase.HALTED_LOOP_GUARD: return env
            # Node replay after checkpoint interruption must not duplicate effects.
            exists = db.execute('SELECT 1 FROM audit WHERE token=? AND json_extract(record,\'$.actor\')=?', (token,actor)).fetchone()
            if exists and actor != 'human-defer': return env
            if increment: env.token.hop_count += 1
            if env.token.hop_count > env.token.max_allowed_hops:
                env.token.current_phase = Phase.HALTED_LOOP_GUARD
                actor,summary = 'loop-guard','Workflow stopped at maximum permitted transitions'
                terminal = False
            else:
                env.token.current_phase = phase
                if mutate: mutate(env)
            record=AuditTrailRecord(token_id=token,phase=env.token.current_phase,actor=actor,
                telemetry_hash=env.telemetry.raw_series_sha256,decision_summary=summary,
                model_configuration_id=f'ao02-workflow-v1|forecast={MODEL_ID}')
            env.audit_trail=[]
            db.execute('UPDATE incidents SET envelope=?,queued=0,active=? WHERE id=?', (env.model_dump_json(),0 if terminal else 1,token))
            db.execute('INSERT INTO audit(token,record) VALUES (?,?)', (token,record.model_dump_json()))
            return env

    def _state(self, env):
        halted=env.token.current_phase == Phase.HALTED_LOOP_GUARD
        return dict(active_token_id=env.token.token_id,current_phase=env.token.current_phase.value,
            hop_count=env.token.hop_count,should_halt=halted,
            halt_reason='Transition limit exceeded' if halted else None,
            awaiting_human_verification=env.token.current_phase == Phase.HUMAN_VERIFICATION)

    def _report(self, state):
        env=self._save(state['active_token_id'],Phase.INCIDENT_REPORTING,'incident-reporting','Formal read-only capacity incident report created')
        return self._state(env)

    def _rca(self, state):
        token=state['active_token_id']; env=self.heap.get_envelope_for_agent(token)
        with self.heap.connection() as db:
            row=db.execute('SELECT series FROM snapshots WHERE hash=?',(env.telemetry.raw_series_sha256,)).fetchone()
        series=json.loads(row[0]) if row else []
        growth=(series[-1]['utilization_pct']-series[max(0,len(series)-30)]['utilization_pct']) if series else 0
        workloads=sorted({p.get('workload_id','unattributed') for p in series})
        evidence={'utilization':f'Observed {env.telemetry.resource_type.value} utilization is {env.telemetry.current_utilization_pct:.2f}%.',
                  'trend':f'Observed change over the last available 30 observations is {growth:.2f} percentage points.',
                  'scope':f'Telemetry scope is {env.token.rack_id}, tenant {env.token.tenant_id or "facility"}.'}
        evidence.update(self._correlations(series, env))
        explanation=self.provider.explain(evidence)
        def update(e):
            e.rca=RCADiagnosis(root_cause_summary=explanation['summary'],attributed_tenant_id=e.token.tenant_id,
                driving_workload_signature=', '.join(workloads) if workloads else None,
                correlated_signals=list(evidence.values()),confidence_score=None,
                investigation_notes=json.dumps(explanation)+' Attribution identifies the measured source, not a proven physical cause.')
        return self._state(self._save(token,Phase.ROOT_CAUSE_ANALYSIS,'rca', 'Evidence-grounded attribution; explanation source: '+explanation['source'],update))

    def _correlations(self, series, env):
        """Only correlate measured same-rack/same-tenant windows at matching times."""
        reference={p['timestamp']:p['utilization_pct'] for p in series[-30:] if 'utilization_pct' in p}
        if len(reference)<7: return {'correlation_limit':'Insufficient matched observations for cross-resource correlation.'}
        with self.heap.connection() as db: snapshots=db.execute('SELECT hash,series FROM snapshots WHERE hash!=?',(env.telemetry.raw_series_sha256,)).fetchall()
        candidates={}
        for digest,raw in snapshots:
            points=json.loads(raw)
            if not points: continue
            first=points[0]
            resource=first.get('resource_type')
            if first.get('rack_id')!=env.token.rack_id or first.get('tenant_id')!=env.token.tenant_id or resource==env.token.resource_type.value: continue
            matched=[(reference[p['timestamp']],p['utilization_pct']) for p in points if p.get('timestamp') in reference and 'utilization_pct' in p]
            if len(matched)<7: continue
            xs,ys=zip(*matched); mx,my=mean(xs),mean(ys)
            denominator=sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
            if not denominator: continue
            coefficient=sum((x-mx)*(y-my) for x,y in matched)/denominator
            if abs(coefficient)>=.7 and (resource not in candidates or len(matched)>candidates[resource][0]):
                candidates[resource]=(len(matched),f'{resource} same-rack/same-tenant correlation r={coefficient:.3f} over {len(matched)} matched observations; source snapshot {digest}. Correlation is not causation.')
        return {f'correlation_{i}':item[1] for i,item in enumerate(candidates.values())} or {'correlation_limit':'No strong same-rack/same-tenant correlation supported by available stored windows.'}

    def _remediate(self, state):
        token=state['active_token_id']; env=self.heap.get_envelope_for_agent(token)
        with self.heap.connection() as db:
            row=db.execute('SELECT series FROM snapshots WHERE hash=?',(env.telemetry.raw_series_sha256,)).fetchone()
        series=json.loads(row[0]) if row else []
        days=max(1,len(series[-30:])-1)
        slope=max(0,(series[-1]['utilization_pct']-series[-min(30,len(series))]['utilization_pct'])/days) if series else 0
        def update(e):
            options=[]
            for reduction in (10,20):
                post=max(0,e.telemetry.current_utilization_pct-reduction)
                extension=(e.telemetry.current_utilization_pct-post)/slope/7 if slope>0 else 0
                options.append(RemediationOption(option_id=f'reduce-{reduction}',title=f'Model {reduction}-point utilization reduction',
                    recommended_action='Review workload demand reduction or capacity planning with the authorized owner. Advisory only.',
                    simulated_post_action_utilization_pct=round(post,3),projected_lead_time_extension_weeks=round(extension,3),
                    simulation_assumptions=f'Hypothetical instantaneous {reduction} percentage-point demand reduction; observed recent slope {slope:.5f} percentage points/day persists. No feasibility or zero downtime claim. A zero extension means no positive trend was supported.'))
            e.remediation_options=options
        return self._state(self._save(token,Phase.REMEDIATION_CHECKING,'remediation','Calculated two offline what-if demand reduction scenarios',update))

    def _risk(self, state):
        def update(e):
            score=min(1,.25+e.telemetry.current_utilization_pct/200+(.15 if e.rca is None else 0))
            e.risk_evaluation=RiskEvaluation(risk_score=round(score,3),blast_radius_summary=f'Proposed scope: {e.token.rack_id}, {e.token.tenant_id or "facility"}. Dependency blast radius is unverified.',
                sla_impact_assessment='Feasibility and SLA effects require operator investigation before any external action.',
                gate_decision=GateDecision.REQUIRE_HUMAN_APPROVAL,selected_option_id=e.remediation_options[0].option_id)
        return self._state(self._save(state['active_token_id'],Phase.RISK_ANALYSIS,'risk','Heuristic risk rubric: 0.25 uncertainty + utilization/200; human approval required',update))

    def _prepare_review(self, state):
        token=state['active_token_id']
        env=self._save(token,Phase.HUMAN_VERIFICATION,'human-review','Paused for explicit operator approval, rejection or deferral')
        return self._state(env)

    def _review(self, state):
        token=state['active_token_id']
        env=self.heap.get_envelope_for_agent(token)
        if env.token.current_phase == Phase.HALTED_LOOP_GUARD: return self._state(env)
        decision=interrupt({'token_id':token,'message':'Advisory review required; no facility controls will be changed','choices':['approve','reject','defer']})
        action,notes=decision['decision'],decision['notes']
        if action=='defer':
            def defer(e):
                e.operator_notes=notes; e.human_approved=None
                e.risk_evaluation.gate_decision=GateDecision.DEFERRED_BY_OPERATOR
            env=self._save(token,Phase.HUMAN_VERIFICATION,'human-defer','Operator deferred advisory review',defer,increment=False)
            return {**self._state(env),'deferred':True}
        def finish(e):
            e.human_approved=action=='approve'; e.operator_notes=notes
            e.risk_evaluation.gate_decision=GateDecision.APPROVED_BY_OPERATOR if action=='approve' else GateDecision.REJECTED_BY_OPERATOR
        env=self._save(token,Phase.RESOLVED,'human-decision',f'Operator {action} recorded; advisory workflow completed, underlying capacity risk not asserted resolved',finish,terminal=True)
        return {**self._state(env),'deferred':False}

    def _builder(self, saver):
        graph=StateGraph(AO02AgentState)
        for name,node in [('report',self._report),('rca',self._rca),('remediation',self._remediate),('risk',self._risk),('prepare_review',self._prepare_review),('review',self._review)]: graph.add_node(name,node)
        graph.add_edge(START,'report')
        for source,target in [('report','rca'),('rca','remediation'),('remediation','risk'),('risk','prepare_review'),('prepare_review','review')]:
            graph.add_conditional_edges(source,lambda s: 'halt' if s['should_halt'] else 'next',{'halt':END,'next':target})
        graph.add_conditional_edges('review',lambda s: 'review' if s.get('deferred') and not s['should_halt'] else 'end',{'review':'review','end':END})
        return graph.compile(checkpointer=saver)

    def status(self, token_id):
        env=self.heap.get_envelope_for_agent(token_id)
        return {**self._state(env),'envelope':env.model_dump(mode='json'),'analysis_source':'local statistical analysis and deterministic evidence explanation; no external gateway'}

    def run(self, token_id):
        with self._lease(token_id), SqliteSaver.from_conn_string(self.checkpoint_path) as saver:
            env=self.heap.get_envelope_for_agent(token_id)
            if env.token.current_phase in (Phase.RESOLVED,Phase.HALTED_LOOP_GUARD): return self.status(token_id)
            graph=self._builder(saver); config={'configurable':{'thread_id':token_id},'recursion_limit':20}
            saved=graph.get_state(config)
            if saved.tasks and any(task.interrupts for task in saved.tasks): return self.status(token_id)
            graph.invoke(None if saved.values else self._state(env),config)
        return self.status(token_id)

    def decide(self, token_id, decision, notes=''):
        if decision not in ('approve','reject','defer'): raise ValueError('Decision must be approve, reject or defer')
        if not isinstance(notes,str) or len(notes)>4000: raise ValueError('Operator notes must be at most 4000 characters')
        with self._lease(token_id), SqliteSaver.from_conn_string(self.checkpoint_path) as saver:
            graph=self._builder(saver); config={'configurable':{'thread_id':token_id},'recursion_limit':20}
            saved=graph.get_state(config)
            if not saved.tasks or not any(task.interrupts for task in saved.tasks): raise ValueError('Incident is not paused for human verification')
            graph.invoke(Command(resume={'decision':decision,'notes':notes}),config)
        return self.status(token_id)


def build_ao02_workflow_blueprint(engine, checkpointer):
    return engine._builder(checkpointer)
