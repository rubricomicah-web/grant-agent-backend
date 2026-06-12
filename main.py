from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from dotenv import load_dotenv
from ddgs import DDGS
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "mogul-grant-system-secret")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 30

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Mogul Grant System API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://grant-simone-frontend-production.up.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String)
    workspace_name = Column(String(255))
    plan = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Grant(Base):
    __tablename__ = "grants"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500))
    agency = Column(String(255))
    funding_amount = Column(String(255))
    deadline = Column(String(100))
    eligibility = Column(String)
    category = Column(String(255))
    apply_url = Column(String)
    source = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

class SignupRequest(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    workspaceName: str
    plan: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    message: str

class GrantSearchRequest(BaseModel):
    query: str

class ProposalRequest(BaseModel):
    project_name: str
    funding_amount: str
    description: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):
    return pwd_context.hash(password[:72])

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def create_access_token(user_id: int):
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=ACCESS_TOKEN_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                     db=Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/")
async def root():
    return {"success": True, "platform": "Mogul Grant System"}

@app.get("/health")
async def health():
    return {"healthy": True}

@app.post("/api/auth/signup")
async def signup(data: SignupRequest, db=Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        return {"success": False, "error": "Email already exists"}

    user = User(
        full_name=data.fullName,
        email=data.email,
        password_hash=hash_password(data.password),
        workspace_name=data.workspaceName,
        plan=data.plan
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "workspace": user.workspace_name,
            "plan": user.plan
        }
    }

@app.post("/api/auth/login")
async def login(data: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.password_hash):
        return {"success": False, "error": "Invalid credentials"}

    token = create_access_token(user.id)

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "workspace": user.workspace_name,
            "plan": user.plan
        }
    }

@app.get("/api/auth/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "name": current_user.full_name,
            "email": current_user.email,
            "workspace": current_user.workspace_name,
            "plan": current_user.plan
        }
    }

from groq import Groq

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

@app.post("/chat")
async def chat(data: ChatRequest):

    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """
You are Mogul Grant System AI.

You help users:

- Find grants
- Evaluate eligibility
- Recommend funding opportunities
- Explain grant requirements
- Build funding strategies

Always answer like a professional grant consultant.
"""
            },
            {
                "role": "user",
                "content": data.message
            }
        ],
        temperature=0.4
    )

    return {
        "success": True,
        "response":
        completion.choices[0].message.content
    }

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f"{data.query} grant funding opportunity"):
                results.append({
                    "title": r.get("title"),
                    "url": r.get("href"),
                    "description": r.get("body")
                })
                if len(results) >= 10:
                    break
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": True, "results": results}

@app.post("/generate-proposal")
async def generate_proposal(
    data: ProposalRequest
):

    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role":"system",
                "content":"""
You are a professional grant writer.

Create a funding proposal.

Include:

1 Executive Summary
2 Project Goals
3 Project Description
4 Budget Justification
5 Expected Impact
6 Conclusion
"""
            },
            {
                "role":"user",
                "content":f"""
Project Name:
{data.project_name}

Funding Amount:
{data.funding_amount}

Description:
{data.description}
"""
            }
        ]
    )

    return {
        "success":True,
        "proposal":
        completion.choices[0].message.content
    }
