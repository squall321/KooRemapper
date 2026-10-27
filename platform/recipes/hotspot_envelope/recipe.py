
def run(reports, params):
    crit = params.get("criterion")
    top = int(params.get("top", 10))
    out = []
    for rep in reports:
        hs = rep.hotspots(criterion=crit, top=top)
        env = hs.get("envelope") or []
        rows = [{"part_id": e.get("part_id"), "part_name": e.get("part_name"),
                 "criterion": e.get("criterion"), "stress_max": e.get("stress_max"),
                 "n_angles": e.get("n_angles"), "worst_case": e.get("worst_case_key")}
                for e in env]
        out.append({"report": rep.id, "available": hs.get("available", True),
                    "n_envelope": len(rows), "envelope": rows, "note": hs.get("note")})
    return {"reports": out}

def test_shape():
    import recipe_kit
    rep = recipe_kit.make_report(kind="deep", data={})
    out = run([rep], {})
    r = out["reports"][0]
    assert r["n_envelope"] == 0 and "report" in r
