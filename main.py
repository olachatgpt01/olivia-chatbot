from flask import Flask, request, jsonify, render_template_string
import os

app = Flask(__name__)

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/", methods=["GET"])
def home():
    # UI mínima de chat
    return render_template_string("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>OLIVIA Chat</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:0; background:#f6f7f8; }
    .wrap { max-width:640px; margin:0 auto; min-height:100vh; display:flex; flex-direction:column; }
    .hdr { padding:16px; background:#0f766e; color:white; font-weight:600; }
    .msgs { flex:1; padding:16px; overflow:auto; }
    .bbl { max-width:75%; padding:10px 14px; border-radius:12px; margin-bottom:10px; line-height:1.35; }
    .me  { background:#d1fae5; margin-left:auto; }
    .bot { background:white; border:1px solid #e5e7eb; }
    .inp { display:flex; gap:8px; padding:12px; border-top:1px solid #e5e7eb; background:white; position:sticky; bottom:0; }
    input[type=text]{ flex:1; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px; }
    button{ padding:10px 14px; border:0; border-radius:10px; background:#0f766e; color:white; font-weight:600; cursor:pointer; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hdr">OLIVIA está en línea ✅</div>
    <div id="msgs" class="msgs">
      <div class="bbl bot">Hola, soy OLIVIA. ¿En qué te ayudo?</div>
    </div>
    <form id="frm" class="inp">
      <input id="txt" type="text" placeholder="Escribe tu mensaje..." required />
      <button>Enviar</button>
    </form>
  </div>

<script>
const frm = document.getElementById('frm');
const txt = document.getElementById('txt');
const msgs = document.getElementById('msgs');

frm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const m = txt.value.trim();
  if(!m) return;

  // burbuja usuario
  const u = document.createElement('div');
  u.className = 'bbl me';
  u.textContent = m;
  msgs.appendChild(u);
  msgs.scrollTop = msgs.scrollHeight;
  txt.value='';

  // llamada al backend
  try{
    const r = await fetch('/responder', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ mensaje: m })
    });
    const data = await r.json();
    const b = document.createElement('div');
    b.className = 'bbl bot';
    b.textContent = data.ok ? data.respuesta : (data.msg || 'Ocurrió un error');
    msgs.appendChild(b);
    msgs.scrollTop = msgs.scrollHeight;
  }catch(err){
    const b = document.createElement('div');
    b.className = 'bbl bot';
    b.textContent = 'Error de red';
    msgs.appendChild(b);
    msgs.scrollTop = msgs.scrollHeight;
  }
});
</script>
</body>
</html>
""")

@app.route("/responder", methods=["POST"])
def responder():
    data = request.get_json(silent=True) or {}
    pregunta = (data.get("mensaje") or "").strip()
    if not pregunta:
        return jsonify({"ok": False, "msg": "Falta 'mensaje'"}), 400
    # Respuesta dummy por ahora
    return jsonify({"ok": True, "respuesta": "Recibido ✅. En breve conectaré con políticas y OpenAI."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
