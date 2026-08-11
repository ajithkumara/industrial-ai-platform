# SUPERSEDED (2026-08) -- delete this file manually
# (PowerShell: Remove-Item ml\feature_store_setup.py).
#
# This was an empty stub. No dedicated feature store is used by this
# platform -- the config-driven flattened Silver tables (e.g.
# silver_bearing_sensor_telemetry) already ARE the feature table
# ml/cloud_forest/train_cloud_forest.py trains against. A separate
# feature-store layer was deliberately rejected as premature
# infrastructure for a single consumer domain -- see
# docs/architecture/PLATFORM_THESIS_REVIEW_2026-08.md Part 6 ("Where NOT
# to abstract").
