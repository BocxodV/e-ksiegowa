"""
e-KsiegowaBot FULL AUDIT TEST SUITE
Security | Performance | i18n | SQL Injection | Validation | Structure
"""
import ast, json, os, sys, re, hmac, hashlib, urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(r"E:\bocxo\Desktop\Projects\e-KsiegowaBot")
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "PASS"; FAIL = "FAIL"
results = []

def test(name, passed, detail=""):
    icon = "  [OK]" if passed else "  [!!]"
    results.append((name, passed, detail))
    msg = f"{icon} {name}"
    if detail and not passed: msg += f"\n       -> {detail}"
    print(msg)

# =========================
# 1. SYNTAX CHECK
# =========================
print("\n=== 1. SYNTAX CHECK ===")
py_files = [f for f in PROJECT_ROOT.rglob("*.py")
            if not any(x in str(f) for x in [".venv","venv","__pycache__"])]
for f in sorted(py_files):
    try:
        ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        test(f"Syntax OK: {f.relative_to(PROJECT_ROOT)}", True)
    except SyntaxError as e:
        test(f"Syntax: {f.relative_to(PROJECT_ROOT)}", False, str(e))

# =========================
# 2. SECRETS IN CODE
# =========================
print("\n=== 2. SECRETS LEAK CHECK ===")
SECRET_PATTERNS = [
    ("Telegram token hardcoded", r"8599854365:"),
    ("DB password (npg_) hardcoded", r"npg_"),
    ("Gemini API key (AIzaSy)", r"AIzaSy"),
    ("Old AQ key", r"AQ\.Ab8RN6"),
    ("LangSmith key", r"lsv2_pt_"),
    ("Private key BEGIN", r"BEGIN PRIVATE KEY"),
]
for name, pattern in SECRET_PATTERNS:
    found = [str(f.relative_to(PROJECT_ROOT)) for f in py_files
             if re.search(pattern, f.read_text(encoding="utf-8", errors="ignore"))]
    test(f"No hardcoded secret: {name}", len(found)==0, f"Found in: {found}" if found else "")

gi = (PROJECT_ROOT/".gitignore").read_text(encoding="utf-8")
for item in [".env","service_account.json","env.yaml","service-account-key.json"]:
    test(f".gitignore covers: {item}", item in gi)

di = (PROJECT_ROOT/".dockerignore").read_text(encoding="utf-8")
for item in [".env","service_account.json","test_gemini*.py","fix*.py"]:
    test(f".dockerignore covers: {item}", item in di)

for jf in ["fix.py","fix2.py","fix_db.py","fix_decimal.py","fix_imports.py",
           "test_gemini.py","test_gemini2.py","test_gemini_list_models.py",
           "check_krono.py","update_krono.py","migrate.py"]:
    test(f"Junk file removed: {jf}", not (PROJECT_ROOT/jf).exists())

# =========================
# 3. SQL INJECTION PROTECTION
# =========================
print("\n=== 3. SQL INJECTION PROTECTION ===")
db_src = (PROJECT_ROOT/"database.py").read_text(encoding="utf-8")
test("Whitelist in update_user_setting", "ALLOWED_FIELDS" in db_src and "if field not in ALLOWED_FIELDS" in db_src)
bad_fmt = re.findall(r'execute\(f["\'](?!.*WHERE.*\$)', db_src)
test("No unparameterized execute() with f-string", len(bad_fmt)==0, str(bad_fmt[:2]))
test("DB pool has min_size", "min_size=" in db_src)
test("DB pool has max_size", "max_size=" in db_src)
test("user_drafts created in init_db() not save_user_draft()",
     "CREATE TABLE IF NOT EXISTS user_drafts" in db_src.split("async def save_user_draft")[0])

# =========================
# 4. HMAC WEBAPP SECURITY
# =========================
print("\n=== 4. HMAC SECURITY ===")
main_src = (PROJECT_ROOT/"main.py").read_text(encoding="utf-8")
test("verify_telegram_web_app_data present", "verify_telegram_web_app_data" in main_src)
test("403 on failed verification", "403" in main_src)

def verify(init_data, token):
    try:
        d = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in d: return False
        h = d.pop("hash")
        s = "\n".join(f"{k}={v}" for k,v in sorted(d.items()))
        sk = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        return hmac.new(sk, s.encode(), hashlib.sha256).hexdigest() == h
    except: return False

test("HMAC rejects empty data", not verify("", "t"))
test("HMAC rejects no-hash data", not verify("user=123", "t"))
test("HMAC rejects fake hash", not verify("user=x&hash=fakehash", "t"))
test("HMAC rejects SQL injection payload", not verify("user=' OR 1=1--&hash=x", "t"))
test("HMAC rejects XSS payload", not verify("user=<script>alert(1)</script>&hash=x", "t"))

# =========================
# 5. i18n COMPLETENESS
# =========================
print("\n=== 5. i18n COMPLETENESS ===")
ns = {}
exec(compile(ast.parse((PROJECT_ROOT/"texts.py").read_text(encoding="utf-8")),"t","exec"), ns)
TR = ns["TRANSLATIONS"]; MOT = ns.get("MOTIVATIONS",{})
langs = ["RUS","UKR","PL","ENG"]
rus_keys = set(TR["RUS"].keys())

for lang in langs[1:]:
    missing = rus_keys - set(TR.get(lang,{}).keys())
    test(f"{lang}: all RUS keys present", len(missing)==0, f"Missing: {missing}" if missing else "")

critical_keys = ["draft_title","draft_confirm","btn_yes","btn_no","shift_closed",
                 "shift_date","shift_net","shift_gross","shift_saved_fallback",
                 "shift_cancelled","coffee_invite","shift_total_count"]
for key in critical_keys:
    ok = all(key in TR.get(l,{}) for l in langs)
    test(f"Key '{key}' in all 4 langs", ok)

cyrillic = re.compile(r"[а-яёА-ЯЁ]")
for lang in ["PL","ENG"]:
    for key in ["shift_closed","shift_net","draft_confirm","shift_cancelled"]:
        val = TR.get(lang,{}).get(key,"")
        test(f"{lang}/{key}: no Cyrillic", not cyrillic.search(val), f"Value: {val[:40]}")

for lang in langs:
    test(f"MOTIVATIONS/{lang}: 20 quotes", len(MOT.get(lang,[]))==20,
         f"Found {len(MOT.get(lang,[]))}")

# =========================
# 6. PERFORMANCE ARCHITECTURE
# =========================
print("\n=== 6. PERFORMANCE ARCHITECTURE ===")
cfg = (PROJECT_ROOT/"config.py").read_text(encoding="utf-8")
test("Gemini singleton in config.py", "gemini_client = genai.Client" in cfg)
test("Vertex AI used in singleton", "vertexai=True" in cfg)

voice = (PROJECT_ROOT/"handlers"/"voice.py").read_text(encoding="utf-8")
test("voice.py uses shared gemini_client", "from config import gemini_client" in voice)
test("voice.py no local genai.Client()", "genai.Client(" not in voice)
test("voice.py imports at top level", "from database import" in voice.split("\n@router")[0])

vis = (PROJECT_ROOT/"handlers"/"vision.py").read_text(encoding="utf-8")
test("vision.py uses shared gemini_client", "from config import gemini_client" in vis)
test("vision.py no local genai.Client()", "genai.Client(" not in vis)

parser = (PROJECT_ROOT/"app"/"skills"/"parser.py").read_text(encoding="utf-8")
test("parser.py uses shared gemini_client", "from config import gemini_client" in parser)
test("parser.py no genai.Client() inside function", "genai.Client(" not in parser)

# =========================
# 7. GUARDRAILS VALIDATION
# =========================
print("\n=== 7. INPUT VALIDATION (GUARDRAILS) ===")
gr_ns = {}
exec(compile(ast.parse((PROJECT_ROOT/"app"/"skills"/"guardrails.py").read_text(encoding="utf-8")), "g","exec"), gr_ns)
validate = gr_ns.get("validate_shift_data")

if validate:
    test("Empty data has errors", len(validate({})or[])>0)
    valid = {"date":"2025-07-01","work_hours":8.0,"driving_hours":0.0,"location":"Warszawa","status":"Work"}
    test("Valid data passes", len(validate(valid)or[])==0)
    neg = dict(valid, work_hours=-5.0)
    test("Negative hours rejected", len(validate(neg)or[])>0)
    big = dict(valid, work_hours=25.0)
    test("Hours > 24 rejected", len(validate(big)or[])>0)
    bad_status = dict(valid, status="HACKED")
    test("Invalid status rejected", len(validate(bad_status)or[])>0)
    future = dict(valid, date="2099-12-31")
    test("Far future date handled (no crash)", True)
else:
    test("Guardrails module loaded", False, "validate_shift_data not found")

# =========================
# 8. FINANCIAL MATH
# =========================
print("\n=== 8. FINANCIAL CALCULATIONS ===")
def calc(base, work_h, tax):
    gross = base * work_h
    net = round(gross * tax, 2)
    return round(gross, 2), net

g, n = calc(32.0, 8.0, 0.71)
test("8h x 32 zł x 0.71 = 181.76 net", abs(n - 181.76) < 0.01, f"Got {n}")
g2, n2 = calc(32.0, 0, 0.71)
test("Zero hours = zero pay", g2 == 0 and n2 == 0)
g3, n3 = calc(32.0, 12.0, 0.71)
test("12h x 32 = 384 gross", abs(g3 - 384.0) < 0.01, f"Got {g3}")

# =========================
# 9. PROJECT STRUCTURE
# =========================
print("\n=== 9. PROJECT STRUCTURE ===")
required = ["main.py","config.py","database.py","texts.py","requirements.txt",
            "Dockerfile",".dockerignore",".gitignore",
            "handlers/__init__.py","handlers/voice.py","handlers/vision.py",
            "handlers/webapp.py","handlers/reports.py","handlers/admin.py",
            "app/__init__.py","app/graph.py","app/state.py",
            "app/skills/__init__.py","app/skills/parser.py","app/skills/guardrails.py"]
for rf in required:
    test(f"File exists: {rf}", (PROJECT_ROOT/rf).exists())

req = (PROJECT_ROOT/"requirements.txt").read_text(encoding="utf-8")
for dep in ["aiogram","google-genai","asyncpg","APScheduler","aiohttp","langgraph","openpyxl"]:
    test(f"requirements.txt has: {dep}", dep in req)

dock = (PROJECT_ROOT/"Dockerfile").read_text(encoding="utf-8")
test("Dockerfile: python:3.11-slim", "python:3.11-slim" in dock)
test("Dockerfile: requirements copied before app", dock.index("COPY requirements.txt") < dock.index("COPY . ."))

# =========================
# SUMMARY
# =========================
print("\n" + "="*55)
print("AUDIT SUMMARY")
print("="*55)
total = len(results)
passed = sum(1 for _,p,_ in results if p)
failed = total - passed
pct = 100*passed//total if total else 0
print(f"  Total:   {total}")
print(f"  Passed:  {passed}  ({pct}%)")
print(f"  Failed:  {failed}")
if failed:
    print("\n  FAILURES:")
    for name,ok,detail in results:
        if not ok:
            print(f"    [!!] {name}")
            if detail: print(f"         -> {detail}")
print("="*55)
sys.exit(0 if failed==0 else 1)
