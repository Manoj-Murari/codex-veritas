# src/codex_veritas/app/main.py

"""
Main entry point for the Flask web application.

This module sets up a simple Flask server to provide a web-based chat interface
for the Codex Veritas AI agent. It handles two primary routes:
- `/`: Serves the main HTML page for the chat interface.
- `/query`: An API endpoint that receives user questions, passes them to the
            agent's engine, and streams the agent's thoughts and final answer
            back to the client in real-time.

It uses Flask-Session to maintain a separate chat history for each user.
"""

from flask import Flask, render_template, request, Response, session, stream_with_context
from flask_session import Session
import json
from pathlib import Path
import os

# --- Local Imports ---
# This brings in the core logic of the AI agent.
from codex_veritas.agent import engine

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Session Configuration ---
# Configure session to use the filesystem; a more robust solution than cookies.
# A secret key is required for session security.
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = os.urandom(24)  # Generate a random secret key
Session(app)

# --- App Routes ---

@app.route('/')
def index():
    """Serves the main chat page and initializes chat history in the session."""
    if 'chat_history' not in session:
        session['chat_history'] = []
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query():
    """Handles incoming user queries and streams the agent's response."""
    data = request.get_json()
    question = data.get('question')
    
    # Retrieve chat history from the user's session.
    chat_history = session.get('chat_history', [])

    def generate():
        """A generator function to stream the agent's response."""
        final_answer_content = ""
        try:
            # The agent's response is a generator. We iterate through its events.
            for event in engine.answer_query(question, chat_history):
                # We format each event as a Server-Sent Event (SSE) for the browser.
                yield f"data: {json.dumps(event)}\n\n"
                if event['type'] == 'final_answer':
                    final_answer_content = event['content']
        
        except Exception as e:
            # If an error occurs, send an error event to the browser.
            error_event = {"type": "error", "content": f"An error occurred: {e}"}
            yield f"data: {json.dumps(error_event)}\n\n"
            print(f"--- ❌ ERROR in response generation: {e} ---")

        finally:
            # --- FINAL FIX HERE: Update session history inside the request context ---
            # This ensures chat history is saved correctly before the request ends.
            chat_history.append({"role": "user", "parts": [{"text": question}]})
            chat_history.append({"role": "model", "parts": [{"text": final_answer_content}]})
            session['chat_history'] = chat_history

    # Return a streaming response.
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

def run():
    """Runs the Flask development server."""
    app.run(host='0.0.0.0', port=5001, debug=True)

# --- Main Execution Guard ---
if __name__ == '__main__':
    run()

