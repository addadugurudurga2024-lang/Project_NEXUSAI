import os
import json
import pandas as pd
import numpy as np

CSV_PATH = r"D:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv"
OUTPUT_DIR = r"D:\NexsusAI\ml\training\reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def audit_dataset():
    print("=" * 70)
    print("STEP 2 & 3: COMPREHENSIVE 50K DATASET AUDIT")
    print("=" * 70)
    
    df = pd.read_csv(CSV_PATH)
    rows, cols = df.shape
    print(f"Loaded CSV successfully: {rows:,} rows, {cols} columns")

    # Column listing and dtypes
    col_info = []
    for c in df.columns:
        null_count = int(df[c].isnull().sum())
        null_pct = float(null_count / rows * 100)
        dtype_str = str(df[c].dtype)
        nunique = int(df[c].nunique())
        col_info.append({
            "column": c,
            "dtype": dtype_str,
            "null_count": null_count,
            "null_pct": round(null_pct, 4),
            "nunique": nunique,
            "sample": str(df[c].iloc[0])
        })
    
    # Save column info
    with open(os.path.join(OUTPUT_DIR, "column_audit.json"), "w") as f:
        json.dump(col_info, f, indent=2)
    print(f"Saved column audit ({len(col_info)} columns) to column_audit.json")

    # Entity counts
    entities = {
        "unique_observations": int(df["observation_id"].nunique()) if "observation_id" in df else None,
        "unique_projects": int(df["project_id"].nunique()) if "project_id" in df else None,
        "unique_employees": int(df["employee_id"].nunique()) if "employee_id" in df else None,
        "unique_tasks": int(df["task_id"].nunique()) if "task_id" in df else None,
        "unique_sprints": int(df["sprint_id"].nunique()) if "sprint_id" in df else None,
        "unique_issues": int(df[df["issue_id"] != "NO_ISSUE"]["issue_id"].nunique()) if "issue_id" in df else None,
    }
    print("Entities:", entities)

    # Date range
    date_cols = [c for c in df.columns if "date" in c.lower() or "at" in c.lower()]
    date_summary = {}
    for dc in date_cols:
        vals = df[dc].dropna().astype(str)
        valid_dates = vals[vals != "NOT_RESOLVED"]
        if len(valid_dates) > 0:
            date_summary[dc] = {
                "min": str(valid_dates.min()),
                "max": str(valid_dates.max()),
                "sample": str(valid_dates.iloc[0])
            }
    print("Date ranges:", json.dumps(date_summary, indent=2))

    # Target column analysis
    target_cols = [
        "risk_class_reference",
        "burnout_risk_reference",
        "deadline_delay_target_days",
        "budget_overrun_target"
    ]
    target_summary = {}
    for tc in target_cols:
        if tc in df.columns:
            if df[tc].dtype == "object":
                vc = df[tc].value_counts().to_dict()
                target_summary[tc] = {
                    "type": "categorical",
                    "distribution": {str(k): int(v) for k, v in vc.items()},
                    "proportions": {str(k): round(float(v / rows), 4) for k, v in vc.items()}
                }
            else:
                target_summary[tc] = {
                    "type": "continuous",
                    "min": float(df[tc].min()),
                    "max": float(df[tc].max()),
                    "mean": round(float(df[tc].mean()), 4),
                    "std": round(float(df[tc].std()), 4),
                    "median": float(df[tc].median()),
                    "zero_count": int((df[tc] == 0).sum()),
                    "negative_count": int((df[tc] < 0).sum())
                }
    print("Target Summary:", json.dumps(target_summary, indent=2))

    # Split column
    split_summary = {}
    if "split" in df.columns:
        sc = df["split"].value_counts().to_dict()
        split_summary = {str(k): int(v) for k, v in sc.items()}
        print("Existing CSV split column distribution:", split_summary)

    # Numerical Validity Audit
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    num_audit = {}
    for nc in num_cols:
        num_audit[nc] = {
            "min": float(df[nc].min()),
            "max": float(df[nc].max()),
            "mean": round(float(df[nc].mean()), 4),
            "median": float(df[nc].median()),
            "negatives": int((df[nc] < 0).sum()),
            "nulls": int(df[nc].isnull().sum())
        }
    with open(os.path.join(OUTPUT_DIR, "numerical_audit.json"), "w") as f:
        json.dump(num_audit, f, indent=2)

    # Categorical Validity Audit
    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    cat_audit = {}
    for cc in cat_cols:
        cat_audit[cc] = {
            "nunique": int(df[cc].nunique()),
            "values": df[cc].value_counts().head(10).to_dict()
        }
    with open(os.path.join(OUTPUT_DIR, "categorical_audit.json"), "w") as f:
        json.dump(cat_audit, f, indent=2)

    # Save summary audit
    summary_audit = {
        "total_rows": rows,
        "total_columns": cols,
        "entities": entities,
        "date_ranges": date_summary,
        "targets": target_summary,
        "split_column": split_summary
    }
    with open(os.path.join(OUTPUT_DIR, "dataset_summary.json"), "w") as f:
        json.dump(summary_audit, f, indent=2)
    print("Saved dataset_summary.json!")

if __name__ == "__main__":
    audit_dataset()
