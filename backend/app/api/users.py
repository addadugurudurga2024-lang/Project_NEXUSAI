from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserCreate, UserUpdate, UserResponse
from app.core.security import get_password_hash
from app.core.deps import get_current_user, require_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId 
from datetime import datetime
from typing import List

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


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    users = await db.users.find({}).to_list(200)
    return [serialize_user(u) for u in users]


@router.post("/", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user=Depends(require_admin),
    db=Depends(get_database),
):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "name": data.name,
        "email": data.email,
        "password_hash": get_password_hash(data.password),
        "role": data.role,
        "specialization": data.specialization,
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_user(doc)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user=Depends(get_current_user), db=Depends(get_database)):
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)
