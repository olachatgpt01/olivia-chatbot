from flask import Flask, request, jsonify, render_template_string
import os

app = Flask(__name__)

@app.route("/")
def home():
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>OLIVIA</title>
<style>
  body {
    font-family: 'Segoe UI', sans-serif;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }
  .chat-box {
    max-width: 420px;
    height: 100vh;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    border: 1px solid #e5e7eb;
  }
  .header {
    text-align: center;
    border-bottom: 1px solid #e5e7eb;
    padding: 16px 0 10px;
  }
  .header img {
    height: 50px;
  }
  .nombre-olivia {
    text-align: center;
    font-size: 20px;
    font-weight: 700;
    color: #00989a;
    margin-top: 6px;
    letter-spacing: 1px;
  }
  .messages {
    flex: 1;
    padding: 20px;
    background: #f9fafb;
    overflow-y: auto;
  }
  .bubble {
    max-width: 75%;
    padding: 10px 14px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.4;
    margin-bottom: 10px;
    clear: both;
  }
  .usuario {
    background: #d1f1e3;
    color: #00332f;
    float: right;
  }
  .olivia {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    float: left;
  }
  .input-area {
    display: flex;
    align-items: center;
    gap: 8px;
    border-top: 1px solid #e5e7eb;
    padding: 10px;
    background: #fff;
  }
  .whatsapp {
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    cursor: pointer;
  }
  .whatsapp img {
    width: 26px;
    height: 26px;
  }
  input[type="text"] {
    flex: 1;
    border: 1px solid #ccc;
    border-radius: 20px;
    padding: 10px;
    font-size: 14px;
  }
  button {
    background: #00989a;
    border: none;
    color: white;
    border-radius: 20px;
    font-weight: bold;
    padding: 8px 16px;
    cursor: pointer;
  }
  .footer {
    text-align: center;
    font-size: 12px;
    color: #94a3b8;
    padding-bottom: 8px;
  }
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
    loader.textContent = data.respuesta || 'Error interno';
  } catch {
    loader.textContent = 'Error de conexión';
  }
});
</script>
</body>
</html>
""")

@app.route("/responder", methods=["POST"])
def responder():
    data = request.get_json(silent=True) or {}
    msg = (data.get("mensaje") or "").strip()
    if not msg:
        return jsonify({"respuesta": "Por favor, escribe un mensaje."})
    return jsonify({"respuesta": "Gracias por tu mensaje. 😊 En breve conectaré con las políticas y OpenAI."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)