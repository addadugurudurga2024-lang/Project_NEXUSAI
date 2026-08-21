"""
Project Risk Prediction Inference Module
Model: RandomForestClassifier (prototype/demo model trained on synthetic data)
"""
import os
import joblib
import numpy as np
from typing import Dict, Any

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'project_risk_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'project_risk_scaler.pkl')

RISK_LABELS = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}

_model = None
_scaler = None


def _load_model():
    global _model, _scaler
    if _model is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            _model = joblib.load(MODEL_PATH)
            _scaler = joblib.load(SCALER_PATH)
            return True
    return _model is not None


def _feature_vector(features: Dict[str, Any]) -> np.ndarray:
    return np.array([[
        features.get("progress", 0),
        features.get("task_completion_rate", 0),
        features.get("overdue_tasks", 0),
        features.get("avg_sprint_velocity", 0),
        features.get("total_bugs", 0),
        features.get("critical_issues", 0),
        features.get("team_workload", 50),
        features.get("budget_utilization", 0),
        features.get("remaining_work", 100),
        features.get("high_priority_tasks", 0),
        features.get("total_tasks", 0),
    ]])


def _rule_based_fallback(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic rule-based fallback when ML model is unavailable.
    Clearly identified as rule-based inference, not ML model output.
    """
    score = 0
    factors = []

    progress = features.get("progress", 0)
    task_rate = features.get("task_completion_rate", 0)
    overdue = features.get("overdue_tasks", 0)
    critical = features.get("critical_issues", 0)
    budget_util = features.get("budget_utilization", 0)
    workload = features.get("team_workload", 50)
    remaining = features.get("remaining_work", 100)

    if progress < 30 and remaining > 70:
        score += 2
        factors.append("Low progress with significant remaining work")
    if overdue > 5:
        score += 2
        factors.append(f"{overdue} overdue tasks detected")
    elif overdue > 2:
        score += 1
        factors.append(f"{overdue} overdue tasks detected")
    if critical > 2:
        score += 2
        factors.append(f"{critical} critical issues open")
    elif critical > 0:
        score += 1
        factors.append(f"{critical} critical issue(s) open")
    if budget_util > 90:
        score += 2
        factors.append(f"Budget utilization at {budget_util:.0f}%")
    elif budget_util > 75:
        score += 1
        factors.append(f"Budget utilization at {budget_util:.0f}%")
    if workload > 120:
        score += 1
        factors.append(f"Team workload at {workload:.0f}%")
    if task_rate < 40:
        score += 1
        factors.append(f"Task completion rate low ({task_rate:.0f}%)")

    if score >= 5:
        risk_class = "HIGH"
        probability = min(0.95, 0.65 + score * 0.04)
    elif score >= 3:
        risk_class = "MEDIUM"
        probability = min(0.75, 0.40 + score * 0.06)
    else:
        risk_class = "LOW"
        probability = max(0.05, 0.25 - score * 0.05)

    if not factors:
        factors.append("Project metrics appear stable")

    return {
        "risk_class": risk_class,
        "risk_probability": round(probability, 3),
        "contributing_factors": factors,
        "model_name": "RuleBasedFallback",
        "model_version": "1.0",
        "is_demo": True,
        "inference_note": "⚠️ Model not trained yet. Using rule-based heuristics. Run scripts/train_models.py to train ML models.",
    }


def predict_project_risk_inference(features: Dict[str, Any]) -> Dict[str, Any]:
    if _load_model():
        try:
            X = _feature_vector(features)
            X_scaled = _scaler.transform(X)
            pred_class = _model.predict(X_scaled)[0]
            probabilities = _model.predict_proba(X_scaled)[0]
            risk_class = RISK_LABELS[pred_class]
            risk_prob = float(probabilities[pred_class])

            # Feature importances → contributing factors
            feature_names = [
                "Progress", "Task Completion Rate", "Overdue Tasks",
                "Sprint Velocity", "Total Bugs", "Critical Issues",
                "Team Workload", "Budget Utilization", "Remaining Work",
                "High Priority Tasks", "Total Tasks"
            ]
            importances = _model.feature_importances_
            feature_impact = sorted(
                zip(feature_names, importances),
                key=lambda x: x[1], reverse=True
            )[:5]
            contributing_factors = [f"{name} (impact: {imp:.2f})" for name, imp in feature_impact if imp > 0.02]

            return {
                "risk_class": risk_class,
                "risk_probability": round(risk_prob, 3),
                "contributing_factors": contributing_factors,
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "is_demo": True,
                "inference_note": "Prototype model trained on synthetic data. For indicative purposes only.",
            }
        except Exception as e:
            pass

    return _rule_based_fallback(features)
