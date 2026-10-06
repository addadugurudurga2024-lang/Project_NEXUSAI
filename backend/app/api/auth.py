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

    # Validate required employee fields for team_member at signup
    clean_skills = [str(s).strip() for s in (data.skills or []) if str(s).strip()]
    cap_hours = float(data.weekly_capacity_hours) if (data.weekly_capacity_hours is not None and float(data.weekly_capacity_hours) > 0) else 40.0

    if role_str == "team_member":
        missing = []
        if not data.job_role or not str(data.job_role).strip():
            missing.append("job_role")
        if not data.specialization or not str(data.specialization).strip():
            missing.append("specialization")
        if not clean_skills:
            missing.append("at least one skill")
        if cap_hours <= 0 or cap_hours > 168:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="weekly_capacity_hours must be between 1 and 168",
            )
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Team members must provide: {', '.join(missing)}",
            )

    clean_email = str(data.email).strip().lower()
    clean_name = str(data.name).strip()

    doc = {
        "name": clean_name,
        "email": clean_email,
        "password_hash": get_password_hash(data.password),
        "role": role_str,
        "specialization": str(data.specialization).strip() if data.specialization else None,
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    user_id_str = str(result.inserted_id)

    # -------------------------------------------------------
    # Auto-create Employee record for team_member signups
    # -------------------------------------------------------
    if role_str == "team_member":
        # Dedup guard: check if an employee already exists for this email
        existing_emp = await db.employees.find_one({"email": clean_email})
        if existing_emp:
            # Link the existing employee to the new user account
            await db.employees.update_one(
                {"_id": existing_emp["_id"]},
                {"$set": {"user_id": user_id_str}},
            )
            created_emp_id = str(existing_emp["_id"])
        else:
            employee_doc = {
                "name": clean_name,
                "email": clean_email,
                "role": str(data.job_role).strip(),          # job title e.g. "Cybersecurity Engineer"
                "specialization": str(data.specialization).strip() if data.specialization else None,
                "skills": clean_skills,
                "experience_years": 0.0,
                "weekly_capacity_hours": cap_hours,
                "availability_percentage": 100.0,
                "status": "active",
                "user_id": user_id_str,
                "assigned_project_ids": [],
                "created_at": datetime.utcnow(),
            }
            try:
                emp_res = await db.employees.insert_one(employee_doc)
                created_emp_id = str(emp_res.inserted_id)
            except Exception as emp_err:
                # Rollback: remove the user to avoid orphaned account
                await db.users.delete_one({"_id": result.inserted_id})
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Account creation failed: could not create employee profile. Please try again.",
                )

        # Create PM request if preferred_pm_id was passed
        pref_pm = str(data.preferred_pm_id).strip() if data.preferred_pm_id else None
        if pref_pm and pref_pm.lower() not in ("none", "", "null"):
            try:
                from app.services.team_capacity_service import create_member_request
                await create_member_request(
                    db=db,
                    pm_user_id=pref_pm,
                    candidate_user_id=user_id_str,
                    employee_id=created_emp_id,
                )
            except Exception:
                # Non-fatal during registration
                pass

    token = create_access_token({"sub": user_id_str, "role": role_str})
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
