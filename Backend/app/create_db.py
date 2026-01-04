# create_db.py
from app.models import user  
from app.database import engine, Base

import app.models

Base.metadata.create_all(bind=engine)
print("Database tables created.")
