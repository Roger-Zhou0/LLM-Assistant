from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api import auth

# Import these two so we can auto-create tables
from app.database import engine, Base

app = FastAPI()

# === AUTO-CREATE TABLES HERE ===
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://yoshi-frontend.onrender.com",
        "https://llm-assistant1-g5mvbj9f2-roger-zhou0s-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth.router, prefix="/auth")
