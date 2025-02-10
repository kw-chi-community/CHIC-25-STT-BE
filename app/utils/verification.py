# /utils/verification.py
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

def create_access_token(payload: dict, expires_delta: timedelta = timedelta(hours=6)):
    expire = datetime.utcnow() + expires_delta
    payload.update(
        {
            "exp": expire,
        }
    )
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    payload = decode_access_token(token)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return user_id
