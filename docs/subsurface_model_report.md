# rainier3d subsurface model: construction and data sources

Living report (Claude Docs, readable and commentable by collaborators once shared):
https://claude.ai/code/artifact/ed5be9f3-c348-4710-942b-7fc0d0e0f18b

As of 2026-09-23 it covers: domain, grids and coordinates; surface layers (3DEP DEM, DNR GeMS
crosswalk, IceBoost v2 ice checked against GlaThiDa); rule-based 3D geology; rock physics
(crack-closure law, Brocher 2005, Q rule, unit parameters); fusion with CVM v1.7 and CRESCENT Gen0;
the PNSN travel-time check; limitations; all data sets and references with DOIs and verification
status; and how to reproduce the model.

The numbers in the report come from outputs/fusion_report.csv, outputs/pnsn_report.txt and
outputs/glacier_thickness_check.csv of the run on 2026-09-23. Source keys and DOIs are kept
machine-readable in configs/sources.yaml.
