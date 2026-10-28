"""Static server-managed bearer identities for local development; no default credentials."""
import secrets
from fastapi import Depends, HTTPException, Request
import time
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer=HTTPBearer(auto_error=False)
def identity_dependency(settings):
    sessions = {}
    def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            for token, principal in settings.auth_tokens.items():
                if secrets.compare_digest(credentials.credentials,token): return principal.model_dump()
        session=sessions.get(request.cookies.get('ao02_session',''))
        if session and session['expires'] > time.time(): return session['principal']
        raise HTTPException(401,'Valid bearer credentials required',headers={'WWW-Authenticate':'Bearer'})
    identity.sessions = sessions
    return identity
