"""SQLite is the source of truth; each queue claim uses an atomic write transaction."""
import heapq
import sqlite3
from datetime import timezone
from contextlib import contextmanager
from app.models import HeapIncidentEnvelope, AuditTrailRecord
from app.core.ao02_state_and_graph import PipelinePhase, ResourceType

class SharedContextHeap:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS incidents (
              id TEXT PRIMARY KEY, scope TEXT NOT NULL, active INTEGER NOT NULL,
              queued INTEGER NOT NULL, priority INTEGER NOT NULL, created TEXT NOT NULL,
              envelope TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS active_scope ON incidents(scope) WHERE active=1;
            CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, token TEXT NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (hash TEXT PRIMARY KEY, series TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
            CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
            ''')
    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db: yield db
        finally: db.close()
    def _save(self, db, envelope, actor, summary):
        record = AuditTrailRecord(token_id=envelope.token.token_id, phase=envelope.token.current_phase,
            actor=actor, telemetry_hash=envelope.telemetry.raw_series_sha256,
            decision_summary=summary, model_configuration_id='domain-v1')
        envelope.audit_trail = []
        db.execute('UPDATE incidents SET envelope=? WHERE id=?', (envelope.model_dump_json(), envelope.token.token_id))
        db.execute('INSERT INTO audit(token,record) VALUES (?,?)', (envelope.token.token_id, record.model_dump_json()))
    def put_envelope(self, envelope):
        envelope = HeapIncidentEnvelope.model_validate_json(envelope.model_dump_json())
        t = envelope.token
        scope = str((t.rack_id,t.tenant_id,t.resource_type.value))
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT INTO incidents VALUES (?,?,1,1,?,?,?)',
                    (t.token_id,scope,t.priority_number,t.created_at.astimezone(timezone.utc).isoformat(),envelope.model_dump_json()))
            except sqlite3.IntegrityError: return False
            self._save(db,envelope,'monitor','Incident enqueued')
        return True
    def get_envelope_for_agent(self, token_id):
        with self.connection() as db:
            row = db.execute('SELECT envelope FROM incidents WHERE id=?',(token_id,)).fetchone()
            if not row: raise KeyError(token_id)
            env = HeapIncidentEnvelope.model_validate_json(row[0])
            env.audit_trail = [AuditTrailRecord.model_validate_json(r[0]) for r in db.execute('SELECT record FROM audit WHERE token=? ORDER BY seq',(token_id,))]
            return env
    def get_tenant_isolated_view(self, token_id, identity):
        env = self.get_envelope_for_agent(token_id)
        if identity['role'] != 'operator' and env.token.tenant_id != identity['tenant_id']: raise PermissionError('Tenant access denied')
        return env
    def advance(self, token_id, phase):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT envelope,active FROM incidents WHERE id=?',(token_id,)).fetchone()
            if not row: raise KeyError(token_id)
            if not row[1]: raise ValueError('Incident is closed')
            env = HeapIncidentEnvelope.model_validate_json(row[0])
            env.token.hop_count += 1
            env.token.current_phase = PipelinePhase.HALTED_LOOP_GUARD if env.token.hop_count > env.token.max_allowed_hops else phase
            self._save(db,env,'workflow','Transition to '+env.token.current_phase.value)
            if env.token.current_phase == PipelinePhase.HALTED_LOOP_GUARD:
                db.execute('UPDATE incidents SET queued=0 WHERE id=?',(token_id,))
            # Halted incidents remain active for review and deduplication.
            if phase == PipelinePhase.RESOLVED and env.token.current_phase != PipelinePhase.HALTED_LOOP_GUARD:
                db.execute('UPDATE incidents SET active=0,queued=0 WHERE id=?',(token_id,))
        return self.get_envelope_for_agent(token_id)

class PriorityTokenQueue:
    def __init__(self, heap): self.heap = heap
    @staticmethod
    def compute_priority_number(resource, utilization, lead_weeks):
        weights = {r:i+1 for i,r in enumerate([ResourceType.POWER,ResourceType.THERMAL_COOLING,ResourceType.STORAGE,ResourceType.NETWORK,ResourceType.VM_COMPUTE,ResourceType.SOFTWARE_LICENSE])}
        if not 0 <= utilization <= 100 or lead_weeks is not None and lead_weeks < 0: raise ValueError('invalid urgency')
        return min(100, max(1, round(weights[resource]*10 + (100-utilization)/5 + min(12,lead_weeks if lead_weeks is not None else 12)*2)))
    def snapshot(self):
        with self.heap.connection() as db:
            rows = db.execute('SELECT priority,created,id FROM incidents WHERE queued=1 AND active=1').fetchall()
        heapq.heapify(rows)
        return [self.heap.get_envelope_for_agent(heapq.heappop(rows)[2]).token for _ in range(len(rows))]
    def dequeue(self):
        with self.heap.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id FROM incidents WHERE queued=1 AND active=1 ORDER BY priority,created,id LIMIT 1').fetchone()
            if not row: return None
            db.execute('UPDATE incidents SET queued=0 WHERE id=?',row)
        return self.heap.get_envelope_for_agent(row[0]).token
