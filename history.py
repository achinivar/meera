import os
import json
from datetime import datetime
from pathlib import Path

# Maximum number of sessions to keep
MAX_SESSIONS = 10

def get_history_dir():
    """Get the directory where chat history is stored."""
    # Use XDG data directory if available, otherwise fall back to ~/.local/share/meera
    data_dir = os.environ.get("XDG_DATA_HOME")
    if not data_dir:
        data_dir = os.path.join(os.path.expanduser("~"), ".local", "share")
    
    history_dir = os.path.join(data_dir, "meera", "history")
    os.makedirs(history_dir, exist_ok=True)
    return history_dir

def save_session(conversation_history):
    """
    Save a conversation session to disk.
    
    Args:
        conversation_history: List of message dicts with 'role' and 'content'
    
    Returns:
        Path to the saved session file
    """
    if not conversation_history:
        # Don't save empty sessions
        return None
    
    history_dir = get_history_dir()
    
    # Create session data with timestamp
    timestamp = datetime.now().isoformat()
    session_data = {
        "timestamp": timestamp,
        "messages": conversation_history
    }
    
    # Generate filename from timestamp (sanitized)
    filename = timestamp.replace(":", "-").replace(".", "-") + ".json"
    filepath = os.path.join(history_dir, filename)
    
    # Save session
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    # Clean up old sessions (keep only last MAX_SESSIONS)
    cleanup_old_sessions(history_dir)
    
    return filepath

def cleanup_old_sessions(history_dir):
    """
    Remove old sessions, keeping only the last MAX_SESSIONS.
    
    Args:
        history_dir: Directory containing session files
    """
    try:
        # Get all session files
        session_files = []
        for filename in os.listdir(history_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(history_dir, filename)
                # Get modification time as a way to sort
                mtime = os.path.getmtime(filepath)
                session_files.append((mtime, filepath))
        
        # Sort by modification time (oldest first)
        session_files.sort(key=lambda x: x[0])
        
        # Delete oldest sessions if we have more than MAX_SESSIONS
        if len(session_files) > MAX_SESSIONS:
            files_to_delete = session_files[:-MAX_SESSIONS]  # All except last MAX_SESSIONS
            for _, filepath in files_to_delete:
                try:
                    os.remove(filepath)
                except OSError:
                    pass  # Ignore errors when deleting
    except OSError:
        pass  # Ignore errors if directory doesn't exist or can't be read

def list_sessions():
    """
    List all saved sessions, sorted by timestamp (newest first).
    
    Returns:
        List of dicts with 'timestamp', 'filepath', and 'message_count'
    """
    history_dir = get_history_dir()
    sessions = []
    
    try:
        for filename in os.listdir(history_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(history_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    
                    sessions.append({
                        "timestamp": session_data.get("timestamp", ""),
                        "filepath": filepath,
                        "message_count": len(session_data.get("messages", []))
                    })
                except (json.JSONDecodeError, KeyError):
                    continue  # Skip corrupted files
        
        # Sort by timestamp (newest first)
        sessions.sort(key=lambda x: x["timestamp"], reverse=True)
    except OSError:
        pass  # Directory doesn't exist yet
    
    return sessions

def load_session(filepath):
    """
    Load a session from disk.
    
    Args:
        filepath: Path to the session file
    
    Returns:
        List of message dicts, or None if file doesn't exist or is invalid
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        return session_data.get("messages", [])
    except (OSError, json.JSONDecodeError, KeyError):
        return None

