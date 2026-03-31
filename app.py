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
# ══════════════════════════════════════════════════════════════════════════════

MUSIK_DIR   = "./musik"
RESULT_DIR  = "./result"
CACHE_FILE  = "./cache.txt"
BG_DIR      = "./background"
CONFIG_FILE = "./config.json"
DATA_FILE   = "./data.txt"    # kredensial sensitif (github token, koyeb url)

GITHUB_API  = "https://api.github.com"

# File/folder yang di-exclude saat upload ke GitHub
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
# DATA.TXT — kredensial sensitif (tidak di-upload ke GitHub)
# Format:
#   github=ghp_xxxxx
#   url=https://your-app.koyeb.app
# ══════════════════════════════════════════════════════════════════════════════

def load_data_txt() -> dict:
    """Baca data.txt, return dict {github: ..., url: ...}"""
    result = {"github": "", "url": ""}
    if not os.path.exists(DATA_FILE):
        # Buat template kosong
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
            # Tambah key baru yang belum ada
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
    """Encode karakter khusus di path (misal # jadi %23) tapi jaga slash."""
    from urllib.parse import quote
    return "/".join(quote(part, safe="") for part in path.split("/"))

def gh_get_file(repo_path):
    """Ambil konten + sha satu file dari GitHub. Return (content_bytes, sha) atau (None, None)."""
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
    """Upload/update satu file ke GitHub."""
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
    """List isi folder di GitHub. Return list of {name, path, sha, download_url}."""
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

    print(f"  {len(to_upload)} file akan di-upload...\n")

    ok_count = err_count = 0
    for local_path, repo_path in to_upload:
        try:
            with open(local_path, "rb") as f:
                content_bytes = f.read()
            _, sha = gh_get_file(repo_path)
            ok, _ = gh_put_file(repo_path, content_bytes, f"[auto] update {repo_path}", sha)
            status = "✓" if ok else "✗"
            if ok: ok_count += 1
            else:  err_count += 1
        except Exception as e:
            status = "✗"
            err_count += 1
            print(f"  {status} {repo_path} — {e}")
            continue
        print(f"  {status} {repo_path}")

    print(f"\n  Selesai! {ok_count} berhasil, {err_count} gagal.")

# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN 5 — UPDATE BACKGROUND/MUSIK DARI GITHUB
# ══════════════════════════════════════════════════════════════════════════════

def sync_assets_from_github(silent=False):
    """
    Ambil file baru di folder background/ dan musik/ dari GitHub.
    Hanya download file yang belum ada di lokal (berdasarkan nama file).
    Return (bg_new, mus_new) — jumlah file baru.
    """
    import base64

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
            # Download
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
# AUTO UPDATE THREAD (config.json → auto_update_github: true)
# ══════════════════════════════════════════════════════════════════════════════

_auto_update_last = 0

def _auto_update_loop():
    global _auto_update_last
    import threading
    interval = 10 * 60  # 10 menit
    while True:
        time.sleep(60)  # cek setiap 1 menit apakah sudah 10 menit
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
    """Pilih satu file .mp4 random dari folder ./background/"""
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
    # Jalankan auto-update thread di background
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
        print(f"BG slowmo: {setpts:.2f}x (bg {bg_dur:.1f}s -> {dur:.1f}s)")
    else:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        print(f"BG cut: {bg_dur:.1f}s -> {dur:.1f}s")

    # ── variasi anti-duplikasi ───────────────────────────────────────────────
    PALETTES = [
        [(220,30,30),  (50,130,255), (50,200,100)],
        [(255,80,0),   (120,40,220), (0,200,200)],
        [(220,30,80),  (30,180,255), (180,220,0)],
        [(255,200,0),  (200,50,200), (0,200,150)],
        [(30,200,255), (255,60,120), (120,255,80)],
        [(80,255,200), (255,140,0),  (140,80,255)],
    ]
    last_pi = cache.get("last_palette_idx", -1)
    pi      = random.choice([i for i in range(len(PALETTES)) if i != last_pi])
    colors  = PALETTES[pi]

    TEXTS = [
        "try use this song",
        "use this song for your video",
        "save this song",
    ]
    last_text   = cache.get("last_text", "")
    bottom_text = random.choice([t for t in TEXTS if t != last_text] or TEXTS)

    STATS_RANGES = [
        ("Subscribe", 1_000_000, 12_000_000),
        ("Views",       500_000,  8_000_000),
        ("Comments",     50_000,    500_000),
    ]
    last_stats = cache.get("last_stats", [0, 0, 0])

    def pick_stat(min_v, max_v, last_v):
        step     = (max_v - min_v) // 4
        quarts   = [min_v + step*qi for qi in range(4)]
        last_q   = max((qi for qi, qv in enumerate(quarts) if last_v >= qv), default=0)
        chosen_q = random.choice([qi for qi in range(4) if qi != last_q])
        return random.randint(quarts[chosen_q], quarts[chosen_q] + step)

    stat_vals = [pick_stat(STATS_RANGES[i][1], STATS_RANGES[i][2], last_stats[i]) for i in range(3)]
    stats_cfg = [(STATS_RANGES[i][0], stat_vals[i], colors[i]) for i in range(3)]

    last_dot = cache.get("last_dot_r", 52)
    dot_r    = random.choice([r for r in [44, 48, 52, 56, 60] if abs(r - last_dot) > 4] or [52])

    last_gap = cache.get("last_gap", 34)
    gap      = random.choice([g for g in [26, 30, 34, 38, 42] if abs(g - last_gap) > 4] or [34])

    last_off    = cache.get("last_offset", -200)
    card_offset = random.choice([o for o in [-240, -200, -160, -120] if abs(o - last_off) > 30] or [-200])

    # simpan cache
    save_cache({
        "last_musik":       chosen_musik,
        "last_bg":          bg_filename,
        "last_palette_idx": pi,
        "last_text":        bottom_text,
        "last_stats":       stat_vals,
        "last_dot_r":       dot_r,
        "last_gap":         gap,
        "last_offset":      card_offset,
        "project_count":    n,
        "uploaded":         cache.get("uploaded", []),
    })

    # ── warna overlay ─────────────────────────────────────────────────────────
    WHITE   = (255, 255, 255)
    GRAY    = (160, 160, 160)
    RED     = colors[0]
    CARD_BG = (20, 20, 20, 200)

    # ── font ─────────────────────────────────────────────────────────────────
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

    F_LABEL  = fnt(38)
    F_NUMBER = fnt(82)
    F_MAIN   = fnt(66)
    F_TIME   = fnt(30)

    # ── layout ────────────────────────────────────────────────────────────────
    CARD_W  = 900
    CARD_H  = 195
    CARD_X  = (W - CARD_W) // 2
    TOTAL_H = 3 * CARD_H + 2 * gap
    START_Y = (H - TOTAL_H) // 2 + card_offset

    def rr(draw, x1, y1, x2, y2, r, fill):
        r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
        draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
        draw.ellipse([x1, y1, x1+2*r, y1+2*r], fill=fill)
        draw.ellipse([x2-2*r, y1, x2, y1+2*r], fill=fill)
        draw.ellipse([x1, y2-2*r, x1+2*r, y2], fill=fill)
        draw.ellipse([x2-2*r, y2-2*r, x2, y2], fill=fill)

    def fmt(nb):
        nb = int(nb)
        if nb >= 1_000_000: return f"{nb/1_000_000:.2f}M"
        if nb >= 1_000:     return f"{nb/1_000:.1f}K"
        return str(nb)

    def draw_overlay(img_rgb, fi):
        """Gambar overlay kartu + teks di atas frame background."""
        t        = fi / FPS
        progress = t / dur

        img  = img_rgb.convert("RGBA")
        card_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd   = ImageDraw.Draw(card_layer)
        draw = ImageDraw.Draw(img)

        # kartu semi-transparan
        for i, (label, max_val, color) in enumerate(stats_cfg):
            cy  = START_Y + i * (CARD_H + gap)
            val = progress * max_val

            rr(cd, CARD_X, cy, CARD_X+CARD_W, cy+CARD_H, 30, CARD_BG)
            rr(cd, CARD_X, cy, CARD_X+10, cy+CARD_H, 5, color + (255,))

        img = Image.alpha_composite(img, card_layer)
        draw = ImageDraw.Draw(img)

        # teks & dot di kartu
        for i, (label, max_val, color) in enumerate(stats_cfg):
            cy     = START_Y + i * (CARD_H + gap)
            val    = progress * max_val
            dot_cx = CARD_X + 55 + dot_r
            dot_cy = cy + CARD_H // 2
            draw.ellipse([dot_cx-dot_r, dot_cy-dot_r,
                          dot_cx+dot_r, dot_cy+dot_r], fill=color)
            tx = dot_cx + dot_r + 30
            draw.text((tx, cy+28), label,    font=F_LABEL,  fill=GRAY)
            draw.text((tx, cy+76), fmt(val), font=F_NUMBER, fill=WHITE)

        # teks bawah (kotak putih)
        bb  = draw.textbbox((0, 0), bottom_text, font=F_MAIN)
        tw  = bb[2]-bb[0]; th = bb[3]-bb[1]
        tx  = (W - tw) // 2
        ty  = START_Y + TOTAL_H + 70
        pad = 28
        rr(draw, tx-pad, ty-pad, tx+tw+pad, ty+th+pad, 22, WHITE)
        draw.text((tx, ty), bottom_text, font=F_MAIN, fill=(15, 15, 15))

        # progress bar
        bar_y = H - 90; bar_x = 80; bar_w = W - 160; bar_h = 10
        rr(draw, bar_x, bar_y, bar_x+bar_w, bar_y+bar_h, 5, (60, 60, 60))
        px = int(bar_w * progress)
        if px > 12:
            rr(draw, bar_x, bar_y, bar_x+px, bar_y+bar_h, 5, RED)
            draw.ellipse([bar_x+px-11, bar_y-5, bar_x+px+11, bar_y+bar_h+5], fill=RED)

        elapsed = f"{int(t//60)}:{int(t%60):02d}"
        total_s = f"{int(dur//60)}:{int(dur%60):02d}"
        draw.text((bar_x, bar_y+16), elapsed, font=F_TIME, fill=(200, 200, 200))
        eb = draw.textbbox((0, 0), total_s, font=F_TIME)
        draw.text((bar_x+bar_w-(eb[2]-eb[0]), bar_y+16), total_s,
                  font=F_TIME, fill=(200, 200, 200))

        return img.convert("RGB")

    # ── buka pipe background ──────────────────────────────────────────────────
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

    # ── buka pipe output ──────────────────────────────────────────────────────
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

    # ── render frame per frame ────────────────────────────────────────────────
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
# UPLOAD SATU FILE — return True jika berhasil/duplikat
# ══════════════════════════════════════════════════════════════════════════════

def upload_file(filepath, filename, submit_url, title, description, category, tags_str, playlist_id):
    try:
        import requests
    except ImportError:
        print("Install dulu: pip install requests --break-system-packages"); sys.exit(1)

    cfg    = load_config()
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
# PILIHAN 2 — UPLOAD KE API KOYEB (hapus file setelah upload)
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

    cfg        = load_config()
    koyeb_url  = load_data_txt().get("url", "").rstrip("/")
    if not koyeb_url:
        print("\n  ⚠  url belum diisi di data.txt\n     Buka data.txt, isi: url=https://your-app.koyeb.app")
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
            # hapus file dari result setelah upload berhasil
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

    submit_url  = f"{load_data_txt().get('url','').rstrip('/')}/api/v1/submit"
    loop_ke     = 0

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

            # ── Step 1: Buat video ────────────────────────────────────────────
            video_dibuat = []
            for i in range(jumlah_per_loop):
                print(f"\n  [Buat {i+1}/{jumlah_per_loop}]")
                hasil = buat_satu_video(musik_files)
                if hasil:
                    video_dibuat.append(hasil)  # (filepath, filename)

            if not video_dibuat:
                print("  Tidak ada video yang berhasil dibuat, skip upload.")
                time.sleep(5)
                continue

            # ── Step 2: Upload & hapus ────────────────────────────────────────
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
