
def run(reports, params):
    metric = params.get("metric", "pf")
    top = int(params.get("top", 15))
    out = []
    for rep in reports:
        cp = rep.contact_profile(metric=metric, top=top)
        pairs = cp.get("pairs") or []
        rows = [{"src": p.get("src_name") or p.get("src"), "dst": p.get("dst_name") or p.get("dst"),
                 "peak": p.get("peak"), "peak_case": p.get("peak_case_key"),
                 "resolved": p.get("resolved")} for p in pairs[:top]]
        out.append({"report": rep.id, "metric": cp.get("metric_name"),
                    "available": cp.get("available", True), "n_pairs": len(rows), "pairs": rows})
    return {"reports": out}

def test_shape():
    import recipe_kit
    rep = recipe_kit.make_report(kind="impact", data={})
    out = run([rep], {})
    r = out["reports"][0]
    assert r["n_pairs"] == 0 and r["available"] in (False, True)
