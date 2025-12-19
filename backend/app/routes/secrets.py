"""API routes for secrets management."""

import os
from typing import Any

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.core import get_db
from .. import models as db_models

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


def _get_encryption_key() -> bytes:
    """Get or generate the encryption key for secrets."""
    key_path = os.path.expanduser("~/.think/.secrets_key")
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        os.chmod(key_path, 0o600)
        return key


def _get_fernet() -> Fernet:
    """Get a Fernet instance for encryption/decryption."""
    return Fernet(_get_encryption_key())


class SecretCreate(BaseModel):
    """Request to create or update a secret."""
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)
    description: str | None = None


class SecretResponse(BaseModel):
    """Response for a secret (value is masked)."""
    name: str
    description: str | None
    created_at: Any
    updated_at: Any
    has_value: bool = True


@router.get("", response_model=list[SecretResponse])
async def list_secrets(db: Session = Depends(get_db)):
    """List all secrets (values are not returned)."""
    secrets = db.query(db_models.Secret).order_by(db_models.Secret.name).all()
    
    return [
        SecretResponse(
            name=s.name,
            description=s.description,
            created_at=s.created_at,
            updated_at=s.updated_at,
            has_value=bool(s.encrypted_value),
        )
        for s in secrets
    ]


@router.post("", response_model=SecretResponse)
async def create_or_update_secret(
    request: SecretCreate,
    db: Session = Depends(get_db),
):
    """Create or update a secret."""
    fernet = _get_fernet()
    encrypted_value = fernet.encrypt(request.value.encode())
    
    existing = db.query(db_models.Secret).filter(
        db_models.Secret.name == request.name
    ).first()
    
    if existing:
        existing.encrypted_value = encrypted_value
        existing.description = request.description
        db.commit()
        db.refresh(existing)
        secret = existing
    else:
        secret = db_models.Secret(
            name=request.name,
            encrypted_value=encrypted_value,
            description=request.description,
        )
        db.add(secret)
        db.commit()
        db.refresh(secret)
    
    return SecretResponse(
        name=secret.name,
        description=secret.description,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
        has_value=True,
    )


@router.get("/{name}")
async def get_secret_value(
    name: str,
    db: Session = Depends(get_db),
):
    """Get a secret's decrypted value (for internal use only)."""
    secret = db.query(db_models.Secret).filter(
        db_models.Secret.name == name
    ).first()
    
    if not secret:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    
    fernet = _get_fernet()
    try:
        decrypted_value = fernet.decrypt(secret.encrypted_value).decode()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt secret")
    
    return {
        "name": secret.name,
        "value": decrypted_value,
    }


@router.delete("/{name}")
async def delete_secret(
    name: str,
    db: Session = Depends(get_db),
):
    """Delete a secret."""
    secret = db.query(db_models.Secret).filter(
        db_models.Secret.name == name
    ).first()
    
    if not secret:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    
    db.delete(secret)
    db.commit()
    
    return {"message": f"Secret '{name}' deleted"}


async def get_secret(name: str, db: Session) -> str | None:
    """
    Helper function to get a decrypted secret value.
    
    For use by other services that need to access secrets.
    """
    secret = db.query(db_models.Secret).filter(
        db_models.Secret.name == name
    ).first()
    
    if not secret:
        return None
    
    fernet = _get_fernet()
    try:
        return fernet.decrypt(secret.encrypted_value).decode()
    except Exception:
        return None
