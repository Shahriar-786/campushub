from django.db import models

from apps.core.models import TimeStampedUUIDModel
from apps.library.models import LibraryZone


class ForecastDatasetVersion(TimeStampedUUIDModel):
    name = models.CharField(max_length=120)
    is_synthetic = models.BooleanField(default=True)
    provenance_note = models.TextField()
    row_count = models.PositiveIntegerField(default=0)
    data_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["-created_at"]


class ForecastModelVersion(TimeStampedUUIDModel):
    version_tag = models.CharField(max_length=60, unique=True)
    algorithm = models.CharField(max_length=100)
    dataset = models.ForeignKey(ForecastDatasetVersion, on_delete=models.PROTECT)
    feature_list = models.JSONField(default=list)
    train_period = models.CharField(max_length=100)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.version_tag} ({self.algorithm})"


class ForecastRun(TimeStampedUUIDModel):
    model_version = models.ForeignKey(ForecastModelVersion, on_delete=models.PROTECT)
    horizon_days = models.PositiveSmallIntegerField(default=7)
    status = models.CharField(max_length=30, default="COMPLETED")
    caveat_text = models.TextField(
        default="Prototype forecast generated from clearly labelled synthetic data. "
        "Estimates are NOT guaranteed live seat availability."
    )

    class Meta:
        ordering = ["-created_at"]


class ForecastMetric(TimeStampedUUIDModel):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="metrics")
    split_name = models.CharField(max_length=30, default="test")
    metric_name = models.CharField(max_length=30)
    baseline_value = models.FloatField()
    model_value = models.FloatField()


class ForecastValue(TimeStampedUUIDModel):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="values")
    zone = models.ForeignKey(LibraryZone, on_delete=models.CASCADE)
    target_date = models.DateField(db_index=True)
    session_index = models.PositiveSmallIntegerField()
    predicted_occupancy = models.FloatField()
    configured_capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["target_date", "session_index", "zone__code"]
