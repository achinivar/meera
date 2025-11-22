import requests
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2:1b"  # tiny, CPU-friendly model

def stream_llm(messages: list, model: str = MODEL_NAME):
    """
    Generator that yields small chunks of text from the model as they arrive.
    
    Args:
        messages: List of message dicts with 'role' ('user' or 'assistant') and 'content'
        model: Model name to use
    
    Yields:
        Chunks of text as they arrive from the model
    """
    payload = {
        "model": model,
        "messages": messages,
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
            if "message" in packet and "content" in packet["message"]:
                chunk = packet["message"]["content"]
                if chunk:
                    yield chunk

            # If Ollama returns an error field
            if "error" in packet:
                yield f"[Model error: {packet['error']}]"
                break

    except Exception as e:
        # Propagate error as a chunk so UI can show it
        yield f"[Error contacting model: {e}]"

