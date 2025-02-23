# /utils/models.py
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine, MetaData
import os
from dotenv import load_dotenv

# Docker 환경인지 확인
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"

if not IS_DOCKER:
    load_dotenv()  # 로컬 개발 환경에서는 .env 파일 로드

# Read DATABASE_URL from .env file
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database engine
engine = create_engine(DATABASE_URL, echo=True)
Base = automap_base()

# Reflect the tables
metadata = MetaData()
metadata.reflect(engine, only=['users', 'conversations', 'key_topics', 'keywords', 'meetings', 'topic_details', 'topics'])

Base.prepare(engine, reflect=True)

# Automatically generated classes
User = Base.classes.users
Meeting = Base.classes.meetings
Topic = Base.classes.topics
TopicDetail = Base.classes.topic_details
Keyword = Base.classes.keywords
KeyTopic = Base.classes.key_topics
Conversation = Base.classes.conversations
