
def run(reports, params):
    metric = params.get("metric", "max_stress")
    thr = params.get("threshold")
    out = []
    for rep in reports:
        over = []
        for c in rep.cases:
            v = c.get(metric)
            if v is None:
                continue
            if thr is None or v >= thr:
                ang = (c.get("identity") or {}).get("angle") or {}
                over.append({"case": c.get("case_key"), "value": v,
                             "angle": ang.get("name"), "category": ang.get("category")})
        over.sort(key=lambda d: -d["value"])
        out.append({"report": rep.id, "metric": metric, "threshold": thr,
                    "n_over": len(over), "cases": over})
    return {"reports": out}

def test_over():
    import recipe_kit
    rep = recipe_kit.make_report(kind="sphere", cases=[
        {"case_key": "hi", "max_stress": 9.0, "identity": {"angle": {"name": "F1", "category": "face"}}},
        {"case_key": "lo", "max_stress": 2.0, "identity": {"angle": {"name": "F2", "category": "face"}}}])
    out = run([rep], {"threshold": 5.0})
    r = out["reports"][0]
    assert r["n_over"] == 1 and r["cases"][0]["case"] == "hi"
