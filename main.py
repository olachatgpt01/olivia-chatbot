from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/", methods=["GET"])
def home():
    return "OLIVIA está en línea ✅", 200

@app.route("/responder", methods=["POST"])
def responder():
    data = request.get_json(silent=True) or {}
    pregunta = (data.get("mensaje") or "").strip()
    # Por ahora, respuesta fija; luego conectamos a OpenAI y tus políticas.
    if not pregunta:
        return jsonify({"ok": False, "msg": "Falta 'mensaje'"}), 400
    return jsonify({"ok": True, "respuesta": "Hola, soy OLIVIA. ¿En qué te ayudo?"})
    
if __name__ == "__main__":
    # Render inyecta $PORT; localmente correrá en 5000
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)