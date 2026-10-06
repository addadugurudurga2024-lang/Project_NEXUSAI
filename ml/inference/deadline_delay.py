"""
Deadline Delay Prediction Inference Module
Model: GradientBoostingRegressor (trained on synthetic data)
Output: Predicted delay in days (continuous regression, >= 0)

Falls back to heuristic estimation if the trained model is unavailable.
"""
import os
import numpy as np
from typing import Dict, Any
from datetime import datetime

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'deadline_delay_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'deadline_delay_scaler.pkl')

_model = None
_scaler = None


def _load_model() -> bool:
    global _model, _scaler
    if _model is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                import joblib
                _model = joblib.load(MODEL_PATH)
                _scaler = joblib.load(SCALER_PATH)
            except Exception:
                return False
    return _model is not None


def _parse_dates(project: dict):
    """Return (total_days, days_remaining, schedule_progress_pct) or (1, 1, 0)."""
    start_str = project.get("start_date")
    end_str = project.get("end_date")
    today = datetime.utcnow()

    if not end_str:
        return 180.0, 90.0, 0.0

    try:
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        days_remaining = max(0.0, (end_date - today).days)
        total_days = 1.0
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            total_days = max(1.0, float((end_date - start_date).days))
        elapsed = total_days - days_remaining
        schedule_progress = max(0.0, min(100.0, (elapsed / total_days) * 100))
        return total_days, days_remaining, schedule_progress
    except Exception:
        return 180.0, 90.0, 0.0


def predict_deadline_delay(features: Dict[str, Any], project: dict) -> Dict[str, Any]:
    """
    Predict deadline delay using a trained GradientBoostingRegressor.
    Falls back to heuristic analysis if the model is unavailable.
    """
    progress = float(features.get("progress", 0))
    task_completion_rate = float(features.get("task_completion_rate", 0))
    overdue_tasks = int(features.get("overdue_tasks", 0))
    critical_issues = int(features.get("critical_issues", 0))
    team_workload = float(features.get("team_workload", 50))

    total_days, days_remaining, schedule_progress = _parse_dates(project)
    if "total_days" in features:
        total_days = float(features["total_days"])
    if "days_remaining" in features:
        days_remaining = float(features["days_remaining"])
    if "schedule_progress" in features:
        schedule_progress = float(features["schedule_progress"])

    progress_gap = float(features.get("progress_gap", schedule_progress - progress))

    factors = []

    # ── ML MODEL PATH ────────────────────────────────────────────────────────
    if _load_model():
        try:
            X = np.array([[
                progress,
                task_completion_rate,
                float(overdue_tasks),
                float(critical_issues),
                team_workload,
                total_days,
                days_remaining,
                schedule_progress,
                progress_gap,
            ]])
            X_scaled = _scaler.transform(X)
            raw_pred = float(_model.predict(X_scaled)[0])
            delay_days = max(0, round(raw_pred))

            # Build readable contributing factors from feature importances
            feature_names = [
                "Progress", "Task Completion Rate", "Overdue Tasks",
                "Critical Issues", "Team Workload", "Total Days",
                "Days Remaining", "Schedule Progress", "Progress Gap",
            ]
            importances = _model.feature_importances_
            top_features = sorted(
                zip(feature_names, importances), key=lambda x: x[1], reverse=True
            )[:4]
            for fname, imp in top_features:
                if imp > 0.05:
                    factors.append(f"{fname} (model weight: {imp:.2f})")

            if progress_gap > 10:
                factors.append(
                    f"Schedule gap: {progress_gap:.0f}% behind expected progress"
                )
            if overdue_tasks > 0:
                factors.append(f"{overdue_tasks} overdue task(s) contributing to delay")
            if critical_issues > 0:
                factors.append(f"{critical_issues} critical issue(s) impacting timeline")

            if not factors:
                factors.append("Project appears on or ahead of schedule")

            # Delay probability: sigmoid of (delay_days / days_remaining)
            ratio = delay_days / max(1, days_remaining)
            delay_prob = min(0.95, max(0.03, ratio / (1 + ratio)))

            return {
                "delay_days": delay_days,
                "raw_delay_days": round(raw_pred, 2),
                "delay_probability": round(delay_prob, 3),
                "contributing_factors": factors,
                "model_name": "GradientBoostingRegressor",
                "model_version": "1.0",
                "is_demo": True,
                "inference_note": "Prototype model trained on synthetic data. For indicative purposes only.",
            }
        except Exception:
            pass  # fall through to heuristic

    # ── HEURISTIC FALLBACK ───────────────────────────────────────────────────
    delay_days = 0

    if progress_gap > 20:
        delay_factor = progress_gap / 100
        delay_days += int(days_remaining * delay_factor * 1.2)
        factors.append(
            f"Progress {progress:.0f}% behind schedule ({schedule_progress:.0f}% expected)"
        )
    if overdue_tasks > 0:
        delay_days += overdue_tasks * 2
        factors.append(f"{overdue_tasks} overdue task(s) contributing to delay")
    if critical_issues > 0:
        delay_days += critical_issues * 3
        factors.append(f"{critical_issues} critical issue(s) impacting timeline")
    if team_workload > 110:
        delay_days += int((team_workload - 100) / 10)
        factors.append(f"Team overloaded ({team_workload:.0f}% capacity)")

    delay_days = max(0, delay_days)
    delay_prob = min(0.95, max(0.03,
        (delay_days / max(1, days_remaining)) * 0.5 +
        overdue_tasks * 0.05 +
        critical_issues * 0.08 +
        max(0, progress_gap) / 200
    ))

    if not factors:
        factors.append("Project appears on schedule")

    return {
        "delay_days": int(delay_days),
        "delay_probability": round(delay_prob, 3),
        "contributing_factors": factors,
        "model_name": "HeuristicFallback",
        "model_version": "1.0",
        "is_demo": True,
        "inference_note": "ML model unavailable. Using rule-based heuristics. Run scripts/train_models.py.",
    }
