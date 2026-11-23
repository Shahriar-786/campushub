from django.db import transaction
from django.utils import timezone

from apps.forecasting.models import (
    ForecastDatasetVersion,
    ForecastMetric,
    ForecastModelVersion,
    ForecastRun,
    ForecastValue,
)
from apps.forecasting.pipeline import (
    evaluate_time_aware_forecast,
    generate_synthetic_occupancy_dataframe,
    predict_horizon,
)
from apps.library.models import LibraryZone


@transaction.atomic
def run_synthetic_forecast_pipeline(horizon_days: int = 7) -> ForecastRun:
    zones = list(LibraryZone.objects.filter(is_active=True).prefetch_related("seats"))
    zone_map = {z.code: z for z in zones}
    zone_capacities = {z.code: max(1, z.seats.filter(is_active=True).count()) for z in zones}

    df = generate_synthetic_occupancy_dataframe(zone_capacities=zone_capacities, days=60, end_date=timezone.localdate())
    eval_result = evaluate_time_aware_forecast(df)

    dataset = ForecastDatasetVersion.objects.create(
        name=f"Synthetic DIU Library Occupancy ({timezone.localdate()})",
        is_synthetic=True,
        provenance_note="Clearly labelled synthetic dataset generated for academic prototype demonstration; not official DIU data.",
        row_count=len(df),
        data_hash=eval_result["data_hash"],
    )
    version_tag = f"ml-demand-v{ForecastModelVersion.objects.count() + 1}"
    model_ver = ForecastModelVersion.objects.create(
        version_tag=version_tag,
        algorithm=eval_result["algorithm"],
        dataset=dataset,
        feature_list=eval_result["features"],
        train_period=eval_result["train_period"],
    )
    run = ForecastRun.objects.create(model_version=model_ver, horizon_days=horizon_days)

    for metric_name, vals in eval_result["metrics"].items():
        ForecastMetric.objects.create(
            run=run,
            split_name="time_ordered_test",
            metric_name=metric_name,
            baseline_value=vals["baseline"],
            model_value=vals["model"],
        )

    preds = predict_horizon(eval_result, zone_capacities, start_date=timezone.localdate(), horizon_days=horizon_days)
    ForecastValue.objects.bulk_create(
        [
            ForecastValue(
                run=run,
                zone=zone_map[p["zone_code"]],
                target_date=p["target_date"],
                session_index=p["session_index"],
                predicted_occupancy=p["predicted_occupancy"],
                configured_capacity=p["configured_capacity"],
            )
            for p in preds
        ]
    )
    return run
