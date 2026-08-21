"""
NexusAI ML Model Training Script
Trains prototype models on synthetic data for demonstration purposes.

IMPORTANT: These are prototype/demo models trained on synthetic data.
Predictions are indicative only and not calibrated for production use.

Usage:
    cd d:\\NexsusAI
    python scripts/train_models.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

np.random.seed(42)
N = 2000


def generate_project_risk_data():
    """Generate synthetic project risk training data."""
    progress = np.random.uniform(0, 100, N)
    task_completion = progress + np.random.normal(0, 10, N)
    task_completion = np.clip(task_completion, 0, 100)
    overdue_tasks = np.random.poisson(2, N)
    sprint_velocity = np.random.uniform(0, 30, N)
    total_bugs = np.random.poisson(5, N)
    critical_issues = np.random.poisson(1, N)
    team_workload = np.random.uniform(50, 180, N)
    budget_utilization = np.random.uniform(0, 120, N)
    remaining_work = 100 - progress
    high_priority_tasks = np.random.poisson(3, N)
    total_tasks = np.random.randint(5, 50, N)

    # Risk logic
    risk_score = (
        (100 - progress) / 50 +
        overdue_tasks * 0.5 +
        critical_issues * 0.8 +
        np.clip((budget_utilization - 70) / 30, 0, 2) +
        np.clip((team_workload - 100) / 40, 0, 1.5) +
        np.clip((100 - task_completion) / 40, 0, 1.5) +
        total_bugs * 0.1
    )

    # Labels: 0=LOW, 1=MEDIUM, 2=HIGH
    labels = np.where(risk_score >= 3.5, 2, np.where(risk_score >= 2.0, 1, 0))
    # Add some noise
    flip_mask = np.random.rand(N) < 0.05
    labels[flip_mask] = np.random.randint(0, 3, flip_mask.sum())

    X = np.column_stack([
        progress, task_completion, overdue_tasks, sprint_velocity,
        total_bugs, critical_issues, team_workload, budget_utilization,
        remaining_work, high_priority_tasks, total_tasks
    ])
    return X, labels


def generate_burnout_risk_data():
    """Generate synthetic employee burnout risk training data."""
    workload_ratio = np.random.uniform(30, 200, N)
    estimated_hours = workload_ratio / 100 * 40
    overtime_hours = np.maximum(0, estimated_hours - 40)
    active_projects = np.random.randint(1, 6, N)
    active_task_count = np.random.poisson(8, N)
    overdue_task_count = np.random.poisson(2, N)
    sprint_story_points = np.random.uniform(0, 40, N)
    completion_rate = np.random.uniform(20, 100, N)
    high_priority_task_count = np.random.poisson(3, N)

    # Burnout risk logic
    burnout_score = (
        (workload_ratio - 80) / 40 +
        overtime_hours / 20 +
        overdue_task_count * 0.4 +
        active_projects * 0.3 +
        high_priority_task_count * 0.2 +
        np.clip((80 - completion_rate) / 30, 0, 1.5)
    )

    labels = np.where(burnout_score >= 3.0, 2, np.where(burnout_score >= 1.5, 1, 0))
    flip_mask = np.random.rand(N) < 0.05
    labels[flip_mask] = np.random.randint(0, 3, flip_mask.sum())

    X = np.column_stack([
        workload_ratio, estimated_hours, overtime_hours,
        active_projects, active_task_count, overdue_task_count,
        sprint_story_points, completion_rate, high_priority_task_count
    ])
    return X, labels


def train_project_risk_model():
    print("\nTraining Project Risk Model (RandomForestClassifier)...")
    X, y = generate_project_risk_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight='balanced')
    model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    print("Project Risk Model Report:")
    print(classification_report(y_test, y_pred, target_names=["LOW", "MEDIUM", "HIGH"]))

    joblib.dump(model, os.path.join(MODELS_DIR, 'project_risk_model.pkl'))
    joblib.dump(scaler, os.path.join(MODELS_DIR, 'project_risk_scaler.pkl'))
    print(f"Project risk model saved to models/")


def train_burnout_risk_model():
    print("\nTraining Burnout Risk Model (RandomForestClassifier)...")
    X, y = generate_burnout_risk_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight='balanced')
    model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    print("Burnout Risk Model Report:")
    print(classification_report(y_test, y_pred, target_names=["LOW", "MEDIUM", "HIGH"]))

    joblib.dump(model, os.path.join(MODELS_DIR, 'burnout_risk_model.pkl'))
    joblib.dump(scaler, os.path.join(MODELS_DIR, 'burnout_risk_scaler.pkl'))
    print(f"Burnout risk model saved to models/")


if __name__ == "__main__":
    print("=" * 60)
    print("NexusAI ML Model Training")
    print("PROTOTYPE MODELS - TRAINED ON SYNTHETIC DATA")
    print("For demonstration purposes only")
    print("=" * 60)
    train_project_risk_model()
    train_burnout_risk_model()
    print("\nAll models trained and saved successfully!")
    print("Models are ready for inference.")
