from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, EmailStr

from app.database import Base

class User(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, index=True, nullable=False)
    hashed_pw = Column(String, nullable=False)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: str | None = None

class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        orm_mode = True
