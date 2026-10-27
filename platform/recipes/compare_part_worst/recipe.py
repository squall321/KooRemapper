
def run(reports, params):
    key = {"stress": "worst_stress", "g": "worst_g", "disp": "worst_disp"}.get(params.get("metric", "stress"), "worst_stress")
    rep_ids = [r.id for r in reports]
    rows = {}
    for rep in reports:
        for pid, a in rep.part_worst().items():
            slot = rows.setdefault(pid, {"part_id": pid, "name": a["part_name"], "values": {}})
            slot["values"][rep.id] = a[key]["value"]
    out = []
    for pid, slot in rows.items():
        present = [v for v in slot["values"].values() if v is not None]
        out.append({"part_id": pid, "name": slot["name"], "values": slot["values"],
                    "max": max(present) if present else None,
                    "spread": (max(present) - min(present)) if len(present) > 1 else None})
    out.sort(key=lambda d: (d["max"] is None, -(d["max"] or 0.0)))
    return {"metric": key, "reports": rep_ids, "parts": out}

def test_compare():
    import recipe_kit
    a = recipe_kit.make_report(report_id="A", kind="sphere", parts=[{"part_id": 1, "name": "P1"}],
        cases=[{"case_key": "k", "parts_metrics": {"1": {"peak_stress": 5.0}}}])
    b = recipe_kit.make_report(report_id="B", kind="sphere", parts=[{"part_id": 1, "name": "P1"}],
        cases=[{"case_key": "k", "parts_metrics": {"1": {"peak_stress": 8.0}}}])
    out = run([a, b], {})
    p = out["parts"][0]
    assert p["part_id"] == 1 and p["values"]["A"] == 5.0 and p["values"]["B"] == 8.0
    assert p["spread"] == 3.0
