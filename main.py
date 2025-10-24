from flask import Flask, request, jsonify, render_template_string, redirect
from dotenv import load_dotenv
from markupsafe import Markup
import os, re, html, unicodedata

# 3rd party
from rapidfuzz import fuzz
from unidecode import unidecode
from openai import OpenAI

# ================= Base =================
load_dotenv()
app = Flask(__name__)

# ---------------- OpenAI ----------------
OPENAI_INIT_ERROR = None
def get_openai_client():
    """Crea cliente con la clave limpia; guarda motivo si falla."""
    global OPENAI_INIT_ERROR
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        OPENAI_INIT_ERROR = "NO_API_KEY"
        return None
    try:
        return OpenAI(api_key=key)
    except Exception as e:
        OPENAI_INIT_ERROR = f"{type(e).__name__}: {e}"
        return None

client = get_openai_client()

# --------------- Utilidades -------------
def _n(s: str) -> str:
    return unidecode((s or "").lower())

def read_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def sanitize(text: str) -> str:
    text = (text or "").replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)

def slugify(label: str) -> str:
    """convierte 'Política de uniformes - Administrativos' -> 'politica_de_uniformes_administrativos'"""
    s = unidecode(label or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

# --------------- Policies ----------------
def load_policies() -> dict:
    base = "policies"
    return {
        "vacaciones": read_txt(os.path.join(base, "politica_vacaciones.txt")),
        "permisos":   read_txt(os.path.join(base, "politica_permisos.txt")),
        "compras":    read_txt(os.path.join(base, "politica_compras.txt")),
        "comision":   read_txt(os.path.join(base, "politica_comision.txt")),
        "banco":      read_txt(os.path.join(base, "banco_preguntas.txt")),
    }

# --------------- Accesos -----------------
def load_access_map_from_your_txt() -> dict:
    """
    Lee policies/accesos.txt con tu formato:
      TÍTULO EN UNA LÍNEA
          URL EN LA SIGUIENTE LÍNEA
    (Hay líneas en blanco entre pares; pueden venir con tabs)
    Devuelve: { slug: {"label": titulo, "url": url} }
    """
    path = os.path.join("policies", "accesos.txt")
    mapping = {}
    if not os.path.isfile(path):
        return mapping

    def is_url(line: str) -> bool:
        return line.startswith("http://") or line.startswith("https://") or line.startswith("chrome-extension://")

    title_buffer = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # algunas líneas vienen con "Título  <tab> URL"
            if "\t" in line and "http" in line:
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                # intenta detectar "titulo \t url"
                if len(parts) >= 2 and is_url(parts[1]):
                    title = parts[0]
                    url = parts[1]
                    mapping[slugify(title)] = {"label": title, "url": url}
                    title_buffer = None
                    continue

            if is_url(line):
                if title_buffer:
                    mapping[slugify(title_buffer)] = {"label": title_buffer, "url": line}
                    title_buffer = None
                else:
                    # url sin título previo: ignora
                    pass
            else:
                # es un título
                title_buffer = line

    return mapping

ACCESS_MAP = load_access_map_from_your_txt()

def short_href(slug: str, label: str) -> str:
    return f'<a href="/go/{slug}" target="_blank">{html.escape(label)}</a>'

@app.route("/go/<slug>")
def go(slug):
    slug = (slug or "").lower()
    data = ACCESS_MAP.get(slug)
    if not data:
        return redirect("/", code=302)
    return redirect(data["url"], code=302)

# ------------- Dominios RRHH -------------
DOMAINS = {
    "BIOMETRIKA": [
        "biometrika","d2movil","d2 movil","marcacion","marcación","marcar",
        "omision","omisión","atraso","atrasos","cambio de turno","reemplazo",
        "usuario bloqueado","dispositivo no autorizado","fuera de rango","gps","ubicacion"
    ],
    "NOMINA": [
        "rol de pagos","mi rol","descargar rol","nomina","nómina","descuento por atraso",
        "salario","remuneración","bono","comprobante","pdf rol"
    ],
    "SEGURO": ["seguro","humana","cobertura médica","red médica","prestadores","aseguradora"],
    "VACACIONES": ["vacaciones","días de vacaciones","pedir vacaciones","solicitar vacaciones","anticipo de vacaciones"],
    "PERMISOS": [
        "permiso","calamidad","cita médica","reposo médico","gestiones personales",
        "maternidad","paternidad","lactancia","fallecimiento","licencia de matrimonio"
    ],
    "COMPRAS": ["compras de empleados","mercadería","remates","descuento por nómina","rol de pagos compras"],
    "COMISIONES": ["comision","comisiones","ip","indicadores","metas","aceleradores"],
}

def route_domain(q: str) -> str:
    qn = _n(q)
    best, score = "PERMISOS", 0
    for dom, terms in DOMAINS.items():
        s = max((fuzz.partial_ratio(qn, _n(t)) for t in terms), default=0)
        if s > score:
            best, score = dom, s
    return best

# ------- Reglas deterministas seguras ----
def fuzzy_any(q: str, terms: list[str], score=85) -> bool:
    qn = _n(q)
    return any(fuzz.partial_ratio(qn, _n(t)) >= score for t in terms)

RESP_OMISION = (
    "De acuerdo con la política, no se puede justificar la omisión de marcaciones por olvido. "
    "Desde la 4ª omisión en el mes se aplica una sanción de $15. ¿Te ayudo con algo más?"
)
RESP_ATRASOS = (
    "Atrasos: desde el minuto 6 se aplica $0,25 por minuto y puede cruzarse con horas extras. "
    "Hasta 5 minutos es obligatoria la recuperación el mismo día. ¿Te ayudo con algo más?"
)
RESP_NO_PERMISOS_COMUNES = (
    "No se consideran permisos: tráfico, clima, pico y placa, eventos, fallos de alarma, problemas mecánicos o detenciones. "
    "Aplica política de atrasos o vacaciones según corresponda. ¿Te ayudo con algo más?"
)
RESP_TECNICO_BIOMETRIA = (
    "Si ves: ‘Usuario bloqueado’ → restablecer contraseña; ‘Dispositivo no autorizado’ → aprobar nuevo dispositivo; "
    "‘Marcación fuera de rango’ → reinicia app/teléfono y actualiza ubicación. Registra ticket en Apolo (DO > Novedades en Biométría). ¿Te ayudo con algo más?"
)
RESP_CAMBIO_TURNO = (
    "Cambio de turno: realiza el proceso en D2 Móvil Plus > ‘Cambio de Turno’. Deben hacerlo ambos colaboradores involucrados. ¿Te ayudo con algo más?"
)
RESP_MATERNIDAD = "Maternidad: 84 días (más 10 si es múltiple). Luego lactancia 6 horas diarias hasta 15 meses. ¿Te ayudo con algo más?"
RESP_PATERNIDAD = "Paternidad: hasta 15 días (más 8 por prematuro). ¿Te ayudo con algo más?"
RESP_LACTANCIA  = "Lactancia: horario especial de 6 horas hasta 15 meses posterior a maternidad. ¿Te ayudo con algo más?"
RESP_FALLECIMIENTO = "Fallecimiento: hasta 4 días (1er grado y cónyuge) / 3 días (2do grado). Requiere acta. ¿Te ayudo con algo más?"
RESP_GESTIONES_PERSONALES = "Gestiones personales: máx. 4 h, 1 permiso/mes, recuperable en la misma semana (hasta 1h/día). ¿Te ayudo con algo más?"
RESP_VACACIONES = "Vacaciones: 15 días/año; desde el 6° sumas 1 día anual hasta 30. Solicítalas en Twiins según la política. ¿Te ayudo con algo más?"
RESP_NOMINA_ROL = "Para ver/descargar tu rol: Twiins > Rol de Pagos > PDF. ¿Te ayudo con algo más?"
RESP_SEGURO = "Seguro médico Humana: revisa cobertura y red; coordina con médico ocupacional cuando aplique. ¿Te ayudo con algo más?"

def detect_intent_fixed(q: str) -> str | None:
    if fuzzy_any(q, [
        "olvido de marcar","me olvide de marcar","omision de marcacion","no marque","no hice la marcacion",
        "sin registro de marcacion","no me registro la marcacion","se me paso marcar","marcacion omitida","falta de marcacion"
    ]) or (("olvid" in _n(q) or "omision" in _n(q)) and ("marc" in _n(q) or "biometr" in _n(q))):
        return RESP_OMISION
    if fuzzy_any(q, ["atraso","llegue tarde","retraso","minutos tarde","multa por atraso","descuento por atraso"]):
        return RESP_ATRASOS
    if fuzzy_any(q, ["trafico","pico y placa","clima","lluvia","partido","evento","alarma","mecanico","detenido"]):
        return RESP_NO_PERMISOS_COMUNES
    if fuzzy_any(q, ["usuario bloqueado","dispositivo no autorizado","fuera de rango","gps","ubicacion","error de marcacion","d2movilplus error"]):
        return RESP_TECNICO_BIOMETRIA
    if fuzzy_any(q, ["cambio de turno","reemplazo de turno","intercambiar turno","cambiar horario"]):
        return RESP_CAMBIO_TURNO
    if fuzzy_any(q, ["maternidad"]): return RESP_MATERNIDAD
    if fuzzy_any(q, ["paternidad"]): return RESP_PATERNIDAD
    if fuzzy_any(q, ["lactancia"]):  return RESP_LACTANCIA
    if fuzzy_any(q, ["fallecimiento"]): return RESP_FALLECIMIENTO
    if fuzzy_any(q, ["gestiones personales","tramites personales","reunion escolar","cedula","documento de identidad"]):
        return RESP_GESTIONES_PERSONALES
    if fuzzy_any(q, ["vacaciones","tomar vacaciones","pedir vacaciones"]): return RESP_VACACIONES
    if fuzzy_any(q, ["rol de pagos","ver rol","descargar rol","mi rol","comprobante de pago"]): return RESP_NOMINA_ROL
    if fuzzy_any(q, ["seguro","humana","cobertura medica","red medica","prestadores"]): return RESP_SEGURO
    return None

# ---------------- Prompt -----------------
def system_prompt_from(p: dict, domain: str) -> str:
    return f"""
Eres OLIVIA, asistente virtual de Grupo OLA. Respondes cálida y directa, máx. 3 líneas.
Usa SOLO la información oficial y limita tu respuesta al DOMINIO actual.

DOMINIO ACTUAL: {domain}

[REGLAS FIJAS]
- Si el usuario consulta por olvido/omisión de marcaciones, responde literalmente:
  "De acuerdo con la política, no se puede justificar la omisión de marcaciones por olvido. Desde la 4ª omisión en el mes se aplica una sanción de $15."

[POLÍTICAS OFICIALES]
VACACIONES:
{p.get('vacaciones','')}

PERMISOS Y ATRASOS:
{p.get('permisos','')}

COMPRAS DE EMPLEADOS:
{p.get('compras','')}

COMISIONES:
{p.get('comision','')}

BANCO DE PREGUNTAS DO:
{p.get('banco','')}
""".strip()

def fallback_answer(q: str) -> str:
    ql = q.lower()
    if "vacacion" in ql or "vacaciones" in ql: return RESP_VACACIONES
    if "permiso" in ql or "biometr" in ql or "d2movil" in ql: return RESP_TECNICO_BIOMETRIA
    if "compr" in ql or "mercader" in ql or "remate" in ql:
        return "Compras de empleados: cupos y descuentos definidos; toda compra debe aprobar DO. En remates hay condiciones específicas. ¿Te ayudo con algo más?"
    if "comision" in ql or "ip" in ql:
        return "Las comisiones dependen del IP y % de cumplimiento, con posibles aceleradores. Revisa la tabla oficial. ¿Te ayudo con algo más?"
    return "Puedo ayudarte con vacaciones, permisos, biometría, compras, comisiones, nómina y seguro. Cuéntame tu caso. ¿Te ayudo con algo más?"

# ------- Accesos contextuales (según tu accesos.txt) -------
def choose_access_slug(question: str, domain: str) -> list[tuple[str, str]]:
    """
    Devuelve lista de (slug,label) para sugerir; así podemos devolver 1 o varios (ej. horarios norte/sur).
    """
    qn = _n(question)
    suggestions = []

    # correo
    for lbl in ("correo zimbra","correo office","zimbra","office"):
        sg = slugify(lbl)
        if lbl in _n(" ".join(ACCESS_MAP.get(sg, {}).values())) or sg in ACCESS_MAP:
            if any(w in qn for w in ["correo","email","zimbra","office","mail"]):
                if sg in ACCESS_MAP:
                    suggestions.append((sg, ACCESS_MAP[sg]["label"]))
    # horarios
    if "horario" in qn or "hora" in qn:
        for lbl in ("horario region norte","horario region sur"):
            sg = slugify(lbl)
            if sg in ACCESS_MAP:
                # si menciona norte/sur, sugiere solo ese; si no, ambos
                if "norte" in qn and "norte" in lbl:
                    suggestions.append((sg, ACCESS_MAP[sg]["label"]))
                elif "sur" in qn and "sur" in lbl:
                    suggestions.append((sg, ACCESS_MAP[sg]["label"]))
        if not suggestions:
            for lbl in ("horario region norte","horario region sur"):
                sg = slugify(lbl)
                if sg in ACCESS_MAP:
                    suggestions.append((sg, ACCESS_MAP[sg]["label"]))

    # twiins / biometrika
    if domain in ("NOMINA","VACACIONES","PERMISOS"):
        sg = slugify("Twins")
        if any(w in qn for w in ["rol de pagos","mi rol","descargar rol","comprobante","twiins","twins"]):
            # en tu txt 'Twins' tiene url a la home de Twiins corporativa
            sgt = slugify("Twins")
            if sgt in ACCESS_MAP:
                suggestions.append((sgt, ACCESS_MAP[sgt]["label"]))
    if domain == "BIOMETRIKA" or any(w in qn for w in ["biometr","d2movil","marcaci","marcar"]):
        for lbl in ("Biométrica",):
            sg = slugify(lbl)
            if sg in ACCESS_MAP:
                suggestions.append((sg, ACCESS_MAP[sg]["label"]))

    # tickets apolo
    if any(w in qn for w in ["ticket","soporte","novedad","apolo"]):
        sg = slugify("Apolo")
        if sg in ACCESS_MAP:
            suggestions.append((sg, ACCESS_MAP[sg]["label"]))

    # eliminar duplicados conservando orden
    seen = set()
    out = []
    for s in suggestions:
        if s[0] not in seen:
            out.append(s); seen.add(s[0])
    return out

# ------------- Flujo: Uniformes -------------
STATE = {}  # { sid: {"flow":"uniformes","step":1..3,"brand":...} }

def render_chip(label: str, value: str) -> str:
    return f'<a class="chip" data-chip="{html.escape(value)}"><span>👉</span> {html.escape(label)}</a>'

def uniform_link_by_title(label: str) -> str:
    sg = slugify(label)
    data = ACCESS_MAP.get(sg)
    if not data: return ""
    return f'👉 {short_href(sg, data["label"])}'

def menu_brand() -> str:
    chips = " ".join([
        render_chip("OLA","OLA"),
        render_chip("Aura Skin","Aura Skin"),
        render_chip("Metrored","Metrored")
    ])
    return f'<div class="box"><div class="hint">¿Dime en dónde trabajas?</div><div class="chips">{chips}</div></div>'

def menu_area_ola() -> str:
    chips = " ".join([render_chip("Administrativo","Administrativo"), render_chip("Comercial","Comercial")])
    return f'<div class="box"><div class="hint">Selecciona en qué área trabajas:</div><div class="chips">{chips}</div></div>'

def menu_cargo_ola() -> str:
    chips = " ".join([render_chip("Asesor Comercial","Asesor Comercial"), render_chip("Optómetra","Optómetra")])
    return f'<div class="box"><div class="hint">¿Cuál es tu cargo?</div><div class="chips">{chips}</div></div>'

def start_uniform_flow(sid: str) -> str:
    STATE[sid] = {"flow":"uniformes","step":1}
    return menu_brand()

def normalize_val(txt: str) -> str:
    t = _n(txt)
    mapping = {
        "ola":"OLA","aura skin":"Aura Skin","metrored":"Metrored",
        "administrativo":"Administrativo","comercial":"Comercial",
        "asesor comercial":"Asesor Comercial","optometra":"Optómetra","optómetra":"Optómetra"
    }
    for k,v in mapping.items():
        if t == _n(k): return v
    for k,v in mapping.items():
        if fuzz.partial_ratio(t, _n(k)) >= 88: return v
    return txt.strip()

def uniform_step(sid: str, user_text: str) -> str | None:
    ctx = STATE.get(sid)
    if not ctx or ctx.get("flow") != "uniformes":
        return None
    val = normalize_val(user_text)

    if val in ("OLA","Aura Skin","Metrored"):
        ctx["brand"] = val
        if val == "OLA":
            ctx["step"] = 2
            return menu_area_ola()
        if val == "Aura Skin":
            htmlx = 'Puedes consultar la política de uniformes de Aura Skin:<br>' + uniform_link_by_title("Política de uniformes - Aura Skin")
            return htmlx + "<br><br>" + menu_brand()
        if val == "Metrored":
            htmlx = 'Puedes consultar la política de uniformes de Metrored:<br>' + uniform_link_by_title("Política de uniformes - Metrored")
            return htmlx + "<br><br>" + menu_brand()

    if ctx.get("brand") == "OLA":
        if val == "Administrativo":
            ctx["step"] = 2
            htmlx = 'Aquí puedes revisar la política de uniformes de OLA Administrativo:<br>' + uniform_link_by_title("Política de uniformes - Administrativos")
            return htmlx + "<br><br>" + menu_area_ola() + "<br>" + menu_brand()
        if val == "Comercial":
            ctx["step"] = 3
            return menu_cargo_ola()
        if ctx.get("step") == 3 and val in ("Asesor Comercial","Optómetra"):
            if val == "Asesor Comercial":
                htmlx = 'Aquí puedes revisar la política de uniformes de OLA para los Asesores Comerciales:<br>' + uniform_link_by_title("Política de uniformes - Asesor Comercial")
            else:
                htmlx = 'Aquí puedes revisar la política de uniformes de OLA para los Optómetras:<br>' + uniform_link_by_title("Política de uniformes - Optometra")
            return htmlx + "<br><br>" + menu_cargo_ola() + "<br>" + menu_area_ola() + "<br>" + menu_brand()
        return menu_area_ola() + "<br>" + menu_brand()

    return menu_brand()

# ================= UI =====================
@app.route("/", methods=["GET"])
def home():
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>OLIVIA</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; background: #ffffff; margin: 0; padding: 0; }
  .chat-box { max-width: 420px; height: 100vh; margin: 0 auto; display: flex; flex-direction: column; border: 1px solid #e5e7eb; }
  .header { text-align: center; border-bottom: 1px solid #e5e7eb; padding: 16px 0 10px; }
  .header img { height: 50px; }
  .nombre-olivia { text-align: center; font-size: 20px; font-weight: 700; color: #00989a; margin-top: 6px; letter-spacing: 1px; }
  .messages { flex: 1; padding: 20px; background: #f9fafb; overflow-y: auto; }
  .bubble { max-width: 75%; padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.4; margin-bottom: 10px; clear: both; }
  .usuario { background: #d1f1e3; color: #00332f; float: right; }
  .olivia { background: #ffffff; border: 1px solid #e0e0e0; float: left; }
  .input-area { display: flex; align-items: center; gap: 8px; border-top: 1px solid #e5e7eb; padding: 10px; background: #fff; }
  .whatsapp { display: flex; align-items: center; justify-content: center; border: none; background: none; cursor: pointer; }
  .whatsapp img { width: 26px; height: 26px; }
  input[type="text"] { flex: 1; border: 1px solid #ccc; border-radius: 20px; padding: 10px; font-size: 14px; }
  button { background: #00989a; border: none; color: white; border-radius: 20px; font-weight: bold; padding: 8px 16px; cursor: pointer; }
  .footer { text-align: center; font-size: 12px; color: #94a3b8; padding-bottom: 8px; }
  /* chips */
  .chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}
  .chip{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:16px;background:#00989a;color:#fff;font-weight:600;cursor:pointer;text-decoration:none}
  .chip span{font-size:18px}
  .hint{color:#0f172a;font-weight:600;margin-bottom:4px}
  .box{background:#eef2ff;border:1px solid #dfe3f0;padding:12px;border-radius:12px}
</style>
</head>
<body>
  <div class="chat-box" id="chatBox">
    <div class="header">
      <img src="https://intranet.opticalosandes.com.ec/wp-content/uploads/2022/02/grupo-ola.png" alt="Grupo OLA" />
      <div class="nombre-olivia">OLIVIA</div>
    </div>

    <div class="messages" id="chatMessages">
      <div class="bubble olivia">Hola, estoy aquí para acompañarte y ayudarte con cualquier duda 😊</div>
    </div>

    <form class="input-area" id="chatForm">
      <a class="whatsapp" href="https://wa.me/593998515934" target="_blank" title="Sugerencias o soporte">
        <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" alt="WhatsApp" />
      </a>
      <input type="text" id="mensaje" placeholder="Mensaje" required />
      <button type="submit">Enviar</button>
    </form>
    <div class="footer">© Grupo OLA 2025</div>
  </div>

<script>
const form = document.getElementById('chatForm');
const inputField = document.getElementById('mensaje');
const chatMessages = document.getElementById('chatMessages');

// SID persistente
const SID_KEY = 'olivia_sid';
let SID = localStorage.getItem(SID_KEY);
if(!SID){ SID = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()); localStorage.setItem(SID_KEY, SID); }

async function sendToBot(text){
  const userBubble = document.createElement('div');
  userBubble.className = 'bubble usuario';
  userBubble.textContent = text;
  chatMessages.appendChild(userBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  const loader = document.createElement('div');
  loader.className = 'bubble olivia';
  loader.textContent = 'Escribiendo...';
  chatMessages.appendChild(loader);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch('/responder', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({mensaje: text, sid: SID})
    });
    const data = await res.json();
    loader.innerHTML = data.respuesta || 'Error interno';
  } catch {
    loader.textContent = 'Error de conexión';
  }
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const mensaje = inputField.value.trim();
  if (!mensaje) return;
  inputField.value = '';
  sendToBot(mensaje);
});

// Click en chips
chatMessages.addEventListener('click', (e)=>{
  const chip = e.target.closest('[data-chip]');
  if(!chip) return;
  const value = chip.getAttribute('data-chip');
  sendToBot(value);
});
</script>
</body>
</html>
""")

# ================= API ====================
@app.route("/responder", methods=["POST"])
def responder():
    data = request.get_json(silent=True) or {}
    pregunta = sanitize(data.get("mensaje", ""))
    sid = (data.get("sid") or "").strip()

    if not pregunta:
        return jsonify({"respuesta": "Por favor, escribe un mensaje."})

    # 0) Flujo Uniformes si está activo
    if sid and STATE.get(sid, {}).get("flow") == "uniformes":
        htmlx = uniform_step(sid, pregunta)
        if htmlx:
            return jsonify({"respuesta": Markup(htmlx)})

    # 1) Disparador Uniformes
    if any(w in _n(pregunta) for w in ["uniforme","uniformes"]):
        htmlx = start_uniform_flow(sid or "anon")
        return jsonify({"respuesta": Markup(htmlx)})

    # 2) Router
    domain = route_domain(pregunta)

    # 3) Reglas deterministas
    fixed = detect_intent_fixed(pregunta)
    if fixed:
        appendix = ""
        links = choose_access_slug(pregunta, domain)
        if links:
            if len(links) == 2 and all("norte" in l[1].lower() or "sur" in l[1].lower() for l in links):
                appendix = (
                    "<br><br>Seleccione el horario según su Región:<br>" +
                    "<br>".join([f"👉 {short_href(sl, lb)}" for sl, lb in links])
                )
            else:
                # muestra el primero
                sl, lb = links[0]
                appendix = f"<br><br>Acceso rápido: {short_href(sl, lb)}"
        return jsonify({"respuesta": fixed + appendix})

    # 4) Políticas y prompt
    policies = load_policies()
    sys_prompt = system_prompt_from(policies, domain)

    # 5) Cliente OpenAI
    global client
    if client is None:
        client = get_openai_client()
    if client is None:
        return jsonify({"respuesta": fallback_answer(pregunta)})

    # 6) IA
    try:
        cmpl = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": f"[DOMINIO={domain}] Pregunta: {pregunta}"}
            ],
            temperature=0.3,
            max_tokens=160
        )
        answer = (cmpl.choices[0].message.content or "").strip()
        lines = [l.strip() for l in re.split(r'(?:\r?\n)+', answer) if l.strip()]
        if len(lines) > 4:
            answer = " ".join(lines[:4])

        appendix = ""
        links = choose_access_slug(pregunta, domain)
        if links:
            if len(links) == 2 and all("norte" in l[1].lower() or "sur" in l[1].lower() for l in links):
                appendix = (
                    "<br><br>Seleccione el horario según su Región:<br>" +
                    "<br>".join([f"👉 {short_href(sl, lb)}" for sl, lb in links])
                )
            else:
                sl, lb = links[0]
                appendix = f"<br><br>Acceso rápido: {short_href(sl, lb)}"

        if "¿Te ayudo con algo más?" not in answer:
            answer = f"{answer} ¿Te ayudo con algo más?"
        return jsonify({"respuesta": Markup(answer + appendix)})
    except Exception:
        return jsonify({"respuesta": fallback_answer(pregunta)})

# --------------- Diagnóstico ---------------
@app.route("/diag")
def diag():
    from importlib.util import find_spec
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    has_pkg = find_spec("openai") is not None
    base = "policies"
    pols = {
        "vacaciones": os.path.isfile(os.path.join(base, "politica_vacaciones.txt")),
        "permisos":   os.path.isfile(os.path.join(base, "politica_permisos.txt")),
        "compras":    os.path.isfile(os.path.join(base, "politica_compras.txt")),
        "comision":   os.path.isfile(os.path.join(base, "politica_comision.txt")),
        "banco":      os.path.isfile(os.path.join(base, "banco_preguntas.txt")),
        "accesos":    os.path.isfile(os.path.join(base, "accesos.txt")),
    }
    sample = list(ACCESS_MAP.keys())[:6]
    return {
        "ai_ready": has_key and has_pkg and (client is not None),
        "has_OPENAI_API_KEY": has_key,
        "openai_installed": has_pkg,
        "policies": pols,
        "access_map_size": len(ACCESS_MAP),
        "access_map_sample": sample,
        "init_error": OPENAI_INIT_ERROR,
        "key_prefix": (os.getenv("OPENAI_API_KEY") or "")[:5],
        "key_len": len(os.getenv("OPENAI_API_KEY") or "")
    }, 200

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)