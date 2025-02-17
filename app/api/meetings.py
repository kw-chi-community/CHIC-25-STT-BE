import logging
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from app.utils.database import get_db
from app.utils.verification import create_access_token, decode_access_token

router = APIRouter()