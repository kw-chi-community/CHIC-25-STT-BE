import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from app.utils.database import get_db
from app.utils.models import Meeting, Topic, TopicDetail, Keyword, KeyTopic, Conversation
from app.utils.verification import get_current_user  # 인증 모듈 추가

router = APIRouter()

# Pydantic 모델 정의
class MeetingCreate(BaseModel):
    meeting_name: str
    meeting_date: datetime
    audio_url: Optional[str] = None

class MeetingResponse(MeetingCreate):
    id: int
    class Config:
        orm_mode = True

class MeetingIDResponse(BaseModel):
    id: int
    class Config:
        orm_mode = True

class TopicCreate(BaseModel):
    meeting_id: int
    title: str

class TopicResponse(TopicCreate):
    id: int
    class Config:
        orm_mode = True

class KeywordCreate(BaseModel):
    meeting_id: int
    keyword: str
    summary: Optional[str] = None

class KeywordResponse(KeywordCreate):
    id: int
    class Config:
        orm_mode = True

class KeyTopicCreate(BaseModel):
    meeting_id: int
    topic: str

class KeyTopicResponse(KeyTopicCreate):
    id: int
    class Config:
        orm_mode = True

class ConversationCreate(BaseModel):
    meeting_id: int
    speaker: str
    time_stamp: str
    content: str
    color: Optional[str] = None

class ConversationResponse(ConversationCreate):
    id: int
    class Config:
        orm_mode = True

# 🔒 회의 생성 API (인증 추가)
@router.post("/", response_model=MeetingResponse)
def create_meeting(
    meeting: MeetingCreate, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    new_meeting = Meeting(**meeting.dict())
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    # 기본 주제 추가
    default_topic = Topic(meeting_id=new_meeting.id, title="기본 주제")
    db.add(default_topic)
    db.commit()
    db.refresh(default_topic)

    # 기본 주제의 세부 내용 추가
    default_topic_detail = TopicDetail(topic_id=default_topic.id, detail="기본 주제에 대한 세부 내용")
    db.add(default_topic_detail)

    # 기본 키워드 추가
    default_keyword = Keyword(meeting_id=new_meeting.id, keyword="기본 키워드", summary="이 키워드는 자동 생성됨")
    db.add(default_keyword)

    # 커밋
    db.commit()

    return new_meeting

# 🔒 모든 회의 조회 API (인증 추가)
@router.get("/", response_model=List[MeetingResponse])
def get_meetings(
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    return db.query(Meeting).all()

# 🔒 특정 회의 조회 API (인증 추가)
@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting

# 🔒 특정 회의의 주제 조회 API (인증 추가)
@router.get("/{meeting_id}/topics", response_model=List[TopicResponse])
def get_topics(
    meeting_id: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    return db.query(Topic).filter(Topic.meeting_id == meeting_id).all()

# 🔒 특정 회의의 핵심 주제 조회 API (인증 추가)
@router.get("/{meeting_id}/key_topics", response_model=List[KeyTopicResponse])
def get_key_topics(
    meeting_id: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    return db.query(KeyTopic).filter(KeyTopic.meeting_id == meeting_id).all()

# 🔒 특정 회의의 대화 내용 조회 API (인증 추가)
@router.get("/{meeting_id}/conversations", response_model=List[ConversationResponse])
def get_conversations(
    meeting_id: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    return db.query(Conversation).filter(Conversation.meeting_id == meeting_id).all()

# 🔒 특정 회의의 대화 기록 추가 API (인증 추가)
@router.post("/{meeting_id}/conversations", response_model=ConversationResponse)
def add_conversation(
    meeting_id: int, 
    conversation: ConversationCreate, 
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    new_conversation = Conversation(
        meeting_id=meeting_id,
        speaker=conversation.speaker,
        time_stamp=conversation.time_stamp,
        content=conversation.content,
        color=conversation.color
    )
    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)
    return new_conversation

# 🔒 특정 년/월의 meeting_id 조회 API (인증 추가)
@router.get("/meetings/by-date/{year}/{month}", response_model=List[MeetingIDResponse])
def get_meetings_by_month(
    year: int, 
    month: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    meetings = db.query(Meeting.id).filter(
        Meeting.meeting_date >= datetime(year, month, 1),
        Meeting.meeting_date < datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
    ).all()
    
    if not meetings:
        raise HTTPException(status_code=404, detail="No meetings found for this month")
    
    return meetings

# 🔒 특정 년/월/일의 meeting_id 조회 API (인증 추가)
@router.get("/meetings/by-date/{year}/{month}/{day}", response_model=List[MeetingIDResponse])
def get_meetings_by_day(
    year: int, 
    month: int, 
    day: int, 
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)  # 🔒 인증 필수
):
    meetings = db.query(Meeting.id).filter(
        Meeting.meeting_date >= datetime(year, month, day),
        Meeting.meeting_date < datetime(year, month, day + 1)
    ).all()
    
    if not meetings:
        raise HTTPException(status_code=404, detail="No meetings found for this date")
    
    return meetings
