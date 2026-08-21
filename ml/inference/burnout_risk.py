"""
Employee Burnout Risk Prediction Inference Module
Model: RandomForestClassifier (prototype/demo model trained on synthetic data)

DISCLAIMER: This is a workload-based burnout RISK indicator.
It is NOT a medical or psychological diagnosis.
"""
import os
import joblib
import numpy as np
from typing import Dict, Any

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'burnout_risk_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'burnout_risk_scaler.pkl')

RISK_LABELS = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}

_model = None
_scaler = None


def _load_model():
    global _model, _scaler
    if _model is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            _model = joblib.load(MODEL_PATH)
            _scaler = joblib.load(SCALER_PATH)
    return _model is not None


def _feature_vector(features: Dict[str, Any]) -> np.ndarray:
    return np.array([[
        features.get("workload_ratio", 100),
        features.get("estimated_hours", 40),
        features.get("overtime_hours", 0),
        features.get("active_projects", 1),
        features.get("active_task_count", 0),
        features.get("overdue_task_count", 0),
        features.get("sprint_story_points", 0),
        features.get("completion_rate", 80),
        features.get("high_priority_task_count", 0),
    ]])


def _rule_based_fallback(features: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    factors = []

    workload_ratio = features.get("workload_ratio", 100)
    overtime = features.get("overtime_hours", 0)
    overdue = features.get("overdue_task_count", 0)
    active_projects = features.get("active_projects", 1)
    active_tasks = features.get("active_task_count", 0)
    completion_rate = features.get("completion_rate", 80)
    high_priority = features.get("high_priority_task_count", 0)

    if workload_ratio > 140:
        score += 3
        factors.append(f"Workload at {workload_ratio:.0f}% of capacity (critical overload)")
    elif workload_ratio > 115:
        score += 2
        factors.append(f"Workload at {workload_ratio:.0f}% of capacity (overloaded)")
    elif workload_ratio > 95:
        score += 1
        factors.append(f"Workload at {workload_ratio:.0f}% of capacity (near limit)")

    if overtime > 20:
        score += 2
        factors.append(f"{overtime:.0f}h estimated overtime this period")
    elif overtime > 8:
        score += 1
        factors.append(f"{overtime:.0f}h estimated overtime this period")

    if overdue > 5:
        score += 2
        factors.append(f"{overdue} overdue tasks creating pressure")
    elif overdue > 2:
        score += 1
        factors.append(f"{overdue} overdue tasks")

    if active_projects > 3:
        score += 1
        factors.append(f"Assigned to {active_projects} active projects simultaneously")

    if high_priority > 5:
        score += 1
        factors.append(f"{high_priority} high-priority tasks requiring attention")

    if completion_rate < 40:
        score += 1
        factors.append(f"Low completion rate ({completion_rate:.0f}%) indicating backlog")

    if score >= 5:
        risk_level = "HIGH"
        probability = min(0.95, 0.65 + score * 0.04)
    elif score >= 3:
        risk_level = "MEDIUM"
        probability = min(0.70, 0.40 + score * 0.06)
    else:
        risk_level = "LOW"
        probability = max(0.05, 0.25 - score * 0.05)

    if not factors:
        factors.append("Workload appears within sustainable limits")

    return {
        "risk_level": risk_level,
        "risk_probability": round(probability, 3),
        "contributing_factors": factors,
        "model_name": "RuleBasedFallback",
        "model_version": "1.0",
        "is_demo": True,
        "inference_note": "⚠️ Model not trained yet. Using rule-based heuristics. Run scripts/train_models.py to train ML models.",
        "disclaimer": "Workload-based burnout risk indicator. NOT a medical or psychological diagnosis.",
    }


def predict_burnout_risk(features: Dict[str, Any]) -> Dict[str, Any]:
    if _load_model():
        try:
            X = _feature_vector(features)
            X_scaled = _scaler.transform(X)
            pred_class = _model.predict(X_scaled)[0]
            probabilities = _model.predict_proba(X_scaled)[0]
            risk_level = RISK_LABELS[pred_class]
            risk_prob = float(probabilities[pred_class])

            feature_names = [
                "Workload Ratio", "Estimated Hours", "Overtime Hours",
                "Active Projects", "Active Tasks", "Overdue Tasks",
                "Sprint Story Points", "Completion Rate", "High Priority Tasks"
            ]
            importances = _model.feature_importances_
            feature_impact = sorted(
                zip(feature_names, importances),
                key=lambda x: x[1], reverse=True
            )[:5]
            contributing_factors = [f"{name} (impact: {imp:.2f})" for name, imp in feature_impact if imp > 0.02]

            return {
                "risk_level": risk_level,
                "risk_probability": round(risk_prob, 3),
                "contributing_factors": contributing_factors,
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "is_demo": True,
                "inference_note": "Prototype model trained on synthetic data. For indicative purposes only.",
                "disclaimer": "Workload-based burnout risk indicator. NOT a medical or psychological diagnosis.",
            }
        except Exception:
            pass

    return _rule_based_fallback(features)
