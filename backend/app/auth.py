"""Static server-managed bearer identities for local development; no default credentials."""
import secrets
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from fastapi import Depends, HTTPException, Request
import time
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class SessionStore:
    """Durable cookie sessions; only token digests are stored on disk."""
    def __init__(self,path):
        self.path=path
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS operator_sessions (digest TEXT PRIMARY KEY, principal TEXT NOT NULL, expires REAL NOT NULL)')
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path)
        try:
            with db: yield db
        finally: db.close()
    def digest(self,token):
        return hashlib.sha256(token.encode()).hexdigest()
    def __setitem__(self,token,record):
        with self.connection() as db:
            db.execute('DELETE FROM operator_sessions WHERE expires <= ?', (time.time(),))
            db.execute('INSERT OR REPLACE INTO operator_sessions VALUES (?,?,?)',(self.digest(token),json.dumps(record['principal']),record['expires']))
    def get(self,token,default=None):
        with self.connection() as db:
            row=db.execute('SELECT principal,expires FROM operator_sessions WHERE digest=? AND expires>?',(self.digest(token),time.time())).fetchone()
        return {'principal':json.loads(row[0]),'expires':row[1]} if row else default
    def pop(self,token,default=None):
        record=self.get(token,default)
        with self.connection() as db:
            db.execute('DELETE FROM operator_sessions WHERE digest=?',(self.digest(token),))
        return record
    def __contains__(self,token):
        return self.get(token) is not None

bearer=HTTPBearer(auto_error=False)
def identity_dependency(settings):
    sessions = SessionStore(settings.database_path)
    def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            for token, principal in settings.auth_tokens.items():
                if secrets.compare_digest(credentials.credentials,token): return principal.model_dump()
        session=sessions.get(request.cookies.get('ao02_session',''))
        if session and session['expires'] > time.time(): return session['principal']
        raise HTTPException(401,'Your session has expired. Please reconnect to the operator workspace.',headers={'WWW-Authenticate':'Bearer'})
    identity.sessions = sessions
    return identity
