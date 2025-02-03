from fastapi import FastAPI, Depends, HTTPException, Form, status, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# Define origins
origins = [
    "http://112.152.14.116:25113"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cors_headers(request, call_next):
    logging.debug(f"Request origin: {request.headers.get('origin')}")
    response = await call_next(request)
    origin = request.headers.get('origin')
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    logging.debug(f"Response headers: {response.headers}")
    return response

# ============================================================
# 회원가입/로그인 기능
# ============================================================

from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# SQLAlchemy 관련 모듈 임포트
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# MySQL 연결 설정 (수정해야함)
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://username:password@localhost/dbname"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 데이터베이스 모델 정의
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)

# 데이터베이스 테이블 생성 (애플리케이션 시작 시 한 번 실행)
Base.metadata.create_all(bind=engine)

# Pydantic 스키마 정의 (요청/응답 검증용)
class UserIn(BaseModel):
    username: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# JWT 및 비밀번호 관련 설정
SECRET_KEY = "your-secret-key"  # 실제 환경에서는 안전한 값 사용
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 데이터베이스 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CRUD 함수: 사용자 조회 및 생성
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserIn):
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 회원가입 엔드포인트
@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: UserIn, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = create_user(db, user)
    logging.debug(f"New user registered: {new_user.username}")
    return {"msg": "User created successfully", "username": new_user.username}

# 로그인 엔드포인트 (Form 데이터를 사용)
@app.post("/login", response_model=Token)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, username)
    if not db_user or not verify_password(password, db_user.hashed_password):
        logging.debug(f"Failed login attempt for user: {username}")
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    logging.debug(f"User logged in: {username}")
    return {"access_token": access_token, "token_type": "bearer"}
