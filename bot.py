#!/usr/bin/env python3
"""
YouTube Shorts Creator + Auto Upload ke Koyeb
- Pilihan 1: Buat video (background dari video, overlay Pillow)
- Pilihan 2: Upload video dari ./result/ ke API Koyeb (hapus setelah upload)
- Pilihan 3: Auto loop — buat video → upload → hapus → ulangi

pkg install ffmpeg
pip install pillow requests --break-system-packages
python app.py
"""

import os, sys, subprocess, shutil, random, math, json, time, base64
from PIL import Image, ImageDraw, ImageFont

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
loop_random_music = False
# ══════════════════════════════════════════════════════════════════════════════

MUSIK_DIR   = "./musik"
RESULT_DIR  = "./result"
CACHE_FILE  = "./cache.txt"
BG_DIR      = "./background"
CONFIG_FILE = "./config.json"
DATA_FILE   = "./data.txt"

GITHUB_API  = "https://api.github.com"

EXCLUDE_UPLOAD = {"result", "__pycache__", ".git", "cache.txt", "data.txt"}

W, H = 1080, 1920
FPS  = 15

# ══════════════════════════════════════════════════════════════════════════════
# CACHE
# ══════════════════════════════════════════════════════════════════════════════

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
# DATA.TXT
# ══════════════════════════════════════════════════════════════════════════════

def load_data_txt() -> dict:
    result = {"github": "", "url": ""}
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            f.write("github=\nurl=\n")
        return result
    with open(DATA_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    return result

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG.JSON
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "timer_value":        15,
    "timer_unit":         "hours",
    "github_repo":        "BimaSkyy/make-send",
    "github_branch":      "main",
    "auto_update_github": True
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            updated = False
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
                    updated = True
            if updated:
                save_config(cfg)
            return cfg
        except:
            pass
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)

def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
# GITHUB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _gh_headers():
    tok = load_data_txt().get("github", "")
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"token {tok}"
    return h

def _gh_repo():
    return load_config().get("github_repo", "BimaSkyy/make-send")

def _gh_branch():
    return load_config().get("github_branch", "main")

def _encode_path(path):
    from urllib.parse import quote
    return "/".join(quote(part, safe="") for part in path.split("/"))

def gh_get_file(repo_path):
    try:
        import requests as r
        encoded = _encode_path(repo_path)
        url  = f"{GITHUB_API}/repos/{_gh_repo()}/contents/{encoded}?ref={_gh_branch()}"
        resp = r.get(url, headers=_gh_headers(), timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            if not isinstance(d, dict):
                return None, None
            raw = base64.b64decode(d["content"])
            return raw, d.get("sha")
    except Exception as e:
        print(f"  [GH] get error {repo_path}: {e}")
    return None, None

def gh_put_file(repo_path, content_bytes, message, sha=None):
    try:
        import requests as r
        encoded = base64.b64encode(content_bytes).decode("utf-8")
        payload = {
            "message": message,
            "content": encoded,
            "branch":  _gh_branch(),
        }
        if sha:
            payload["sha"] = sha
        path_enc = _encode_path(repo_path)
        url  = f"{GITHUB_API}/repos/{_gh_repo()}/contents/{path_enc}"
        resp = r.put(url, headers=_gh_headers(), json=payload, timeout=60)
        if resp.status_code in (200, 201):
            return True, resp.json().get("content", {}).get("sha")
        print(f"  [GH] PUT {repo_path} → {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"  [GH] put error {repo_path}: {e}")
    return False, None

def gh_list_folder(folder_path):
    try:
        import requests as r
        path_enc = _encode_path(folder_path)
        url  = f"{GITHUB_API}/repos/{_gh_repo()}/contents/{path_enc}?ref={_gh_branch()}"
        resp = r.get(url, headers=_gh_headers(), timeout=15)
        if resp.status_code == 200:
            items = resp.json()
            if isinstance(items, list):
                return [i for i in items if isinstance(i, dict) and i.get("type") == "file"]
        elif resp.status_code == 404:
            return []
    except Exception as e:
        print(f"  [GH] list error {folder_path}: {e}")
    return []

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 4 — UPLOAD PROJEK KE GITHUB
# ══════════════════════════════════════════════════════════════════════════════

def menu_upload_github():
    creds = load_data_txt()
    if not creds.get("github"):
        print("\n  ⚠  github token belum diisi di data.txt")
        print("     Buka data.txt, isi: github=ghp_tokenmu")
        return

    cfg = load_config()
    print(f"\n{'─'*40}")
    print(f"  Upload projek → github.com/{cfg['github_repo']}")
    print(f"  Branch : {cfg['github_branch']}")
    print(f"  Exclude: {', '.join(EXCLUDE_UPLOAD)}")
    print(f"{'─'*40}")

    BASE = os.path.dirname(os.path.abspath(__file__)) or "."

    to_upload = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_UPLOAD and not d.startswith(".")]
        rel_root = os.path.relpath(root, BASE)
        for fname in files:
            if fname.startswith("."): continue
            rel_path = os.path.join(rel_root, fname) if rel_root != "." else fname
            rel_path = rel_path.replace("\\", "/")
            top = rel_path.split("/")[0]
            if top in EXCLUDE_UPLOAD: continue
            to_upload.append((os.path.join(root, fname), rel_path))

    print(f"  Cek file yang sudah ada di GitHub...")
    existing_on_gh = set()
    folders_checked = set()
    for _, repo_path in to_upload:
        folder = "/".join(repo_path.split("/")[:-1]) if "/" in repo_path else ""
        key = folder or "."
        if key not in folders_checked:
            folders_checked.add(key)
            items = gh_list_folder(folder) if folder else gh_list_folder("")
            for item in items:
                existing_on_gh.add(item.get("path", "").replace("\\", "/"))

    need_upload = [(lp, rp) for lp, rp in to_upload if rp not in existing_on_gh]
    skip_count  = len(to_upload) - len(need_upload)

    print(f"  Total lokal  : {len(to_upload)} file")
    print(f"  Sudah ada    : {skip_count} file (di-skip)")
    print(f"  Perlu upload : {len(need_upload)} file\n")

    if not need_upload:
        print("  Semua file sudah ada di GitHub!")
        return

    MAX_SIZE = 99 * 1024 * 1024
    ok_count = err_count = skip_size = 0

    for local_path, repo_path in need_upload:
        try:
            size = os.path.getsize(local_path)
            if size > MAX_SIZE:
                size_mb = size / 1024 / 1024
                print(f"  ⚠ skip (terlalu besar {size_mb:.1f}MB > 99MB): {repo_path}")
                skip_size += 1
                continue
            with open(local_path, "rb") as f:
                content_bytes = f.read()
            ok, _ = gh_put_file(repo_path, content_bytes, f"[auto] add {repo_path}")
            status = "✓" if ok else "✗"
            if ok: ok_count += 1
            else:  err_count += 1
        except Exception as e:
            status = "✗"
            err_count += 1
            print(f"  {status} {repo_path} — {e}")
            continue
        print(f"  {status} {repo_path}")

    print(f"\n  Selesai! {ok_count} berhasil, {err_count} gagal, {skip_size} skip (>99MB)")

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 5 — UPDATE BACKGROUND/MUSIK DARI GITHUB
# ══════════════════════════════════════════════════════════════════════════════

def sync_assets_from_github(silent=False):
    if not silent:
        print(f"\n{'─'*40}")
        print(f"  Sync background & musik dari GitHub...")
        print(f"{'─'*40}")

    bg_new = mus_new = 0

    for folder, local_dir in [("background", BG_DIR), ("musik", MUSIK_DIR)]:
        os.makedirs(local_dir, exist_ok=True)
        items = gh_list_folder(folder)
        if not items:
            if not silent:
                print(f"  [{folder}] Kosong / tidak ditemukan di GitHub")
            continue

        for item in items:
            fname      = item["name"]
            local_path = os.path.join(local_dir, fname)
            if os.path.exists(local_path):
                if not silent:
                    print(f"  [{folder}] skip (sudah ada): {fname}")
                continue
            try:
                import requests as r
                dl_url = item.get("download_url")
                if not dl_url:
                    continue
                resp = r.get(dl_url, headers=_gh_headers(), timeout=60, stream=True)
                if resp.status_code == 200:
                    with open(local_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            f.write(chunk)
                    size_mb = os.path.getsize(local_path) / 1024 / 1024
                    print(f"  [{folder}] ✓ {fname} ({size_mb:.1f} MB)")
                    if folder == "background": bg_new += 1
                    else: mus_new += 1
                else:
                    print(f"  [{folder}] ✗ {fname} — HTTP {resp.status_code}")
            except Exception as e:
                print(f"  [{folder}] ✗ {fname} — {e}")

    if not silent:
        print(f"\n  Selesai! background baru: {bg_new}, musik baru: {mus_new}")
    return bg_new, mus_new

def menu_update_assets():
    sync_assets_from_github(silent=False)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO UPDATE THREAD
# ══════════════════════════════════════════════════════════════════════════════

_auto_update_last = 0

def _auto_update_loop():
    global _auto_update_last
    import threading
    interval = 10 * 60
    while True:
        time.sleep(60)
        cfg = load_config()
        if not cfg.get("auto_update_github", False):
            continue
        now = time.time()
        if now - _auto_update_last >= interval:
            _auto_update_last = now
            print("\n  [auto-update] Cek background/musik dari GitHub...")
            bg_new, mus_new = sync_assets_from_github(silent=True)
            if bg_new or mus_new:
                print(f"  [auto-update] File baru: {bg_new} background, {mus_new} musik")

# ══════════════════════════════════════════════════════════════════════════════
# HELPER — PILIH BACKGROUND RANDOM
# ══════════════════════════════════════════════════════════════════════════════

def pick_bg_video():
    if not os.path.isdir(BG_DIR):
        print(f"Folder background tidak ditemukan: {BG_DIR}"); sys.exit(1)
    bg_files = [f for f in os.listdir(BG_DIR) if f.lower().endswith(".mp4")]
    if not bg_files:
        print(f"Tidak ada file .mp4 di folder '{BG_DIR}'!"); sys.exit(1)
    cache = load_cache()
    last_bg = cache.get("last_bg", "")
    kandidat = [f for f in bg_files if f != last_bg] or bg_files
    chosen = random.choice(kandidat)
    return os.path.join(BG_DIR, chosen), chosen

# ══════════════════════════════════════════════════════════════════════════════
# MENU UTAMA
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import threading
    t = threading.Thread(target=_auto_update_loop, daemon=True)
    t.start()

    print("\n" + "="*40)
    print("  YouTube Shorts Creator + Uploader")
    print("="*40)
    print("  1. Buat video")
    print("  2. Upload ke API Koyeb")
    print("  3. Auto (buat → upload → hapus → loop)")
    print("  4. Upload projek ke GitHub")
    print("  5. Update background/musik dari GitHub")
    print("="*40)
    pilihan = input("Mau apa? [1/2/3/4/5]: ").strip()
    if pilihan == "1":
        menu_buat_video()
    elif pilihan == "2":
        menu_upload()
    elif pilihan == "3":
        menu_auto()
    elif pilihan == "4":
        menu_upload_github()
    elif pilihan == "5":
        menu_update_assets()
    else:
        print("Pilihan tidak valid."); sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 1 — BUAT VIDEO
# ══════════════════════════════════════════════════════════════════════════════

def menu_buat_video():
    try:
        jumlah = int(input("\nMau buat berapa video?: ").strip())
        if jumlah < 1: raise ValueError
    except ValueError:
        print("Masukkan angka yang valid."); sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("ffmpeg tidak ditemukan. Jalankan: pkg install ffmpeg"); sys.exit(1)

    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(MUSIK_DIR,  exist_ok=True)

    EXT_VALID   = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac")
    musik_files = [f for f in os.listdir(MUSIK_DIR) if f.lower().endswith(EXT_VALID)]
    if not musik_files:
        print(f"Tidak ada file musik di folder '{MUSIK_DIR}'!"); sys.exit(1)

    for i in range(jumlah):
        print(f"\n{'─'*40}")
        print(f"  Video {i+1} dari {jumlah}")
        print(f"{'─'*40}")
        buat_satu_video(musik_files)

    print(f"\nSelesai! {jumlah} video tersimpan di folder '{RESULT_DIR}'")


def get_duration(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    return float(probe.stdout.strip())


def buat_satu_video(musik_files):
    cache = load_cache()

    # ── pilih background random ───────────────────────────────────────────────
    bg_video_path, bg_filename = pick_bg_video()
    print(f"Background: {bg_filename}")

    # ── output path ──────────────────────────────────────────────────────────
    n = 1
    while os.path.exists(os.path.join(RESULT_DIR, f"project-{n}.mp4")):
        n += 1
    output_path = os.path.join(RESULT_DIR, f"project-{n}.mp4")
    print(f"Output: project-{n}.mp4")

    # ── pilih musik ──────────────────────────────────────────────────────────
    used_music = cache.get("used_music", [])

    if not loop_random_music:
        sisa = [m for m in musik_files if m not in used_music]

        if not sisa:
           print("\nSemua musik telah digunakan untuk dijadikan video.")
           print("Silahkan tambahkan musik baru dulu lalu jalankan kembali.\n")
           return None

        chosen_musik = sisa[0]
        used_music.append(chosen_musik)
        cache["used_music"] = used_music

    else:
        last_musik   = cache.get("last_musik", "")
        kandidat     = [m for m in musik_files if m != last_musik] or musik_files
        chosen_musik = random.choice(kandidat)

    music_path   = os.path.join(MUSIK_DIR, chosen_musik)
    print(f"Musik : {chosen_musik}")

    # ── durasi musik ─────────────────────────────────────────────────────────
    dur    = get_duration(music_path)
    frames = int(dur * FPS)
    print(f"Durasi: {dur:.1f}s | {frames} frames")

    # ── durasi background & hitung kecepatan ─────────────────────────────────
    bg_dur = get_duration(bg_video_path)
    if bg_dur < dur:
        setpts = dur / bg_dur
        vf = f"setpts={setpts:.6f}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    else:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    # ══════════════════════════════════════════════════════════════════════════
    # VARIASI RANDOM — disimpan ke cache agar setiap video berbeda
    # ══════════════════════════════════════════════════════════════════════════

    PALETTES = [
        [(120, 220, 255), (180, 120, 255), (100, 255, 180)],
        [(255, 160, 100), (255, 100, 160), (100, 200, 255)],
        [(140, 255, 200), (120, 160, 255), (255, 200, 100)],
        [(255, 120, 180), (120, 220, 255), (180, 255, 140)],
        [(200, 160, 255), (100, 220, 220), (255, 180, 100)],
        [(255, 210, 100), (100, 200, 255), (200, 120, 255)],
    ]
    last_pi = cache.get("last_palette_idx", -1)
    pi      = random.choice([i for i in range(len(PALETTES)) if i != last_pi])
    colors  = PALETTES[pi]

    # Warna karakter — random tiap video, tersimpan di cache
    SHIRT_PALETTES = [
        (255, 80,  80),   # merah
        (80,  150, 255),  # biru
        (80,  220, 120),  # hijau
        (255, 200, 50),   # kuning
        (200, 80,  255),  # ungu
        (255, 140, 50),   # oranye
        (50,  220, 220),  # cyan
        (255, 80,  180),  # pink
    ]
    last_shirt_idx = cache.get("last_shirt_idx", -1)
    shirt_indices  = [i for i in range(len(SHIRT_PALETTES)) if i != last_shirt_idx]
    # Pilih 4 warna baju berbeda untuk 4 tipe karakter
    chosen_shirt_indices = random.sample(shirt_indices if len(shirt_indices) >= 4
                                         else list(range(len(SHIRT_PALETTES))), 4)
    CHAR_COLORS = [SHIRT_PALETTES[i] for i in chosen_shirt_indices]

    # Warna line/track — random tiap video
    LINE_COLORS = [
        colors[i % len(colors)] for i in range(4)
    ]

    TEXTS = [
        "try use this song",
        "save this song",
    ]
    last_text   = cache.get("last_text", "")
    bottom_text = random.choice([t for t in TEXTS if t != last_text] or TEXTS)

    SUB_TEXT_OPTIONS = [
        "♪ drop a comment if u vibe",
        "♪ tap subscribe for magic ♪",
        "♪ save this for ur next vid ♪",
    ]
    last_sub = cache.get("last_sub_text", "")
    sub_text = random.choice(
        [s for s in SUB_TEXT_OPTIONS if s != last_sub] or SUB_TEXT_OPTIONS
    )

    CHANNEL_NAME = "Love Sky"

    STATS_RANGES = [
        ("Subscribers", 1_000_000, 12_000_000),
        ("Views",         500_000,  8_000_000),
        ("Comments",       50_000,    500_000),
    ]
    last_stats = cache.get("last_stats", [0, 0, 0])

    def pick_stat(min_v, max_v, last_v):
        step     = (max_v - min_v) // 4
        quarts   = [min_v + step*qi for qi in range(4)]
        last_q   = max((qi for qi, qv in enumerate(quarts) if last_v >= qv), default=0)
        chosen_q = random.choice([qi for qi in range(4) if qi != last_q])
        return random.randint(quarts[chosen_q], quarts[chosen_q] + step)

    stat_vals  = [pick_stat(STATS_RANGES[i][1], STATS_RANGES[i][2], last_stats[i]) for i in range(3)]
    stats_cfg  = [(STATS_RANGES[i][0], stat_vals[i], colors[i]) for i in range(3)]

    last_off    = cache.get("last_offset", -180)
    card_offset = random.choice([o for o in [-220, -180, -140, -100] if abs(o - last_off) > 30] or [-180])

    # ── Petir: kapan kesambar (random interval, bukan terus-terusan) ──────────
    # Setiap kejadian petir berlangsung ~1.5 detik, lalu respawn normal
    LIGHTNING_INTERVAL_MIN = 6.0   # minimal jeda antar petir (detik)
    LIGHTNING_INTERVAL_MAX = 14.0  # maksimal jeda
    lightning_events = []          # list waktu mulai kejadian petir
    t_cursor = random.uniform(2.0, 5.0)
    while t_cursor < dur - 3.0:
        lightning_events.append(t_cursor)
        t_cursor += random.uniform(LIGHTNING_INTERVAL_MIN, LIGHTNING_INTERVAL_MAX)

    # ── Snowball: posisi awal random ────────────────────────────────────────
    snowball_seed = random.random()

    # ── Karakter lari bergerombol: jumlah & warna random ───────────────────
    GROUP_COUNT = random.randint(3, 5)
    group_offsets = [random.uniform(0, 0.8) for _ in range(GROUP_COUNT)]  # fase awal

    # Simpan cache
    save_cache({
        "last_musik":        chosen_musik,
        "used_music": cache.get("used_music", []),
        "last_bg":           bg_filename,
        "last_palette_idx":  pi,
        "last_shirt_idx":    chosen_shirt_indices[0],
        "last_text":         bottom_text,
        "last_sub_text":     sub_text,
        "last_stats":        stat_vals,
        "last_offset":       card_offset,
        "project_count":     n,
        "uploaded":          cache.get("uploaded", []),
    })

    # ══════════════════════════════════════════════════════════════════════════
    # FONT
    # ══════════════════════════════════════════════════════════════════════════

    font_path = next((f for f in [
        os.path.expanduser("~/.termux/font.ttf"),
        "/system/fonts/Roboto-Bold.ttf",
        "/system/fonts/NotoSans-Bold.ttf",
        "/system/fonts/DroidSans-Bold.ttf",
    ] if os.path.exists(f)), None)

    def fnt(size):
        if font_path:
            try: return ImageFont.truetype(font_path, size)
            except: pass
        try: return ImageFont.load_default(size=size)
        except: return ImageFont.load_default()

    F_LABEL      = fnt(22)
    F_NUMBER     = fnt(52)
    F_MAIN       = fnt(48)
    F_SUB        = fnt(24)
    F_TIME       = fnt(22)
    F_CHANNEL    = fnt(30)
    F_CHANNEL_SM = fnt(18)

    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT — card diperkecil
    # ══════════════════════════════════════════════════════════════════════════

    CARD_W  = 820    # diperkecil dari 860
    CARD_H  = 128    # diperkecil dari 148
    GAP     = 14
    CARD_X  = (W - CARD_W) // 2
    TOTAL_H = 3 * CARD_H + 2 * GAP
    START_Y = (H - TOTAL_H) // 2 + card_offset

    CARD_RADIUS = 28  # sudut bulat

    # ══════════════════════════════════════════════════════════════════════════
    # HELPER DRAW
    # ══════════════════════════════════════════════════════════════════════════

    def rr(draw, x1, y1, x2, y2, r, fill):
        r = max(1, min(r, (x2-x1)//2, (y2-y1)//2))
        draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
        draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
        draw.ellipse([x1, y1, x1+2*r, y1+2*r], fill=fill)
        draw.ellipse([x2-2*r, y1, x2, y1+2*r], fill=fill)
        draw.ellipse([x1, y2-2*r, x1+2*r, y2], fill=fill)
        draw.ellipse([x2-2*r, y2-2*r, x2, y2], fill=fill)

    def rr_outline(draw, x1, y1, x2, y2, r, outline, width=2):
        r = max(1, min(r, (x2-x1)//2, (y2-y1)//2))
        draw.rectangle([x1+r, y1, x2-r, y1+width], fill=outline)
        draw.rectangle([x1+r, y2-width, x2-r, y2], fill=outline)
        draw.rectangle([x1, y1+r, x1+width, y2-r], fill=outline)
        draw.rectangle([x2-width, y1+r, x2, y2-r], fill=outline)
        draw.ellipse([x1, y1, x1+2*r, y1+2*r], outline=outline, width=width)
        draw.ellipse([x2-2*r, y1, x2, y1+2*r], outline=outline, width=width)
        draw.ellipse([x1, y2-2*r, x1+2*r, y2], outline=outline, width=width)
        draw.ellipse([x2-2*r, y2-2*r, x2, y2], outline=outline, width=width)

    def fmt(nb):
        nb = int(nb)
        if nb >= 1_000_000: return f"{nb/1_000_000:.1f}M"
        if nb >= 1_000:     return f"{nb/1_000:.1f}K"
        return str(nb)

    # ══════════════════════════════════════════════════════════════════════════
    # PIXEL SPRITE HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    _CELL   = 3
    _HAIR_C = (60,  35,  10)
    _SKIN_C = (255, 200, 150)
    _EYE_C  = (30,  30,  100)
    _WHT_C  = (255, 255, 255)
    _SHOE_C = (35,  25,  15)

    # ── Running sprite (4 frame) ─────────────────────────────────────────────
    _SPR_RUN = [
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,4,4,4,4,0,0,0],[0,4,4,4,4,4,4,0,0],
         [4,4,4,4,4,0,0,0,0],[0,0,0,4,4,4,4,4,0],[0,0,0,4,4,0,0,0,0],
         [0,0,4,4,0,2,0,0,0],[0,0,4,7,0,2,0,0,0],[0,7,7,0,0,7,7,0,0]],
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,4,4,4,4,0,0,0],[0,4,4,4,4,4,4,0,0],
         [0,4,4,4,4,4,0,0,0],[0,0,4,4,4,4,0,0,0],[0,0,0,4,4,0,0,0,0],
         [0,0,0,2,2,0,0,0,0],[0,0,0,7,7,0,0,0,0],[0,0,7,7,0,0,0,0,0]],
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,4,4,4,4,0,0,0],[0,4,4,4,4,4,4,0,0],
         [0,4,4,4,4,4,4,4,0],[4,4,4,4,4,0,0,0,0],[0,0,0,4,4,0,0,0,0],
         [0,0,2,0,4,4,0,0,0],[0,0,2,0,0,4,7,0,0],[0,2,2,0,0,7,7,0,0]],
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,4,4,4,4,0,0,0],[0,4,4,4,4,4,4,0,0],
         [0,0,4,4,4,4,4,0,0],[0,0,0,4,4,4,0,0,0],[0,0,0,4,4,0,0,0,0],
         [0,0,0,2,2,0,0,0,0],[0,0,0,7,7,0,0,0,0],[0,0,0,0,7,7,0,0,0]],
    ]

    # ── Sitting / breathing sprite (2 frame) ────────────────────────────────
    # Duduk diam, nafas = badan sedikit naik-turun
    _SPR_SIT = [
        # F0 — normal
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,4,4,4,4,0,0,0],[0,0,4,4,4,4,0,0,0],
         [0,0,4,4,4,4,0,0,0],[0,4,4,0,0,4,4,0,0],[0,2,2,0,0,2,2,0,0],
         [0,7,7,0,0,7,7,0,0]],
        # F1 — tarik napas (badan naik 1 px, kepala naik)
        [[0,0,1,1,1,1,0,0,0],[0,1,1,2,2,2,1,0,0],[0,0,2,3,2,3,2,0,0],
         [0,0,2,2,5,2,2,0,0],[0,0,0,0,0,0,0,0,0],[0,0,4,4,4,4,0,0,0],
         [0,0,4,4,4,4,0,0,0],[0,4,4,0,0,4,4,0,0],[0,2,2,0,0,2,2,0,0],
         [0,7,7,0,0,7,7,0,0]],
    ]

    # ── Dead / tengkurep sprite (1 frame) ───────────────────────────────────
    _SPR_DEAD = [
        [0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0],
        [7,7,7,4,4,4,4,2,0],  # badan tergeletak horizontal
        [0,7,4,4,4,4,2,2,1],  # kepala di kanan
        [0,0,2,4,4,2,0,0,0],
        [0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0],
    ]

    # ── Spawn blink sprite (karakter muncul kembali, kedip) ─────────────────
    # Pakai running frame F0 tapi dengan efek alpha

    def draw_pixel_sprite_raw(draw_obj, cx, cy, accent_color, grid, flip_h=False, alpha_factor=1.0):
        """Render sprite grid ke canvas. flip_h=True untuk cermin horizontal."""
        rows = len(grid)
        cols = len(grid[0])
        tw   = cols * _CELL
        th   = rows * _CELL
        ox = cx - tw // 2
        oy = cy - th // 2
        for r, row in enumerate(grid):
            for ci, code in enumerate(row):
                if code == 0: continue
                c = ci if not flip_h else (cols - 1 - ci)
                if   code == 1: col = _HAIR_C
                elif code == 2: col = _SKIN_C
                elif code == 3: col = _EYE_C
                elif code == 5: col = _WHT_C
                elif code == 7: col = _SHOE_C
                else:           col = accent_color
                if alpha_factor < 1.0:
                    a = int(255 * alpha_factor)
                    col = col + (a,)
                draw_obj.rectangle(
                    [ox + c*_CELL, oy + r*_CELL,
                     ox + c*_CELL+_CELL-1, oy + r*_CELL+_CELL-1],
                    fill=col
                )

    def draw_pixel_sprite(draw_obj, cx, cy, accent_color, fidx, flip_h=False):
        grid   = _SPR_RUN[fidx % 4]
        bounce = -2 if fidx % 2 == 0 else 1
        draw_pixel_sprite_raw(draw_obj, cx, cy + bounce, accent_color, grid, flip_h=flip_h)

    def draw_sit_sprite(draw_obj, cx, cy, accent_color, t):
        """Duduk sambil bernafas."""
        breath_rate = 0.4  # siklus/detik nafas lambat
        fidx = int(t * breath_rate * 2) % 2
        grid = _SPR_SIT[fidx]
        # naik sedikit saat tarik napas
        breath_offset = -1 if fidx == 1 else 0
        draw_pixel_sprite_raw(draw_obj, cx, cy + breath_offset, accent_color, grid)

    def draw_dead_sprite(draw_obj, cx, cy, accent_color):
        draw_pixel_sprite_raw(draw_obj, cx, cy, accent_color, _SPR_DEAD)

    # ══════════════════════════════════════════════════════════════════════════
    # KARAKTER 1: KESAMBAR PETIR
    # State machine: RUNNING → LIGHTNING_HIT → DEAD → SPAWN → RUNNING
    # ══════════════════════════════════════════════════════════════════════════

    LIGHTNING_HIT_DUR  = 0.3   # durasi efek cahaya petir
    DEAD_DUR           = 1.2   # durasi tengkurep
    SPAWN_DUR          = 0.8   # durasi kedip saat spawn
    LIGHTNING_TOTAL    = LIGHTNING_HIT_DUR + DEAD_DUR + SPAWN_DUR

    # Posisi track karakter petir — di dalam card pertama
    _lc = CHAR_COLORS[0]  # warna baju karakter petir

    def get_lightning_state(t):
        """Return state karakter petir: ('run', phase), ('hit', phase), ('dead', phase), ('spawn', phase)"""
        for ev_t in lightning_events:
            rel = t - ev_t
            if 0 <= rel < LIGHTNING_HIT_DUR:
                return 'hit', rel / LIGHTNING_HIT_DUR
            if LIGHTNING_HIT_DUR <= rel < LIGHTNING_HIT_DUR + DEAD_DUR:
                return 'dead', (rel - LIGHTNING_HIT_DUR) / DEAD_DUR
            if LIGHTNING_HIT_DUR + DEAD_DUR <= rel < LIGHTNING_TOTAL:
                return 'spawn', (rel - LIGHTNING_HIT_DUR - DEAD_DUR) / SPAWN_DUR
        return 'run', 0.0

    def lightning_x_pos(t):
        """Posisi X karakter petir (lari bolak-balik dalam track)."""
        # Karakter berlari dari kiri ke kanan terus, loop
        speed = 0.12  # fraksi track per detik
        raw   = (t * speed) % 1.0
        # ping-pong: 0→1→0→1
        cycle = (t * speed) % 2.0
        if cycle < 1.0:
            return cycle
        else:
            return 2.0 - cycle

    # ══════════════════════════════════════════════════════════════════════════
    # KARAKTER 2: SNOWBALL
    # State: WALK_LEFT → PICK → WALK_RIGHT → THROW → WALK_LEFT
    # ══════════════════════════════════════════════════════════════════════════

    _sc = CHAR_COLORS[1]  # warna baju karakter snowball

    SNOW_CYCLE = 6.0  # detik per siklus lengkap
    def get_snowball_state(t):
        """Return (state, phase) untuk karakter snowball."""
        phase = (t % SNOW_CYCLE) / SNOW_CYCLE  # 0..1
        # 0.00-0.35: jalan ke kiri
        # 0.35-0.40: ambil bola
        # 0.40-0.75: jalan ke kanan
        # 0.75-0.85: lempar
        # 0.85-1.00: balik ke kiri
        if phase < 0.35:
            return 'walk_left', phase / 0.35
        elif phase < 0.40:
            return 'pick', (phase - 0.35) / 0.05
        elif phase < 0.75:
            return 'walk_right', (phase - 0.40) / 0.35
        elif phase < 0.85:
            return 'throw', (phase - 0.75) / 0.10
        else:
            return 'return', (phase - 0.85) / 0.15

    # ══════════════════════════════════════════════════════════════════════════
    # KARAKTER 3: DUDUK DIAM NAFAS
    # ══════════════════════════════════════════════════════════════════════════

    _bc = CHAR_COLORS[2]  # warna baju karakter duduk

    # ══════════════════════════════════════════════════════════════════════════
    # KARAKTER 4: LARI BERGEROMBOL — loop portal atas→kanan→bawah→kiri→atas
    # ══════════════════════════════════════════════════════════════════════════

    _gc = CHAR_COLORS[3]  # warna baju grup

    GROUP_SPEED  = 0.10  # fraksi perimeter per detik
    GROUP_COLORS_LIST = [
        colors[i % len(colors)] for i in range(GROUP_COUNT)
    ]

    def group_pos_xy(phase_0to1, card_x, card_y, card_w, card_h, margin=22):
        """Hitung koordinat (x, y) karakter di tepi card berdasarkan phase 0..1."""
        # Perimeter: atas(0→1) → kanan(0→1) → bawah(0→1) → kiri(0→1)
        x1 = card_x + margin
        y1 = card_y + margin
        x2 = card_x + card_w - margin
        y2 = card_y + card_h - margin
        perimeter_fracs = [
            (x2 - x1) / (2*(x2-x1) + 2*(y2-y1)),  # atas
            (y2 - y1) / (2*(x2-x1) + 2*(y2-y1)),  # kanan
            (x2 - x1) / (2*(x2-x1) + 2*(y2-y1)),  # bawah
            (y2 - y1) / (2*(x2-x1) + 2*(y2-y1)),  # kiri
        ]
        p = phase_0to1 % 1.0
        acc = 0.0
        # sisi atas
        if p < acc + perimeter_fracs[0]:
            frac = (p - acc) / perimeter_fracs[0]
            return int(x1 + frac * (x2 - x1)), y1, False  # gerak ke kanan
        acc += perimeter_fracs[0]
        # sisi kanan
        if p < acc + perimeter_fracs[1]:
            frac = (p - acc) / perimeter_fracs[1]
            return x2, int(y1 + frac * (y2 - y1)), False
        acc += perimeter_fracs[1]
        # sisi bawah
        if p < acc + perimeter_fracs[2]:
            frac = (p - acc) / perimeter_fracs[2]
            return int(x2 - frac * (x2 - x1)), y2, True  # gerak ke kiri
        acc += perimeter_fracs[2]
        # sisi kiri
        frac = (p - acc) / max(perimeter_fracs[3], 1e-9)
        frac = max(0.0, min(1.0, frac))
        return x1, int(y2 - frac * (y2 - y1)), True  # gerak ke atas (flip)

    # ══════════════════════════════════════════════════════════════════════════
    # FADE IN / FADE OUT
    # ══════════════════════════════════════════════════════════════════════════

    FADE_IN_DUR  = 1.0   # detik fade masuk
    FADE_OUT_DUR = 1.5   # detik fade keluar

    def get_fade_alpha(t):
        """Return alpha overlay hitam (255=hitam total, 0=normal)"""
        if t < FADE_IN_DUR:
            # fade in: hitam → normal
            return int(255 * (1.0 - t / FADE_IN_DUR))
        if t > dur - FADE_OUT_DUR:
            # fade out: normal → hitam
            return int(255 * ((t - (dur - FADE_OUT_DUR)) / FADE_OUT_DUR))
        return 0

    # ══════════════════════════════════════════════════════════════════════════
    # FUNGSI DRAW OVERLAY UTAMA
    # ══════════════════════════════════════════════════════════════════════════

    def draw_overlay(img_rgb, fi):
        t        = fi / FPS
        progress = t / dur

        img  = img_rgb.convert("RGBA")

        # ── Gradient gelap ───────────────────────────────────────────────────
        grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd   = ImageDraw.Draw(grad)
        for y in range(H // 2, H):
            alpha = int(160 * ((y - H // 2) / (H // 2)) ** 1.4)
            gd.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        for y in range(0, H // 4):
            alpha = int(80 * (1 - y / (H // 4)))
            gd.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, grad)

        # ── Card glassmorphism layer ─────────────────────────────────────────
        card_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_layer)

        for i, (label, max_val, color) in enumerate(stats_cfg):
            cy  = START_Y + i * (CARD_H + GAP)
            cx2 = CARD_X + CARD_W
            rr(cd, CARD_X, cy, cx2, cy + CARD_H, CARD_RADIUS, (255, 255, 255, 22))
            rr_outline(cd, CARD_X, cy, cx2, cy + CARD_H, CARD_RADIUS, (255, 255, 255, 55), width=1)
            rr(cd, CARD_X, cy, CARD_X + 5, cy + CARD_H, 4, color + (200,))

        img = Image.alpha_composite(img, card_layer)
        draw = ImageDraw.Draw(img)

        # ════════════════════════════════════════════════════════════════════
        # KARAKTER DI DALAM CARD
        # ════════════════════════════════════════════════════════════════════

        for i, (label, max_val, color) in enumerate(stats_cfg):
            cy  = START_Y + i * (CARD_H + GAP)
            cx2 = CARD_X + CARD_W
            val = progress * max_val

            # Track parameter (pastikan sprite tidak keluar card)
            SPR_HALF_W = (_CELL * 9) // 2 + 2
            SPR_H      = _CELL * 12
            TRK_L      = CARD_X + 28 + SPR_HALF_W
            TRK_R      = CARD_X + CARD_W - 160 - SPR_HALF_W
            trk_range  = max(1, TRK_R - TRK_L)
            trk_y_base = cy + CARD_H - 22   # dasar track, jangan sampai keluar bawah card
            trk_y      = min(trk_y_base, cy + CARD_H - SPR_H // 2 - 6)

            # ──── Card 0: Karakter kesambar petir ───────────────────────────
            if i == 0:
                state, phase = get_lightning_state(t)
                lx_frac = lightning_x_pos(t)
                spr_cx  = TRK_L + int(lx_frac * trk_range)
                spr_cy  = trk_y - SPR_H // 2

                # Garis track
                rr(draw, TRK_L - SPR_HALF_W, trk_y,
                   TRK_R + SPR_HALF_W, trk_y + 3, 1, color + (55,))

                if state == 'run':
                    # Debu di belakang
                    for di in range(1, 4):
                        dx = spr_cx - di * 5 * (1 if lx_frac < 0.5 else -1)
                        da = max(0, 50 - di * 14)
                        draw.ellipse([dx-2, trk_y-2, dx+2, trk_y+1], fill=color + (da,))
                    draw_pixel_sprite(draw, spr_cx, spr_cy, _lc, int(t * 8) % 4,
                                      flip_h=(lx_frac > 0.5))

                elif state == 'hit':
                    # Flash cahaya petir — lingkaran kuning menyilaukan
                    flash_alpha = int(220 * (1.0 - phase))
                    draw.ellipse([spr_cx - 22, spr_cy - 22, spr_cx + 22, spr_cy + 22],
                                 fill=(255, 255, 100, flash_alpha))
                    # Zigzag petir sederhana
                    bolt_pts = [
                        (spr_cx, cy + 6),
                        (spr_cx - 6, cy + 14),
                        (spr_cx + 4, cy + 22),
                        (spr_cx - 4, spr_cy - 10),
                        (spr_cx, spr_cy - 4),
                    ]
                    for bi in range(len(bolt_pts) - 1):
                        bx1, by1 = bolt_pts[bi]
                        bx2, by2 = bolt_pts[bi+1]
                        draw.line([bx1, by1, bx2, by2],
                                  fill=(255, 255, 0, 240), width=3)
                    # Karakter berkedip (flash)
                    if phase < 0.5:
                        draw_pixel_sprite(draw, spr_cx, spr_cy, (255, 255, 180), 0)
                    else:
                        draw_pixel_sprite(draw, spr_cx, spr_cy, _lc, 0)

                elif state == 'dead':
                    # Jatuh tengkurep — karakter rebah
                    dead_cx = spr_cx
                    dead_cy = trk_y - 5  # rebah di tanah
                    draw_dead_sprite(draw, dead_cx, dead_cy, _lc)
                    # Tanda X di atas
                    if phase < 0.6:
                        xb_alpha = int(200 * (1.0 - phase / 0.6))
                        draw.text((dead_cx - 8, cy + 4), "✕",
                                  font=fnt(18), fill=(255, 60, 60, xb_alpha))

                elif state == 'spawn':
                    # Spawn: kedip-kedip masuk
                    blink_period = 0.15
                    blink_on = (phase % blink_period) < (blink_period * 0.6)
                    if blink_on:
                        alpha_f = phase  # makin solid seiring waktu
                        draw_pixel_sprite_raw(draw, spr_cx, spr_cy, _lc,
                                              _SPR_RUN[0], alpha_factor=min(1.0, alpha_f * 2))
                    # Lingkaran spawn
                    ring_r = int(18 * (1.0 - phase))
                    if ring_r > 2:
                        draw.ellipse([spr_cx - ring_r, spr_cy - ring_r,
                                      spr_cx + ring_r, spr_cy + ring_r],
                                     outline=(150, 220, 255, int(160 * (1.0 - phase))),
                                     width=2)

            # ──── Card 1: Karakter Snowball ──────────────────────────────────
            elif i == 1:
                snow_state, snow_phase = get_snowball_state(t)

                # Posisi berdasarkan state
                if snow_state == 'walk_left':
                    spr_cx = TRK_R - int(snow_phase * (TRK_R - TRK_L) * 0.8)
                elif snow_state == 'pick':
                    spr_cx = TRK_L + 12
                elif snow_state == 'walk_right':
                    spr_cx = TRK_L + int(snow_phase * (TRK_R - TRK_L) * 0.9)
                elif snow_state == 'throw':
                    spr_cx = TRK_R - 20
                else:  # return
                    spr_cx = TRK_R - int(snow_phase * (TRK_R - TRK_L) * 0.15)
                spr_cx = max(TRK_L, min(TRK_R, spr_cx))
                spr_cy = trk_y - SPR_H // 2

                # Track
                rr(draw, TRK_L - SPR_HALF_W, trk_y,
                   TRK_R + SPR_HALF_W, trk_y + 3, 1, color + (55,))

                # Bola salju (muncul saat pick, hilang saat throw)
                has_snowball = snow_state in ('walk_right', 'return') or (snow_state == 'pick' and snow_phase > 0.5)
                if has_snowball:
                    # Bola di tangan kanan karakter
                    ball_x = spr_cx + 12
                    ball_y = spr_cy + 10
                    draw.ellipse([ball_x - 7, ball_y - 7, ball_x + 7, ball_y + 7],
                                 fill=(220, 240, 255, 220))
                    draw.ellipse([ball_x - 7, ball_y - 7, ball_x + 7, ball_y + 7],
                                 outline=(180, 200, 255, 180), width=1)

                if snow_state == 'throw':
                    # Animasi lempar — bola terbang ke kanan
                    throw_dist = int(snow_phase * 60)
                    bx = spr_cx + 14 + throw_dist
                    by = spr_cy + 8 - int(snow_phase * 20)  # parabola kecil
                    bx = min(bx, TRK_R + 20)
                    draw.ellipse([bx - 7, by - 7, bx + 7, by + 7],
                                 fill=(220, 240, 255, int(220 * (1.0 - snow_phase))))

                # Sprite arah sesuai state
                flip = snow_state in ('walk_left', 'return', 'pick')
                draw_pixel_sprite(draw, spr_cx, spr_cy, _sc, int(t * 8) % 4, flip_h=flip)

            # ──── Card 2: Karakter duduk diam nafas ─────────────────────────
            elif i == 2:
                # Posisi tengah kiri track
                sit_cx = TRK_L + 30
                sit_cy = trk_y - 14  # duduk, sedikit lebih rendah

                # Bayangannya
                draw.ellipse([sit_cx - 13, trk_y, sit_cx + 13, trk_y + 4],
                             fill=(0, 0, 0, 40))
                draw_sit_sprite(draw, sit_cx, sit_cy, _bc, t)

                # Efek napas — lingkaran kecil keluar dari mulut
                breath_t  = (t * 0.4) % 1.0
                if breath_t > 0.5:
                    bp    = (breath_t - 0.5) / 0.5
                    br_x  = sit_cx + 8
                    br_y  = sit_cy - 2
                    br_r  = int(3 + bp * 8)
                    ba    = int(80 * (1.0 - bp))
                    draw.ellipse([br_x, br_y - br_r, br_x + br_r * 2, br_y + br_r],
                                 fill=(200, 220, 255, ba))

                # Track tetap ada (lebih tipis)
                rr(draw, TRK_L - SPR_HALF_W, trk_y,
                   TRK_R + SPR_HALF_W, trk_y + 3, 1, color + (30,))

            # ── Angka statistik di kanan card ────────────────────────────────
            num_x = CARD_X + CARD_W - 145
            num_y = cy + (CARD_H - 52) // 2
            # Pastikan teks tidak keluar card
            num_y = max(cy + 6, min(cy + CARD_H - 58, num_y))
            draw.text((num_x, num_y), fmt(val), font=F_NUMBER, fill=(255, 255, 255))

        # ════════════════════════════════════════════════════════════════════
        # KARAKTER BERGEROMBOL — lari loop di luar card, antara card & teks
        # ════════════════════════════════════════════════════════════════════

        # Area loop: di seputar semua card
        loop_x1 = CARD_X + 10
        loop_y1 = START_Y + 10
        loop_x2 = CARD_X + CARD_W - 10
        loop_y2 = START_Y + TOTAL_H - 10

        for gi in range(GROUP_COUNT):
            raw_phase = (t * GROUP_SPEED + group_offsets[gi]) % 1.0
            gx, gy, gflip = group_pos_xy(raw_phase, loop_x1, loop_y1,
                                          loop_x2 - loop_x1, loop_y2 - loop_y1)
            # Warna baju grup — alternasi dari colors
            gc = GROUP_COLORS_LIST[gi % len(GROUP_COLORS_LIST)]
            draw_pixel_sprite(draw, gx, gy, gc,
                              int((t * 8 + gi * 1.3)) % 4, flip_h=gflip)

            # "Portal" effect di sudut kiri & kanan — lingkaran kecil
            if abs(gx - loop_x1) < 12 or abs(gx - loop_x2) < 12:
                portal_alpha = int(80 * abs(math.sin(t * 4 + gi)))
                draw.ellipse([gx - 10, gy - 10, gx + 10, gy + 10],
                             outline=gc + (portal_alpha,), width=2)

        # ════════════════════════════════════════════════════════════════════
        # TEKS UTAMA BAWAH
        # ════════════════════════════════════════════════════════════════════

        TEXT_Y = START_Y + TOTAL_H + 44

        bt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        btd = ImageDraw.Draw(bt_layer)
        bb  = draw.textbbox((0, 0), bottom_text, font=F_MAIN)
        tw  = bb[2] - bb[0]
        th  = bb[3] - bb[1]
        tx  = (W - tw) // 2
        pad_x, pad_y = 32, 14
        rr(btd, tx - pad_x, TEXT_Y - pad_y,
           tx + tw + pad_x, TEXT_Y + th + pad_y, 20, (0, 0, 0, 140))
        rr_outline(btd, tx - pad_x, TEXT_Y - pad_y,
                   tx + tw + pad_x, TEXT_Y + th + pad_y, 20,
                   (255, 255, 255, 40), width=1)
        img = Image.alpha_composite(img, bt_layer)
        draw = ImageDraw.Draw(img)

        draw.text((tx, TEXT_Y), bottom_text, font=F_MAIN, fill=(255, 255, 255))

        # ── Sub text ─────────────────────────────────────────────────────────
        sub_bb = draw.textbbox((0, 0), sub_text, font=F_SUB)
        sw     = sub_bb[2] - sub_bb[0]
        sx     = (W - sw) // 2
        sy     = TEXT_Y + th + pad_y + 12
        draw.text((sx, sy), sub_text, font=F_SUB, fill=(180, 180, 180))

        # ════════════════════════════════════════════════════════════════════
        # ════════════════════════════════════════════════════════════════════
        # CHANNEL NAME — simple seperti sub text + bintang
        # ════════════════════════════════════════════════════════════════════

        channel_text = "♦ Love Sky ♦"

        ch_bb = draw.textbbox((0, 0), channel_text, font=F_SUB)
        ch_w  = ch_bb[2] - ch_bb[0]

        ch_x = (W - ch_w) // 2
        ch_y = sy + 38

        # warna abu-abu mirip sub text
        draw.text((ch_x, ch_y), channel_text, font=F_SUB, fill=(180, 180, 180))
        # ════════════════════════════════════════════════════════════════════
        # PROGRESS BAR BAWAH
        # ════════════════════════════════════════════════════════════════════

        bar_y = H - 80
        bar_x = 70
        bar_w = W - 140
        bar_h = 5
        rr(draw, bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, 3, (255, 255, 255, 35))
        px = int(bar_w * progress)
        if px > 6:
            accent = colors[0]
            rr(draw, bar_x, bar_y, bar_x + px, bar_y + bar_h, 3, accent)
            draw.ellipse([bar_x + px - 9, bar_y - 5,
                          bar_x + px + 9, bar_y + bar_h + 5], fill=accent)

        elapsed = f"{int(t//60)}:{int(t%60):02d}"
        total_s = f"{int(dur//60)}:{int(dur%60):02d}"
        draw.text((bar_x, bar_y + 12), elapsed, font=F_TIME, fill=(180, 180, 180))
        eb = draw.textbbox((0, 0), total_s, font=F_TIME)
        draw.text((bar_x + bar_w - (eb[2] - eb[0]), bar_y + 12),
                  total_s, font=F_TIME, fill=(180, 180, 180))

        # ════════════════════════════════════════════════════════════════════
        # FADE IN / FADE OUT — layer hitam di atas semua
        # ════════════════════════════════════════════════════════════════════

        fade_alpha = get_fade_alpha(t)
        if fade_alpha > 0:
            fade_layer = Image.new("RGBA", (W, H), (0, 0, 0, fade_alpha))
            img = Image.alpha_composite(img, fade_layer)

        return img.convert("RGB")

    # ── Buka pipe background ──────────────────────────────────────────────────
    bg_cmd = [
        "ffmpeg", "-y",
        "-i", bg_video_path,
        "-t", str(dur),
        "-vf", vf,
        "-r", str(FPS),
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-an",
        "pipe:1",
    ]
    bg_proc = subprocess.Popen(bg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ── Buka pipe output ──────────────────────────────────────────────────────
    out_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "pipe:0",
        "-i", music_path,
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]
    out_proc = subprocess.Popen(out_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ── Render frame per frame ────────────────────────────────────────────────
    frame_bytes = W * H * 3
    for i in range(frames):
        raw = b""
        while len(raw) < frame_bytes:
            chunk = bg_proc.stdout.read(frame_bytes - len(raw))
            if not chunk:
                raw += b"\x00" * (frame_bytes - len(raw))
                break
            raw += chunk

        bg_frame = Image.frombytes("RGB", (W, H), raw)
        result   = draw_overlay(bg_frame, i)
        out_proc.stdin.write(result.tobytes())

        if i % 10 == 0:
            pct = i * 100 // frames
            bar = "█" * (pct//5) + "░" * (20 - pct//5)
            print(f"  [{bar}] {pct}%", end="\r")

    bg_proc.stdout.close()
    bg_proc.wait()
    out_proc.stdin.close()
    out_proc.wait()

    if out_proc.returncode == 0:
        mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"\n  Selesai: project-{n}.mp4 ({mb:.1f} MB) | {bottom_text}")
        return output_path, f"project-{n}.mp4"
    else:
        print("\n  Error encode."); sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD SATU FILE
# ══════════════════════════════════════════════════════════════════════════════

def upload_file(filepath, filename, submit_url, title, description, category, tags_str, playlist_id):
    try:
        import requests
    except ImportError:
        print("Install dulu: pip install requests --break-system-packages"); sys.exit(1)

    cfg     = load_config()
    api_key = load_data_txt().get("api_key", "")

    mb = os.path.getsize(filepath) / 1024 / 1024
    print(f"  Mengupload {filename} ({mb:.1f} MB)...")

    try:
        with open(filepath, "rb") as f:
            files   = {"video": (filename, f, "video/mp4")}
            data    = {
                "timer_value": str(cfg.get("timer_value", 15)),
                "timer_unit":  cfg.get("timer_unit", "hours"),
                "title":       title,
                "description": description,
                "category":    category,
                "tags":        tags_str,
                "playlist_id": playlist_id,
            }
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key

            resp = requests.post(submit_url, files=files, data=data,
                                 headers=headers, timeout=120)

        result = resp.json()
        if result.get("success"):
            print(f"  Berhasil | queue_id: {result.get('queue_id', '-')}")
            print(f"  {result.get('message', '')}")
            return True
        elif result.get("duplicate"):
            print(f"  Duplikat — dilewati")
            return True
        else:
            print(f"  Gagal: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"  Error: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 2 — UPLOAD KE API KOYEB
# ══════════════════════════════════════════════════════════════════════════════

def menu_upload():
    title       = "Use this sound you will go viral 🎵 #shorts"
    description = "Use this sound and go viral 🔥 Save this for your next video! #shorts #viral #sound #music #fyp #foryou #youtubeshorts #trending"
    category    = "22"
    playlist_id = "PLKoSMe2lPRm_GT30XcdNBDNfqkOh9TlPe"
    tags_str    = ",".join([
        "shorts","viral","sound","music","fyp","foryou","foryoupage",
        "youtubeshorts","trending","trythissong","usethissong","musicedit",
        "songoftheday","vibes","aesthetic","gamingmusic","gamingvibes",
        "musicshorts","chill","chillmusic","epicmusic","edit","viralshorts",
        "gaming","thelastofus","tlou","ghostoftsushima","ps5","playstation",
        "gamer","videogames","ncs",
    ])

    os.makedirs(RESULT_DIR, exist_ok=True)
    cache    = load_cache()
    uploaded = set(cache.get("uploaded", []))

    semua = sorted([f for f in os.listdir(RESULT_DIR) if f.lower().endswith(".mp4")])
    belum = [f for f in semua if f not in uploaded]

    if not belum:
        print(f"\nTidak ada video baru di folder '{RESULT_DIR}'.")
        print(f"Total sudah terupload: {len(uploaded)} video")
        return

    cfg       = load_config()
    koyeb_url = load_data_txt().get("url", "").rstrip("/")
    if not koyeb_url:
        print("\n  ⚠  url belum diisi di data.txt")
        return

    print(f"\n{'─'*40}")
    print(f"  Video siap upload : {len(belum)}")
    print(f"  Sudah terupload   : {len(uploaded)}")
    print(f"  Koyeb URL         : {koyeb_url}")
    print(f"  Timer             : {cfg.get('timer_value',15)} {cfg.get('timer_unit','hours')} per video")
    print(f"{'─'*40}")

    konfirm = input(f"Upload {len(belum)} video? [y/n]: ").strip().lower()
    if konfirm != "y":
        print("Dibatalkan."); return

    submit_url = f"{koyeb_url}/api/v1/submit"

    for idx, filename in enumerate(belum, 1):
        filepath = os.path.join(RESULT_DIR, filename)
        print(f"\n[{idx}/{len(belum)}]", end=" ")
        berhasil = upload_file(filepath, filename, submit_url, title, description,
                               category, tags_str, playlist_id)
        if berhasil:
            uploaded.add(filename)
            try:
                os.remove(filepath)
                print(f"  File dihapus: {filename}")
            except Exception as e:
                print(f"  Gagal hapus file: {e}")

        cache["uploaded"] = list(uploaded)
        save_cache(cache)

        if idx < len(belum):
            print("  Jeda 3 detik...")
            time.sleep(3)

    print(f"\n{'─'*40}")
    print(f"  Total terupload: {len(uploaded)} video")

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 3 — AUTO LOOP
# ══════════════════════════════════════════════════════════════════════════════

def menu_auto():
    if not shutil.which("ffmpeg"):
        print("ffmpeg tidak ditemukan. Jalankan: pkg install ffmpeg"); sys.exit(1)

    try:
        import requests  # noqa: F401
    except ImportError:
        print("Install dulu: pip install requests --break-system-packages"); sys.exit(1)

    try:
        jumlah_per_loop = int(input("\nBuat berapa video per loop? (default 1): ").strip() or "1")
        if jumlah_per_loop < 1: raise ValueError
    except ValueError:
        jumlah_per_loop = 1

    title       = "Use this sound you will go viral 🎵 #shorts"
    description = "Use this sound and go viral 🔥 Save this for your next video! #shorts #viral #sound #music #fyp #foryou #youtubeshorts #trending"
    category    = "22"
    playlist_id = "PLKoSMe2lPRm_GT30XcdNBDNfqkOh9TlPe"
    tags_str    = ",".join([
        "shorts","viral","sound","music","fyp","foryou","foryoupage",
        "youtubeshorts","trending","trythissong","usethissong","musicedit",
        "songoftheday","vibes","aesthetic","gamingmusic","gamingvibes",
        "musicshorts","chill","chillmusic","epicmusic","edit","viralshorts",
        "gaming","thelastofus","tlou","ghostoftsushima","ps5","playstation",
        "gamer","videogames","ncs",
    ])

    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(MUSIK_DIR,  exist_ok=True)

    EXT_VALID   = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac")
    musik_files = [f for f in os.listdir(MUSIK_DIR) if f.lower().endswith(EXT_VALID)]
    if not musik_files:
        print(f"Tidak ada file musik di folder '{MUSIK_DIR}'!"); sys.exit(1)

    submit_url = f"{load_data_txt().get('url','').rstrip('/')}/api/v1/submit"
    loop_ke    = 0

    print(f"\n{'═'*40}")
    print(f"  MODE AUTO — tekan Ctrl+C untuk berhenti")
    print(f"  Video per loop : {jumlah_per_loop}")
    print(f"{'═'*40}\n")

    try:
        while True:
            loop_ke += 1
            print(f"\n{'═'*40}")
            print(f"  LOOP #{loop_ke}")
            print(f"{'═'*40}")

            video_dibuat = []
            for i in range(jumlah_per_loop):
                print(f"\n  [Buat {i+1}/{jumlah_per_loop}]")
                hasil = buat_satu_video(musik_files)

                if hasil is None and not loop_random_music:
                    print("Auto dihentikan karena semua musik sudah dipakai.")
                    break

                if hasil:
                    video_dibuat.append(hasil)

            if not video_dibuat:
                print("  Tidak ada video yang berhasil dibuat, skip upload.")
                time.sleep(5)
                continue

            print(f"\n  Upload {len(video_dibuat)} video...")
            cache    = load_cache()
            uploaded = set(cache.get("uploaded", []))

            for filepath, filename in video_dibuat:
                print(f"\n  →", end=" ")
                berhasil = upload_file(filepath, filename, submit_url, title,
                                       description, category, tags_str, playlist_id)
                if berhasil:
                    uploaded.add(filename)
                    try:
                        os.remove(filepath)
                        print(f"  File dihapus: {filename}")
                    except Exception as e:
                        print(f"  Gagal hapus file: {e}")
                else:
                    print(f"  Upload gagal, file TIDAK dihapus: {filename}")

                cache["uploaded"] = list(uploaded)
                save_cache(cache)
                time.sleep(3)

            print(f"\n  Loop #{loop_ke} selesai. Total terupload: {len(uploaded)}")
            print("  Lanjut loop berikutnya...\n")
            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n\n  Auto mode dihentikan. Total loop: {loop_ke}")
        cache = load_cache()
        print(f"  Total video terupload: {len(cache.get('uploaded', []))}")

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()