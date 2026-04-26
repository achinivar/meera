import requests
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3.5:2b-q4_K_M"

def stream_llm_events(messages: list, model: str = MODEL_NAME):
    """
    Generator that yields small chunks of text from the model as they arrive.
    
    Args:
        messages: List of message dicts with 'role' ('user' or 'assistant') and 'content'
        model: Model name to use
    
    Yields:
        Event dicts: {"kind":"content"|"thinking","text": "..."}
    """
    payload = {
        "model": model,
        "messages": messages,
        "options": {
            "num_predict": 1024,
            "num_ctx": 4096
        },
        "stream": True,
        # Qwen3 / thinking-capable models: top-level flag for Ollama chat API
        "think": False,
    }

    try:
        response = requests.post(OLLAMA_URL, data=json.dumps(payload), stream=True)

        for line in response.iter_lines():
            if not line:
                continue

            packet = json.loads(line.decode())

            if "message" in packet:
                message = packet["message"] or {}
                chunk = message.get("content")
                if chunk:
                    yield {"kind": "content", "text": chunk}

            # If Ollama returns an error field
            if "error" in packet:
                yield {"kind": "content", "text": f"[Model error: {packet['error']}]"}
                break

    except Exception as e:
        # Propagate error as a chunk so UI can show it
        yield {"kind": "content", "text": f"[Error contacting model: {e}]"}


def stream_llm(messages: list, model: str = MODEL_NAME):
    for event in stream_llm_events(messages, model=model):
        if event.get("kind") == "content":
            chunk = event.get("text")
            if chunk:
                yield chunk

