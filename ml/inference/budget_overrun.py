"""
Budget Overrun Prediction Inference Module
Model: GradientBoostingRegressor (trained on synthetic data)
Output: Predicted budget overrun amount in dollars (continuous regression, >= 0)

Falls back to spending-rate heuristic if the trained model is unavailable.
"""
import os
import numpy as np
from typing import Dict, Any

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'budget_overrun_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'budget_overrun_scaler.pkl')

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


def predict_budget_overrun(features: Dict[str, Any], project: dict) -> Dict[str, Any]:
    """
    Predict budget overrun using a trained GradientBoostingRegressor.
    Falls back to spending-rate extrapolation if the model is unavailable.
    """
    budget = float(project.get("budget", 0) or 0)
    expenditure = float(project.get("current_expenditure", 0) or 0)
    progress = float(features.get("progress", 0))
    remaining_work = float(features.get("remaining_work", 100))
    budget_utilization = float(features.get("budget_utilization", 0))
    overdue_tasks = float(features.get("overdue_tasks", 0))
    critical_issues = float(features.get("critical_issues", 0))
    team_workload = float(features.get("team_workload", 50))

    factors = []

    if budget <= 0:
        return {
            "predicted_final_cost": expenditure,
            "overrun_amount": 0.0,
            "overrun_risk": "UNKNOWN",
            "budget": budget,
            "expenditure": expenditure,
            "budget_utilization": 0.0,
            "contributing_factors": ["No budget set for this project"],
            "model_name": "N/A",
            "is_demo": True,
        }

    # Spending rate per 1% of progress (normalised per $1000)
    spending_rate_k = (expenditure / max(1.0, progress)) / 1000.0 if progress > 0 else 0.0

    # Days remaining estimate (approximate from project if available)
    days_remaining_pct = max(0.0, 100.0 - progress)

    # ── ML MODEL PATH ────────────────────────────────────────────────────────
    if _load_model():
        try:
            X = np.array([[
                budget_utilization,
                progress,
                spending_rate_k,
                remaining_work,
                overdue_tasks,
                critical_issues,
                team_workload,
                days_remaining_pct,
            ]])
            X_scaled = _scaler.transform(X)
            raw_pred = float(_model.predict(X_scaled)[0])
            overrun_amount = max(0.0, raw_pred)

            predicted_final_cost = expenditure + overrun_amount
            overrun_pct = (overrun_amount / budget) * 100

            if overrun_pct > 20:
                overrun_risk = "HIGH"
                factors.append(f"ML model predicts {overrun_pct:.1f}% budget overrun")
            elif overrun_pct > 8:
                overrun_risk = "MEDIUM"
                factors.append(f"ML model predicts moderate overrun ({overrun_pct:.1f}%)")
            elif overrun_amount > 0:
                overrun_risk = "LOW"
                factors.append(f"Minor overrun risk ({overrun_pct:.1f}%)")
            else:
                overrun_risk = "LOW"
                factors.append("Budget utilization appears within limits")

            # Supplementary context factors
            feature_names = [
                "Budget Utilization", "Progress", "Spending Rate",
                "Remaining Work", "Overdue Tasks", "Critical Issues",
                "Team Workload", "Days Remaining %",
            ]
            importances = _model.feature_importances_
            top_features = sorted(
                zip(feature_names, importances), key=lambda x: x[1], reverse=True
            )[:3]
            for fname, imp in top_features:
                if imp > 0.05:
                    factors.append(f"{fname} (model weight: {imp:.2f})")

            if budget_utilization > 90:
                factors.append(
                    f"Budget {budget_utilization:.0f}% consumed with {remaining_work:.0f}% work remaining"
                )

            return {
                "predicted_final_cost": round(predicted_final_cost, 2),
                "overrun_amount": round(overrun_amount, 2),
                "overrun_risk": overrun_risk,
                "budget": budget,
                "expenditure": expenditure,
                "budget_utilization": round(budget_utilization, 1),
                "contributing_factors": factors,
                "model_name": "GradientBoostingRegressor",
                "model_version": "1.0",
                "is_demo": True,
                "inference_note": "Prototype model trained on synthetic data. For indicative purposes only.",
            }
        except Exception:
            pass  # fall through to heuristic

    # ── HEURISTIC FALLBACK ───────────────────────────────────────────────────
    predicted_final_cost = expenditure
    overrun_amount = 0.0
    overrun_risk = "LOW"

    if progress > 0:
        spending_rate = expenditure / max(1.0, progress)  # cost per 1% progress
        predicted_final_cost = spending_rate * 100
        overrun_amount = max(0.0, predicted_final_cost - budget)

        if overrun_amount > 0:
            overrun_pct = (overrun_amount / budget) * 100
            if overrun_pct > 20:
                overrun_risk = "HIGH"
                factors.append(f"Spending rate predicts {overrun_pct:.0f}% over budget")
            elif overrun_pct > 8:
                overrun_risk = "MEDIUM"
                factors.append(f"Spending rate predicts {overrun_pct:.0f}% over budget")
            else:
                overrun_risk = "LOW"
                factors.append(f"Minor overrun risk ({overrun_pct:.0f}%)")
        else:
            factors.append("Budget utilization appears within limits")

        if budget_utilization > 90:
            if overrun_risk == "LOW":
                overrun_risk = "MEDIUM"
            factors.append(
                f"Budget {budget_utilization:.0f}% consumed with {remaining_work:.0f}% work remaining"
            )
        if budget_utilization > 75 and progress < 50:
            overrun_risk = "HIGH"
            factors.append(f"High spending ({budget_utilization:.0f}%) with low progress ({progress:.0f}%)")
    else:
        factors.append("Insufficient progress data for reliable budget projection")

    if not factors:
        factors.append("Budget appears within acceptable range")

    return {
        "predicted_final_cost": round(predicted_final_cost, 2),
        "overrun_amount": round(overrun_amount, 2),
        "overrun_risk": overrun_risk,
        "budget": budget,
        "expenditure": expenditure,
        "budget_utilization": round(budget_utilization, 1),
        "contributing_factors": factors,
        "model_name": "HeuristicFallback",
        "model_version": "1.0",
        "is_demo": True,
        "inference_note": "ML model unavailable. Using spending-rate heuristic. Run scripts/train_models.py.",
    }
