from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import LoginRequest, TokenResponse, UserResponse, UserCreate
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.deps import get_current_user
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime

router = APIRouter()


def serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "team_member"),
        "specialization": user.get("specialization"),
        "created_at": user.get("created_at"),
    }


@router.post("/signup", response_model=TokenResponse)
async def signup(data: UserCreate, db=Depends(get_database)):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    role_str = data.role.value if hasattr(data.role, "value") else str(data.role)

    # Task 10: Prevent unrestricted public Admin creation
    if role_str == "admin":
        user_count = await db.users.count_documents({})
        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin accounts cannot be registered publicly. Must be created by an existing administrator.",
            )
    
    doc = {
        "name": data.name,
        "email": data.email,
        "password_hash": get_password_hash(data.password),
        "role": role_str,
        "specialization": data.specialization,
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    
    token = create_access_token({"sub": str(doc["_id"]), "role": role_str})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(doc)}



@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db=Depends(get_database)):
    user = await db.users.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user["_id"]), "role": user.get("role")})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return serialize_user(current_user)
