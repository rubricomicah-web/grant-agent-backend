from fastapi import (
    FastAPI,
    HTTPException,
    Depends
)

from fastapi.middleware.cors import CORSMiddleware

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from pydantic import BaseModel, EmailStr

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)

from passlib.context import CryptContext

from jose import jwt, JWTError

from datetime import (
    datetime,
    timedelta
)

from dotenv import load_dotenv

import os


# ==========================================
# ENVIRONMENT
# ==========================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "mogul-grant-system-secret"
)

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_DAYS = 30


# ==========================================
# DATABASE
# ==========================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# ==========================================
# APP
# ==========================================

app = FastAPI(

    title="Mogul Grant System API",

    description="""
    AI Funding Platform
    Grant Search
    Proposal Generation
    User Authentication
    White Label Funding System
    """,

    version="1.0"

)

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)


# ==========================================
# SECURITY
# ==========================================

pwd_context = CryptContext(

    schemes=["bcrypt"],

    deprecated="auto"

)

security = HTTPBearer()


# ==========================================
# DATABASE MODEL
# ==========================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    full_name = Column(
        String(255)
    )

    email = Column(
        String(255),
        unique=True,
        index=True
    )

    password_hash = Column(
        String
    )

    workspace_name = Column(
        String(255)
    )

    plan = Column(
        String(100)
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


Base.metadata.create_all(bind=engine)


# ==========================================
# REQUEST MODELS
# ==========================================

class SignupRequest(BaseModel):

    fullName: str

    email: EmailStr

    password: str

    workspaceName: str

    plan: str


class LoginRequest(BaseModel):

    email: EmailStr

    password: str


# ==========================================
# HELPERS
# ==========================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def hash_password(password):

    return pwd_context.hash(password)


def verify_password(
    password,
    hashed
):

    return pwd_context.verify(
        password,
        hashed
    )


def create_access_token(
    user_id
):

    payload = {

        "sub": str(user_id),

        "exp":
        datetime.utcnow()
        + timedelta(
            days=ACCESS_TOKEN_DAYS
        )

    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


def get_current_user(

    credentials:
    HTTPAuthorizationCredentials
    = Depends(security),

    db=Depends(get_db)

):

    try:

        token = credentials.credentials

        payload = jwt.decode(

            token,

            JWT_SECRET,

            algorithms=[
                JWT_ALGORITHM
            ]

        )

        user_id = payload.get("sub")

        if not user_id:

            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        user = (
            db.query(User)
            .filter(
                User.id == int(user_id)
            )
            .first()
        )

        if not user:

            raise HTTPException(
                status_code=401,
                detail="User not found"
            )

        return user

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


# ==========================================
# ROOT
# ==========================================

@app.get("/")
async def root():

    return {

        "success": True,

        "platform":
        "Mogul Grant System",

        "version": "1.0"

    }


# ==========================================
# HEALTH
# ==========================================

@app.get("/health")
async def health():

    return {

        "healthy": True,

        "database":
        "connected"

    }


# ==========================================
# SIGNUP
# ==========================================

@app.post("/api/auth/signup")
async def signup(

    data: SignupRequest,

    db=Depends(get_db)

):

    existing = (

        db.query(User)

        .filter(
            User.email == data.email
        )

        .first()

    )

    if existing:

        return {

            "success": False,

            "error":
            "Email already exists"

        }

    user = User(

        full_name=data.fullName,

        email=data.email,

        password_hash=hash_password(
            data.password
        ),

        workspace_name=
        data.workspaceName,

        plan=data.plan

    )

    db.add(user)

    db.commit()

    db.refresh(user)

    token = create_access_token(
        user.id
    )

    return {

        "success": True,

        "token": token,

        "user": {

            "id": user.id,

            "name":
            user.full_name,

            "email":
            user.email,

            "workspace":
            user.workspace_name,

            "plan":
            user.plan

        }

    }


# ==========================================
# LOGIN
# ==========================================

@app.post("/api/auth/login")
async def login(

    data: LoginRequest,

    db=Depends(get_db)

):

    user = (

        db.query(User)

        .filter(
            User.email == data.email
        )

        .first()

    )

    if not user:

        return {

            "success": False,

            "error":
            "Invalid credentials"

        }

    if not verify_password(

        data.password,

        user.password_hash

    ):

        return {

            "success": False,

            "error":
            "Invalid credentials"

        }

    token = create_access_token(
        user.id
    )

    return {

        "success": True,

        "token": token,

        "user": {

            "id": user.id,

            "name":
            user.full_name,

            "email":
            user.email,

            "workspace":
            user.workspace_name,

            "plan":
            user.plan

        }

    }


# ==========================================
# CURRENT USER
# ==========================================

@app.get("/api/auth/me")
async def me(

    current_user=
    Depends(get_current_user)

):

    return {

        "success": True,

        "user": {

            "id":
            current_user.id,

            "name":
            current_user.full_name,

            "email":
            current_user.email,

            "workspace":
            current_user.workspace_name,

            "plan":
            current_user.plan

        }

    }