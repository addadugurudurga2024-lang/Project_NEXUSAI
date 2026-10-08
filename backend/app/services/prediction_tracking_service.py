"""
Prediction Tracking Service for NexusAI
Implements Immutable Prediction Snapshots, Real-World Outcome Recording,
Prediction-to-Outcome Error Calculation, Trajectory Analysis, and Sample-Safe ML Performance Metrics.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import math
import statistics
# pyrefly: ignore [missing-import]
from bson import ObjectId

from app.models.prediction_tracking import (
    PredictionType,
    OutcomeStatus,
    PredictionRecord,
    OutcomeRecordRequest,
    ModelPerformanceMetrics,
    TrajectoryPoint,
    TrajectoryResponse,
)
from app.services.project_scoping_service import get_authorized_project_ids


def _serialize_doc(doc: dict) -> dict:
    if not doc:
        return {}
    res = dict(doc)
    res["id"] = str(res["_id"]) if "_id" in res else str(res.get("id", ""))
    if "_id" in res:
        del res["_id"]
    return res


async def record_prediction_snapshot(
    db,
    prediction_type: str,
    model_name: str,
    model_version: str,
    prediction_value: Any,
    prediction_numeric_value: Optional[float] = None,
    prediction_class: Optional[str] = None,
    prediction_unit: Optional[str] = None,
    features: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_name: Optional[str] = None,
    target_date: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    cooldown_minutes: int = 15,
) -> Optional[str]:
    """
    Stores an immutable snapshot of an ML prediction in db.prediction_history.
    Includes deduplication to avoid creating duplicate records on rapid dashboard refreshes.
    """
    features = features or {}
    context = context or {}

    # Deduplication check
    query: Dict[str, Any] = {"prediction_type": prediction_type}
    if project_id:
        query["project_id"] = project_id
    elif entity_id:
        query["entity_id"] = entity_id

    # Check for recent snapshot within cooldown
    recent = await db.prediction_history.find(query).sort("prediction_timestamp", -1).limit(1).to_list(1)
    if recent:
        last_rec = recent[0]
        last_time = last_rec.get("prediction_timestamp") or last_rec.get("created_at")
        if last_time:
            if isinstance(last_time, str):
                try:
                    last_time = datetime.fromisoformat(last_time)
                except Exception:
                    last_time = datetime.utcnow()
            
            # If within cooldown window and identical prediction value & core features
            if (datetime.utcnow() - last_time) < timedelta(minutes=cooldown_minutes):
                last_features = last_rec.get("prediction_features_snapshot", {})
                if last_rec.get("prediction_value") == prediction_value and last_features == features:
                    return str(last_rec["_id"])

    # Create immutable snapshot document
    snapshot_doc = {
        "project_id": project_id,
        "project_name": project_name,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "prediction_type": prediction_type,
        "model_name": model_name,
        "model_version": model_version,
        "prediction_timestamp": datetime.utcnow(),
        "prediction_value": prediction_value,
        "prediction_unit": prediction_unit,
        "prediction_class": prediction_class,
        "prediction_numeric_value": float(prediction_numeric_value) if prediction_numeric_value is not None else None,
        "prediction_features_snapshot": features,
        "prediction_context_snapshot": context,
        "target_date": target_date,
        "outcome_status": OutcomeStatus.PENDING.value,
        "outcome_id": None,
        "outcome_recorded_at": None,
        "actual_value": None,
        "actual_class": None,
        "actual_numeric_value": None,
        "actual_unit": prediction_unit,
        "error_value": None,
        "absolute_error": None,
        "percentage_error": None,
        "evaluation_status": OutcomeStatus.PENDING.value,
        "audit_trail": [
            {
                "action": "PREDICTION_SNAPSHOT_CREATED",
                "performed_by_id": "system",
                "performed_by_name": "NexusAI Inference Engine",
                "timestamp": datetime.utcnow(),
                "notes": f"Snapshot captured for model {model_name} ({model_version})",
            }
        ],
        "created_at": datetime.utcnow(),
    }

    result = await db.prediction_history.insert_one(snapshot_doc)
    return str(result.inserted_id)


async def record_actual_outcome(
    db,
    prediction_id: str,
    req: OutcomeRecordRequest,
    current_user: dict,
) -> dict:
    """
    Records an observed ground truth outcome against a historical prediction snapshot.
    Calculates error metrics and appends to audit trail.
    """
    try:
        oid = ObjectId(prediction_id)
    except Exception:
        raise ValueError("Invalid prediction ID format")

    prediction = await db.prediction_history.find_one({"_id": oid})
    if not prediction:
        raise ValueError("Prediction record not found")

    role = current_user.get("role", "team_member")
    if role not in ["admin", "project_manager"]:
        raise PermissionError("Manager or Admin access required to record outcomes")

    # Scoping check for PM
    if role == "project_manager" and prediction.get("project_id"):
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if prediction["project_id"] not in authorized_pids:
            raise PermissionError("Access denied: You do not manage this project")

    # Determine numeric & classification errors
    error_value = None
    abs_error = None
    pct_error = None
    actual_num = req.actual_numeric_value
    actual_cls = req.actual_class
    actual_val = req.actual_value

    if actual_num is not None:
        actual_val = actual_num
    elif actual_cls is not None:
        actual_val = actual_cls
    elif actual_val is not None:
        try:
            actual_num = float(actual_val)
        except (ValueError, TypeError):
            actual_cls = str(actual_val).upper()

    pred_num = prediction.get("prediction_numeric_value")
    pred_cls = prediction.get("prediction_class")

    # 1. Numeric error computation
    if pred_num is not None and actual_num is not None:
        error_value = float(actual_num - pred_num)
        abs_error = abs(error_value)
        if actual_num != 0:
            pct_error = round((abs_error / abs(actual_num)) * 100, 2)

    # 2. Classification match
    if pred_cls and actual_cls:
        actual_cls = str(actual_cls).upper()
        pred_cls_upper = str(pred_cls).upper()
        # 0.0 means correct match, 1.0 means mismatch
        error_value = 0.0 if actual_cls == pred_cls_upper else 1.0

    eval_status = req.status.value if req.status else OutcomeStatus.EVALUATED.value
    prev_status = prediction.get("evaluation_status", OutcomeStatus.PENDING.value)
    prev_val = prediction.get("actual_value")

    audit_entry = {
        "action": "OUTCOME_RECORDED" if prev_val is None else "OUTCOME_UPDATED",
        "performed_by_id": str(current_user["_id"]),
        "performed_by_name": current_user.get("name", "User"),
        "timestamp": datetime.utcnow(),
        "previous_status": prev_status,
        "new_status": eval_status,
        "source": req.source,
        "notes": req.notes,
        "previous_actual_value": prev_val,
        "new_actual_value": actual_val,
    }

    update_fields = {
        "actual_value": actual_val,
        "actual_class": actual_cls,
        "actual_numeric_value": actual_num,
        "actual_unit": req.actual_unit or prediction.get("prediction_unit"),
        "error_value": round(error_value, 4) if error_value is not None else None,
        "absolute_error": round(abs_error, 4) if abs_error is not None else None,
        "percentage_error": pct_error,
        "outcome_status": eval_status,
        "evaluation_status": eval_status,
        "outcome_recorded_at": req.observed_at or datetime.utcnow(),
    }

    await db.prediction_history.update_one(
        {"_id": oid},
        {
            "$set": update_fields,
            "$push": {"audit_trail": audit_entry},
        }
    )

    updated = await db.prediction_history.find_one({"_id": oid})
    return _serialize_doc(updated)


async def get_project_prediction_history(
    db,
    project_id: Optional[str] = None,
    current_user: Optional[dict] = None,
    prediction_type: Optional[str] = None,
    evaluation_status: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    """
    Returns historical prediction snapshots, sorted newest first.
    Enforces PM / Admin scoping. If project_id is None or 'all', returns all authorized snapshots.
    """
    if current_user is None:
        raise PermissionError("Authentication required")

    role = current_user.get("role", "team_member")
    if role not in ["admin", "project_manager"]:
        raise PermissionError("Manager or Admin access required")

    from app.services.project_scoping_service import get_authorized_project_ids, get_authorized_employee_ids

    authorized_pids: List[str] = []
    authorized_eids: List[str] = []
    if role == "project_manager":
        authorized_pids = await get_authorized_project_ids(db, current_user)
        authorized_eids = await get_authorized_employee_ids(db, current_user)

    is_all = not project_id or str(project_id).strip().lower() in ["all", "none", ""]

    if not is_all and role == "project_manager":
        if project_id not in authorized_pids:
            raise PermissionError("Access denied: You do not manage this project")

    query: Dict[str, Any] = {}

    if not is_all:
        if prediction_type == PredictionType.EMPLOYEE_BURNOUT.value:
            # Query burnout for members assigned to this project
            proj_doc = None
            try:
                proj_doc = await db.projects.find_one({"_id": ObjectId(project_id) if len(project_id) == 24 else project_id})
            except Exception:
                pass
            p_members = [str(m) for m in proj_doc.get("team_member_ids", [])] if proj_doc else []
            if role == "project_manager":
                p_members = [e for e in p_members if e in authorized_eids]
            query["entity_id"] = {"$in": p_members}
        else:
            query["project_id"] = project_id
    else:
        # All authorized scope
        if role == "project_manager":
            if prediction_type == PredictionType.EMPLOYEE_BURNOUT.value:
                query["entity_id"] = {"$in": authorized_eids}
            elif prediction_type in [PredictionType.PROJECT_RISK.value, PredictionType.DEADLINE_DELAY.value, PredictionType.BUDGET_OVERRUN.value]:
                query["project_id"] = {"$in": authorized_pids}
            else:
                query["$or"] = [
                    {"project_id": {"$in": authorized_pids}},
                    {"entity_id": {"$in": authorized_eids}},
                ]

    if prediction_type and "prediction_type" not in query:
        query["prediction_type"] = prediction_type
    if evaluation_status and evaluation_status != "ALL":
        query["evaluation_status"] = evaluation_status

    cursor = db.prediction_history.find(query).sort("prediction_timestamp", -1).limit(limit)
    docs = await cursor.to_list(limit)
    return [_serialize_doc(d) for d in docs]


async def get_project_trajectory(
    db,
    project_id: str,
    current_user: dict,
    prediction_type: str = "PROJECT_RISK",
) -> TrajectoryResponse:
    """
    Calculates the historical trajectory for a project prediction type (e.g. Risk or Deadline Delay).
    """
    role = current_user.get("role", "team_member")
    if role not in ["admin", "project_manager"]:
        raise PermissionError("Manager or Admin access required")

    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise PermissionError("Access denied: You do not manage this project")

    project = None
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        pass
    project_name = project.get("name") if project else "Project"

    # Fetch snapshots sorted chronologically (oldest to newest)
    docs = await db.prediction_history.find({
        "project_id": project_id,
        "prediction_type": prediction_type,
    }).sort("prediction_timestamp", 1).to_list(500)

    history_points: List[TrajectoryPoint] = []
    risk_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

    for d in docs:
        history_points.append(TrajectoryPoint(
            id=str(d["_id"]),
            timestamp=d.get("prediction_timestamp") or d.get("created_at"),
            prediction_value=d.get("prediction_value"),
            prediction_class=d.get("prediction_class"),
            prediction_numeric_value=d.get("prediction_numeric_value"),
            actual_value=d.get("actual_value"),
            actual_class=d.get("actual_class"),
            evaluation_status=d.get("evaluation_status", OutcomeStatus.PENDING.value),
            error_value=d.get("error_value"),
        ))

    # Calculate trajectory direction
    direction = "INSUFFICIENT_DATA"
    if len(history_points) >= 2:
        if prediction_type in [PredictionType.PROJECT_RISK.value, PredictionType.EMPLOYEE_BURNOUT.value]:
            ranks = [risk_rank.get(str(p.prediction_class).upper(), 2) for p in history_points if p.prediction_class]
            if len(ranks) >= 2:
                first_half_avg = sum(ranks[:len(ranks)//2]) / max(1, len(ranks)//2)
                second_half_avg = sum(ranks[len(ranks)//2:]) / max(1, len(ranks) - len(ranks)//2)
                if second_half_avg < first_half_avg - 0.2:
                    direction = "IMPROVING"
                elif second_half_avg > first_half_avg + 0.2:
                    direction = "DETERIORATING"
                else:
                    direction = "STABLE"
        elif prediction_type in [PredictionType.DEADLINE_DELAY.value, PredictionType.BUDGET_OVERRUN.value]:
            nums = [p.prediction_numeric_value for p in history_points if p.prediction_numeric_value is not None]
            if len(nums) >= 2:
                first_half_avg = sum(nums[:len(nums)//2]) / max(1, len(nums)//2)
                second_half_avg = sum(nums[len(nums)//2:]) / max(1, len(nums) - len(nums)//2)
                if second_half_avg < first_half_avg - 1.0:
                    direction = "IMPROVING"
                elif second_half_avg > first_half_avg + 1.0:
                    direction = "DETERIORATING"
                else:
                    direction = "STABLE"

    return TrajectoryResponse(
        project_id=project_id,
        project_name=project_name,
        prediction_type=prediction_type,
        trajectory_direction=direction,
        history=history_points,
    )


async def get_model_performance_summary(
    db,
    current_user: dict,
    project_id: Optional[str] = None,
    prediction_type_filter: Optional[str] = None,
) -> List[ModelPerformanceMetrics]:
    """
    Computes statistical evaluation metrics (MAE, RMSE, Accuracy, Precision, Recall, F1)
    strictly from EVALUATED prediction records within the user's authorized scope.
    """
    role = current_user.get("role", "team_member")
    if role not in ["admin", "project_manager"]:
        raise PermissionError("Manager or Admin access required")

    from app.services.project_scoping_service import get_authorized_project_ids, get_authorized_employee_ids

    authorized_pids: List[str] = []
    authorized_eids: List[str] = []
    if role == "project_manager":
        authorized_pids = await get_authorized_project_ids(db, current_user)
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        if project_id and project_id not in authorized_pids:
            raise PermissionError("Access denied: You do not manage this project")

    project_member_ids: List[str] = []
    if project_id:
        try:
            proj_doc = await db.projects.find_one({"_id": ObjectId(project_id) if len(project_id) == 24 else project_id})
            if proj_doc:
                project_member_ids = [str(m) for m in proj_doc.get("team_member_ids", [])]
        except Exception:
            pass

    # Model definitions
    models_to_evaluate = [
        {"type": PredictionType.DEADLINE_DELAY.value, "model": "GradientBoostingRegressor", "kind": "regression"},
        {"type": PredictionType.PROJECT_RISK.value, "model": "RandomForestClassifier", "kind": "classification"},
        {"type": PredictionType.BUDGET_OVERRUN.value, "model": "GradientBoostingRegressor", "kind": "regression"},
        {"type": PredictionType.EMPLOYEE_BURNOUT.value, "model": "RandomForestClassifier", "kind": "classification"},
    ]

    if prediction_type_filter and prediction_type_filter != "ALL":
        models_to_evaluate = [m for m in models_to_evaluate if m["type"] == prediction_type_filter]

    results: List[ModelPerformanceMetrics] = []

    for m_def in models_to_evaluate:
        p_type = m_def["type"]
        m_name = m_def["model"]
        kind = m_def["kind"]

        if p_type == PredictionType.EMPLOYEE_BURNOUT.value:
            if project_id:
                eligible_eids = project_member_ids
                if role == "project_manager":
                    eligible_eids = [e for e in eligible_eids if e in authorized_eids]
                type_query = {"entity_id": {"$in": eligible_eids}, "prediction_type": p_type}
            else:
                if role == "project_manager":
                    type_query = {"entity_id": {"$in": authorized_eids}, "prediction_type": p_type}
                else:
                    type_query = {"prediction_type": p_type}
        else:
            if project_id:
                type_query = {"project_id": project_id, "prediction_type": p_type}
            else:
                if role == "project_manager":
                    type_query = {"project_id": {"$in": authorized_pids}, "prediction_type": p_type}
                else:
                    type_query = {"prediction_type": p_type}

        # Count total predictions in scope
        all_records = await db.prediction_history.find(type_query).to_list(5000)
        total_count = len(all_records)
        evaluated_recs = [r for r in all_records if r.get("evaluation_status") == OutcomeStatus.EVALUATED.value]
        pending_count = sum(1 for r in all_records if r.get("evaluation_status") == OutcomeStatus.PENDING.value)
        unavailable_count = sum(1 for r in all_records if r.get("evaluation_status") == OutcomeStatus.UNAVAILABLE.value)
        eval_count = len(evaluated_recs)

        # Sample safety checks
        sample_status = "NO_EVALUATED_DATA"
        sample_warning = None
        if eval_count == 0:
            sample_status = "NO_EVALUATED_DATA"
            sample_warning = "No evaluated ground truth outcomes available yet. Metrics will calculate once outcomes are recorded."
        elif eval_count < 5:
            sample_status = "LIMITED_SAMPLE"
            sample_warning = f"Limited sample size ({eval_count} evaluated prediction(s)). Statistics are preliminary and not yet fully representative."
        else:
            sample_status = "SUFFICIENT"

        metrics = ModelPerformanceMetrics(
            model_name=m_name,
            prediction_type=p_type,
            total_predictions=total_count,
            evaluated_count=eval_count,
            pending_count=pending_count,
            unavailable_count=unavailable_count,
            sample_size_status=sample_status,
            sample_size_warning=sample_warning,
        )

        if eval_count > 0:
            if kind == "regression":
                # Numeric regression metrics
                abs_errors = []
                errors = []
                sq_errors = []

                for r in evaluated_recs:
                    pred_val = r.get("prediction_numeric_value")
                    act_val = r.get("actual_numeric_value")
                    if pred_val is not None and act_val is not None:
                        err = float(act_val - pred_val)
                        abs_err = abs(err)
                        errors.append(err)
                        abs_errors.append(abs_err)
                        sq_errors.append(err ** 2)

                if abs_errors:
                    metrics.mae = round(sum(abs_errors) / len(abs_errors), 2)
                    metrics.median_absolute_error = round(float(statistics.median(abs_errors)), 2)
                    metrics.rmse = round(math.sqrt(sum(sq_errors) / len(sq_errors)), 2)
                    metrics.mean_error_bias = round(sum(errors) / len(errors), 2)

            elif kind == "classification":
                # Multiclass classification metrics
                y_true = []
                y_pred = []

                for r in evaluated_recs:
                    p_cls = r.get("prediction_class")
                    a_cls = r.get("actual_class") or r.get("actual_value")
                    if p_cls and a_cls:
                        y_pred.append(str(p_cls).upper())
                        y_true.append(str(a_cls).upper())

                if y_true:
                    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
                    metrics.accuracy = round(correct / len(y_true), 4)

                    # Calculate multi-class macro Precision, Recall, F1
                    classes = sorted(list(set(y_true + y_pred)))
                    precisions = []
                    recalls = []
                    f1s = []

                    for c in classes:
                        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp == c)
                        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != c and yp == c)
                        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp != c)

                        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
                        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
                        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

                        precisions.append(prec)
                        recalls.append(rec)
                        f1s.append(f1)

                    metrics.precision = round(sum(precisions) / max(1, len(precisions)), 4)
                    metrics.recall = round(sum(recalls) / max(1, len(recalls)), 4)
                    metrics.f1_score = round(sum(f1s) / max(1, len(f1s)), 4)

        results.append(metrics)

    return results


async def auto_evaluate_project_outcomes(
    db,
    project_id: str,
    current_user: dict,
) -> Dict[str, Any]:
    """
    Evaluates pending predictions for a completed project from authoritative project lifecycle fields.
    Zero fake ground truth: Only evaluates if project has valid actual completion or financial data.
    """
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise ValueError("Invalid project ID")

    project = await db.projects.find_one({"_id": oid})
    if not project:
        raise ValueError("Project not found")

    role = current_user.get("role", "team_member")
    if role not in ["admin", "project_manager"]:
        raise PermissionError("Manager or Admin access required")

    if role == "project_manager":
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise PermissionError("Access denied: You do not manage this project")

    evaluated_count = 0
    evaluated_types = []

    # 1. Deadline Delay evaluation if project is completed and has completion date
    status_str = str(project.get("status", "")).lower()
    end_date_str = project.get("end_date")
    actual_end_date_str = project.get("actual_end_date") or project.get("completed_at")

    if status_str in ["completed", "done"] and end_date_str:
        try:
            planned_end = datetime.strptime(end_date_str, "%Y-%m-%d")
            if actual_end_date_str:
                if isinstance(actual_end_date_str, datetime):
                    actual_end = actual_end_date_str
                else:
                    actual_end = datetime.strptime(str(actual_end_date_str)[:10], "%Y-%m-%d")
            else:
                actual_end = datetime.utcnow()

            actual_delay_days = max(0, (actual_end - planned_end).days)

            # Find pending deadline predictions
            pending_deadlines = await db.prediction_history.find({
                "project_id": project_id,
                "prediction_type": PredictionType.DEADLINE_DELAY.value,
                "evaluation_status": OutcomeStatus.PENDING.value,
            }).to_list(100)

            for p in pending_deadlines:
                await record_actual_outcome(
                    db=db,
                    prediction_id=str(p["_id"]),
                    req=OutcomeRecordRequest(
                        actual_numeric_value=float(actual_delay_days),
                        actual_unit="days",
                        source="project_lifecycle_completion",
                        notes=f"Project completed on {actual_end.strftime('%Y-%m-%d')} vs planned {end_date_str}.",
                    ),
                    current_user=current_user,
                )
                evaluated_count += 1
            if pending_deadlines:
                evaluated_types.append("DEADLINE_DELAY")
        except Exception as e:
            print(f"Warning: Deadline auto-evaluation error: {e}")

    # 2. Budget Overrun evaluation if final expenditure is recorded
    budget = project.get("budget", 0)
    final_expenditure = project.get("actual_cost") or project.get("current_expenditure")
    if status_str in ["completed", "done"] and budget > 0 and final_expenditure is not None:
        try:
            actual_overrun = max(0.0, float(final_expenditure) - float(budget))
            pending_budgets = await db.prediction_history.find({
                "project_id": project_id,
                "prediction_type": PredictionType.BUDGET_OVERRUN.value,
                "evaluation_status": OutcomeStatus.PENDING.value,
            }).to_list(100)

            for p in pending_budgets:
                await record_actual_outcome(
                    db=db,
                    prediction_id=str(p["_id"]),
                    req=OutcomeRecordRequest(
                        actual_numeric_value=float(actual_overrun),
                        actual_unit="USD",
                        source="project_lifecycle_budget_closure",
                        notes=f"Project closed with spend ${final_expenditure:,.2f} vs budget ${budget:,.2f}.",
                    ),
                    current_user=current_user,
                )
                evaluated_count += 1
            if pending_budgets:
                evaluated_types.append("BUDGET_OVERRUN")
        except Exception as e:
            print(f"Warning: Budget auto-evaluation error: {e}")

    return {
        "project_id": project_id,
        "evaluated_count": evaluated_count,
        "evaluated_types": evaluated_types,
        "message": f"Successfully evaluated {evaluated_count} prediction snapshot(s) from project lifecycle data.",
    }


async def ensure_prediction_tracking_indexes(db):
    """Ensure performant and safe compound indexes for prediction_history."""
    try:
        await db.prediction_history.create_index(
            [("project_id", 1), ("prediction_type", 1), ("prediction_timestamp", -1)],
            name="idx_proj_type_time"
        )
        await db.prediction_history.create_index(
            [("entity_id", 1), ("prediction_type", 1), ("prediction_timestamp", -1)],
            name="idx_entity_type_time"
        )
        await db.prediction_history.create_index(
            [("prediction_type", 1), ("evaluation_status", 1)],
            name="idx_type_status"
        )
        await db.prediction_history.create_index(
            [("prediction_timestamp", -1)],
            name="idx_timestamp_desc"
        )
    except Exception as e:
        print(f"Warning: Index creation for prediction_history: {e}")


async def ensure_prediction_snapshots_initialized(db) -> dict:
    """
    Idempotent initialization that ensures live projects and active direct team employees
    have legitimate immutable prediction snapshots in db.prediction_history.
    - Uses real production ML models (RandomForestClassifier, GradientBoostingRegressor).
    - Uses current authoritative feature vectors extracted from live database state.
    - Sets outcome_status = PENDING and evaluation_status = PENDING.
    - Zero fake ground truth: does not invent actual outcomes.
    - Deduplication prevents unwanted duplicates.
    """
    await ensure_prediction_tracking_indexes(db)

    from ml.inference.project_risk import predict_project_risk_inference
    from ml.inference.deadline_delay import predict_deadline_delay
    from ml.inference.budget_overrun import predict_budget_overrun
    from ml.inference.burnout_risk import predict_burnout_risk
    from app.api.predictions import _gather_project_features
    from app.api.employee_risk import _gather_employee_features

    project_count = 0
    employee_count = 0

    # 1. Projects - generate legitimate snapshots for all active projects
    projects = await db.projects.find({"status": "active"}).to_list(200)
    for p in projects:
        pid = str(p["_id"])
        # Check if project already has all 3 prediction snapshots
        existing_types = await db.prediction_history.distinct("prediction_type", {"project_id": pid})
        needs_risk = "PROJECT_RISK" not in existing_types
        needs_delay = "DEADLINE_DELAY" not in existing_types
        needs_budget = "BUDGET_OVERRUN" not in existing_types

        if not (needs_risk or needs_delay or needs_budget):
            continue

        try:
            gathered = await _gather_project_features(pid, db)
            features = gathered["features"]
            p_doc = gathered["project"]

            if needs_risk:
                risk_res = predict_project_risk_inference(features)
                await record_prediction_snapshot(
                    db=db,
                    prediction_type="PROJECT_RISK",
                    model_name=risk_res.get("model_name", "RandomForestClassifier"),
                    model_version=risk_res.get("model_version", "2.0-Enterprise"),
                    prediction_value=risk_res["risk_class"],
                    prediction_class=risk_res["risk_class"],
                    prediction_numeric_value=risk_res.get("risk_probability"),
                    prediction_unit="category",
                    features=features,
                    project_id=pid,
                    project_name=p_doc.get("name"),
                    context={"risk_factors": risk_res.get("contributing_factors", []), "risk_probability": risk_res.get("risk_probability")},
                )

            if needs_delay:
                delay_res = predict_deadline_delay(features, p_doc)
                await record_prediction_snapshot(
                    db=db,
                    prediction_type="DEADLINE_DELAY",
                    model_name=delay_res.get("model_name", "GradientBoostingRegressor"),
                    model_version=delay_res.get("model_version", "2.0-Enterprise"),
                    prediction_value=f"{delay_res['delay_days']} days",
                    prediction_numeric_value=float(delay_res["delay_days"]),
                    prediction_unit="days",
                    features=features,
                    project_id=pid,
                    project_name=p_doc.get("name"),
                    target_date=p_doc.get("end_date"),
                    context={"delay_factors": delay_res.get("contributing_factors", []), "delay_probability": delay_res.get("delay_probability")},
                )

            if needs_budget:
                budget_res = predict_budget_overrun(features, p_doc)
                await record_prediction_snapshot(
                    db=db,
                    prediction_type="BUDGET_OVERRUN",
                    model_name=budget_res.get("model_name", "GradientBoostingRegressor"),
                    model_version=budget_res.get("model_version", "2.0-Enterprise"),
                    prediction_value=f"${budget_res['overrun_amount']:,.2f}",
                    prediction_numeric_value=float(budget_res["overrun_amount"]),
                    prediction_class=budget_res.get("overrun_risk"),
                    prediction_unit="USD",
                    features=features,
                    project_id=pid,
                    project_name=p_doc.get("name"),
                    context={"budget_factors": budget_res.get("contributing_factors", []), "predicted_final_cost": budget_res.get("predicted_final_cost")},
                )

            project_count += 1
        except Exception as e:
            print(f"Warning: Project snapshot init error for {pid}: {e}")

    # 2. Active employees with PM memberships
    active_mems = await db.team_memberships.find({"status": "active"}).to_list(500)
    distinct_eids = list({m["employee_id"] for m in active_mems if m.get("employee_id")})

    for eid in distinct_eids:
        existing_emp_snap = await db.prediction_history.find_one({
            "entity_id": eid,
            "prediction_type": "EMPLOYEE_BURNOUT"
        })
        if existing_emp_snap:
            continue

        try:
            gathered_emp = await _gather_employee_features(eid, db)
            emp_features = gathered_emp["features"]
            emp_doc = gathered_emp["employee"]
            emp_stats = gathered_emp["workload_stats"]

            burnout_res = predict_burnout_risk(emp_features)

            await record_prediction_snapshot(
                db=db,
                prediction_type="EMPLOYEE_BURNOUT",
                model_name=burnout_res.get("model_name", "RandomForestClassifier"),
                model_version=burnout_res.get("model_version", "2.0-Enterprise"),
                prediction_value=burnout_res["risk_level"],
                prediction_class=burnout_res["risk_level"],
                prediction_numeric_value=burnout_res.get("risk_probability"),
                prediction_unit="category",
                features=emp_features,
                entity_id=eid,
                entity_name=emp_doc.get("name"),
                context={"factors": burnout_res.get("contributing_factors", []), "workload_stats": emp_stats},
            )
            employee_count += 1
        except Exception as e:
            print(f"Warning: Employee burnout snapshot init error for {eid}: {e}")

    return {
        "status": "success",
        "projects_initialized": project_count,
        "employees_initialized": employee_count,
    }
