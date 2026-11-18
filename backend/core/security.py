import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Union, Any, Optional
from passlib.context import CryptContext
from .config import settings

# CryptContext defaults to bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Handle seed fallback (SHA-256) first
    if hashed_password.startswith("$sha256$"):
        parts = hashed_password.split("$")
        if len(parts) >= 4:
            salt = parts[2]
            target_hash = parts[3]
            hashed = hashlib.sha256((plain_password + salt).encode('utf-8')).hexdigest()
            return hashed == target_hash
            
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return decoded
    except jwt.PyJWTError:
        return None
