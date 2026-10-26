import subprocess
import os
import uuid
import re
import json
import logging
import shutil
import hashlib
import time
import wave

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from ebooklib import epub
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False

LOG_DIR = os.path.expanduser("~/.local/share/linuquendo")
CACHE_DIR = os.path.expanduser("~/.cache/linuquendo")
CONFIG_DIR = os.path.expanduser("~/.config/linuquendo")
AUDIO_CACHE_DIR = os.path.join(CACHE_DIR, "audio")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "linuquendo.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PREFERENCES_FILE = os.path.join(CONFIG_DIR, "preferences.json")
VOICES_COLORS_FILE = os.path.join(CONFIG_DIR, "voices_colors.json")
PRONUNCIATIONS_FILE = os.path.join(CONFIG_DIR, "pronunciations.json")

DEFAULT_VOICE_COLORS = {
    "Jorge": "#A0C4FF", "Carlos": "#FFD6A5", "Carmen": "#CAFFBF",
    "Soledad": "#FFC6FF", "Diego": "#BDB2FF", "Esperanza": "#FDFFB6",
    "Ludoviko": "#D0D0D0",
}
DEFAULT_COLOR = "#E0E0E0"

def load_config():
    config_path = os.path.join(CONFIG_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {"wineprefix": "", "app_dir": ""}

CONFIG = load_config()
WINEPREFIX = CONFIG.get("wineprefix", "")

ENGINE_BIN_LINUX = os.path.join(WINEPREFIX, "drive_c", "Program Files (x86)", "Loquendo", "LTTS7", "bin")
SYSWOW64_LINUX = os.path.join(WINEPREFIX, "drive_c", "windows", "syswow64")
SETUP_FLAG = os.path.join(LOG_DIR, "setup_done.flag")
VOICES_CACHE = os.path.join(LOG_DIR, "voices_cache.json")
AUDIO_CACHE_INDEX = os.path.join(AUDIO_CACHE_DIR, "index.json")
CACHE_MAX_BYTES = 500 * 1024 * 1024
CACHE_MAX_FILES = 1000

TTS_GEN = r"C:\Program Files (x86)\Loquendo\LTTS7\bin\TTSFileGenerator.exe"
REG_QUERY_TIMEOUT = 15


def load_preferences():
    if os.path.exists(PREFERENCES_FILE):
        try:
            with open(PREFERENCES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"theme": "system", "language": "", "volume": 1.0}


def save_preferences(prefs):
    try:
        with open(PREFERENCES_FILE, "w") as f:
            json.dump(prefs, f)
        return True
    except Exception as e:
        logging.error(f"No se pudieron guardar preferencias: {e}")
        return False


def load_voice_colors():
    colors = dict(DEFAULT_VOICE_COLORS)
    if os.path.exists(VOICES_COLORS_FILE):
        try:
            with open(VOICES_COLORS_FILE, "r") as f:
                saved = json.load(f)
            colors.update(saved)
        except Exception:
            pass
    return colors


def save_voice_colors(colors):
    try:
        with open(VOICES_COLORS_FILE, "w") as f:
            json.dump(colors, f)
        return True
    except Exception as e:
        logging.error(f"No se pudieron guardar colores: {e}")
        return False


def load_pronunciations():
    if os.path.exists(PRONUNCIATIONS_FILE):
        try:
            with open(PRONUNCIATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_pronunciations(data):
    try:
        with open(PRONUNCIATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"No se pudieron guardar pronunciaciones: {e}")
        return False


def apply_pronunciations(text):
    rules = load_pronunciations()
    if not rules:
        return text
    keys = sorted(rules.keys(), key=len, reverse=True)
    for key in keys:
        replacement = rules[key]
        pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
        text = pattern.sub(replacement, text)
    return text


def get_cache_info():
    if not os.path.isdir(AUDIO_CACHE_DIR):
        return (0, 0)
    count = 0
    total = 0
    for f in os.listdir(AUDIO_CACHE_DIR):
        if f.endswith(".wav"):
            p = os.path.join(AUDIO_CACHE_DIR, f)
            try:
                total += os.path.getsize(p)
                count += 1
            except Exception:
                pass
    return (count, total)


def clear_audio_cache():
    count = 0
    total = 0
    if os.path.isdir(AUDIO_CACHE_DIR):
        for f in os.listdir(AUDIO_CACHE_DIR):
            if f.endswith(".wav"):
                p = os.path.join(AUDIO_CACHE_DIR, f)
                try:
                    total += os.path.getsize(p)
                    os.unlink(p)
                    count += 1
                except Exception:
                    pass
    try:
        if os.path.exists(AUDIO_CACHE_INDEX):
            os.unlink(AUDIO_CACHE_INDEX)
    except Exception:
        pass
    logging.info(f"Caché de audio borrado: {count} archivos, {total} bytes")
    return (count, total)


def extract_text_from_file(path):
    if not os.path.exists(path):
        return (None, "El archivo no existe.")
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        if not HAS_PYPDF:
            return (None, "Falta la librería 'pypdf'. Instálala con: sudo pacman -S python-pypdf")
        try:
            reader = PdfReader(path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            full = "\n\n".join(pages).strip()
            if not full:
                return (None, "El PDF no contiene texto extraíble (puede ser una imagen escaneada).")
            logging.info(f"PDF importado: {path} ({len(pages)} páginas)")
            return (full, None)
        except Exception as e:
            logging.error(f"Error leyendo PDF {path}: {e}")
            return (None, f"Error al leer el PDF: {e}")

    elif ext == ".docx":
        if not HAS_DOCX:
            return (None, "Falta la librería 'python-docx'. Instálala con: sudo pacman -S python-docx")
        try:
            doc = Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full = "\n".join(paragraphs).strip()
            if not full:
                return (None, "El DOCX no contiene texto.")
            logging.info(f"DOCX importado: {path} ({len(paragraphs)} párrafos)")
            return (full, None)
        except Exception as e:
            logging.error(f"Error leyendo DOCX {path}: {e}")
            return (None, f"Error al leer el DOCX: {e}")

    elif ext == ".epub":
        if not HAS_EBOOKLIB:
            return (None, "Falta la librería 'ebooklib'. Instálala con: sudo pacman -S python-ebooklib")
        try:
            book = epub.read_epub(path)
            chapters = []
            for item in book.get_items():
                if item.get_type() == 9:
                    try:
                        content = item.get_content().decode("utf-8", errors="ignore")
                        text = re.sub(r'<[^>]+>', ' ', content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        if text:
                            chapters.append(text)
                    except Exception:
                        continue
            full = "\n\n".join(chapters).strip()
            if not full:
                return (None, "El EPUB no contiene texto extraíble.")
            logging.info(f"EPUB importado: {path} ({len(chapters)} capítulos)")
            return (full, None)
        except Exception as e:
            logging.error(f"Error leyendo EPUB {path}: {e}")
            return (None, f"Error al leer el EPUB: {e}")

    else:
        return (None, f"Formato no soportado: {ext}. Usa PDF, DOCX o EPUB.")


def list_installed_voices(force_refresh=False):
    if not force_refresh and os.path.exists(VOICES_CACHE):
        try:
            with open(VOICES_CACHE, "r") as f:
                cached = json.load(f)
                if cached: return cached
        except Exception:
            pass

    if not WINEPREFIX or not os.path.exists(os.path.join(WINEPREFIX, "drive_c")):
        return []
    env = os.environ.copy()
    env["WINEPREFIX"] = WINEPREFIX
    env["WINEDEBUG"] = "-all"
    voces = set()
    for regkey in ["HKLM\\Software\\Loquendo\\LTTS7\\Voices",
                   "HKLM\\Software\\Wow6432Node\\Loquendo\\LTTS7\\Voices"]:
        try:
            result = subprocess.run(
                ["wine", "reg", "query", regkey, "/s"],
                env=env, capture_output=True, text=True, errors='replace', check=False,
                timeout=REG_QUERY_TIMEOUT
            )
            prefix = regkey.upper() + "\\"
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.upper().startswith(prefix):
                    nombre = line.split("\\")[-1]
                    if nombre and nombre.lower() != "voices":
                        voces.add(nombre)
        except subprocess.TimeoutExpired:
            logging.warning(f"Timeout consultando {regkey} (Wine frío). Usando carpetas.")
        except Exception as e:
            logging.error(f"Error consultando {regkey}: {e}")
    voices_dir = os.path.join(WINEPREFIX, "drive_c", "Program Files (x86)", "Loquendo", "LTTS7", "data", "voices")
    if os.path.isdir(voices_dir):
        for item in os.listdir(voices_dir):
            if os.path.isdir(os.path.join(voices_dir, item)):
                voces.add(item)
    voces_list = sorted(list(voces))
    if voces_list:
        try:
            with open(VOICES_CACHE, "w") as f:
                json.dump(voces_list, f)
        except Exception:
            pass
    return voces_list


SOUND_NAMES = {
    "Ah": "Ah", "Ay": "Ay", "Breath": "Respiración", "Buh": "Buh",
    "Buuu": "Buuu", "Cataplum": "Cataplum", "Click": "Clic",
    "Cough": "Tos", "Cry": "Llanto", "Ehi": "Ehi", "Ehm": "Ehm",
    "Epa": "Epa", "Hiccup": "Hipo", "Laugh": "Risa", "Mhmm": "Mhmm",
    "Oh": "Oh", "Ohoh": "Ohoh", "Ops": "Ups", "Prrr": "Prrr",
    "Shhh": "Shhh", "Sigh": "Suspiro", "Singing": "Canto",
    "Smack": "Beso", "Sniff": "Sorber", "Snore": "Ronquido",
    "Swallow": "Tragar", "Throat": "Aclarar garganta",
    "Uff": "Uff", "Ups": "Ups", "Whistle": "Silbido",
    "Yawn": "Bostezo", "Yeee": "Yeee", "Yuhu": "Yuhu", "Zas": "Zas",
}

PHRASE_NAMES = {
    "Announce": "Anuncio", "Apologies": "Disculpa", "Approval": "Aprobación",
    "Compliments": "Cumplido", "Contrast": "Contraste",
    "Disapproval": "Desaprobación", "Disbelief": "Incredulidad",
    "Greetings": "Saludo", "Prohibition": "Prohibición",
    "Recall": "Recordatorio", "Refuse": "Negación", "Regret": "Lamento",
    "Request_Action": "Solicitud de acción",
    "Request_Confirmation": "Pregunta de confirmación",
    "Request_Information": "Pregunta", "Surprise": "Sorpresa",
    "Thanks": "Agradecimiento",
}

MAX_PHRASES_PER_CATEGORY = 5


def _read_gde_content(gde_path):
    try:
        with open(gde_path, "r", encoding="utf-8", errors="strict") as f:
            content = f.read()
        logging.info(f"Leído {os.path.basename(gde_path)} como UTF-8")
        return content
    except UnicodeDecodeError:
        pass
    try:
        with open(gde_path, "r", encoding="cp1252", errors="strict") as f:
            content = f.read()
        logging.info(f"Leído {os.path.basename(gde_path)} como CP1252")
        return content
    except Exception as e:
        logging.error(f"Error leyendo {gde_path}: {e}")
        return ""


def get_expressions_for_voice(voice_name):
    voices_dir = os.path.join(WINEPREFIX, "drive_c", "Program Files (x86)", "Loquendo", "LTTS7", "data", "voices", voice_name)
    if not os.path.isdir(voices_dir):
        return []
    gde_file = None
    for f in os.listdir(voices_dir):
        if f.lower().endswith("gilded.gde"):
            gde_file = os.path.join(voices_dir, f)
            break
    if not gde_file:
        return []

    content = _read_gde_content(gde_file)
    if not content:
        return []

    expressions = []
    try:
        pattern = r'^"(\w+)\[(\d+)\]"\s*=\s*"([^"]*)"'
        matches = re.findall(pattern, content, re.MULTILINE)
        phrase_counts = {}

        for category, index, values_str in matches:
            values = [v.strip() for v in values_str.split("~") if v.strip()]

            if category in SOUND_NAMES:
                for v in values:
                    if not v.startswith("\\_"):
                        continue
                    sound_name = v[2:]
                    variant = ""
                    parts = sound_name.split("_")
                    if len(parts) >= 2 and parts[-1].isdigit():
                        variant = f" {int(parts[-1])}"
                        base = "_".join(parts[:-1])
                    else:
                        base = sound_name
                    display_name = SOUND_NAMES.get(base, base) + variant + " (sonido)"
                    code = f"\\item={sound_name}"
                    expressions.append({
                        "code": code,
                        "name": display_name,
                        "type": "sonido"
                    })

            elif category in PHRASE_NAMES:
                count = phrase_counts.get(category, 0)
                if count >= MAX_PHRASES_PER_CATEGORY:
                    continue
                for v in values:
                    if count >= MAX_PHRASES_PER_CATEGORY:
                        break
                    phrase = " ".join(v.split())
                    if not phrase:
                        continue
                    name = f"{PHRASE_NAMES[category]}: {phrase} (frase)"
                    expressions.append({
                        "code": phrase,
                        "name": name,
                        "type": "frase"
                    })
                    count += 1
                phrase_counts[category] = count

    except Exception as e:
        logging.error(f"Error parseando .gde: {e}")

    expressions.sort(key=lambda x: (0 if x["type"] == "sonido" else 1, x["name"]))
    logging.info(f"Expresiones cargadas para {voice_name}: {len(expressions)}")
    return expressions


def _load_cache_index():
    if os.path.exists(AUDIO_CACHE_INDEX):
        try:
            with open(AUDIO_CACHE_INDEX, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache_index(index):
    try:
        with open(AUDIO_CACHE_INDEX, "w") as f:
            json.dump(index, f)
    except Exception as e:
        logging.error(f"No se pudo guardar índice de caché: {e}")


def _cache_key(text, voice, freq, channels, speed, pitch, ssml, volume, language):
    payload = json.dumps({
        "text": text, "voice": voice, "freq": freq,
        "channels": channels, "speed": speed, "pitch": pitch,
        "ssml": bool(ssml), "volume": volume, "language": language
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key):
    index = _load_cache_index()
    entry = index.get(key)
    if not entry:
        return None
    path = entry.get("path")
    if path and os.path.exists(path) and os.path.getsize(path) > 44:
        entry["last_access"] = time.time()
        index[key] = entry
        _save_cache_index(index)
        return path
    del index[key]
    _save_cache_index(index)
    return None


def _cache_put(key, src_path):
    index = _load_cache_index()
    dst = os.path.join(AUDIO_CACHE_DIR, f"{key}.wav")
    try:
        if not os.path.exists(dst) or os.path.getsize(src_path) > os.path.getsize(dst):
            shutil.copy(src_path, dst)
        index[key] = {
            "path": dst,
            "size": os.path.getsize(dst),
            "created": time.time(),
            "last_access": time.time()
        }
        _save_cache_index(index)
        _cache_evict_if_needed(index)
        return dst
    except Exception as e:
        logging.error(f"No se pudo guardar en caché: {e}")
        return None


def _cache_evict_if_needed(index):
    total_bytes = sum(e.get("size", 0) for e in index.values())
    if total_bytes <= CACHE_MAX_BYTES and len(index) <= CACHE_MAX_FILES:
        return
    items = sorted(index.items(), key=lambda kv: kv[1].get("last_access", 0))
    while items and (total_bytes > CACHE_MAX_BYTES or len(items) > CACHE_MAX_FILES):
        key, entry = items.pop(0)
        try: os.unlink(entry.get("path", ""))
        except Exception: pass
        total_bytes -= entry.get("size", 0)
        del index[key]
    _save_cache_index(index)
    logging.info(f"Caché depurado: {len(index)} archivos, {total_bytes} bytes")


def build_loquendo_markup(text, rate, pitch):
    prefix = ""
    speed_val = max(0, min(100, int(rate * 50)))
    pitch_val = max(0, min(100, int(pitch * 50)))
    if speed_val != 50:
        prefix += f"\\speed={speed_val} "
    if pitch_val != 50:
        prefix += f"\\pitch={pitch_val} "
    if prefix:
        return prefix + text
    return text


def _concat_wavs(paths, out_path):
    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]
    try:
        with wave.open(paths[0], 'rb') as w0:
            params = w0.getparams()
        with wave.open(out_path, 'wb') as wout:
            wout.setparams(params)
            for p in paths:
                with wave.open(p, 'rb') as w:
                    wout.writeframes(w.readframes(w.getnframes()))
        return out_path
    except Exception as e:
        logging.error(f"Error concatenando WAVs: {e}")
        return paths[0]


def apply_volume(wav_path, volume):
    if abs(volume - 1.0) < 0.01:
        return wav_path
    if not shutil.which("ffmpeg"):
        logging.warning("ffmpeg no está instalado. Se omite el control de volumen.")
        return wav_path
    tmp_out = wav_path + ".vol.wav"
    try:
        cmd = [
            "ffmpeg", "-y", "-i", wav_path,
            "-af", f"volume={volume:.2f}",
            tmp_out
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        os.replace(tmp_out, wav_path)
        logging.info(f"Volumen aplicado: {volume:.2f}")
        return wav_path
    except Exception as e:
        logging.error(f"Error aplicando volumen: {e}")
        try: os.unlink(tmp_out)
        except Exception: pass
        return wav_path


# Mapeo de códigos ISO a mnemónicos de Loquendo
ISO_TO_MNEMONIC = {
    "es": "spanish", "en": "english", "fr": "french", "de": "german",
    "it": "italian", "pt": "portuguese", "ca": "catalan", "gl": "galician",
    "eu": "basque"
}

def _normalize_language(lang):
    if not lang:
        return ""
    lang = lang.lower().strip()
    if len(lang) == 2 and lang in ISO_TO_MNEMONIC:
        return ISO_TO_MNEMONIC[lang]
    return lang


def generate_audio(text, voice="Jorge", frequency=44100, channels=2, rate=1.0, pitch=1.0, mode="export", ssml_mode=False, volume=None, language=None):
    if not text.strip():
        return None
    if not WINEPREFIX or not os.path.exists(WINEPREFIX):
        logging.error("WINEPREFIX no existe.")
        return None

    prefs = load_preferences()
    if volume is None:
        volume = prefs.get("volume", 1.0)
    if language is None:
        language = prefs.get("language", "")
    language = _normalize_language(language)

    speed_for_key = max(0, min(100, int(rate * 50)))
    pitch_for_key = max(0, min(100, int(pitch * 50)))
    key = _cache_key(text, voice, frequency, channels, speed_for_key, pitch_for_key, ssml_mode, volume, language)
    cached = _cache_get(key)
    if cached:
        logging.info(f"Cache HIT: {key[:12]}")
        return cached

    text = apply_pronunciations(text)

    if not ssml_mode and (rate != 1.0 or pitch != 1.0):
        text = build_loquendo_markup(text, rate, pitch)
    elif ssml_mode:
        if not text.strip().startswith("<?xml"):
            text = '<?xml version="1.0" encoding="UTF-8"?>\n<speak>\n' + text + '\n</speak>'

    unique = uuid.uuid4().hex[:8]
    win_txt_name = f"linuquendo_{unique}.txt"
    win_out_name = f"linuquendo_{unique}.wav"
    linux_txt_path = os.path.join(WINEPREFIX, "drive_c", win_txt_name)
    linux_out_path = os.path.join(WINEPREFIX, "drive_c", win_out_name)

    env = os.environ.copy()
    env["WINEPREFIX"] = WINEPREFIX
    env["WINEDEBUG"] = "-all"

    try:
        text_to_write = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
        if not text_to_write.endswith('\r\n'):
            text_to_write += '\r\n'
        with open(linux_txt_path, "w", encoding="cp1252", errors="replace", newline="") as f:
            f.write(text_to_write)

        cmd = [
            "wine", TTS_GEN,
            "-v", voice,
            "-f", str(frequency),
            "-s", str(channels),
        ]
        # Solo añadimos -l si el usuario ha elegido explícitamente un idioma
        # y NO está vacío. Además, solo lo hacemos si el valor parece un mnemónico
        # (no un código ISO, que ya se ha normalizado).
        if language:
            cmd.extend(["-l", language])
        cmd.extend([
            "-o", f"C:\\{win_out_name}",
            f"C:\\{win_txt_name}"
        ])

        logging.info(f"Ejecutando (ssml={ssml_mode}, lang={language}): {' '.join(cmd)}")
        subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

        out_dir = os.path.dirname(linux_out_path)
        base = win_out_name.replace(".wav", "")
        wav_files = []
        for f in os.listdir(out_dir):
            if f.startswith(base) and f.endswith(".wav"):
                wav_files.append(os.path.join(out_dir, f))
        wav_files.sort()

        if not wav_files:
            logging.error(f"No se encontró ningún WAV generado para: {win_out_name}")
            return None

        if len(wav_files) == 1:
            real_out = wav_files[0]
        else:
            logging.info(f"Concatenando {len(wav_files)} WAVs...")
            concat_path = os.path.join(out_dir, f"linuquendo_concat_{unique}.wav")
            real_out = _concat_wavs(wav_files, concat_path)
            for p in wav_files:
                try: os.unlink(p)
                except Exception: pass

        real_out = apply_volume(real_out, volume)

        cached_path = _cache_put(key, real_out)
        if cached_path:
            try: os.unlink(real_out)
            except Exception: pass
            try: os.unlink(linux_txt_path)
            except Exception: pass
            return cached_path

        try: os.unlink(linux_txt_path)
        except Exception: pass
        return real_out

    except subprocess.CalledProcessError as e:
        logging.error(f"Error en TTSFileGenerator: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        logging.error("Timeout en TTSFileGenerator")
        return None
    except Exception as e:
        logging.error(f"Error inesperado: {e}")
        return None
    finally:
        if os.path.exists(linux_txt_path):
            try: os.unlink(linux_txt_path)
            except Exception: pass


def start_daemon_async():
    pass

def daemon_ready():
    return True

def shutdown_daemon():
    pass
