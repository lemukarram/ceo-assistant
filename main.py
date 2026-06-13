import os
import logging
import base64
import re
import mimetypes
import io
import json
import time
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import httpx

# Clean, simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [EVO-BRIDGE] - %(levelname)s - %(message)s')
logger = logging.getLogger("EVO-BRIDGE")

load_dotenv()

app = FastAPI(title="WhatsApp Media & Dynamic Admin Bridge (Evolution API)")

# --- Configuration ---
MASTER_CEO = os.getenv("MASTER_CEO", "").strip().replace("+", "")
EVO_API_URL = os.getenv("EVOLUTION_API_URL", "http://evolution-api:8080").rstrip("/")
EVO_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME", "loops")
BASE_URL = os.getenv("BASE_URL", "http://evolution-bridge:8000").rstrip("/")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Shared Storage Paths
DATA_DIR = "/opt/data"
MEDIA_DIR = os.path.join(DATA_DIR, "media")
TRUSTED_DB_PATH = os.path.join(DATA_DIR, "trusted_numbers.json")

os.makedirs(MEDIA_DIR, exist_ok=True)
for d in [DATA_DIR, MEDIA_DIR]:
    try:
        os.chmod(d, 0o777)
    except Exception as e:
        logger.warning(f"Could not set world-writable permissions on {d}: {e}")

# Mount the media directory so Evolution API can fetch files via a clear public URL
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# In-memory deduplication
processed_message_ids = set()

# In-memory conversational context (chat_id -> list of messages)
chat_history = {}

# --- Dynamic Trust Management ---
def load_trusted_numbers():
    trusted = {MASTER_CEO} if MASTER_CEO else set()
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
    return {n for n in trusted if n}

def save_trusted_numbers(numbers):
    try:
        to_save = list(set(numbers) - {MASTER_CEO})
        with open(TRUSTED_DB_PATH, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        logger.error(f"Error saving trusted DB: {e}")

TRUSTED_LIST = load_trusted_numbers()

def is_trusted(remote_jid: str):
    # remote_jid format: 5511999999999@s.whatsapp.net
    number = remote_jid.split("@")[0]
    return number in TRUSTED_LIST

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    global TRUSTED_LIST
    try:
        payload = await request.json()
        
        # Evolution API event check
        if payload.get("event") not in ["messages.upsert", "MESSAGES_UPSERT"]:
            return {"status": "ignored_non_message_event"}

        instance_name = payload.get("instance", EVO_INSTANCE)

        data = payload.get("data", {})
        key = data.get("key", {})
        if key.get("fromMe") is True:
            return {"status": "ignored_self_message"}

        msg_id = key.get("id")
        if msg_id:
            if len(processed_message_ids) > 1000:
                processed_message_ids.clear()
            if msg_id in processed_message_ids:
                return {"status": "ignored_duplicate"}
            processed_message_ids.add(msg_id)

        remote_jid = key.get("remoteJid", "")
        from_number = remote_jid.split("@")[0]
        
        message = data.get("message", {})
        body = message.get("conversation") or message.get("extendedTextMessage", {}).get("text") or ""
        body = body.strip()

        logger.info(f"INCOMING WHATSAPP MESSAGE FROM {from_number} (Instance: {instance_name}): {body}")

        # --- ADMIN COMMAND LOGIC ---
        if from_number == MASTER_CEO and body.startswith("/"):
            logger.info(f"Admin command from CEO: {body}")
            if body.startswith("/add "):
                raw_num = body.replace("/add ", "").strip().replace("+", "")
                TRUSTED_LIST.add(raw_num)
                save_trusted_numbers(TRUSTED_LIST)
                
                background_tasks.add_task(send_to_whatsapp_simple, remote_jid, f"✅ Added {raw_num} to trusted list.", instance_name)
                
                new_user_jid = f"{raw_num}@s.whatsapp.net"
                greeting_msg = "Hello! You have been granted access to LOOPS CA. How can I assist you today?"
                background_tasks.add_task(send_to_whatsapp_simple, new_user_jid, greeting_msg, instance_name)
                
                return {"status": "admin_command_executed"}
            
            elif body.startswith("/remove "):
                rem_num = body.replace("/remove ", "").strip().replace("+", "")
                if rem_num == MASTER_CEO:
                    background_tasks.add_task(send_to_whatsapp_simple, remote_jid, "❌ Cannot remove the Master CEO.", instance_name)
                else:
                    TRUSTED_LIST.discard(rem_num)
                    save_trusted_numbers(TRUSTED_LIST)
                    background_tasks.add_task(send_to_whatsapp_simple, remote_jid, f"🗑️ Removed {rem_num} from trusted list.", instance_name)
                return {"status": "admin_command_executed"}
            
            elif body == "/list":
                msg = "📋 *Trusted Numbers:*\n" + "\n".join([f"- {n}" for n in sorted(TRUSTED_LIST)])
                background_tasks.add_task(send_to_whatsapp_simple, remote_jid, msg, instance_name)
                return {"status": "admin_command_executed"}

        # --- REGULAR MESSAGE LOGIC ---
        if not is_trusted(remote_jid):
            logger.warning(f"SECURITY: Blocked untrusted number {from_number}")
            return {"status": "unauthorized"}

        # Media handling directly from Evolution Payload
        base64_data = data.get("base64")
        msg_type = data.get("messageType", "")
        
        media_obj = None
        is_voice = False
        if msg_type in ["imageMessage", "documentMessage", "audioMessage", "videoMessage"]:
            media_obj = message.get(msg_type)
            if msg_type == "audioMessage":
                is_voice = True

        background_tasks.add_task(process_and_reply, remote_jid, body, media_obj, base64_data, is_voice, instance_name)
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def transcribe_audio(audio_data: bytes, mimetype: str):
    if not OPENAI_API_KEY: return "[Voice transcription disabled]"
    try:
        ext = mimetypes.guess_extension(mimetype.split(";")[0]) or ".ogg"
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

async def process_and_reply(chat_id: str, user_message: str, media_obj: dict = None, base64_data: str = None, is_voice: bool = False, instance_name: str = EVO_INSTANCE):
    try:
        async with httpx.AsyncClient() as client:
            content = []
            if media_obj and base64_data:
                mimetype = media_obj.get("mimetype", "application/octet-stream")
                # Handle base64 stripping if Evolution sends data URI scheme
                if "," in base64_data:
                    base64_data = base64_data.split(",")[1]
                
                media_bytes = base64.b64decode(base64_data)
                
                ext = mimetypes.guess_extension(mimetype.split(";")[0]) or ".bin"
                filename = media_obj.get("fileName") or media_obj.get("title") or f"incoming_{int(time.time())}{ext}"
                file_path = os.path.join(MEDIA_DIR, filename)
                
                with open(file_path, "wb") as f:
                    f.write(media_bytes)

                if is_voice:
                    transcription = await transcribe_audio(media_bytes, mimetype)
                    user_message = f"{user_message} {transcription}".strip()
                elif mimetype.startswith("image/"):
                    content.append({"type": "image_url", "image_url": {"url": f"data:{mimetype};base64,{base64_data}"}})
                    user_message = f"{user_message}\n[System Note: Image also saved locally at {file_path} for script/tool processing]".strip()
                else:
                    user_message = f"{user_message}\n[System Note: Document saved locally at {file_path}]".strip()

            if user_message: content.append({"type": "text", "text": user_message})

            # Retrieve and update conversation history
            if chat_id not in chat_history:
                chat_history[chat_id] = []
            
            chat_history[chat_id].append({"role": "user", "content": content})
            if len(chat_history[chat_id]) > 3:
                chat_history[chat_id] = chat_history[chat_id][-3:]

            h_res = await client.post(HERMES_API_URL, headers={"Authorization": f"Bearer {HERMES_API_KEY}"}, json={"model": "hermes-agent", "messages": chat_history[chat_id], "stream": False}, timeout=150.0)
            reply_text = h_res.json().get("choices", [{}])[0].get("message", {}).get("content", "") if h_res.status_code == 200 else "⚠️ AI Error."

            logger.info(f"RAW HERMES REPLY: {reply_text}")

            if h_res.status_code == 200 and reply_text:
                chat_history[chat_id].append({"role": "assistant", "content": reply_text})

            media_to_send = []
            def extract_media_tags(match):
                media_to_send.append(match.group(1).strip())
                return ""
            
            # 1. Handle explicit <send_media> tags
            clean_reply = re.sub(r'<send_media>(.*?)</send_media>', extract_media_tags, reply_text, flags=re.IGNORECASE)
            
            # 2. Handle raw file paths in text (auto-detect /opt/data/...)
            # We copy them to a list and also strip them from the clean_reply to avoid cluttering the chat
            raw_paths = re.findall(r'(/opt/data/[a-zA-Z0-9_./-]+)', clean_reply)
            for path in raw_paths:
                if path not in media_to_send:
                    media_to_send.append(path)
                # Remove the path from the text message so the CEO sees a clean reply
                clean_reply = clean_reply.replace(path, "").strip()
            
            # 3. Handle markdown images (already handled but ensuring it's stripped)
            clean_reply = re.sub(r'!\[.*?\]\((/opt/data/.*?)\)', '', clean_reply).strip()

            # 4. Process and send all detected media
            public_urls = []
            for path in media_to_send:
                if os.path.exists(path) and os.path.isfile(path):
                    url = await send_to_whatsapp_media(chat_id, path, instance_name)
                    if url:
                        public_urls.append(url)
                else:
                    logger.warning(f"Agent attempted to send missing file: {path}")

            # 5. Append public URLs to the clean reply for easy access
            if public_urls:
                links_text = "\n\n🔗 *Public Access Links:*\n" + "\n".join([f"- {u}" for u in public_urls])
                clean_reply += links_text

            if clean_reply:
                await send_to_whatsapp_simple(chat_id, clean_reply, instance_name)

    except Exception as e: logger.error(f"Processing Crash: {e}")

async def send_to_whatsapp_simple(chat_id: str, text: str, instance_name: str = EVO_INSTANCE):
    try:
        async with httpx.AsyncClient() as client:
            url = f"{EVO_API_URL}/message/sendText/{instance_name}"
            payload = {
                "number": chat_id,
                "text": text
            }
            headers = {"Content-Type": "application/json"}
            if EVO_API_KEY: headers["apikey"] = EVO_API_KEY
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code >= 400:
                logger.error(f"EVO API Text Error ({res.status_code}): {res.text}")
    except Exception as e: logger.error(f"WhatsApp Text Error: {e}")

import shutil

async def send_to_whatsapp_media(chat_id: str, file_path: str, instance_name: str = EVO_INSTANCE):
    try:
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        filename = os.path.basename(file_path)
        
        media_type = "document"
        if mime_type.startswith("image/"): media_type = "image"
        elif mime_type.startswith("video/"): media_type = "video"
        elif mime_type.startswith("audio/"): media_type = "audio"

        # Securely expose only the specific file by copying it to the media directory
        public_file_path = os.path.join(MEDIA_DIR, filename)
        if os.path.abspath(file_path) != os.path.abspath(public_file_path):
            shutil.copy2(file_path, public_file_path)
            
        # Ensure the file is world-readable for the Evolution API to fetch
        try:
            os.chmod(public_file_path, 0o644)
        except:
            pass

        # Generate the clear public URL
        # Evolution API downloads this and natively uploads it to WhatsApp's servers.
        media_url = f"{BASE_URL}/media/{filename}"

        async with httpx.AsyncClient() as client:
            url = f"{EVO_API_URL}/message/sendMedia/{instance_name}"
            payload = {
                "number": chat_id,
                "mediatype": media_type,
                "mimetype": mime_type,
                "fileName": filename,
                "media": media_url
            }
            headers = {"Content-Type": "application/json"}
            if EVO_API_KEY: headers["apikey"] = EVO_API_KEY
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code >= 400:
                logger.error(f"EVO API Media Error ({res.status_code}): {res.text}")
                return None
            return media_url
    except Exception as e: 
        logger.error(f"WhatsApp Media Error: {e}")
        return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
