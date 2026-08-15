# SmartTwin 낙하/충격 리포트(deep/sphere/impact) 인제스트·정규화 도메인 패키지.
"""Impact/drop report ingestion for DynaForge.

Parses the self-contained HTML reports produced by koo_deep_report /
koo_sphere_report / koo_impact_report (data embedded as ``const … = {…}``) and
normalizes all three into one ``kind``-tagged study schema for storage + MCP
analysis. See docs/impact-ingest/plan.md.
"""
