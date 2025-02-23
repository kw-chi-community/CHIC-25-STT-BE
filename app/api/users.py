# /app/api/users.py
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.utils.database import get_db
from app.utils.auth import oauth2_scheme, get_password_hash, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from app.utils.verification import create_access_token, decode_access_token
from app.utils.models import User

router = APIRouter()

# 현재 사용자 확인 (인증용)
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    # payload에 'sub' 키에 userid가 들어있다고 가정
    userid = payload.get("sub")
    if userid is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = db.query(User).filter(User.userid == userid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# 모든 사용자 조회 (예시, 인증 필요)
@router.get("/")
async def get_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User.id, User.username, User.userid).all()
    return [{"id": user.id, "username": user.username, "userid": user.userid} for user in users]
router = APIRouter()

from fastapi import Body

@router.post("/")
async def create_user(
    username: str = Body(...),
    userid: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db)
):
    # 중복 체크 및 사용자 생성 코드 동일
    existing_user = db.query(User).filter(or_(User.username == username, User.userid == userid)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or Userid already exists")
    
    hashed_password = get_password_hash(password)
    new_user = User(username=username, userid=userid, hashed_password=hashed_password)
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="User creation failed")
    return {"msg": "User created successfully", "username": new_user.username, "userid": new_user.userid}

# 로그인 엔드포인트
@router.post("/login")
async def login(
    userid: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    # 요청 데이터를 확인하기 위한 로그 출력 (비밀번호 전체는 출력하지 않음)
    logging.info(f"Received login request: userid={userid}, password_length={len(password)}")
    
    try:
        user = db.query(User).filter(User.userid == userid).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect userid or password")
        access_token = create_access_token(
            {"user_id": user.userid},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logging.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


