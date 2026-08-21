"""
Budget Overrun Prediction Inference Module
"""
from typing import Dict, Any


def predict_budget_overrun(features: Dict[str, Any], project: dict) -> Dict[str, Any]:
    """
    Predict budget overrun using spending rate analysis.
    Can be replaced with a trained ML regression model.
    """
    budget = project.get("budget", 0)
    expenditure = project.get("current_expenditure", 0)
    progress = features.get("progress", 0)
    remaining_work = features.get("remaining_work", 100)
    budget_utilization = features.get("budget_utilization", 0)

    factors = []
    predicted_final_cost = expenditure
    overrun_amount = 0.0
    overrun_risk = "LOW"

    if budget <= 0:
        return {
            "predicted_final_cost": 0,
            "overrun_amount": 0,
            "overrun_risk": "UNKNOWN",
            "contributing_factors": ["No budget set for this project"],
            "is_demo": True,
            "model_name": "HeuristicBudgetEstimator",
        }

    # Spending rate extrapolation
    if progress > 0:
        spending_rate = expenditure / max(1, progress)  # cost per % progress
        predicted_final_cost = spending_rate * 100
        overrun_amount = max(0, predicted_final_cost - budget)

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
            factors.append(f"Budget {budget_utilization:.0f}% consumed with {remaining_work:.0f}% work remaining")

        if budget_utilization > 75 and progress < 50:
            overrun_risk = "HIGH"
            factors.append(f"High spending ({budget_utilization:.0f}%) with low progress ({progress:.0f}%)")
    else:
        predicted_final_cost = expenditure
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
        "model_name": "HeuristicBudgetEstimator",
        "is_demo": True,
        "inference_note": "Spending rate extrapolation. Replace with trained regression model for production.",
    }
