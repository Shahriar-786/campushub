from datetime import date

from apps.forecasting.pipeline import (
    evaluate_time_aware_forecast,
    generate_synthetic_occupancy_dataframe,
    predict_horizon,
)


def test_time_aware_forecast_pipeline_and_baseline_metrics():
    caps = {"ZONE-A": 20, "ZONE-B": 15}
    df = generate_synthetic_occupancy_dataframe(zone_capacities=caps, days=60, end_date=date(2026, 11, 20))
    result = evaluate_time_aware_forecast(df)

    assert "MAE" in result["metrics"]
    assert "RMSE" in result["metrics"]
    assert result["metrics"]["MAE"]["baseline"] >= 0
    assert result["metrics"]["MAE"]["model"] >= 0

    preds = predict_horizon(result, caps, start_date=date(2026, 11, 21), horizon_days=7)
    assert len(preds) == 7 * 2 * 4
    for p in preds:
        assert 0 <= p["predicted_occupancy"] <= p["configured_capacity"]
