import os
import logging
import base64
import re
import mimetypes
import io
import json
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
import httpx

# Clean, simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WAHA-BRIDGE] - %(levelname)s - %(message)s')
logger = logging.getLogger("WAHA-BRIDGE")

load_dotenv()

app = FastAPI(title="WhatsApp Media & Dynamic Admin Bridge")

# --- Configuration ---
# MASTER_CEO is the permanent admin number from .env
MASTER_CEO = os.getenv("MASTER_CEO", "").strip().replace("+", "")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Shared Storage Paths
DATA_DIR = "/opt/data"
MEDIA_DIR = os.path.join(DATA_DIR, "media")
TRUSTED_DB_PATH = os.path.join(DATA_DIR, "trusted_numbers.json")

os.makedirs(MEDIA_DIR, exist_ok=True)

# In-memory deduplication
processed_message_ids = set()

# --- Dynamic Trust Management ---
def load_trusted_numbers():
    """Loads trusted numbers from environment and JSON file."""
    trusted = {MASTER_CEO} if MASTER_CEO else set()
    
    # Load from TRUSTED_NUMBERS env var (comma-separated)
    env_trusted = os.getenv("TRUSTED_NUMBERS", "")
    if env_trusted:
        for num in env_trusted.split(","):
            clean_num = num.strip().replace("+", "")
            if clean_num:
                trusted.add(clean_num)

    if os.path.exists(TRUSTED_DB_PATH):
        try:
            with open(TRUSTED_DB_PATH, "r") as f:
                data = json.load(f)
                trusted.update(data)
        except Exception as e:
            logger.error(f"Error loading trusted DB: {e}")
    return {n for n in trusted if n} # Remove empty strings

def save_trusted_numbers(numbers):
    """Saves trusted numbers to JSON file."""
    try:
        # Don't save the MASTER_CEO to the JSON to keep it clean (it's always in .env)
        to_save = list(set(numbers) - {MASTER_CEO})
        with open(TRUSTED_DB_PATH, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        logger.error(f"Error saving trusted DB: {e}")

# Initial load
TRUSTED_LIST = load_trusted_numbers()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    global TRUSTED_LIST
    try:
        data = await request.json()
        if data.get("event") != "message":
            return {"status": "ignored_non_message_event"}

        payload = data.get("payload", {})
        if payload.get("fromMe") is True:
            return {"status": "ignored_self_message"}

        msg_id = payload.get("id")
        if msg_id:
            if len(processed_message_ids) > 1000:
                processed_message_ids.clear()
            if msg_id in processed_message_ids:
                return {"status": "ignored_duplicate"}
            processed_message_ids.add(msg_id)

        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        body = payload.get("body", "").strip()

        # --- ADMIN COMMAND LOGIC ---
        if from_number == MASTER_CEO and body.startswith("/"):
            logger.info(f"Admin command from CEO: {body}")
            if body.startswith("/add "):
                new_num = body.replace("/add ", "").strip().replace("+", "")
                TRUSTED_LIST.add(new_num)
                save_trusted_numbers(TRUSTED_LIST)
                background_tasks.add_task(send_to_whatsapp_simple, from_chat, f"✅ Added {new_num} to trusted list.")
                return {"status": "admin_command_executed"}
            
            elif body.startswith("/remove "):
                rem_num = body.replace("/remove ", "").strip().replace("+", "")
                if rem_num == MASTER_CEO:
                    background_tasks.add_task(send_to_whatsapp_simple, from_chat, "❌ Cannot remove the Master CEO.")
                else:
                    TRUSTED_LIST.discard(rem_num)
                    save_trusted_numbers(TRUSTED_LIST)
                    background_tasks.add_task(send_to_whatsapp_simple, from_chat, f"🗑️ Removed {rem_num} from trusted list.")
                return {"status": "admin_command_executed"}
            
            elif body == "/list":
                msg = "📋 *Trusted Numbers:*\n" + "\n".join([f"- {n}" for n in sorted(TRUSTED_LIST)])
                background_tasks.add_task(send_to_whatsapp_simple, from_chat, msg)
                return {"status": "admin_command_executed"}

        # --- REGULAR MESSAGE LOGIC ---
        if from_number not in TRUSTED_LIST:
            logger.warning(f"SECURITY: Blocked untrusted number {from_number}")
            return {"status": "unauthorized"}

        has_media = payload.get("hasMedia", False)
        media_info = payload.get("media") if has_media else None
        msg_type = payload.get("type", "chat")
        is_voice = msg_type in ["ptt", "audio"]

        background_tasks.add_task(process_and_reply, from_chat, body, media_info, is_voice)
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def download_media(media_url: str):
    async with httpx.AsyncClient() as client:
        headers = {"X-Api-Key": WAHA_API_KEY} if WAHA_API_KEY else {}
        res = await client.get(media_url, headers=headers)
        return res.content if res.status_code == 200 else None

async def transcribe_audio(audio_data: bytes, mimetype: str):
    if not OPENAI_API_KEY: return "[Voice transcription disabled]"
    try:
        ext = mimetypes.guess_extension(mimetype) or ".ogg"
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
                files={'file': (f"voice{ext}", io.BytesIO(audio_data), mimetype)},
                data={'model': 'whisper-1'},
                timeout=60.0
            )
            return res.json().get("text", "") if res.status_code == 200 else "[Transcription error]"
    except Exception: return "[Voice processing error]"

async def process_and_reply(chat_id: str, user_message: str, media_info: dict = None, is_voice: bool = False):
    try:
        async with httpx.AsyncClient() as client:
            content = []
            if media_info:
                media_url = media_info.get("url").replace("localhost:3000", "waha:3000")
                mimetype = media_info.get("mimetype", "")
                media_data = await download_media(media_url)
                if media_data:
                    if is_voice:
                        transcription = await transcribe_audio(media_data, mimetype)
                        user_message = f"{user_message} {transcription}".strip()
                    elif mimetype.startswith("image/"):
                        content.append({"type": "image_url", "image_url": {"url": f"data:{mimetype};base64,{base64.b64encode(media_data).decode('utf-8')}"}})
                    else:
                        filename = media_info.get("filename") or f"incoming_{int(client._transport._pool.time())}"
                        file_path = os.path.join(MEDIA_DIR, filename)
                        with open(file_path, "wb") as f: f.write(media_data)
                        user_message = f"{user_message}\n[Document available at: {file_path}]".strip()

            if user_message: content.append({"type": "text", "text": user_message})

            h_res = await client.post(HERMES_API_URL, headers={"Authorization": f"Bearer {HERMES_API_KEY}"}, json={"model": "hermes-agent", "messages": [{"role": "user", "content": content}], "stream": False}, timeout=150.0)
            reply_text = h_res.json().get("choices", [{}])[0].get("message", {}).get("content", "") if h_res.status_code == 200 else "⚠️ AI Error."

            file_paths = re.findall(r'(/opt/data/[^\s,]+\.[a-zA-Z0-9]+)', reply_text)
            await send_to_whatsapp_full(client, chat_id, "text", {"text": reply_text})
            for path in file_paths:
                if os.path.exists(path):
                    mime, _ = mimetypes.guess_type(path)
                    m_type = "image" if mime and mime.startswith("image/") else "document"
                    await send_to_whatsapp_full(client, chat_id, m_type, {"path": path, "filename": os.path.basename(path)})
    except Exception as e: logger.error(f"Processing Crash: {e}")

async def send_to_whatsapp_simple(chat_id: str, text: str):
    async with httpx.AsyncClient() as client:
        await send_to_whatsapp_full(client, chat_id, "text", {"text": text})

async def send_to_whatsapp_full(client, chat_id: str, msg_type: str, data: dict):
    try:
        url = f"{WAHA_API_URL}/api/sendText"
        payload = {"chatId": chat_id, "session": "default"}
        if msg_type == "text": payload["text"] = data["text"]
        else:
            url = f"{WAHA_API_URL}/api/sendImage" if msg_type == "image" else f"{WAHA_API_URL}/api/sendDocument"
            with open(data["path"], "rb") as f:
                payload["file"] = f"data:{mimetypes.guess_type(data['path'])[0]};base64," + base64.b64encode(f.read()).decode('utf-8')
                if msg_type == "document": payload["filename"] = data.get("filename", "document")
        
        headers = {"Content-Type": "application/json"}
        if WAHA_API_KEY: headers["X-Api-Key"] = WAHA_API_KEY
        await client.post(url, json=payload, headers=headers)
    except Exception as e: logger.error(f"WhatsApp Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
