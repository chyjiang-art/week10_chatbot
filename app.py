import streamlit as st
import requests
import json
import os
import time
from datetime import datetime

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "meta-llama/Llama-3.2-1B-Instruct"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chats")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
ALLOWED_MEMORY_KEYS = {"name", "preferred_language", "likes"}
INVALID_NAME_VALUES = {"you", "me", "i", "my", "myself", "we", "us", "them", "he", "she", "it", "they", "them"}
INVALID_GENERIC_VALUES = {"you", "me", "i", "we", "us", "they", "them"}
KNOWN_LANGUAGES = {
    "english",
    "chinese",
    "mandarin",
    "spanish",
    "french",
    "german",
    "italian",
    "japanese",
    "korean",
    "russian",
    "arabic",
    "portuguese",
    "hindi",
    "bengali",
    "urdu",
    "punjabi",
    "dutch",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
    "polish",
    "greek",
    "thai",
    "vietnamese",
    "turkish",
}


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_next_chat_id(chats):
    if not chats:
        return 1

    max_id = 0
    for chat in chats:
        try:
            chat_id = int(chat.get("id", 0))
            max_id = max(max_id, chat_id)
        except Exception:
            pass
    return max_id + 1


def chat_file_path(chat_id):
    return os.path.join(CHAT_DIR, "chat_" + str(chat_id) + ".json")


def create_empty_chat(chat_id):
    return {
        "id": chat_id,
        "title": "Chat " + str(chat_id),
        "updated": now_string(),
        "messages": [],
    }


def load_chat_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None

        chat_id = data.get("id")
        if not isinstance(chat_id, int):
            return None

        if not isinstance(data.get("title"), str) or not data.get("title"):
            data["title"] = "Chat " + str(chat_id)

        if not isinstance(data.get("updated"), str) or not data.get("updated"):
            data["updated"] = now_string()

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        data["messages"] = messages
        return data
    except Exception:
        return None


def load_chats_from_disk():
    if not os.path.exists(CHAT_DIR):
        os.makedirs(CHAT_DIR)

    chats = []
    try:
        files = sorted(os.listdir(CHAT_DIR))
    except Exception:
        files = []

    for name in files:
        if not name.endswith(".json"):
            continue
        path = os.path.join(CHAT_DIR, name)
        chat = load_chat_file(path)
        if chat is not None:
            chats.append(chat)

    chats.sort(key=lambda c: c.get("updated", ""), reverse=True)
    return chats


def save_chat_to_disk(chat):
    if not os.path.exists(CHAT_DIR):
        os.makedirs(CHAT_DIR)

    try:
        path = chat_file_path(chat.get("id"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chat, f, ensure_ascii=True, indent=2)
        return True
    except Exception:
        return False


def delete_chat_file(chat_id):
    path = chat_file_path(chat_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def get_active_chat():
    active_id = st.session_state.get("active_chat_id")
    for chat in st.session_state.chats:
        if chat["id"] == active_id:
            return chat
    return None


def compact_time(updated):
    try:
        dt = datetime.strptime(updated, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M")
    except Exception:
        if isinstance(updated, str) and len(updated) >= 5:
            return updated[-5:]
        return str(updated)


def safe_parse_json(text_value):
    if not isinstance(text_value, str):
        return {}

    text_value = text_value.strip()
    if not text_value:
        return {}

    try:
        data = json.loads(text_value)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = text_value.find("{")
    end = text_value.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        data = json.loads(text_value[start:end + 1])
        if isinstance(data, dict):
            return data
    except Exception:
        return {}

    return {}


def extract_language_from_message(message):
    if not isinstance(message, str):
        return ""

    msg = message.lower()
    msg = msg.replace("!", " ").replace("?", " ").replace(".", " ").replace(",", " ").replace(";", " ")
    phrases = [
        "my preferred language is",
        "my preferred language",
        "preferred language is",
        "i prefer ",
        "i'd prefer ",
        "prefer to speak",
        "please speak",
        "speak ",
    ]

    for phrase in phrases:
        pos = msg.find(phrase)
        if pos == -1:
            continue

        rest = msg[pos + len(phrase):].strip()
        for _ in range(2):
            if rest.startswith("the "):
                rest = rest[4:]
            if rest.startswith("my "):
                rest = rest[3:]

        if not rest:
            continue

        rest = rest.split(" and ")[0]
        rest = rest.split(" or ")[0]
        rest = rest.split(" with ")[0]
        rest = rest.split(" for ")[0]
        rest = rest.split(" now")[0]
        rest = rest.split(" please")[0]
        rest = rest.strip(" :")
        if not rest:
            continue

        if " " in rest:
            candidate = " ".join(rest.split()[:2])
        else:
            candidate = rest

        candidate = candidate.strip()
        if not candidate:
            continue

        return candidate.title()

    return ""


def sanitize_memory(raw_memory):
    if not isinstance(raw_memory, dict):
        return {}

    cleaned = {}
    for key in ALLOWED_MEMORY_KEYS:
        if key not in raw_memory:
            continue
        value = raw_memory[key]

        if key == "likes":
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list):
                likes = []
                for item in value:
                    if isinstance(item, str):
                        item = item.strip()
                        if item and item not in likes:
                            likes.append(item)
                if likes:
                    cleaned[key] = likes
            continue

        if isinstance(value, str):
            value = value.strip()
            if value:
                cleaned[key] = value

    return cleaned


def filter_explicit_memory(raw_memory, user_message):
    if not isinstance(raw_memory, dict) or not isinstance(user_message, str):
        return {}

    msg = user_message.strip().lower()
    explicit = {}
    like_trigger = [" i like ", " i love ", " i enjoy ", " i prefer ", " i am into ", " i'm into "]
    lang_trigger = [
        " language is",
        " language",
        " i prefer",
        " i'd prefer",
        " prefer ",
        " please speak",
        " speak",
        " speaking",
        " can you speak",
        " i speak",
        " i can speak",
        " can you say",
    ]
    name_trigger = [
        "my name is",
        "name is",
        "call me",
        "it's",
        "i am",
        "i'm",
        "this is",
    ]
    has_name_trigger = any(trigger in msg for trigger in name_trigger)
    has_lang_trigger = any(trigger in msg for trigger in lang_trigger)
    has_like_trigger = any(trigger in msg for trigger in like_trigger)

    for key, value in raw_memory.items():
        if key == "likes":
            if isinstance(value, list):
                likes = []
                for item in value:
                    if not isinstance(item, str):
                        continue
                    item_clean = item.strip()
                    if not item_clean:
                        continue
                    item_low = item_clean.lower()
                    if item_low in INVALID_GENERIC_VALUES:
                        continue
                    if has_like_trigger and item_low in msg:
                        likes.append(item_clean)
                if likes:
                    explicit[key] = likes
            continue

        if key in ("name", "preferred_language") and isinstance(value, str):
            value_clean = value.strip()
            value_low = value_clean.lower()
            if not value_clean or len(value_clean) < 2:
                continue

            if value_low in INVALID_NAME_VALUES or value_low in INVALID_GENERIC_VALUES:
                continue

            if key == "name":
                if not has_name_trigger:
                    continue
            if key == "preferred_language":
                language_value = value_clean
                if not has_lang_trigger:
                    language_value = extract_language_from_message(user_message)

                if not language_value:
                    continue

                language_value = language_value.strip()
                if not language_value:
                    continue

                language_low = language_value.lower()
                if language_low not in KNOWN_LANGUAGES:
                    first_word = language_low.split(" ")[0]
                    if first_word in KNOWN_LANGUAGES:
                        language_value = first_word.title()
                        language_low = first_word
                    else:
                        if not has_lang_trigger:
                            continue
                        if language_low not in KNOWN_LANGUAGES:
                            # Keep strong quality bar for ambiguous extractions
                            continue

                if language_low not in KNOWN_LANGUAGES:
                    # Keep strict memory quality
                    continue

                explicit[key] = language_value
            elif value_low in msg:
                explicit[key] = value_clean

    return explicit


def merge_memory(existing, new):
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(new, dict):
        return existing

    merged = dict(existing)
    for key, value in new.items():
        if value is None:
            continue

        if key not in merged:
            merged[key] = value
            continue

        old = merged[key]

        if key in ("name", "preferred_language"):
            if isinstance(old, str) and isinstance(value, str):
                old_clean = old.strip().lower()
                new_clean = value.strip().lower()
                if old_clean == new_clean:
                    merged[key] = old
                elif old_clean and len(new_clean) >= 2 and new_clean not in INVALID_NAME_VALUES:
                    merged[key] = value
                else:
                    merged[key] = old
                continue
            if isinstance(old, str) and not isinstance(value, str):
                merged[key] = old
                continue

        if isinstance(old, list) and isinstance(value, list):
            merged_list = list(old)
            for item in value:
                if item not in merged_list:
                    merged_list.append(item)
            merged[key] = merged_list
            continue

        if isinstance(old, list) and not isinstance(value, list):
            if value not in old:
                merged[key] = list(old) + [value]
            else:
                merged[key] = old
            continue

        if isinstance(old, dict) and isinstance(value, dict):
            merged[key] = merge_memory(old, value)
            continue

        merged[key] = value

    return merged


def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return sanitize_memory(data)
    except Exception:
        return {}

    return {}


def save_memory(memory):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=True, indent=2)
        return True
    except Exception:
        return False


def build_api_messages(chat_messages, memory):
    messages = []
    if isinstance(memory, dict) and memory:
        memory_text = "Known user memory: " + json.dumps(memory, ensure_ascii=True)
        messages.append({"role": "system", "content": memory_text})

    for message in chat_messages:
        if isinstance(message, dict):
            messages.append(message)
    return messages


def extract_user_memory(token, user_message):
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a memory extractor. "
        "Read only the latest user message. "
        "Return one plain JSON object only. "
        "Do not use markdown, fences, bullets, extra text, or explanations. "
        "Extract only clearly stated facts from that one message. "
        "Use only these keys: name, preferred_language, likes. "
        "Use list of strings for likes. "
        "If a value is not clearly stated, do not include that key. "
        "Return {} if no memory is clearly stated."
    )

    payload = {
        "model": MODEL_NAME,
        "stream": False,
        "temperature": 0,
        "max_tokens": 120,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
    except requests.RequestException:
        return {}

    if response.status_code != 200:
        return {}

    try:
        data = response.json()
    except ValueError:
        return {}

    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return {}

    first = choices[0]
    if not isinstance(first, dict):
        return {}

    message = first.get("message", {})
    if not isinstance(message, dict):
        return {}

    content = message.get("content", "")
    parsed = safe_parse_json(content)
    if not isinstance(parsed, dict):
        return {}

    parsed = sanitize_memory(parsed)
    if "preferred_language" not in parsed:
        recovered_language = extract_language_from_message(user_message)
        if recovered_language:
            parsed["preferred_language"] = recovered_language

    parsed = filter_explicit_memory(parsed, user_message)
    return parsed


st.set_page_config(page_title="My AI Chat", layout="wide")
st.title("My AI Chat")

# Load token
try:
    token = st.secrets["HF_TOKEN"]
except Exception:
    token = ""

if (not token) or token.strip() == "" or token.strip() == "PASTE_YOUR_REAL_TOKEN_HERE":
    st.error("HF_TOKEN is missing or not replaced yet in .streamlit/secrets.toml")
    st.stop()

token = token.strip()

# Load state on startup
if "chats" not in st.session_state:
    loaded_chats = load_chats_from_disk()
    if not loaded_chats:
        default_chat = create_empty_chat(1)
        loaded_chats = [default_chat]
        save_chat_to_disk(default_chat)

    st.session_state.chats = loaded_chats
    st.session_state.next_chat_id = get_next_chat_id(loaded_chats)
    st.session_state.active_chat_id = loaded_chats[0]["id"]

if "next_chat_id" not in st.session_state:
    st.session_state.next_chat_id = get_next_chat_id(st.session_state.chats)

if "active_chat_id" not in st.session_state and st.session_state.chats:
    st.session_state.active_chat_id = st.session_state.chats[0]["id"]

if "streaming_drafts" not in st.session_state:
    st.session_state.streaming_drafts = {}

if "memory" not in st.session_state:
    st.session_state.memory = load_memory()

# Sidebar chat and memory
with st.sidebar:
    st.header("Chats")

    if st.button("New Chat"):
        new_id = st.session_state.next_chat_id
        st.session_state.next_chat_id += 1
        new_chat = create_empty_chat(new_id)
        st.session_state.chats.append(new_chat)
        st.session_state.active_chat_id = new_id
        save_chat_to_disk(new_chat)
        st.rerun()

    if not st.session_state.chats:
        st.write("No chats yet.")
    else:
        for chat in st.session_state.chats:
            is_active = chat["id"] == st.session_state.get("active_chat_id")
            display_title = chat["title"] + " - " + compact_time(chat["updated"])

            left, right = st.columns([4, 2])
            if is_active:
                left.button(
                    display_title,
                    key="open_chat_" + str(chat["id"]),
                    type="secondary",
                    disabled=True,
                )
            else:
                if left.button(
                    display_title,
                    key="open_chat_" + str(chat["id"]),
                    type="secondary",
                ):
                    st.session_state.active_chat_id = chat["id"]
                    st.rerun()

            if right.button("Del", key="delete_chat_" + str(chat["id"])):
                st.session_state.chats = [c for c in st.session_state.chats if c["id"] != chat["id"]]
                delete_chat_file(chat["id"])
                st.session_state.streaming_drafts.pop(str(chat["id"]), None)

                if st.session_state.chats:
                    if st.session_state.active_chat_id == chat["id"]:
                        st.session_state.active_chat_id = st.session_state.chats[0]["id"]
                else:
                    default_chat = create_empty_chat(1)
                    st.session_state.chats = [default_chat]
                    st.session_state.next_chat_id = get_next_chat_id(st.session_state.chats)
                    st.session_state.active_chat_id = default_chat["id"]
                    save_chat_to_disk(default_chat)

                st.rerun()

    with st.expander("User Memory", expanded=True):
        if isinstance(st.session_state.memory, dict) and st.session_state.memory:
            name = st.session_state.memory.get("name")
            if isinstance(name, str) and name.strip():
                st.write("Name: " + name.strip())

            preferred_language = st.session_state.memory.get("preferred_language")
            if isinstance(preferred_language, str) and preferred_language.strip():
                st.write("Preferred language: " + preferred_language.strip())

            likes = st.session_state.memory.get("likes")
            if isinstance(likes, list) and likes:
                visible_likes = [item for item in likes if isinstance(item, str) and item.strip()]
                if visible_likes:
                    st.write("Likes: " + ", ".join(visible_likes))
            elif isinstance(likes, str) and likes.strip():
                st.write("Likes: " + likes.strip())
        else:
            st.write("No memory yet.")

        if st.button("Reset Memory"):
            st.session_state.memory = {}
            save_memory({})
            st.rerun()

# Ensure active chat exists
active_chat = get_active_chat()
if active_chat is None and st.session_state.chats:
    st.session_state.active_chat_id = st.session_state.chats[0]["id"]
    active_chat = get_active_chat()

if active_chat is None:
    st.info("No chat selected. Click New Chat to start.")
    st.stop()

# Show history when there is no new user message yet
for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_message = st.chat_input("Type a message")
if user_message is None:
    st.stop()

if not user_message.strip():
    st.stop()

# Add user message
active_chat["messages"].append({"role": "user", "content": user_message})
with st.chat_message("user"):
    st.write(user_message)

# Save after user message so it is durable even if stream is interrupted
active_chat["updated"] = now_string()
save_chat_to_disk(active_chat)

# Prepare streaming assistant placeholder
stream_key = str(active_chat["id"])
existing = None
for i in range(len(active_chat["messages"]) - 1, -1, -1):
    msg = active_chat["messages"][i]
    if (
        isinstance(msg, dict)
        and msg.get("role") == "assistant"
        and msg.get("streaming", False)
    ):
        existing = msg
        break

if existing is not None:
    existing["content"] = st.session_state.streaming_drafts.get(stream_key, existing.get("content", ""))
    streaming_message = existing
else:
    streaming_message = {"role": "assistant", "content": "", "streaming": True}
    active_chat["messages"].append(streaming_message)

st.session_state.streaming_drafts[stream_key] = streaming_message.get("content", "")

# Display assistant stream
assistant_reply = streaming_message.get("content", "")
headers = {
    "Authorization": "Bearer " + token,
    "Content-Type": "application/json",
}

messages_for_api = build_api_messages(active_chat["messages"][:-1], st.session_state.memory)
payload = {
    "model": MODEL_NAME,
    "messages": messages_for_api,
    "stream": True,
}

try:
    response = requests.post(API_URL, headers=headers, json=payload, timeout=20, stream=True)
except requests.Timeout:
    st.error("Request timed out. Please try again later.")
    st.stop()
except requests.RequestException as exc:
    st.error("Network error while contacting API: " + str(exc))
    st.stop()

if response.status_code in (401, 403):
    st.error("Invalid token. Check your HF_TOKEN value in .streamlit/secrets.toml")
    st.stop()

if response.status_code == 429:
    st.error("Rate limit reached. Please wait and try again later.")
    st.stop()

if response.status_code != 200:
    st.error("API request failed with status " + str(response.status_code) + ": " + str(response.text))
    st.stop()

with st.chat_message("assistant"):
    message_box = st.empty()
    message_box.markdown(assistant_reply)

    found_chunk = False
    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue

            event_data = line[5:].strip()
            if event_data == "[DONE]":
                break

            try:
                event = json.loads(event_data)
            except Exception:
                continue

            choices = event.get("choices") if isinstance(event, dict) else None
            if not isinstance(choices, list) or not choices:
                continue

            first = choices[0]
            if not isinstance(first, dict):
                continue

            delta = first.get("delta", {})
            if not isinstance(delta, dict):
                delta = {}

            piece = delta.get("content", "")
            if not piece:
                message = first.get("message", {})
                if isinstance(message, dict):
                    piece = message.get("content", "")

            if isinstance(piece, str) and piece:
                assistant_reply += piece
                streaming_message["content"] = assistant_reply
                streaming_message["streaming"] = True
                st.session_state.streaming_drafts[stream_key] = assistant_reply
                active_chat["updated"] = now_string()
                save_chat_to_disk(active_chat)
                message_box.markdown(assistant_reply)
                found_chunk = True
                time.sleep(0.02)
    except Exception:
        found_chunk = False

if not isinstance(assistant_reply, str) or not assistant_reply.strip():
    st.error("Unexpected response format: could not read streaming content.")
    st.stop()

# Finalize stream state and persist
streaming_message["content"] = assistant_reply
if "streaming" in streaming_message:
    del streaming_message["streaming"]
active_chat["updated"] = now_string()
st.session_state.streaming_drafts.pop(stream_key, None)
save_chat_to_disk(active_chat)

# Add memory from latest user message
if isinstance(assistant_reply, str) and assistant_reply.strip():
    extracted = extract_user_memory(token, user_message)
    if not isinstance(extracted, dict):
        extracted = {}

    new_memory = merge_memory(st.session_state.memory, extracted)
    if new_memory != st.session_state.memory:
        st.session_state.memory = new_memory
        if save_memory(st.session_state.memory):
            st.rerun()
