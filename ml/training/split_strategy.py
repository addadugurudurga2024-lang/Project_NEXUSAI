import os
import json
import pandas as pd
import numpy as np

CSV_PATH = r"D:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv"
OUTPUT_DIR = r"D:\NexsusAI\ml\training\reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_splits(random_state=42):
    print("=" * 70)
    print("STEP 8 & 9: LEAKAGE-RESISTANT SPLIT GENERATION")
    print("=" * 70)

    df = pd.read_csv(CSV_PATH)
    total_rows = len(df)
    print(f"Loaded {total_rows:,} rows.")

    np.random.seed(random_state)

    # -------------------------------------------------------------
    # 1. GROUP-AWARE SPLIT: By project_id (for Models 1, 3, 4)
    # -------------------------------------------------------------
    unique_projects = np.sort(df["project_id"].unique())
    num_projects = len(unique_projects)
    np.random.shuffle(unique_projects)

    # 80% train (800), 10% val (100), 10% test (100)
    n_train_p = int(0.80 * num_projects)
    n_val_p = int(0.10 * num_projects)

    train_pids = set(unique_projects[:n_train_p])
    val_pids = set(unique_projects[n_train_p:n_train_p + n_val_p])
    test_pids = set(unique_projects[n_train_p + n_val_p:])

    # Strict overlap assertions
    assert train_pids.isdisjoint(test_pids), "Project Train/Test overlap detected!"
    assert train_pids.isdisjoint(val_pids), "Project Train/Val overlap detected!"
    assert val_pids.isdisjoint(test_pids), "Project Val/Test overlap detected!"

    project_split_indices = {
        "train": df[df["project_id"].isin(train_pids)].index.tolist(),
        "val": df[df["project_id"].isin(val_pids)].index.tolist(),
        "test": df[df["project_id"].isin(test_pids)].index.tolist()
    }

    print(f"\n[Strategy A - Project Group Split]")
    print(f"  Train: {len(train_pids)} projects -> {len(project_split_indices['train']):,} rows ({len(project_split_indices['train'])/total_rows*100:.1f}%)")
    print(f"  Val:   {len(val_pids)} projects -> {len(project_split_indices['val']):,} rows ({len(project_split_indices['val'])/total_rows*100:.1f}%)")
    print(f"  Test:  {len(test_pids)} projects -> {len(project_split_indices['test']):,} rows ({len(project_split_indices['test'])/total_rows*100:.1f}%)")
    print(f"  [PASS] Zero project leakage across train/val/test confirmed!")

    # -------------------------------------------------------------
    # 2. GROUP-AWARE SPLIT: By employee_id (for Model 2: Burnout)
    # -------------------------------------------------------------
    unique_employees = np.sort(df["employee_id"].unique())
    num_employees = len(unique_employees)
    np.random.shuffle(unique_employees)

    n_train_e = int(0.80 * num_employees)
    n_val_e = int(0.10 * num_employees)

    train_eids = set(unique_employees[:n_train_e])
    val_eids = set(unique_employees[n_train_e:n_train_e + n_val_e])
    test_eids = set(unique_employees[n_train_e + n_val_e:])

    assert train_eids.isdisjoint(test_eids), "Employee Train/Test overlap detected!"
    assert train_eids.isdisjoint(val_eids), "Employee Train/Val overlap detected!"
    assert val_eids.isdisjoint(test_eids), "Employee Val/Test overlap detected!"

    employee_split_indices = {
        "train": df[df["employee_id"].isin(train_eids)].index.tolist(),
        "val": df[df["employee_id"].isin(val_eids)].index.tolist(),
        "test": df[df["employee_id"].isin(test_eids)].index.tolist()
    }

    print(f"\n[Strategy A - Employee Group Split]")
    print(f"  Train: {len(train_eids)} employees -> {len(employee_split_indices['train']):,} rows ({len(employee_split_indices['train'])/total_rows*100:.1f}%)")
    print(f"  Val:   {len(val_eids)} employees -> {len(employee_split_indices['val']):,} rows ({len(employee_split_indices['val'])/total_rows*100:.1f}%)")
    print(f"  Test:  {len(test_eids)} employees -> {len(employee_split_indices['test']):,} rows ({len(employee_split_indices['test'])/total_rows*100:.1f}%)")
    print(f"  [PASS] Zero employee leakage across train/val/test confirmed!")

    # -------------------------------------------------------------
    # 3. TEMPORAL SPLIT: Chronological cutoff by snapshot_date
    # -------------------------------------------------------------
    df["snapshot_dt"] = pd.to_datetime(df["snapshot_date"])
    
    # 70% earliest -> Train (before 2025-04-24)
    # 15% middle -> Val (2025-04-24 to 2025-07-15)
    # 15% latest -> Test (after 2025-07-15)
    t_val_cutoff = pd.to_datetime("2025-04-24")
    t_test_cutoff = pd.to_datetime("2025-07-15")

    temp_train_idx = df[df["snapshot_dt"] < t_val_cutoff].index.tolist()
    temp_val_idx = df[(df["snapshot_dt"] >= t_val_cutoff) & (df["snapshot_dt"] < t_test_cutoff)].index.tolist()
    temp_test_idx = df[df["snapshot_dt"] >= t_test_cutoff].index.tolist()

    print(f"\n[Strategy B - Temporal Chronological Split]")
    print(f"  Train: < {t_val_cutoff.strftime('%Y-%m-%d')} -> {len(temp_train_idx):,} rows ({len(temp_train_idx)/total_rows*100:.1f}%)")
    print(f"  Val:   {t_val_cutoff.strftime('%Y-%m-%d')} to {t_test_cutoff.strftime('%Y-%m-%d')} -> {len(temp_val_idx):,} rows ({len(temp_val_idx)/total_rows*100:.1f}%)")
    print(f"  Test:  >= {t_test_cutoff.strftime('%Y-%m-%d')} -> {len(temp_test_idx):,} rows ({len(temp_test_idx)/total_rows*100:.1f}%)")
    print(f"  [PASS] Strict chronological ordering: all test dates strictly postdate training cutoffs!")

    temporal_split_indices = {
        "train": temp_train_idx,
        "val": temp_val_idx,
        "test": temp_test_idx
    }

    # Save split metadata (without writing huge row lists to single JSON)
    metadata = {
        "random_state": random_state,
        "project_group_split": {
            "num_projects_train": len(train_pids),
            "num_projects_val": len(val_pids),
            "num_projects_test": len(test_pids),
            "rows_train": len(project_split_indices["train"]),
            "rows_val": len(project_split_indices["val"]),
            "rows_test": len(project_split_indices["test"])
        },
        "employee_group_split": {
            "num_employees_train": len(train_eids),
            "num_employees_val": len(val_eids),
            "num_employees_test": len(test_eids),
            "rows_train": len(employee_split_indices["train"]),
            "rows_val": len(employee_split_indices["val"]),
            "rows_test": len(employee_split_indices["test"])
        },
        "temporal_split": {
            "val_cutoff": str(t_val_cutoff),
            "test_cutoff": str(t_test_cutoff),
            "rows_train": len(temp_train_idx),
            "rows_val": len(temp_val_idx),
            "rows_test": len(temp_test_idx)
        }
    }
    with open(os.path.join(OUTPUT_DIR, "split_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return project_split_indices, employee_split_indices, temporal_split_indices, metadata

if __name__ == "__main__":
    generate_splits()
