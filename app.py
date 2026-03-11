from flask import Flask, request, render_template, send_file, jsonify
import requests
import io
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# File to store email history
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_history.json')

# Language mapping - focus on Indian languages + major world languages
language_names = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "pa": "Punjabi",
    "es": "Spanish", 
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese"
}

def load_history():
    """Load email history from JSON file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    """Save email history to JSON file"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def add_to_history(email_type, subject, content, metadata):
    """Add an email to history"""
    history = load_history()
    entry = {
        "id": len(history) + 1,
        "type": email_type,  # "generated" or "smart_reply"
        "subject": subject,
        "content": content,
        "metadata": metadata,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history.insert(0, entry)  # Add to beginning
    save_history(history)
    return entry["id"]

def delete_from_history(email_id):
    """Delete an email from history"""
    history = load_history()
    history = [e for e in history if e["id"] != email_id]
    save_history(history)

def call_ollama(prompt, model="llama3.2"):
    """Call Ollama API and return the response"""
    try:
        url = "http://localhost:11434/api/chat"
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        response = requests.post(url, json=data, timeout=120)
        if response.status_code == 200:
            result = response.json()
            if 'message' in result and result['message'].get('content'):
                return result['message']['content'].strip()
    except Exception as e:
        print(f"Ollama error: {e}")
    
    # Try mistral if llama3.2 fails
    try:
        url = "http://localhost:11434/api/chat"
        data = {
            "model": "mistral",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        response = requests.post(url, json=data, timeout=120)
        if response.status_code == 200:
            result = response.json()
            if 'message' in result and result['message'].get('content'):
                return result['message']['content'].strip()
    except:
        pass
    
    return None

def extract_subject(content):
    """Extract subject line from email content"""
    lines = content.split('\n')
    for line in lines:
        if line.startswith('Subject:'):
            return line.replace('Subject:', '').strip()
        elif line.strip() and not line.startswith('---'):
            return line[:50] + "..."
    return "No Subject"

def generate_email(receiver, topic, tone, length, language, input_language):
    """AI-powered email generator using Ollama local AI"""
    
    output_lang_name = language_names.get(language, "English")
    input_lang_name = language_names.get(input_language, "English")
    
    # If input language is not English, translate the topic to English first
    final_topic = topic
    if input_language != "en":
        translate_prompt = f"""Translate the following text from {input_lang_name} to English. 
Only output the translated text, nothing else:

{topic}"""
        
        translated = call_ollama(translate_prompt)
        if translated:
            final_topic = translated
    
    # Auto-detect tone if not provided
    if tone is None or tone == "":
        topic_lower = final_topic.lower()
        if any(word in topic_lower for word in ['apolog', 'sorry', 'mistake', 'error', 'regret']):
            tone = "apology"
        elif any(word in topic_lower for word in ['friend', 'casual', 'informal', 'hey', 'what\'s up', 'great', 'awesome']):
            tone = "friendly"
        elif any(word in topic_lower for word in ['business', 'professional', 'client', 'meeting', 'project', 'report', 'work']):
            tone = "professional"
        else:
            tone = "formal"
    
    # Auto-detect length if not provided
    if length is None or length == "":
        topic_lower = final_topic.lower()
        if any(word in topic_lower for word in ['quick', 'brief', 'short', 'simple', 'just', 'little']):
            length = "short"
        elif any(word in topic_lower for word in ['detailed', 'comprehensive', 'thorough', 'extensive', 'full', 'long']):
            length = "long"
        else:
            length = "medium"
    
    # Build prompt for AI
    length_guide = {
        "short": "Keep it very brief - just 2-3 sentences.",
        "medium": "Write a proper email with 2-3 paragraphs.",
        "long": "Write a detailed, comprehensive email with multiple well-developed paragraphs."
    }
    
    prompt = f"""Write a {tone} email addressed to {receiver} in {output_lang_name} language.

Topic/Purpose: {final_topic}
Length: {length_guide[length]}

The email should:
- Start with an appropriate greeting
- Include a clear subject line at the top
- Sound natural, human-written, and conversational
- Be relevant and meaningful to the topic
- End with a professional closing
- Write entirely in {output_lang_name}

Write the email with the subject line first, then the email body. Format: "Subject: [subject]" on first line, then the email content."""
    
    result = call_ollama(prompt)
    if result:
        return result
    
    return "AI service unavailable. Please make sure Ollama is running with: ollama run llama3.2"

def generate_smart_reply(received_email, tone, length, language):
    """AI-powered smart reply generator using Ollama local AI"""
    
    output_lang_name = language_names.get(language, "English")
    
    # Auto-detect tone if not provided
    if tone is None or tone == "":
        email_lower = received_email.lower()
        if any(word in email_lower for word in ['thank', 'thanks', 'appreciate', 'grateful']):
            tone = "appreciative"
        elif any(word in email_lower for word in ['sorry', 'apologize', 'mistake', 'error']):
            tone = "apologetic"
        elif any(word in email_lower for word in ['meeting', 'project', 'business', 'proposal', 'contract']):
            tone = "professional"
        elif any(word in email_lower for word in ['friend', 'casual', 'hey', 'what\'s up', 'great', 'awesome']):
            tone = "friendly"
        else:
            tone = "formal"
    
    # Auto-detect length if not provided
    if length is None or length == "":
        email_len = len(received_email)
        if email_len < 100:
            length = "short"
        elif email_len > 500:
            length = "long"
        else:
            length = "medium"
    
    # Build prompt for AI
    length_guide = {
        "short": "Keep it very brief - just 2-3 sentences.",
        "medium": "Write a proper reply with 2-3 paragraphs.",
        "long": "Write a detailed, comprehensive reply with multiple well-developed paragraphs."
    }
    
    prompt = f"""You are writing a smart reply to an email. 

Original Email received:
---
{received_email}
---

Write a {tone} reply in {output_lang_name} language.
Length: {length_guide[length]}

The reply should:
- Be directly relevant to the received email
- Reference key points from the original email appropriately
- Start with an appropriate greeting (acknowledge the sender)
- Include a clear subject line at the top (Re: related to original subject)
- Sound natural, human-written, and conversational
- End with a professional closing
- Write entirely in {output_lang_name}

Format: "Subject: [subject]" on first line, then the email body."""
    
    result = call_ollama(prompt)
    if result:
        return result
    
    return "AI service unavailable. Please make sure Ollama is running with: ollama run llama3.2"

@app.route("/", methods=["GET", "POST"])
def home():
    email = ""
    smart_reply = ""
    active_tab = "generate"
    history = []
    
    if request.method == "POST":
        # Check which form was submitted
        if 'received_email' in request.form:
            # Smart Reply form
            active_tab = "smart-reply"
            received_email = request.form.get("received_email", "")
            tone = request.form.get("tone", "") or None
            length = request.form.get("length", "") or None
            language = request.form.get("language", "en") or "en"
            
            smart_reply = generate_smart_reply(received_email, tone, length, language)
        elif 'save_email' in request.form:
            # Save email to history
            email_type = request.form.get("email_type", "generated")
            subject = request.form.get("email_subject", "")
            content = request.form.get("email_content", "")
            metadata_json = request.form.get("email_metadata", "{}")
            try:
                metadata = json.loads(metadata_json)
            except:
                metadata = {}
            
            add_to_history(email_type, subject, content, metadata)
            
            # Determine which tab to show
            active_tab = request.form.get("active_tab", "generate")
            if active_tab == "smart-reply":
                smart_reply = content
            else:
                email = content
        else:
            # Email Generator form
            active_tab = "generate"
            receiver = request.form.get("receiver", "")
            topic = request.form.get("topic", "")
            tone = request.form.get("tone", "") or None
            length = request.form.get("length", "") or None
            language = request.form.get("language", "en") or "en"
            input_language = request.form.get("input_language", "en") or "en"
            
            email = generate_email(receiver, topic, tone, length, language, input_language)
    
    return render_template("index.html", email=email, smart_reply=smart_reply, active_tab=active_tab, history=load_history())

@app.route("/history")
def get_history():
    """Get all saved emails"""
    return jsonify(load_history())

@app.route("/delete-email", methods=["POST"])
def delete_email():
    """Delete an email from history"""
    email_id = request.form.get("email_id")
    try:
        delete_from_history(int(email_id))
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    email_content = request.form.get("email_content", "")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Add title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Generated Email")
    
    # Add email content
    c.setFont("Helvetica", 12)
    y = height - 100
    
    # Wrap text and draw line by line
    lines = email_content.split('\n')
    for line in lines:
        if y < 50:  # New page if needed
            c.showPage()
            c.setFont("Helvetica", 12)
            y = height - 50
        c.drawString(50, y, line[:80])  # Limit line width
        y -= 20
    
    c.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name="email.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True, port=5000)

