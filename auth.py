from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from config import API_KEY

_header_scheme = APIKeyHeader(name="X-API-Key")

async def require_api_key(key: str = Security(_header_scheme)):
    if key != API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
