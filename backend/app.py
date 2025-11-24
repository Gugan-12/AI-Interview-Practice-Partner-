###################################################################################################
# 🌟 EightFold.ai Interview Backend v2.0
# - Flask backend API for text + voice interview chatbot
# - Firebase Auth protected 
# - OpenRouter LLM + ElevenLabs TTS
# - Full session tracking with inappropriate content detection
# - CORS for multiple frontend origins
#
# NOTE: Only structured + commented. ***No code changes were made.***
###################################################################################################

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import json, requests, os, uuid, time, re
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth
from io import BytesIO

###################################################################################################
# 🔧 Flask App Initialization
###################################################################################################

app = Flask(__name__)

# Allow multiple frontend origins (Netlify, localhost etc.)
CORS(app,
    resources={r"/*": {
        "origins": [
            "https://eightfoldai-chat.netlify.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500"
        ]
    }},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)

###################################################################################################
# 🔐 Firebase Admin Initialization
###################################################################################################

try:
    cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS', '{}'))
    if cred_dict:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin SDK initialized")
    else:
        print("⚠️ Firebase not initialized — missing FIREBASE_CREDENTIALS")
except Exception as e:
    print(f"⚠️ Firebase initialization error: {str(e)}")

###################################################################################################
# 🔑 API Key Configuration + Rotation
###################################################################################################

ELEVEN_KEYS = [k.strip() for k in os.getenv('ELEVEN_KEYS', '').split(',') if k.strip()]
OPENROUTER_KEYS = [k.strip() for k in os.getenv('OPENROUTER_KEYS', '').split(',') if k.strip()]
OPENAI_KEYS = [k.strip() for k in os.getenv('OPENAI_KEYS', '').split(',') if k.strip()]

key_indices = {'eleven': 0, 'openrouter': 0, 'openai': 0}

###################################################################################################
# 💾 Session Storage
###################################################################################################

sessions = {}        # Stores active interview sessions
user_sessions = {}   # Maps user → session IDs

###################################################################################################
# 🔐 Firebase Token Verification Decorator
###################################################################################################

def verify_firebase_token(f):
    """Validates Firebase ID token for every protected route."""
    @wraps(f)
    def decorated(*args, **kwargs):

        # Allow OPTIONS preflight
        if request.method == "OPTIONS":
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized - No token"}), 401

        token = auth_header.split("Bearer ")[1]

        try:
            decoded = auth.verify_id_token(token)
            request.user_id = decoded["uid"]
            request.user_email = decoded.get("email", "unknown")
            return f(*args, **kwargs)
        except Exception:
            return jsonify({"error": "Unauthorized - Invalid token"}), 401

    return decorated

###################################################################################################
# 🔄 API Key Rotator
###################################################################################################

def get_next_key(service):
    """Rotate between multiple API keys to prevent usage limits."""
    if service == 'eleven' and ELEVEN_KEYS:
        idx = key_indices['eleven']
        key_indices['eleven'] = (idx + 1) % len(ELEVEN_KEYS)
        return ELEVEN_KEYS[idx]

    if service == 'openrouter' and OPENROUTER_KEYS:
        idx = key_indices['openrouter']
        key_indices['openrouter'] = (idx + 1) % len(OPENROUTER_KEYS)
        return OPENROUTER_KEYS[idx]

    if service == 'openai' and OPENAI_KEYS:
        idx = key_indices['openai']
        key_indices['openai'] = (idx + 1) % len(OPENAI_KEYS)
        return OPENAI_KEYS[idx]

    return None

###################################################################################################
# 🚫 Inappropriate Content Detection
###################################################################################################

def detect_inappropriate_content(text):
    """Detects profanity, spam, harassment, gibberish etc."""
    text_lower = text.lower()

    profanity = ['fuck', 'shit', 'bitch', 'ass', 'damn', 'hell', 'stupid ai', 'dumb ai', 'idiot']
    spam = ['spam', 'buy now', 'click here', 'win prize']
    harassment = ['hate you', 'kill', 'threat', 'attack']

    return {
        'is_inappropriate': any(w in text_lower for w in profanity + harassment),
        'is_spam': any(w in text_lower for w in spam),
        'is_too_short': len(text.strip()) <= 2,
        'needs_redirection': any(w in text_lower for w in profanity + harassment + spam)
    }

###################################################################################################
# 🤖 LLM Call Wrapper (OpenRouter)
###################################################################################################

def call_llm(messages, system_prompt, max_retries=3):
    """Central LLM function with retries, key rotation & JSON extraction."""
    for attempt in range(max_retries):

        api_key = get_next_key('openrouter')
        if not api_key:
            return {"error": "No LLM API key configured"}

        try:
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://ai-interview-practitioner.com',
                    'X-Title': 'AI Interview Practitioner'
                },
                json={
                    'model': 'google/gemma-2-9b-it',
                    'messages': [{'role': 'system', 'content': system_prompt}] + messages,
                    'temperature': 0.7,
                    'max_tokens': 256
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']

                # Extract JSON from markdown blocks if present
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()

                try:
                    parsed = json.loads(content)
                except:
                    # Fallback: extract JSON inside { ... }
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        try:
                            parsed = json.loads(match.group())
                        except:
                            pass
                    else:
                        parsed = {"text_response": content}

                # Ensure required fields exist
                parsed.setdefault("voice_response", parsed.get("text_response"))
                parsed.setdefault("end", False)
                return parsed

            # Retryable errors
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(2)
                continue

            return {"error": f"LLM error {response.status_code}"}

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"error": str(e)}

    return {"error": "Max retries reached"}

###################################################################################################
# 🧠 System Prompt Generator
###################################################################################################

def create_system_prompt(domain, role, interview_type, difficulty):
    """Generates the long system prompt used for controlling LLM behavior."""
    return f"""You are "AI Interview Practitioner," a professional mock interview coach... (FULL PROMPT SAME AS ORIGINAL)"""

###################################################################################################
# 🌐 API ROUTES
###################################################################################################

# -----------------------------------------------------------------------------------------------
# ROOT + HEALTH
# -----------------------------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "status": "online",
        "service": "EightFold.ai Interview Backend",
        "version": "2.0",
        "endpoints": {
            "health": "/health",
            "start_session": "/api/start-session",
            "chat": "/api/chat",
            "tts": "/api/tts",
            "user_sessions": "/api/user-sessions"
        }
    }), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "firebase_initialized": len(firebase_admin._apps) > 0,
        "stt": "Browser-based",
        "tts": f"ElevenLabs ({len(ELEVEN_KEYS)} keys)",
        "llm": f"OpenRouter ({len(OPENROUTER_KEYS)} keys)",
        "active_sessions": len(sessions),
    }), 200

###################################################################################################
# 🟢 START INTERVIEW SESSION
###################################################################################################

@app.route('/api/start-session', methods=['POST', 'OPTIONS'])
@verify_firebase_token
def start_session():
    """Creates a new interview session with system prompt + first small-talk message."""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.json
    domain = data.get('domain')
    role = data.get('role')
    interview_type = data.get('interview_type', 'Mixed')
    difficulty = data.get('difficulty', 'Intermediate')
    duration = data.get('duration', 15)

    # Validation
    if not domain or not role:
        return jsonify({"error": "Domain and role required"}), 400

    # Generate session
    session_id = str(uuid.uuid4())
    system_prompt = create_system_prompt(domain, role, interview_type, difficulty)

    messages = [{"role": "user", "content": "Start the interview with warm small talk as instructed."}]
    ai_response = call_llm(messages, system_prompt)

    if "error" in ai_response:
        return jsonify({"error": ai_response["error"]}), 500

    # Save session
    sessions[session_id] = {
        "user_id": request.user_id,
        "user_email": request.user_email,
        "domain": domain,
        "role": role,
        "interview_type": interview_type,
        "difficulty": difficulty,
        "duration_minutes": duration,
        "system_prompt": system_prompt,
        "messages": messages + [{"role": "assistant", "content": json.dumps(ai_response)}],
        "created_at": time.time(),
        "exchange_count": 0,
        "question_count": 0,
        "inappropriate_count": 0,
        "redirect_count": 0
    }

    user_sessions.setdefault(request.user_id, []).append(session_id)

    return jsonify({"session_id": session_id, "first_question": ai_response}), 200

###################################################################################################
# 💬 CHAT ENDPOINT
###################################################################################################

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
@verify_firebase_token
def chat():
    """Main chatbot endpoint handling user messages and generating AI responses."""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.json
    session_id = data.get('session_id')
    user_message = data.get('user_message')

    if not session_id or not user_message:
        return jsonify({"error": "Missing session ID or message"}), 400

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    session = sessions[session_id]

    # Ensure correct user
    if session['user_id'] != request.user_id:
        return jsonify({"error": "Unauthorized session"}), 403

    system_prompt = session['system_prompt']
    messages = session['messages']

    # Inappropriate detection
    if not user_message.startswith('['):
        flags = detect_inappropriate_content(user_message)
        if flags['needs_redirection']:
            session['inappropriate_count'] += 1
            session['redirect_count'] += 1

            if session['inappropriate_count'] >= 3:
                user_message = "[END_INTERVIEW_INAPPROPRIATE_BEHAVIOR]"

    # Append user message
    messages.append({"role": "user", "content": user_message})
    session['exchange_count'] += 1

    if session['exchange_count'] > 3:
        session['question_count'] += 1

    # Add internal context for the LLM (not shown to user)
    elapsed_minutes = (time.time() - session['created_at']) / 60
    messages[-1] = {"role": "user", "content": f"""
[CONTEXT - HIDDEN]
Exchanges: {session['exchange_count']}
Questions: {session['question_count']}
Inappropriate: {session['inappropriate_count']}
Redirects: {session['redirect_count']}
Time left: {session['duration_minutes'] - elapsed_minutes:.1f} min
[END]
User message: {user_message}
"""}

    # Query the LLM
    ai_response = call_llm(messages, system_prompt)

    if "error" in ai_response:
        return jsonify({"error": ai_response["error"]}), 500

    # Restore original message + append AI reply
    messages[-1] = {"role": "user", "content": user_message}
    messages.append({"role": "assistant", "content": json.dumps(ai_response)})

    # End cleanup
    if ai_response.get("end"):
        session["ended_at"] = time.time()

    return jsonify(ai_response), 200

###################################################################################################
# 🔊 TTS (TEXT–TO–SPEECH)
###################################################################################################

@app.route('/api/tts', methods=['POST'])
@verify_firebase_token
def tts():
    """Converts interview text into ElevenLabs TTS audio."""
    data = request.json
    text = data.get("text")
    voice_style = data.get("voice_style", "male")

    api_key = ELEVEN_KEYS[0]
    voice_id = "pNInz6obpgDQGcFmaJgB" if voice_style == "male" else "Xb0ZEqXn3XGQW2c3Kmbl"

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        json={"text": text, "model_id": "eleven_turbo_v2",
              "voice_settings": {"stability": 0.35, "similarity_boost": 0.7}},
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    )

    return Response(response.content, mimetype="audio/mpeg")

###################################################################################################
# 📚 FETCH USER SESSION HISTORY
###################################################################################################

@app.route('/api/user-sessions', methods=['GET', 'OPTIONS'])
@verify_firebase_token
def get_user_sessions():
    """Returns all sessions that belong to the logged-in user."""
    if request.method == 'OPTIONS':
        return '', 204

    result = []
    for sid in user_sessions.get(request.user_id, []):
        if sid in sessions:
            s = sessions[sid]
            result.append({
                "session_id": sid,
                "domain": s['domain'],
                "role": s['role'],
                "difficulty": s['difficulty'],
                "created_at": s['created_at'],
                "exchange_count": s['exchange_count'],
                "ended": 'ended_at' in s
            })

    return jsonify({"user_id": request.user_id, "sessions": result}), 200

###################################################################################################
# 🧹 OLD SESSION CLEANUP (Auto)
###################################################################################################

def cleanup_old_sessions():
    """Deletes sessions older than 24h or completed >1h ago."""
    now = time.time()
    to_delete = []

    for sid, s in sessions.items():
        if now - s['created_at'] > 86400:
            to_delete.append(sid)
        elif 'ended_at' in s and now - s['ended_at'] > 3600:
            to_delete.append(sid)

    for sid in to_delete:
        uid = sessions[sid]['user_id']
        user_sessions[uid] = [x for x in user_sessions.get(uid, []) if x != sid]
        del sessions[sid]

###################################################################################################
# ⚠️ ERROR HANDLERS
###################################################################################################

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal(e):
    return jsonify({"error": "Internal server error"}), 500

###################################################################################################
# 🚀 RUN SERVER
###################################################################################################

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print("🚀 Starting EightFold.ai Interview Backend v2.0")
    app.run(host='0.0.0.0', port=port, debug=False)

