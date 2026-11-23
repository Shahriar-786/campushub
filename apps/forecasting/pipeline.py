import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd


def generate_synthetic_occupancy_dataframe(
    zone_capacities: dict[str, int], days: int = 60, end_date: date | None = None, seed: int = 42
) -> pd.DataFrame:
    """Generates clearly labelled synthetic occupancy history for prototype evaluation."""
    rng = np.random.default_rng(seed)
    end = end_date or date.today()
    start = end - timedelta(days=days - 1)
    rows = []
    for day_offset in range(days):
        d = start + timedelta(days=day_offset)
        dow = d.weekday()  # 0=Mon ... 6=Sun (in Bangladesh Fri/Sat are weekend)
        is_weekend = 1 if dow in (4, 5) else 0
        is_exam_period = 1 if (day_offset % 30) >= 22 else 0
        for zone_code, cap in zone_capacities.items():
            for session_index in (1, 2, 3, 4):
                session_factor = {1: 0.55, 2: 0.82, 3: 0.78, 4: 0.45}[session_index]
                weekend_factor = 0.25 if is_weekend else 1.0
                exam_boost = 1.15 if is_exam_period else 1.0
                expected = cap * session_factor * weekend_factor * exam_boost
                noise = rng.normal(0, max(1.0, cap * 0.06))
                occupancy = int(np.clip(round(expected + noise), 0, cap))
                rows.append(
                    {
                        "date": d,
                        "zone_code": zone_code,
                        "session_index": session_index,
                        "day_of_week": dow,
                        "is_weekend": is_weekend,
                        "is_exam_period": is_exam_period,
                        "capacity": cap,
                        "occupancy": occupancy,
                    }
                )
    return pd.DataFrame(rows).sort_values(["date", "session_index", "zone_code"]).reset_index(drop=True)


def evaluate_time_aware_forecast(df: pd.DataFrame) -> dict:
    """
    Time-ordered train/test split (no random shuffle -> zero future-data leakage).
    Compares a naive baseline (same zone + weekday + session historical mean) against
    a scikit-learn GradientBoostingRegressor (with OLS numpy fallback if sklearn absent).
    """
    df = df.sort_values(["date", "session_index", "zone_code"]).reset_index(drop=True)
    unique_dates = sorted(df["date"].unique())
    split_idx = int(len(unique_dates) * 0.8)
    train_dates = set(unique_dates[:split_idx])
    train_df = df[df["date"].isin(train_dates)].copy()
    test_df = df[~df["date"].isin(train_dates)].copy()

    # Naive baseline: mean occupancy for (zone_code, day_of_week, session_index) in train
    baseline_map = (
        train_df.groupby(["zone_code", "day_of_week", "session_index"])["occupancy"].mean().to_dict()
    )
    global_mean = float(train_df["occupancy"].mean())
    baseline_preds = np.array(
        [
            baseline_map.get((r.zone_code, r.day_of_week, r.session_index), global_mean)
            for r in test_df.itertuples()
        ]
    )

    zone_codes = sorted(df["zone_code"].unique())
    zone_to_int = {z: i for i, z in enumerate(zone_codes)}

    def featurize(frame: pd.DataFrame) -> np.ndarray:
        return np.column_stack(
            [
                frame["zone_code"].map(zone_to_int).to_numpy(),
                frame["session_index"].to_numpy(),
                frame["day_of_week"].to_numpy(),
                frame["is_weekend"].to_numpy(),
                frame["is_exam_period"].to_numpy(),
                frame["capacity"].to_numpy(),
            ]
        )

    X_train, y_train = featurize(train_df), train_df["occupancy"].to_numpy(dtype=float)
    X_test, y_test = featurize(test_df), test_df["occupancy"].to_numpy(dtype=float)

    try:
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(random_state=42, n_estimators=80, max_depth=3)
        model.fit(X_train, y_train)
        model_preds = np.clip(model.predict(X_test), 0, test_df["capacity"].to_numpy())
        algorithm = "scikit-learn GradientBoostingRegressor"
    except ImportError:
        # Pure-numpy least-squares fallback for offline environments without scikit-learn
        X_tr_b = np.column_stack([np.ones(len(X_train)), X_train])
        X_te_b = np.column_stack([np.ones(len(X_test)), X_test])
        beta, *_ = np.linalg.lstsq(X_tr_b, y_train, rcond=None)
        model = ("numpy_ols", beta)
        model_preds = np.clip(X_te_b @ beta, 0, test_df["capacity"].to_numpy())
        algorithm = "NumPy OLS Fallback"

    def mae(y_true, y_hat):
        return float(np.mean(np.abs(y_true - y_hat)))

    def rmse(y_true, y_hat):
        return float(np.sqrt(np.mean((y_true - y_hat) ** 2)))

    data_hash = hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()

    return {
        "algorithm": algorithm,
        "model": model,
        "zone_to_int": zone_to_int,
        "data_hash": data_hash,
        "train_period": f"{min(train_dates)} to {max(train_dates)}",
        "metrics": {
            "MAE": {"baseline": round(mae(y_test, baseline_preds), 3), "model": round(mae(y_test, model_preds), 3)},
            "RMSE": {"baseline": round(rmse(y_test, baseline_preds), 3), "model": round(rmse(y_test, model_preds), 3)},
        },
        "features": ["zone_code", "session_index", "day_of_week", "is_weekend", "is_exam_period", "capacity"],
    }


def predict_horizon(model_bundle: dict, zone_capacities: dict[str, int], start_date: date, horizon_days: int = 7) -> list[dict]:
    model = model_bundle["model"]
    zone_to_int = model_bundle["zone_to_int"]
    results = []
    for offset in range(horizon_days):
        d = start_date + timedelta(days=offset)
        dow = d.weekday()
        is_weekend = 1 if dow in (4, 5) else 0
        is_exam_period = 0
        for zone_code, cap in zone_capacities.items():
            for session_index in (1, 2, 3, 4):
                x = np.array([[zone_to_int[zone_code], session_index, dow, is_weekend, is_exam_period, cap]], dtype=float)
                if isinstance(model, tuple) and model[0] == "numpy_ols":
                    x_b = np.column_stack([np.ones(1), x])
                    pred = float(np.clip((x_b @ model[1])[0], 0, cap))
                else:
                    pred = float(np.clip(model.predict(x)[0], 0, cap))
                results.append(
                    {
                        "zone_code": zone_code,
                        "target_date": d,
                        "session_index": session_index,
                        "predicted_occupancy": round(pred, 1),
                        "configured_capacity": cap,
                    }
                )
    return results
