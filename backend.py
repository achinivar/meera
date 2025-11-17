import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"  # tiny, CPU-friendly model

def stream_llm(prompt: str, model: str = MODEL_NAME):
    """
    Generator that yields small chunks of text from the model as they arrive.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "options": {
            "num_predict": 128,
            "num_ctx": 1024,
        },
        "stream": True,
    }

    try:
        response = requests.post(OLLAMA_URL, data=json.dumps(payload), stream=True)

        for line in response.iter_lines():
            if not line:
                continue

            packet = json.loads(line.decode())

            # Normal streaming token
            if "response" in packet:
                chunk = packet["response"]
                if chunk:
                    yield chunk

            # If Ollama returns an error field
            if "error" in packet:
                yield f"[Model error: {packet['error']}]"
                break

    except Exception as e:
        # Propagate error as a chunk so UI can show it
        yield f"[Error contacting model: {e}]"

