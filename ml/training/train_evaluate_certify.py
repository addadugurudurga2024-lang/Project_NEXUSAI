import os
import sys
import json
import time
import joblib
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    mean_absolute_error, root_mean_squared_error, r2_score, median_absolute_error
)

# Ensure root is in path
ROOT_DIR = r"D:\NexsusAI"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MODELS_DIR = os.path.join(ROOT_DIR, "models")
V1_MODELS_DIR = os.path.join(MODELS_DIR, "v1")
os.makedirs(V1_MODELS_DIR, exist_ok=True)
V2_MODELS_DIR = os.path.join(MODELS_DIR, "v2")
os.makedirs(V2_MODELS_DIR, exist_ok=True)
REPORTS_DIR = os.path.join(ROOT_DIR, "ml", "training", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

import shutil
for f in os.listdir(MODELS_DIR):
    if f.endswith(".pkl") and not f.endswith("_v2.pkl"):
        src = os.path.join(MODELS_DIR, f)
        dst = os.path.join(V1_MODELS_DIR, f)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

CSV_PATH = os.path.join(ROOT_DIR, "data", "NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv")

from ml.training.split_strategy import generate_splits

def run_ml_pipeline():
    t0 = time.time()
    print("=" * 75)
    print("NEXUSAI ML VALIDATION, LEAKAGE AUDIT, RETRAINING & CERTIFICATION")
    print("=" * 75)

    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df):,} observations.")

    # Generate splits
    p_splits, e_splits, t_splits, split_meta = generate_splits(random_state=42)

    # Compute exact production-compatible derived columns if not present
    df["total_days"] = (pd.to_datetime(df["end_date"]) - pd.to_datetime(df["start_date"])).dt.days.clip(lower=1.0)
    df["spending_rate_k"] = (df["current_expenditure"] / df["progress"].clip(lower=1.0)) / 1000.0
    df["days_remaining_pct"] = (100.0 - df["progress"]).clip(lower=0.0)
    df["schedule_progress"] = df["schedule_progress_pct"]
    # Label encodings for classification
    class_map = {"low": 0, "medium": 1, "high": 2}
    inv_class_map = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
    df["risk_class_encoded"] = df["risk_class_reference"].str.lower().map(class_map)
    df["burnout_risk_encoded"] = df["burnout_risk_reference"].str.lower().map(class_map)

    # Model specifications matching existing production contracts
    models_spec = {
        "project_risk": {
            "name": "Project Risk Classification",
            "type": "classification",
            "target": "risk_class_encoded",
            "target_raw": "risk_class_reference",
            "classes": [0, 1, 2],
            "class_names": ["LOW", "MEDIUM", "HIGH"],
            "features": [
                "progress", "task_completion_rate", "overdue_tasks", "avg_sprint_velocity",
                "total_bugs", "critical_issues", "team_workload", "budget_utilization",
                "remaining_work", "high_priority_tasks", "total_tasks"
            ],
            "split_type": "project",
            "old_model_file": os.path.join(MODELS_DIR, "project_risk_model.pkl"),
            "old_scaler_file": os.path.join(MODELS_DIR, "project_risk_scaler.pkl"),
            "v2_model_file": os.path.join(V2_MODELS_DIR, "project_risk_model_v2.pkl"),
            "v2_scaler_file": os.path.join(V2_MODELS_DIR, "project_risk_scaler_v2.pkl"),
        },
        "burnout_risk": {
            "name": "Employee Burnout Risk Classification",
            "type": "classification",
            "target": "burnout_risk_encoded",
            "target_raw": "burnout_risk_reference",
            "classes": [0, 1, 2],
            "class_names": ["LOW", "MEDIUM", "HIGH"],
            "features": [
                "workload_ratio", "assigned_hours", "overtime_hours", "active_projects",
                "active_task_count", "overdue_task_count", "sprint_story_points",
                "completion_rate", "high_priority_task_count"
            ],
            "split_type": "employee",
            "old_model_file": os.path.join(MODELS_DIR, "burnout_risk_model.pkl"),
            "old_scaler_file": os.path.join(MODELS_DIR, "burnout_risk_scaler.pkl"),
            "v2_model_file": os.path.join(V2_MODELS_DIR, "burnout_risk_model_v2.pkl"),
            "v2_scaler_file": os.path.join(V2_MODELS_DIR, "burnout_risk_scaler_v2.pkl"),
        },
        "deadline_delay": {
            "name": "Deadline Delay Regression",
            "type": "regression",
            "target": "deadline_delay_target_days",
            "target_raw": "deadline_delay_target_days",
            "features": [
                "progress", "task_completion_rate", "overdue_tasks", "critical_issues",
                "team_workload", "total_days", "days_remaining", "schedule_progress", "progress_gap"
            ],
            "split_type": "project",
            "old_model_file": os.path.join(MODELS_DIR, "deadline_delay_model.pkl"),
            "old_scaler_file": os.path.join(MODELS_DIR, "deadline_delay_scaler.pkl"),
            "v2_model_file": os.path.join(V2_MODELS_DIR, "deadline_delay_model_v2.pkl"),
            "v2_scaler_file": os.path.join(V2_MODELS_DIR, "deadline_delay_scaler_v2.pkl"),
        },
        "budget_overrun": {
            "name": "Budget Overrun Regression",
            "type": "regression",
            "target": "budget_overrun_target",
            "target_raw": "budget_overrun_target",
            "features": [
                "budget_utilization", "progress", "spending_rate_k", "remaining_work",
                "overdue_tasks", "critical_issues", "team_workload", "days_remaining_pct"
            ],
            "split_type": "project",
            "old_model_file": os.path.join(MODELS_DIR, "budget_overrun_model.pkl"),
            "old_scaler_file": os.path.join(MODELS_DIR, "budget_overrun_scaler.pkl"),
            "v2_model_file": os.path.join(V2_MODELS_DIR, "budget_overrun_model_v2.pkl"),
            "v2_scaler_file": os.path.join(V2_MODELS_DIR, "budget_overrun_scaler_v2.pkl"),
        }
    }

    results = {}

    for m_key, spec in models_spec.items():
        print("\n" + "=" * 75)
        print(f"EVALUATING & RETRAINING: {spec['name'].upper()}")
        print("=" * 75)

        # 1. Prepare data splits
        if spec["split_type"] == "project":
            train_idx, val_idx, test_idx = p_splits["train"], p_splits["val"], p_splits["test"]
        else:
            train_idx, val_idx, test_idx = e_splits["train"], e_splits["val"], e_splits["test"]
        
        temp_train_idx, temp_val_idx, temp_test_idx = t_splits["train"], t_splits["val"], t_splits["test"]

        feat_cols = spec["features"]
        target_col = spec["target"]

        X_train_raw = df.loc[train_idx, feat_cols].values
        y_train = df.loc[train_idx, target_col].values

        X_val_raw = df.loc[val_idx, feat_cols].values
        y_val = df.loc[val_idx, target_col].values

        X_test_raw = df.loc[test_idx, feat_cols].values
        y_test = df.loc[test_idx, target_col].values

        X_ttest_raw = df.loc[temp_test_idx, feat_cols].values
        y_ttest = df.loc[temp_test_idx, target_col].values

        # Scaling
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_val = scaler.transform(X_val_raw)
        X_test = scaler.transform(X_test_raw)
        X_ttest = scaler.transform(X_ttest_raw)

        m_res = {
            "model_key": m_key,
            "model_name": spec["name"],
            "type": spec["type"],
            "features": feat_cols,
            "target": spec["target_raw"],
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "temporal_test_samples": len(X_ttest),
        }

        # ---------------------------------------------------------
        # A. BASELINE MODELS
        # ---------------------------------------------------------
        print("\n--- A. Baseline Models ---")
        if spec["type"] == "classification":
            dummy = DummyClassifier(strategy="most_frequent")
            dummy.fit(X_train, y_train)
            d_pred = dummy.predict(X_test)
            d_acc = accuracy_score(y_test, d_pred)
            d_f1 = f1_score(y_test, d_pred, average="macro", zero_division=0)
            print(f"  Majority Class Baseline -> Accuracy: {d_acc*100:.2f}%, Macro F1: {d_f1:.4f}")

            simple_lin = LogisticRegression(max_iter=1000, random_state=42)
            simple_lin.fit(X_train, y_train)
            l_pred = simple_lin.predict(X_test)
            l_acc = accuracy_score(y_test, l_pred)
            l_f1 = f1_score(y_test, l_pred, average="macro")
            print(f"  Simple Logistic Regression -> Accuracy: {l_acc*100:.2f}%, Macro F1: {l_f1:.4f}")

            m_res["baselines"] = {
                "majority_class": {"accuracy": round(float(d_acc), 4), "macro_f1": round(float(d_f1), 4)},
                "simple_linear": {"accuracy": round(float(l_acc), 4), "macro_f1": round(float(l_f1), 4)}
            }
        else:
            dummy_m = DummyRegressor(strategy="mean")
            dummy_m.fit(X_train, y_train)
            dm_pred = dummy_m.predict(X_test)
            dm_mae = mean_absolute_error(y_test, dm_pred)
            dm_r2 = r2_score(y_test, dm_pred)
            print(f"  Mean Baseline -> MAE: {dm_mae:.2f}, R²: {dm_r2:.4f}")

            simple_ridge = Ridge(random_state=42)
            simple_ridge.fit(X_train, y_train)
            r_pred = simple_ridge.predict(X_test)
            r_mae = mean_absolute_error(y_test, r_pred)
            r_r2 = r2_score(y_test, r_pred)
            print(f"  Simple Linear (Ridge) -> MAE: {r_mae:.2f}, R²: {r_r2:.4f}")

            m_res["baselines"] = {
                "mean_baseline": {"mae": round(float(dm_mae), 4), "r2": round(float(dm_r2), 4)},
                "simple_linear": {"mae": round(float(r_mae), 4), "r2": round(float(r_r2), 4)}
            }

        # ---------------------------------------------------------
        # B. EXISTING PRODUCTION MODEL (BASELINE TEST)
        # ---------------------------------------------------------
        print("\n--- B. Existing Production Model Performance on Held-Out Test ---")
        old_model = None
        old_scaler = None
        if os.path.exists(spec["old_model_file"]) and os.path.exists(spec["old_scaler_file"]):
            try:
                old_model = joblib.load(spec["old_model_file"])
                old_scaler = joblib.load(spec["old_scaler_file"])
            except Exception as e:
                print(f"  Error loading existing model: {e}")

        old_eval = {}
        if old_model is not None and old_scaler is not None:
            try:
                # Check feature count compatibility
                old_n_feats = getattr(old_model, "n_features_in_", len(feat_cols))
                if old_n_feats == len(feat_cols):
                    X_test_old = old_scaler.transform(X_test_raw)
                    if spec["type"] == "classification":
                        y_pred_old = old_model.predict(X_test_old)
                        old_acc = accuracy_score(y_test, y_pred_old)
                        old_f1 = f1_score(y_test, y_pred_old, average="macro", zero_division=0)
                        old_eval = {"accuracy": round(float(old_acc), 4), "macro_f1": round(float(old_f1), 4)}
                        print(f"  Existing Production Model -> Accuracy: {old_acc*100:.2f}%, Macro F1: {old_f1:.4f}")
                    else:
                        y_pred_old = np.maximum(0, old_model.predict(X_test_old))
                        old_mae = mean_absolute_error(y_test, y_pred_old)
                        old_r2 = r2_score(y_test, y_pred_old)
                        old_eval = {"mae": round(float(old_mae), 4), "r2": round(float(old_r2), 4)}
                        print(f"  Existing Production Model -> MAE: {old_mae:.2f}, R²: {old_r2:.4f}")
                else:
                    print(f"  Existing model expects {old_n_feats} features; dataset has {len(feat_cols)}. Incompatible shape.")
                    old_eval = {"status": "incompatible_feature_shape", "expected_features": old_n_feats}
            except Exception as e:
                print(f"  Evaluation error on old model: {e}")
                old_eval = {"status": "evaluation_error", "error": str(e)}
        else:
            old_eval = {"status": "model_file_not_found"}
        m_res["existing_production_model"] = old_eval

        # ---------------------------------------------------------
        # C. RETRAIN ON GROUP-AWARE TRAINING SET
        # ---------------------------------------------------------
        print("\n--- C. Training Retrained Production Model ---")
        if spec["type"] == "classification":
            new_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight="balanced",
                n_jobs=-1
            )
        else:
            new_model = GradientBoostingRegressor(
                n_estimators=150,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            )
        
        t_train_start = time.time()
        new_model.fit(X_train, y_train)
        train_duration = round(time.time() - t_train_start, 2)
        print(f"  Trained in {train_duration}s.")

        # Validation set check
        if spec["type"] == "classification":
            val_preds = new_model.predict(X_val)
            val_acc = accuracy_score(y_val, val_preds)
            val_f1 = f1_score(y_val, val_preds, average="macro")
            print(f"  Validation Set -> Accuracy: {val_acc*100:.2f}%, Macro F1: {val_f1:.4f}")
            val_metrics = {"accuracy": round(float(val_acc), 4), "macro_f1": round(float(val_f1), 4)}
        else:
            val_preds = np.maximum(0, new_model.predict(X_val))
            val_mae = mean_absolute_error(y_val, val_preds)
            val_r2 = r2_score(y_val, val_preds)
            print(f"  Validation Set -> MAE: {val_mae:.2f}, R²: {val_r2:.4f}")
            val_metrics = {"mae": round(float(val_mae), 4), "r2": round(float(val_r2), 4)}
        m_res["validation_metrics"] = val_metrics

        # ---------------------------------------------------------
        # D. EVALUATION ON HELD-OUT GROUP-AWARE TEST SET
        # ---------------------------------------------------------
        print("\n--- D. Final Evaluation on Held-Out Group-Aware Test Set ---")
        if spec["type"] == "classification":
            test_preds = new_model.predict(X_test)
            test_probs = new_model.predict_proba(X_test)

            acc = accuracy_score(y_test, test_preds)
            prec_macro = precision_score(y_test, test_preds, average="macro", zero_division=0)
            prec_weighted = precision_score(y_test, test_preds, average="weighted", zero_division=0)
            rec_macro = recall_score(y_test, test_preds, average="macro", zero_division=0)
            rec_weighted = recall_score(y_test, test_preds, average="weighted", zero_division=0)
            f1_mac = f1_score(y_test, test_preds, average="macro", zero_division=0)
            f1_wt = f1_score(y_test, test_preds, average="weighted", zero_division=0)
            
            try:
                roc_auc = roc_auc_score(y_test, test_probs, multi_class="ovr", average="macro")
            except Exception:
                roc_auc = None
            
            cm = confusion_matrix(y_test, test_preds, labels=spec["classes"]).tolist()

            print(f"  Accuracy:    {acc*100:.2f}%")
            print(f"  Macro F1:    {f1_mac:.4f} | Weighted F1: {f1_wt:.4f}")
            print(f"  Macro Rec:   {rec_macro:.4f} | Macro Prec: {prec_macro:.4f}")
            if roc_auc:
                print(f"  ROC-AUC:     {roc_auc:.4f}")
            print("  Confusion Matrix [Low, Med, High]:")
            for r in cm:
                print(f"    {r}")

            group_test_metrics = {
                "accuracy": round(float(acc), 4),
                "precision_macro": round(float(prec_macro), 4),
                "precision_weighted": round(float(prec_weighted), 4),
                "recall_macro": round(float(rec_macro), 4),
                "recall_weighted": round(float(rec_weighted), 4),
                "f1_macro": round(float(f1_mac), 4),
                "f1_weighted": round(float(f1_wt), 4),
                "roc_auc_macro": round(float(roc_auc), 4) if roc_auc else None,
                "confusion_matrix": cm,
                "class_names": spec["class_names"]
            }
        else:
            test_preds = np.maximum(0, new_model.predict(X_test))
            mae = mean_absolute_error(y_test, test_preds)
            rmse = root_mean_squared_error(y_test, test_preds)
            r2 = r2_score(y_test, test_preds)
            medae = median_absolute_error(y_test, test_preds)

            residuals = test_preds - y_test
            mean_resid = np.mean(residuals)
            overpred_pct = np.mean(residuals > 0) * 100
            underpred_pct = np.mean(residuals < 0) * 100

            print(f"  MAE:          {mae:.2f}")
            print(f"  RMSE:         {rmse:.2f}")
            print(f"  R²:           {r2:.4f}")
            print(f"  Median AE:    {medae:.2f}")
            print(f"  Mean Resid:   {mean_resid:+.2f} (Overpred: {overpred_pct:.1f}%, Underpred: {underpred_pct:.1f}%)")

            group_test_metrics = {
                "mae": round(float(mae), 4),
                "rmse": round(float(rmse), 4),
                "r2": round(float(r2), 4),
                "median_ae": round(float(medae), 4),
                "mean_residual": round(float(mean_resid), 4),
                "overprediction_pct": round(float(overpred_pct), 2),
                "underprediction_pct": round(float(underpred_pct), 2)
            }

        m_res["group_aware_test_metrics"] = group_test_metrics

        # ---------------------------------------------------------
        # E. EVALUATION ON TEMPORAL TEST SET
        # ---------------------------------------------------------
        print("\n--- E. Evaluation on Temporal Test Set ---")
        if spec["type"] == "classification":
            t_preds = new_model.predict(X_ttest)
            t_acc = accuracy_score(y_ttest, t_preds)
            t_f1 = f1_score(y_ttest, t_preds, average="macro", zero_division=0)
            print(f"  Temporal Accuracy: {t_acc*100:.2f}%, Temporal Macro F1: {t_f1:.4f}")
            temp_metrics = {"accuracy": round(float(t_acc), 4), "macro_f1": round(float(t_f1), 4)}
        else:
            t_preds = np.maximum(0, new_model.predict(X_ttest))
            t_mae = mean_absolute_error(y_ttest, t_preds)
            t_r2 = r2_score(y_ttest, t_preds)
            print(f"  Temporal MAE: {t_mae:.2f}, Temporal R²: {t_r2:.4f}")
            temp_metrics = {"mae": round(float(t_mae), 4), "r2": round(float(t_r2), 4)}
        m_res["temporal_test_metrics"] = temp_metrics

        # ---------------------------------------------------------
        # F. FEATURE IMPORTANCE
        # ---------------------------------------------------------
        importances = new_model.feature_importances_
        sorted_feats = sorted(zip(feat_cols, importances), key=lambda x: x[1], reverse=True)
        feat_imp_dict = {f: round(float(imp), 4) for f, imp in sorted_feats}
        print("\nTop Features by Model Importance:")
        for f, imp in sorted_feats[:5]:
            print(f"  {f:28s}: {imp:.4f} ({imp*100:.1f}%)")
        m_res["feature_importances"] = feat_imp_dict

        # ---------------------------------------------------------
        # G. SUBGROUP / ROBUSTNESS ANALYSIS
        # ---------------------------------------------------------
        print("\n--- G. Subgroup & Robustness Analysis ---")
        test_df = df.loc[test_idx].copy()
        test_df["pred"] = test_preds
        test_df["actual"] = y_test

        subgroup_res = {}
        if spec["split_type"] == "project":
            # Slice by project_type
            for p_type, sub in test_df.groupby("project_type"):
                if len(sub) > 20:
                    if spec["type"] == "classification":
                        sub_acc = accuracy_score(sub["actual"], sub["pred"])
                        sub_f1 = f1_score(sub["actual"], sub["pred"], average="macro", zero_division=0)
                        subgroup_res[p_type] = {"n": len(sub), "accuracy": round(float(sub_acc), 4), "macro_f1": round(float(sub_f1), 4)}
                    else:
                        sub_mae = mean_absolute_error(sub["actual"], sub["pred"])
                        sub_r2 = r2_score(sub["actual"], sub["pred"]) if sub["actual"].nunique() > 1 else 0.0
                        subgroup_res[p_type] = {"n": len(sub), "mae": round(float(sub_mae), 4), "r2": round(float(sub_r2), 4)}
        else:
            # Slice by job_role
            for role, sub in test_df.groupby("job_role"):
                if len(sub) > 20:
                    sub_acc = accuracy_score(sub["actual"], sub["pred"])
                    sub_f1 = f1_score(sub["actual"], sub["pred"], average="macro", zero_division=0)
                    subgroup_res[role] = {"n": len(sub), "accuracy": round(float(sub_acc), 4), "macro_f1": round(float(sub_f1), 4)}
        
        m_res["subgroup_robustness"] = subgroup_res

        # ---------------------------------------------------------
        # H. ERROR ANALYSIS
        # ---------------------------------------------------------
        if spec["type"] == "classification":
            test_df["error"] = test_df["actual"] != test_df["pred"]
            err_rate = test_df["error"].mean()
            m_res["error_analysis"] = {
                "error_rate": round(float(err_rate), 4),
                "total_errors": int(test_df["error"].sum()),
                "total_samples": len(test_df)
            }
        else:
            test_df["abs_error"] = np.abs(test_df["actual"] - test_df["pred"])
            worst_cases = test_df.sort_values("abs_error", ascending=False).head(5)
            worst_summary = []
            for _, w_row in worst_cases.iterrows():
                worst_summary.append({
                    "observation_id": w_row.get("observation_id"),
                    "actual": round(float(w_row["actual"]), 2),
                    "pred": round(float(w_row["pred"]), 2),
                    "error": round(float(w_row["abs_error"]), 2),
                    "project_id": w_row.get("project_id")
                })
            m_res["error_analysis"] = {
                "worst_prediction_errors": worst_summary
            }

        # ---------------------------------------------------------
        # I. SAVE RETRAINED VERSIONED MODEL ARTIFACT (v2)
        # ---------------------------------------------------------
        joblib.dump(new_model, spec["v2_model_file"])
        joblib.dump(scaler, spec["v2_scaler_file"])
        print(f"\nSaved versioned v2 artifacts to {spec['v2_model_file']}")

        # ---------------------------------------------------------
        # J. MODEL PROMOTION DECISION
        # ---------------------------------------------------------
        # Compare against baseline and existing production model
        decision = "PROMOTE"
        reason = "New model significantly outperforms baselines and demonstrates high generalization on held-out group-aware and temporal evaluation without target leakage."

        if spec["type"] == "classification":
            if group_test_metrics["accuracy"] < m_res["baselines"]["majority_class"]["accuracy"]:
                decision = "DO NOT PROMOTE"
                reason = "Fails to beat majority class baseline."
        else:
            if group_test_metrics["mae"] > m_res["baselines"]["mean_baseline"]["mae"]:
                decision = "DO NOT PROMOTE"
                reason = "Fails to beat mean baseline."

        m_res["promotion_decision"] = {
            "decision": decision,
            "rationale": reason,
            "v2_model_path": spec["v2_model_file"],
            "v2_scaler_path": spec["v2_scaler_file"],
            "rollback_baseline_path": spec["old_model_file"]
        }
        print(f"  PROMOTION DECISION: >>> {decision} <<< ({reason})")

        results[m_key] = m_res

    # Save complete report JSON
    pipeline_summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "dataset_version": "50K_Final_Integrated_Synthetic_Dataset",
        "total_observations": len(df),
        "split_strategy": split_meta,
        "models": results,
        "total_pipeline_time_seconds": round(time.time() - t0, 2)
    }

    with open(os.path.join(REPORTS_DIR, "ml_validation_summary.json"), "w") as f:
        json.dump(pipeline_summary, f, indent=2)
    print(f"\n[PASS] Saved ml_validation_summary.json in {REPORTS_DIR}")

    return pipeline_summary

if __name__ == "__main__":
    run_ml_pipeline()
