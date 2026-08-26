"""DATAPREV 2026 – Flask Web App para Azure App Service (v2)"""
import os, json, uuid
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort
from azure.data.tables import TableServiceClient, UpdateMode
from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.dirname(os.path.abspath(__file__))

_content_cache = None

def _content():
    global _content_cache
    if _content_cache is None:
        p = os.path.join(ROOT, "static", "conteudo.json")
        _content_cache = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _content_cache
app  = Flask(__name__, template_folder="templates", static_folder="static")

# ── helpers ────────────────────────────────────────────────────────────────────

def _conn():
    return os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true")

def _tbl(name):
    svc = TableServiceClient.from_connection_string(_conn())
    svc.create_table_if_not_exists(name)
    return svc.get_table_client(name)

def _ok(data, status=200):
    r = jsonify(data)
    r.status_code = status
    return r

def _body():
    try:    return request.get_json() or {}
    except: return {}

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

@app.after_request
def cors(r):
    for k, v in CORS_HEADERS.items():
        r.headers[k] = v
    return r

# ── páginas ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("checklist_page"))

@app.route("/checklist")
def checklist_page():
    return render_template("checklist.html", active_page="checklist")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html", active_page="dashboard")

@app.route("/simulados")
def simulados_page():
    return render_template("simulados.html", active_page="simulados")

@app.route("/edital")
def edital_page():
    return render_template("edital.html", active_page="edital")

# Redirects de URLs antigas (bookmarks)
@app.route("/plano-de-estudos.html")
def compat_checklist():
    return redirect(url_for("checklist_page"), code=301)

@app.route("/dashboard.html")
def compat_dashboard():
    return redirect(url_for("dashboard_page"), code=301)

@app.route("/simulados.html")
def compat_simulados():
    return redirect(url_for("simulados_page"), code=301)

@app.route("/estudar/<date>")
def estudar_page(date):
    entry = _content().get(date)
    return render_template("estudar.html", active_page="estudar", date=date, entry=entry)

# ── checklist ─────────────────────────────────────────────────────────────────

@app.route("/api/checklist", methods=["GET", "OPTIONS"])
def get_checklist():
    if request.method == "OPTIONS": return _ok({})
    tbl  = _tbl("checklist")
    rows = [
        {"date": e["RowKey"], "done": bool(e.get("done", False)),
         "notes": e.get("notes", ""), "minutes": int(e.get("minutes", 0))}
        for e in tbl.list_entities()
    ]
    return _ok(rows)

@app.route("/api/checklist/toggle", methods=["POST", "OPTIONS"])
def toggle_checklist():
    if request.method == "OPTIONS": return _ok({})
    b    = _body()
    date = b.get("date", "")
    tbl  = _tbl("checklist")
    try:
        e    = tbl.get_entity("cl", date)
        done = not bool(e.get("done", False))
    except Exception:
        e    = {"PartitionKey": "cl", "RowKey": date, "notes": "", "minutes": 0}
        done = True
    e["done"] = done
    tbl.upsert_entity(e, mode=UpdateMode.REPLACE)
    return _ok({"date": date, "done": done})

@app.route("/api/checklist/notes", methods=["POST", "OPTIONS"])
def update_notes():
    if request.method == "OPTIONS": return _ok({})
    b     = _body()
    date  = b.get("date", "")
    notes = b.get("notes", "")
    tbl   = _tbl("checklist")
    tbl.upsert_entity({"PartitionKey": "cl", "RowKey": date, "notes": notes}, mode=UpdateMode.MERGE)
    return _ok({"ok": True})

@app.route("/api/checklist/time", methods=["POST", "OPTIONS"])
def update_time():
    if request.method == "OPTIONS": return _ok({})
    b       = _body()
    date    = b.get("date", "")
    minutes = int(b.get("minutes", 0))
    tbl     = _tbl("checklist")
    tbl.upsert_entity({"PartitionKey": "cl", "RowKey": date, "minutes": minutes}, mode=UpdateMode.MERGE)
    return _ok({"ok": True})

# ── simulados ─────────────────────────────────────────────────────────────────

@app.route("/api/simulados", methods=["GET", "POST", "OPTIONS"])
def api_simulados():
    if request.method == "OPTIONS": return _ok({})
    tbl = _tbl("simulados")
    if request.method == "GET":
        rows = [
            {"id": e["RowKey"], "date": e.get("date",""),
             "especifico": int(e.get("especifico",0)), "portugues": int(e.get("portugues",0)),
             "ingles": int(e.get("ingles",0)), "logica": int(e.get("logica",0)),
             "legislacao": int(e.get("legislacao",0)), "atualidades": int(e.get("atualidades",0)),
             "notes": e.get("notes","")}
            for e in tbl.list_entities()
        ]
        rows.sort(key=lambda r: r["date"], reverse=True)
        return _ok(rows)
    b = _body()
    rk = str(uuid.uuid4())
    tbl.create_entity({"PartitionKey":"sim","RowKey":rk,"date":b.get("date",""),
        "especifico":int(b.get("especifico",0)),"portugues":int(b.get("portugues",0)),
        "ingles":int(b.get("ingles",0)),"logica":int(b.get("logica",0)),
        "legislacao":int(b.get("legislacao",0)),"atualidades":int(b.get("atualidades",0)),
        "notes":b.get("notes","")})
    return _ok({"ok": True, "id": rk})

@app.route("/api/simulados/<sid>", methods=["DELETE", "OPTIONS"])
def delete_simulado(sid):
    if request.method == "OPTIONS": return _ok({})
    _tbl("simulados").delete_entity("sim", sid)
    return _ok({"ok": True})

# ── questões ──────────────────────────────────────────────────────────────────

@app.route("/api/questoes/batch", methods=["POST", "OPTIONS"])
def questoes_batch():
    if request.method == "OPTIONS": return _ok({})
    b = request.get_json()
    if not isinstance(b, list): return _ok({"error": "expected array"}, 400)
    tbl = _tbl("questoes")
    inserted = 0
    for q in b:
        if not q.get("enunciado"): continue
        tbl.upsert_entity({
            "PartitionKey":"q",
            "RowKey": str(uuid.uuid5(uuid.NAMESPACE_DNS, q["enunciado"][:200])),
            "disciplina":q.get("disciplina","Específico"),"enunciado":q.get("enunciado",""),
            "a":q.get("a",""),"b":q.get("b",""),"c":q.get("c",""),"d":q.get("d",""),
            "e":q.get("e",""),"gabarito":q.get("gabarito","a"),
            "fonte":q.get("fonte",""),"explicacao":q.get("explicacao",""),
            "date":q.get("date","")
        }, mode=UpdateMode.REPLACE)
        inserted += 1
    return _ok({"ok": True, "inserted": inserted})

@app.route("/api/questoes", methods=["GET", "POST", "OPTIONS"])
def api_questoes():
    if request.method == "OPTIONS": return _ok({})
    tbl = _tbl("questoes")
    if request.method == "GET":
        disc   = request.args.get("disciplina", "")
        date_f = request.args.get("date", "")
        if disc:
            entities = tbl.query_entities(f"disciplina eq '{disc}'")
        elif date_f:
            entities = tbl.query_entities(f"date eq '{date_f}'")
        else:
            entities = tbl.list_entities()
        rows = [{"id":e["RowKey"],"disciplina":e.get("disciplina",""),"enunciado":e.get("enunciado",""),
                 "a":e.get("a",""),"b":e.get("b",""),"c":e.get("c",""),"d":e.get("d",""),
                 "e":e.get("e",""),"gabarito":e.get("gabarito","a"),
                 "fonte":e.get("fonte",""),"explicacao":e.get("explicacao",""),
                 "date":e.get("date","")} for e in entities]
        rows.sort(key=lambda r: (r["disciplina"], r["id"]))
        return _ok(rows)
    b = _body()
    if not b.get("enunciado"): return _ok({"error": "enunciado obrigatório"}, 400)
    rk = str(uuid.uuid4())
    tbl.create_entity({"PartitionKey":"q","RowKey":rk,
        "disciplina":b.get("disciplina","Específico"),"enunciado":b.get("enunciado",""),
        "a":b.get("a",""),"b":b.get("b",""),"c":b.get("c",""),"d":b.get("d",""),
        "e":b.get("e",""),"gabarito":b.get("gabarito","a"),
        "fonte":b.get("fonte",""),"explicacao":b.get("explicacao",""),
        "date":b.get("date","")})
    return _ok({"ok": True, "id": rk})

@app.route("/api/questoes/<qid>", methods=["DELETE", "OPTIONS"])
def delete_questao(qid):
    if request.method == "OPTIONS": return _ok({})
    _tbl("questoes").delete_entity("q", qid)
    return _ok({"ok": True})

# ── quiz results ──────────────────────────────────────────────────────────────

@app.route("/api/quiz-results", methods=["GET", "POST", "OPTIONS"])
def quiz_results():
    if request.method == "OPTIONS": return _ok({})
    tbl = _tbl("quizresults")
    if request.method == "GET":
        rows = [{"id":e["RowKey"],"date":e.get("date",""),"disciplina":e.get("disciplina","Todas"),
                 "total":int(e.get("total",0)),"acertos":int(e.get("acertos",0)),
                 "erros":json.loads(e.get("erros","[]"))} for e in tbl.list_entities()]
        rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
        return _ok(rows)
    b  = _body()
    dt = b.get("date", "")
    tbl.create_entity({"PartitionKey":"qr","RowKey":f"{dt}__{uuid.uuid4()}",
        "date":dt,"disciplina":b.get("disciplina","Todas"),
        "total":int(b.get("total",0)),"acertos":int(b.get("acertos",0)),
        "erros":json.dumps(b.get("erros",[]))})
    return _ok({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
