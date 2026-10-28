"""Static server-managed bearer identities for local development; no default credentials."""
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer=HTTPBearer(auto_error=False)
def identity_dependency(settings):
    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            for token, principal in settings.auth_tokens.items():
                if secrets.compare_digest(credentials.credentials,token): return principal.model_dump()
        raise HTTPException(401,'Valid bearer credentials required',headers={'WWW-Authenticate':'Bearer'})
    return identity
