"""Detailed integration test for all 12 Studio Pipeline MCP tools."""
import asyncio, base64, importlib, json, os, pkgutil, sys, tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mcp.server.fastmcp import FastMCP

PASS, FAIL = "✅", "❌"
_results = []

def check(name, condition, detail=""):
    tag = PASS if condition else FAIL
    _results.append((tag, name, detail))
    print(f"  {tag}  {name}" + (f"  — {detail}" if detail else ""))
    return condition

def section(title):
    print(f"\n{'─'*62}\n  {title}\n{'─'*62}")

def get(r):
    val = r[1]
    if isinstance(val, dict) and list(val.keys()) == ["result"]:
        return val["result"]
    return val

def reload_mod(name):
    return importlib.reload(importlib.import_module(f"rhmcp.tools.{name}"))

FAKE_DL = {
    "style_name": "Brutalist Concrete",
    "facade_vocabulary": ["board-formed concrete", "deep reveals"],
    "material_palette": [{"name": "Raw Concrete", "hex": "#C8C0B8", "role": "primary"}],
    "colour_story": {"primary": "#C8C0B8", "secondary": "#1E293B", "accent": "#F97316"},
    "landscape_character": "native grasses, birch groves",
    "diffusion_prompt": "brutalist residential tower, board-formed concrete, photorealistic",
    "negative_prompt": "cartoon, sketch, blurry",
    "executive_summary": "A 15-storey podium tower with exposed concrete.",
}
FAKE_B64 = base64.b64encode(b"\x89PNG\r\nfakeimage").decode()
FAL_RESPONSE = {"images": [{"url": "https://fal.ai/fake/img.jpg", "content_type": "image/jpeg"}], "seed": 42, "timings": {}}

def mock_httpx_client(post_json=None, get_content=b"fakeimgbytes"):
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = post_json or FAL_RESPONSE
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.raise_for_status = MagicMock()
    get_resp.content = get_content
    inst = MagicMock()
    inst.__enter__ = MagicMock(return_value=inst)
    inst.__exit__ = MagicMock(return_value=False)
    inst.post.return_value = post_resp
    inst.get.return_value = get_resp
    return MagicMock(return_value=inst), inst


if __name__ == "__main__":
 # ── 1. DESIGN LANGUAGE ────────────────────────────────────────────────────
 section("1. Design Language Generator")
 mcp1 = FastMCP("dl"); dl = reload_mod("urban_design_language"); dl.register(mcp1); dl._current_design_language = None
 reg1 = {t.name for t in asyncio.run(mcp1.list_tools())}
 check("urban_generate_design_language registered", "urban_generate_design_language" in reg1)
 check("urban_update_design_language registered", "urban_update_design_language" in reg1)
 check("urban_get_design_language registered", "urban_get_design_language" in reg1)

 async def _dl():
    r = {}
    dl._current_design_language = None
    r["get_empty"] = get(await mcp1.call_tool("urban_get_design_language", {}))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    r["gen_no_key"] = get(await mcp1.call_tool("urban_generate_design_language", {"brief":"test","typology":"tower","far":3.5,"climate_zone":"temperate"}))
    mock_msg = MagicMock(); mock_msg.content = [MagicMock(text=json.dumps(FAKE_DL))]
    mock_cl = MagicMock(); mock_cl.messages.create.return_value = mock_msg
    dl._current_design_language = None
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), patch("anthropic.Anthropic", return_value=mock_cl):
        r["gen_ok"] = get(await mcp1.call_tool("urban_generate_design_language", {"brief":"100x80m Shoreditch","typology":"podium_tower","far":3.5,"climate_zone":"temperate","style_hints":"warm brick"}))
    r["get_after"] = get(await mcp1.call_tool("urban_get_design_language", {}))
    r["upd_colour"] = get(await mcp1.call_tool("urban_update_design_language", {"field":"landscape_character","value":"reed beds"}))
    r["upd_style"] = get(await mcp1.call_tool("urban_update_design_language", {"field":"style_name","value":"High-Tech"}))
    r["upd_bad"] = get(await mcp1.call_tool("urban_update_design_language", {"field":"does_not_exist","value":"x"}))
    dl._current_design_language = None
    r["upd_none"] = get(await mcp1.call_tool("urban_update_design_language", {"field":"style_name","value":"x"}))
    return r

 d = asyncio.run(_dl())
 check("get_empty → set:false", d["get_empty"].get("set") is False)
 check("gen_no_key → ok:false", d["gen_no_key"].get("ok") is False)
 check("gen_no_key → error mentions API key", "ANTHROPIC_API_KEY" in str(d["gen_no_key"].get("error","")))
 check("gen_ok → ok:true", d["gen_ok"].get("ok") is True, str(d["gen_ok"].get("error","")))
 check("gen_ok → style_name correct", d["gen_ok"].get("style_name") == "Brutalist Concrete")
 check("gen_ok → material_palette is list", isinstance(d["gen_ok"].get("material_palette"), list))
 check("gen_ok → diffusion_prompt non-empty", bool(d["gen_ok"].get("diffusion_prompt")))
 check("gen_ok → executive_summary non-empty", bool(d["gen_ok"].get("executive_summary")))
 check("get_after → set:true", d["get_after"].get("set") is True)
 check("get_after → style_name persisted", d["get_after"].get("style_name") == "Brutalist Concrete")
 check("upd_colour → ok:true", d["upd_colour"].get("ok") is True)
 check("upd_colour → diffusion_prompt_updated:false", d["upd_colour"].get("diffusion_prompt_updated") is False)
 check("upd_style → ok:true", d["upd_style"].get("ok") is True)
 check("upd_style → diffusion_prompt_updated:true", d["upd_style"].get("diffusion_prompt_updated") is True)
 check("upd_bad → ok:false", d["upd_bad"].get("ok") is False)
 check("upd_bad → error names the field", "does_not_exist" in str(d["upd_bad"].get("error","")))
 check("upd_none → ok:false (nothing set)", d["upd_none"].get("ok") is False)

 # ── 2. AI RENDERS ─────────────────────────────────────────────────────────
 section("2. AI Render Pipeline")
 mcp2 = FastMCP("renders"); r_mod = reload_mod("urban_renders"); r_mod.register(mcp2); r_mod._current_renders = {}
 reg2 = {t.name for t in asyncio.run(mcp2.list_tools())}
 check("urban_render_views registered", "urban_render_views" in reg2)
 check("urban_render_style_preview registered", "urban_render_style_preview" in reg2)
 check("urban_get_renders registered", "urban_get_renders" in reg2)

 async def _renders():
    r = {}
    r["get_empty"] = get(await mcp2.call_tool("urban_get_renders", {}))
    os.environ.pop("FAL_KEY", None); r_mod._current_renders = {}
    r["no_key"] = get(await mcp2.call_tool("urban_render_views", {"views":["Perspective","Top"]}))
    hc, _ = mock_httpx_client(); r_mod._current_renders = {}
    with patch.dict(os.environ,{"FAL_KEY":"fal-test"}), patch("rhmcp.tools.urban_renders._capture_named_view",return_value=FAKE_B64), patch("httpx.Client",hc):
        r["render_ok"] = get(await mcp2.call_tool("urban_render_views", {"views":["Perspective","Top"],"strength":0.7,"seed":42}))
    r["get_after"] = get(await mcp2.call_tool("urban_get_renders", {}))
    hc2, _ = mock_httpx_client(); r_mod._current_renders = {}
    with patch.dict(os.environ,{"FAL_KEY":"fal-test"}), patch("rhmcp.tools.urban_renders._capture_named_view",return_value=""), patch("httpx.Client",hc2):
        r["empty_cap"] = get(await mcp2.call_tool("urban_render_views", {"views":["Perspective"]}))
    os.environ.pop("FAL_KEY", None)
    r["prev_no_key"] = get(await mcp2.call_tool("urban_render_style_preview", {"style_prompt":"brutalist tower"}))
    hc3, _ = mock_httpx_client()
    with patch.dict(os.environ,{"FAL_KEY":"fal-test"}), patch("httpx.Client",hc3):
        r["prev_ok"] = get(await mcp2.call_tool("urban_render_style_preview", {"style_prompt":"brutalist tower","seed":7}))
    return r

 rv = asyncio.run(_renders())
 check("get_renders empty → {}", rv["get_empty"] == {})
 nk = rv["no_key"]
 check("render_views no key → list", isinstance(nk, list), f"type={type(nk).__name__}")
 if isinstance(nk, list):
    check("render_views no key → 2 items", len(nk) == 2)
    check("render_views no key → all ok:false", all(x.get("ok") is False for x in nk))
 ok_l = rv["render_ok"]
 check("render_views mocked → list of 2", isinstance(ok_l,list) and len(ok_l)==2, f"got {len(ok_l) if isinstance(ok_l,list) else ok_l}")
 if isinstance(ok_l,list) and ok_l:
    f = ok_l[0]
    check("render[0] ok:true", f.get("ok") is True, str(f.get("error","")))
    check("render[0] has original_b64", bool(f.get("original_b64")))
    check("render[0] has rendered_b64", bool(f.get("rendered_b64")))
    check("render[0] has prompt_used", bool(f.get("prompt_used")))
    check("render[0] has seed", "seed" in f)
    check("render[0] view=Perspective", f.get("view") == "Perspective")
 check("get_renders after → Perspective key", isinstance(rv["get_after"],dict) and "Perspective" in rv["get_after"])
 ec = rv["empty_cap"]
 check("empty capture → ok:false", isinstance(ec,list) and ec[0].get("ok") is False)
 check("style_preview no key → ok:false", rv["prev_no_key"].get("ok") is False)
 check("style_preview mocked → ok:true", rv["prev_ok"].get("ok") is True, str(rv["prev_ok"].get("error","")))
 check("style_preview has image_b64", bool(rv["prev_ok"].get("image_b64")))
 check("style_preview has seed", "seed" in rv["prev_ok"])

 # ── 3. REPORT GENERATOR ───────────────────────────────────────────────────
 section("3. Report Generator")
 mcp3 = FastMCP("report"); rep = reload_mod("urban_report"); rep.register(mcp3); rep._report_history = []
 reg3 = {t.name for t in asyncio.run(mcp3.list_tools())}
 check("urban_export_report registered", "urban_export_report" in reg3)
 check("urban_preview_report registered", "urban_preview_report" in reg3)
 check("urban_list_reports registered", "urban_list_reports" in reg3)

 dl_m = importlib.import_module("rhmcp.tools.urban_design_language")
 r_m = importlib.import_module("rhmcp.tools.urban_renders")
 dl_m._current_design_language = FAKE_DL.copy()
 r_m._current_renders = {"Perspective":{"ok":True,"original_b64":FAKE_B64,"rendered_b64":FAKE_B64,"prompt_used":"test","seed":42}}

 async def _report():
    r = {}; tmpdir = Path(tempfile.mkdtemp())
    r["preview"] = get(await mcp3.call_tool("urban_preview_report", {}))
    rep._report_history = []
    r["list_empty"] = get(await mcp3.call_tool("urban_list_reports", {}))
    os.environ.pop("DOCRAPTOR_API_KEY",None); os.environ.pop("URBAN_AGENT_S3_BUCKET",None)
    rep._report_history = []
    with patch("pathlib.Path.home", return_value=tmpdir):
        r["export_local"] = get(await mcp3.call_tool("urban_export_report", {"project_name":"Tower","scheme_name":"V1","author":"Test","include_solar":False,"include_design_language":True}))
    r["list_one"] = get(await mcp3.call_tool("urban_list_reports", {}))
    rep._report_history = []
    with patch("pathlib.Path.home", return_value=tmpdir):
        r["export_no_sec"] = get(await mcp3.call_tool("urban_export_report", {"project_name":"Tower","scheme_name":"V2","include_solar":False,"include_design_language":False}))
    fpr = MagicMock(); fpr.status_code=200; fpr.raise_for_status=MagicMock(); fpr.content=b"%PDF-1.4 fake"
    ms3 = MagicMock(); ms3.put_object.return_value={}; ms3.generate_presigned_url.return_value="https://s3.example.com/reports/test.pdf"
    rep._report_history = []
    with patch.dict(os.environ,{"DOCRAPTOR_API_KEY":"dr","URBAN_AGENT_S3_BUCKET":"bkt","AWS_ACCESS_KEY_ID":"k","AWS_SECRET_ACCESS_KEY":"s"}), \
         patch("httpx.post",return_value=fpr), patch("boto3.client",return_value=ms3):
        r["export_cloud"] = get(await mcp3.call_tool("urban_export_report", {"project_name":"Tower","scheme_name":"V3"}))
    r["list_cloud"] = get(await mcp3.call_tool("urban_list_reports", {}))
    return r

 rp = asyncio.run(_report())
 check("preview → ok:true", rp["preview"].get("ok") is True, str(rp["preview"].get("error","")))
 check("preview → has html_content key", "html_content" in rp["preview"], str(list(rp["preview"].keys())))
 html_body = rp["preview"].get("html_content","")
 check("preview HTML → >500 chars", len(html_body)>500, f"len={len(html_body)}")
 check("preview HTML → contains DOCTYPE", "<!DOCTYPE" in html_body or "<html" in html_body)
 check("list_empty → []", rp["list_empty"]==[])
 check("export_local → ok:true", rp["export_local"].get("ok") is True, str(rp["export_local"].get("error","")))
 check("export_local → has url/path", bool(rp["export_local"].get("pdf_url") or rp["export_local"].get("local_path")))
 check("export_local → no scheme_name in return (by design)", "scheme_name" not in rp["export_local"])
 check("list after export → 1 entry", isinstance(rp["list_one"],list) and len(rp["list_one"])==1)
 if isinstance(rp["list_one"],list) and rp["list_one"]:
    e = rp["list_one"][0]
    check("list entry has scheme_name","scheme_name" in e)
    check("list entry has timestamp","timestamp" in e)
 check("export_no_sections → ok:true", rp["export_no_sec"].get("ok") is True)
 check("export_cloud → ok:true", rp["export_cloud"].get("ok") is True, str(rp["export_cloud"].get("error","")))
 check("export_cloud → S3 URL", "s3.example.com" in str(rp["export_cloud"].get("pdf_url","")))
 check("list_cloud → 1 entry", isinstance(rp["list_cloud"],list) and len(rp["list_cloud"])==1)

 # ── 4. PIPELINE ORCHESTRATOR ──────────────────────────────────────────────
 section("4. Studio Pipeline Orchestrator")
 mcp4 = FastMCP("pipeline"); pipe = reload_mod("urban_pipeline"); pipe.register(mcp4); pipe._current_run=None; pipe._pipeline_history=[]
 reg4 = {t.name for t in asyncio.run(mcp4.list_tools())}
 check("urban_run_studio_pipeline registered", "urban_run_studio_pipeline" in reg4)
 check("urban_pipeline_status registered", "urban_pipeline_status" in reg4)
 check("urban_list_pipeline_runs registered", "urban_list_pipeline_runs" in reg4)

 _DL_OK={"ok":True,**FAKE_DL}
 _RV_OK=[{"view":v,"ok":True,"original_b64":FAKE_B64,"rendered_b64":FAKE_B64,"prompt_used":"t","seed":0} for v in ["Perspective","Top","Front","Right"]]
 _SOLAR={"ok":False,"error":"solar analysis not available"}
 _REP={"ok":True,"pdf_url":"file:///tmp/r.pdf","html_url":"file:///tmp/r.html","scheme_name":"V1","page_count":6,"file_size_kb":200}

 async def _pipeline():
    r = {}
    pipe._current_run=None; pipe._pipeline_history=[]
    r["idle"] = get(await mcp4.call_tool("urban_pipeline_status",{}))
    r["list0"] = get(await mcp4.call_tool("urban_list_pipeline_runs",{}))
    pipe._pipeline_history=[]
    with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",return_value=_DL_OK), \
         patch("rhmcp.tools.urban_pipeline._step_render_views",return_value=_RV_OK), \
         patch("rhmcp.tools.urban_pipeline._step_run_solar",return_value=_SOLAR), \
         patch("rhmcp.tools.urban_pipeline._step_export_report",return_value=_REP):
        r["full"] = get(await mcp4.call_tool("urban_run_studio_pipeline",{"project_name":"T","scheme_name":"V1","brief":"test","render_views":["Perspective","Top","Front","Right"],"include_solar":True}))
    r["done"] = get(await mcp4.call_tool("urban_pipeline_status",{}))
    r["list1"] = get(await mcp4.call_tool("urban_list_pipeline_runs",{}))
    with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",return_value=_DL_OK), \
         patch("rhmcp.tools.urban_pipeline._step_render_views",return_value=_RV_OK) as mrv, \
         patch("rhmcp.tools.urban_pipeline._step_run_solar",return_value=_SOLAR), \
         patch("rhmcp.tools.urban_pipeline._step_export_report",return_value=_REP):
        r["skip_rv"] = (get(await mcp4.call_tool("urban_run_studio_pipeline",{"project_name":"T","scheme_name":"V2","brief":"t","skip_steps":["renders"]})), mrv.call_count)
    with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",return_value=_DL_OK), \
         patch("rhmcp.tools.urban_pipeline._step_render_views",return_value=_RV_OK), \
         patch("rhmcp.tools.urban_pipeline._step_run_solar",return_value=_SOLAR) as ms, \
         patch("rhmcp.tools.urban_pipeline._step_export_report",return_value=_REP):
        r["no_solar"] = (get(await mcp4.call_tool("urban_run_studio_pipeline",{"project_name":"T","scheme_name":"V3","brief":"t","include_solar":False})), ms.call_count)
    with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",return_value={"ok":False,"error":"ANTHROPIC_API_KEY not set"}), \
         patch("rhmcp.tools.urban_pipeline._step_render_views",return_value=_RV_OK) as mrv2, \
         patch("rhmcp.tools.urban_pipeline._step_export_report",return_value=_REP) as me2:
        r["dl_abort"] = (get(await mcp4.call_tool("urban_run_studio_pipeline",{"project_name":"T","scheme_name":"V4","brief":"t"})), mrv2.call_count, me2.call_count)
    with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",return_value=_DL_OK), \
         patch("rhmcp.tools.urban_pipeline._step_render_views",return_value=[{"view":"Perspective","ok":False,"error":"timeout"}]), \
         patch("rhmcp.tools.urban_pipeline._step_run_solar",return_value=_SOLAR), \
         patch("rhmcp.tools.urban_pipeline._step_export_report",return_value=_REP) as me3:
        r["rv_fail"] = (get(await mcp4.call_tool("urban_run_studio_pipeline",{"project_name":"T","scheme_name":"V5","brief":"t"})), me3.call_count)
    r["listN"] = get(await mcp4.call_tool("urban_list_pipeline_runs",{}))
    return r

 pp = asyncio.run(_pipeline())
 check("status idle → running:false", pp["idle"].get("running") is False)
 check("list_empty → []", pp["list0"]==[])
 full=pp["full"]
 check("full → ok:true", full.get("ok") is True, str(full.get("errors","")))
 check("full → has run_id", bool(full.get("run_id")))
 check("full → has report_url", bool(full.get("report_url")))
 check("full → has elapsed_s", isinstance(full.get("elapsed_s"),(int,float)))
 check("full → 4 steps in log", len(full.get("step_log",[]))==4, str([s.get("step") for s in full.get("step_log",[])]))
 lm={s["step"]:s["status"] for s in full.get("step_log",[])}
 check("step design_language → ok", lm.get("design_language")=="ok")
 check("step renders → ok", lm.get("renders")=="ok")
 check("step solar → failed (stub)", lm.get("solar")=="failed")
 check("step export → ok", lm.get("export")=="ok")
 check("status done → running:false", pp["done"].get("running") is False)
 check("list after 1 run → 1 entry", isinstance(pp["list1"],list) and len(pp["list1"])==1)
 if isinstance(pp["list1"],list) and pp["list1"]:
    e=pp["list1"][0]; check("run entry has run_id","run_id" in e); check("run entry has scheme_name","scheme_name" in e)
 sr,rvc=pp["skip_rv"]
 check("skip_renders → ok:true", sr.get("ok") is True)
 check("skip_renders → render not called", rvc==0, f"called {rvc}×")
 check("skip_renders → log renders=skipped", {s["step"]:s["status"] for s in sr.get("step_log",[])}.get("renders")=="skipped")
 ns,sc=pp["no_solar"]
 check("no_solar → ok:true", ns.get("ok") is True)
 check("no_solar → solar not called", sc==0, f"called {sc}×")
 check("no_solar → log solar=skipped", {s["step"]:s["status"] for s in ns.get("step_log",[])}.get("solar")=="skipped")
 da,rc2,ec2=pp["dl_abort"]
 check("DL abort → ok:false", da.get("ok") is False)
 check("DL abort → render not called", rc2==0, f"called {rc2}×")
 check("DL abort → export not called", ec2==0, f"called {ec2}×")
 rf,ec3=pp["rv_fail"]
 check("render fail → pipeline continues (ok:true)", rf.get("ok") is True)
 check("render fail → export still called", ec3==1, f"called {ec3}×")
 check("render fail → errors non-empty", bool(rf.get("errors")))
 check("list_multi → 3+ runs", isinstance(pp["listN"],list) and len(pp["listN"])>=3, f"got {len(pp['listN']) if isinstance(pp['listN'],list) else pp['listN']}")

 # ── 5. STATE RESET ────────────────────────────────────────────────────────
 section("5. State Reset")
 dlm=importlib.import_module("rhmcp.tools.urban_design_language"); rm=importlib.import_module("rhmcp.tools.urban_renders"); pm=importlib.import_module("rhmcp.tools.urban_pipeline")
 dlm._current_design_language=FAKE_DL.copy(); rm._current_renders={"P":{"ok":True}}; pm._pipeline_history=[{"x":1}]; pm._current_run={"running":False}
 dlm.reset(); rm.reset(); pm.reset()
 check("dl.reset() clears state", dlm._current_design_language is None)
 check("renders.reset() clears state", rm._current_renders=={})
 check("pipeline.reset() clears history", pm._pipeline_history==[])
 check("pipeline.reset() clears current_run", pm._current_run is None)

 # ── 6. FULL SERVER REGISTRATION ───────────────────────────────────────────
 section("6. Full MCP Server — All 12 Studio Tools Present")
 import rhmcp.tools as tools_pkg
 mcp_all=FastMCP("all")
 for _,modname,_ in pkgutil.iter_modules(tools_pkg.__path__):
    if modname.startswith("_"): continue
    m=importlib.import_module(f"rhmcp.tools.{modname}")
    if hasattr(m,"register"): m.register(mcp_all)
 all_names={t.name for t in asyncio.run(mcp_all.list_tools())}
 for tool in ["urban_generate_design_language","urban_update_design_language","urban_get_design_language","urban_render_views","urban_render_style_preview","urban_get_renders","urban_export_report","urban_preview_report","urban_list_reports","urban_run_studio_pipeline","urban_pipeline_status","urban_list_pipeline_runs"]:
    check(f"{tool} in server", tool in all_names)
 check("total tools = 353", len(all_names)==353, f"got {len(all_names)}")

 # ── SUMMARY ───────────────────────────────────────────────────────────────
 print(f"\n{'═'*62}")
 passed=sum(1 for s,*_ in _results if s==PASS); failed=sum(1 for s,*_ in _results if s==FAIL)
 print(f"  RESULT: {passed}/{len(_results)} passed   {failed} failed")
 print(f"{'═'*62}")
 if failed:
    print("\nFailed checks:")
    for tag,name,detail in _results:
        if tag==FAIL: print(f"  {FAIL}  {name}" + (f"  — {detail}" if detail else ""))
    sys.exit(1)
 else:
    print("\n  All checks passed.")
