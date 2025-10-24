from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from markupsafe import Markup
import os, re

# ============ Config ============
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# SDK OpenAI v1.x
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    client = None

app = Flask(__name__)

# ============ Utils ============
def read_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def load_policies() -> dict:
    base = "policies"
    return {
        "vacaciones": read_txt(os.path.join(base, "politica_vacaciones.txt")),
        "permisos":   read_txt(os.path.join(base, "politica_permisos.txt")),
        "compras":    read_txt(os.path.join(base, "politica_compras.txt")),
        "comision":   read_txt(os.path.join(base, "politica_comision.txt")),
        "banco":      read_txt(os.path.join(base, "banco_preguntas.txt")),
    }

def sanitize(text: str) -> str:
    text = (text or "").replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)

def system_prompt_from(p: dict) -> str:
    return f"""
Eres OLIVIA, asistente virtual de Grupo OLA enfocada en RRHH (vacaciones, permisos/biometría, compras internas y comisiones).
Respondes cálida y directo, con máximo 3 líneas. Si algo no está en políticas, dilo y pide precisión.
Usa SOLO el contenido oficial de abajo.

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
    if "vacacion" in ql or "vacaciones" in ql:
        return "Tienes 15 días por año; desde el sexto año sumas 1 día anual hasta 30. Solicítalas en Twiins según la anticipación de la política. ¿Te ayudo con algo más?"
    if "permiso" in ql or "biometr" in ql or "d2movil" in ql:
        return "Los permisos se gestionan en D2MovilPlus/Biometrika con respaldos según el tipo. Enfermedad: certificado; calamidad: según alcance. ¿Te ayudo con algo más?"
    if "compr" in ql or "mercader" in ql or "remate" in ql:
        return "Compras de empleados: cupos y descuentos definidos; toda compra debe aprobar DO. En remates aplican condiciones específicas. ¿Te ayudo con algo más?"
    if "comision" in ql or "ip" in ql:
        return "Las comisiones dependen del IP y % de cumplimiento, con aceleradores por sobrecumplimiento. Revisa la tabla oficial. ¿Te ayudo con algo más?"
    return "Puedo ayudarte con vacaciones, permisos, compras internas y comisiones según la política oficial. Cuéntame tu caso. ¿Te ayudo con algo más?"

# ============ UI ============
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

form.addEventListener('submit', async function(e) {
  e.preventDefault();
  const mensaje = inputField.value.trim();
  if (!mensaje) return;

  const userBubble = document.createElement('div');
  userBubble.className = 'bubble usuario';
  userBubble.textContent = mensaje;
  chatMessages.appendChild(userBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  inputField.value = '';

  const loader = document.createElement('div');
  loader.className = 'bubble olivia';
  loader.textContent = 'Escribiendo...';
  chatMessages.appendChild(loader);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch('/responder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mensaje})
    });
    const data = await res.json();
    loader.innerHTML = data.respuesta || 'Error interno';
  } catch {
    loader.textContent = 'Error de conexión';
  }
});
</script>
</body>
</html>
""")

# ============ API ============
@app.route("/responder", methods=["POST"])
def responder():
    data = request.get_json(silent=True) or {}
    pregunta = sanitize(data.get("mensaje", ""))

    if not pregunta:
        return jsonify({"respuesta": "Por favor, escribe un mensaje."})

    policies = load_policies()
    sys_prompt = system_prompt_from(policies)

    # Si no hay clave o cliente, usa fallback determinista
    if client is None:
        return jsonify({"respuesta": fallback_answer(pregunta)})

    try:
        cmpl = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": pregunta}
            ],
            temperature=0.4,
            max_tokens=160
        )
        answer = (cmpl.choices[0].message.content or "").strip()
        # Limita a 3 líneas por seguridad
        lines = [l.strip() for l in re.split(r'(?:\r?\n)+', answer) if l.strip()]
        if len(lines) > 3:
            answer = " ".join(lines[:3])
        if "¿Te ayudo con algo más?" not in answer:
            answer = f"{answer} ¿Te ayudo con algo más?"
        return jsonify({"respuesta": Markup(answer)})
    except Exception:
        return jsonify({"respuesta": fallback_answer(pregunta)})

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
    }
    return {
        "ai_ready": has_key and has_pkg and (client is not None),
        "has_OPENAI_API_KEY": has_key,
        "openai_installed": has_pkg,
        "policies": pols
    }, 200

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
