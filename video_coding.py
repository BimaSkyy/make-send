#!/usr/bin/env python3
"""
Coding Video Creator — YouTube Shorts
======================================
- Background dari folder background/ (video, muted, slowmo/cut sesuai durasi musik)
- Musik dari folder musik/ (max 58 detik, otomatis cut)
- Card di tengah mengetik code dari coding.txt (kecepatan sesuai durasi)
- Sticker GIF dari folder sticker/ mengelilingi card
- Selesai ngetik → tombol START → animasi klik → loading → screenshot website

Install:
  pkg install ffmpeg
  pip install pillow requests --break-system-packages

Jalankan:
  python make2.py
"""

import os, sys, json, math, time, shutil, random, subprocess, urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont

# ══════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════

W, H    = 1080, 1920
FPS     = 15
MAX_DUR = 58.0

BG_DIR      = "./background"
MUSIK_DIR   = "./musik"
BAHAN_DIR   = "./bahan"
STICKER_DIR = "./sticker"
CODE_FILE   = "./coding.txt"
CACHE_DIR   = "./cachescreenshot"
RESULT_DIR  = "./result"
TEMP_DIR    = "./temp_frames"

# Warna tema
CARD_BG      = (13, 17, 23, 230)
CARD_BORDER  = (48, 212, 100, 200)
CARD_HEADER  = (22, 27, 34, 255)
CODE_DEFAULT = (201, 209, 217)
BUTTON_COLOR = (35, 134, 54)
BUTTON_GLOW  = (56, 211, 84)

# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def run(cmd, quiet=True):
    kw = dict(capture_output=True) if quiet else {}
    subprocess.run(cmd, **kw)

def get_duration(path):
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True
    )
    return float(json.loads(res.stdout)["format"]["duration"])

def pick_random(folder, exts):
    if not os.path.exists(folder):
        return None
    files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts]
    return random.choice(files) if files else None

def get_font(size):
    candidates = [
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/data/data/com.termux/files/usr/share/fonts/TTF/Hack-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/system/fonts/DroidSansMono.ttf",
        "/system/fonts/RobotoMono-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════
# SCREENSHOT WEBSITE (via API, tanpa Chromium / TCPServer)
# ══════════════════════════════════════════════════════════════════════════

def screenshot_website():
    """
    Upload bahan/index.html ke hosting sementara (file.io),
    lalu screenshot via API zenzxz.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    ss_png = os.path.abspath(os.path.join(CACHE_DIR, "screenshot.png"))
    ss_jpg = os.path.abspath(os.path.join(CACHE_DIR, "screenshot.jpg"))

    index_path = os.path.join(os.path.abspath(BAHAN_DIR), "index.html")
    if not os.path.exists(index_path):
        print("  ⚠  bahan/index.html tidak ditemukan, pakai blank screenshot")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    # ── Step 1: Upload HTML ke file.io ────────────────────────────────────
    print("  Uploading HTML ke file.io...")
    try:
        with open(index_path, "rb") as f:
            upload_res = requests.post(
                "https://file.io",
                files={"file": ("index.html", f, "text/html")},
                timeout=30
            )
        upload_data = upload_res.json()
    except Exception as e:
        print(f"  ⚠  Upload gagal: {e}, pakai blank screenshot")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    if not upload_data.get("success"):
        print(f"  ⚠  Upload gagal: {upload_data}, pakai blank screenshot")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    hosted_url = upload_data["link"]
    print(f"  URL hosting: {hosted_url}")

    # ── Step 2: Screenshot via API zenzxz ────────────────────────────────
    encoded_url = urllib.parse.quote(hosted_url, safe="")
    api_url = f"https://api.zenzxz.my.id/tools/ssweb?url={encoded_url}&device=mobile"

    print("  Requesting screenshot...")
    try:
        ss_res  = requests.get(api_url, timeout=60)
        ss_data = ss_res.json()
    except Exception as e:
        print(f"  ⚠  Screenshot API error: {e}, pakai blank")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    if not ss_data.get("status") or not ss_data.get("result", {}).get("url"):
        print(f"  ⚠  Screenshot API gagal: {ss_data}, pakai blank")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    img_url = ss_data["result"]["url"]
    print(f"  Download screenshot: {img_url}")

    try:
        img_res = requests.get(img_url, timeout=30)
        with open(ss_png, "wb") as f:
            f.write(img_res.content)
    except Exception as e:
        print(f"  ⚠  Download screenshot gagal: {e}, pakai blank")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)
        return ss_jpg

    # ── Step 3: Convert & resize ──────────────────────────────────────────
    try:
        img = Image.open(ss_png).convert("RGB").resize((W, H), Image.LANCZOS)
        img.save(ss_jpg, "JPEG", quality=95)
        os.remove(ss_png)
        print(f"  ✓ Screenshot tersimpan: {ss_jpg}")
    except Exception as e:
        print(f"  ⚠  Gagal proses gambar: {e}, pakai blank")
        Image.new("RGB", (W, H), (20, 20, 30)).save(ss_jpg)

    return ss_jpg

# ══════════════════════════════════════════════════════════════════════════
# BACKGROUND FRAMES
# ══════════════════════════════════════════════════════════════════════════

def extract_bg_frames(video_path, total_frames):
    bg_dir = os.path.join(TEMP_DIR, "bg")
    os.makedirs(bg_dir, exist_ok=True)

    vid_dur    = get_duration(video_path)
    target_dur = total_frames / FPS
    pts_factor = target_dur / vid_dur
    pts_factor = max(0.25, min(4.0, pts_factor))

    vf = (
        f"setpts={pts_factor:.4f}*PTS,"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"fps={FPS}"
    )

    run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf, "-an",
        "-frames:v", str(total_frames),
        os.path.join(bg_dir, "frame_%05d.jpg"),
    ])

    frames = []
    for i in range(1, total_frames + 1):
        p = os.path.join(bg_dir, f"frame_{i:05d}.jpg")
        if os.path.exists(p):
            frames.append(Image.open(p).convert("RGBA").copy())

    if not frames:
        frames = [Image.new("RGBA", (W, H), (20, 20, 30))]
    while len(frames) < total_frames:
        frames.append(frames[len(frames) % len(frames)].copy())

    return frames[:total_frames]

# ══════════════════════════════════════════════════════════════════════════
# STICKER GIF
# ══════════════════════════════════════════════════════════════════════════

def load_stickers():
    result = []
    if not os.path.exists(STICKER_DIR):
        return result

    STICKER_SIZE = 150

    for fname in sorted(os.listdir(STICKER_DIR)):
        if not fname.lower().endswith(".gif"):
            continue
        path = os.path.join(STICKER_DIR, fname)
        try:
            gif    = Image.open(path)
            frames = []
            try:
                while True:
                    f = gif.convert("RGBA").copy()
                    f = f.resize((STICKER_SIZE, STICKER_SIZE), Image.LANCZOS)
                    frames.append(f)
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass
            if frames:
                result.append({"frames": frames, "name": fname})
                print(f"    Sticker: {fname} ({len(frames)} frames)")
        except Exception as e:
            print(f"    ⚠  Gagal load sticker {fname}: {e}")
    return result

def place_stickers(base, stickers, card_rect, frame_idx):
    if not stickers:
        return base

    cx1, cy1, cx2, cy2 = card_rect
    margin = 10
    sz     = 150

    positions = [
        (cx1 - sz - margin, cy1),
        (cx1 - sz - margin, cy1 + (cy2 - cy1)//3),
        (cx1 - sz - margin, cy1 + 2*(cy2 - cy1)//3),
        (cx2 + margin, cy1),
        (cx2 + margin, cy1 + (cy2 - cy1)//3),
        (cx2 + margin, cy1 + 2*(cy2 - cy1)//3),
        (cx1, cy1 - sz - margin),
        (cx1 + (cx2 - cx1)//3, cy1 - sz - margin),
        (cx1 + 2*(cx2 - cx1)//3, cy1 - sz - margin),
        (cx1, cy2 + margin),
        (cx1 + (cx2 - cx1)//3, cy2 + margin),
        (cx1 + 2*(cx2 - cx1)//3, cy2 + margin),
    ]

    for idx, sticker in enumerate(stickers):
        if idx >= len(positions):
            break
        x, y = positions[idx]
        x = max(0, min(W - sz, x))
        y = max(0, min(H - sz, y))
        frame = sticker["frames"][frame_idx % len(sticker["frames"])]
        base.paste(frame, (x, y), frame)

    return base

# ══════════════════════════════════════════════════════════════════════════
# CARD RENDERER
# ══════════════════════════════════════════════════════════════════════════

SYNTAX_COLORS = [
    ("def ",    (86,  156, 214)),
    ("class ",  (86,  156, 214)),
    ("import ", (197, 134, 192)),
    ("from ",   (197, 134, 192)),
    ("return ", (197, 134, 192)),
    ("yield ",  (197, 134, 192)),
    ("for ",    (197, 134, 192)),
    ("while ",  (197, 134, 192)),
    ("if ",     (197, 134, 192)),
    ("elif ",   (197, 134, 192)),
    ("else:",   (197, 134, 192)),
    ("try:",    (197, 134, 192)),
    ("except ", (197, 134, 192)),
    ("#",       (106, 153,  85)),
    ("\"\"\"",  (206, 145,  80)),
]

_font_cache = {}

def cached_font(size):
    if size not in _font_cache:
        _font_cache[size] = get_font(size)
    return _font_cache[size]

def make_card_image(code_so_far, card_w, card_h, show_cursor=True):
    card = Image.new("RGBA", (card_w, card_h), CARD_BG)
    draw = ImageDraw.Draw(card)

    for bw, alpha in [(4, 60), (2, 120), (1, 200)]:
        draw.rectangle([bw//2, bw//2, card_w - bw//2, card_h - bw//2],
                       outline=(*CARD_BORDER[:3], alpha), width=bw)

    draw.rectangle([0, 0, card_w, 38], fill=CARD_HEADER)
    draw.ellipse([12, 11, 26, 25], fill=(255, 90, 80))
    draw.ellipse([34, 11, 48, 25], fill=(255, 190, 40))
    draw.ellipse([56, 11, 70, 25], fill=(48, 200, 60))
    draw.text((88, 10), "coding.txt", font=cached_font(15), fill=(140, 148, 158))

    PAD        = 16
    LINE_H     = 23
    font_code  = cached_font(17)
    font_lnum  = cached_font(13)
    max_lines  = (card_h - 55) // LINE_H
    lines      = code_so_far.split("\n")
    start_line = max(0, len(lines) - max_lines)
    visible    = lines[start_line:]
    line_num_w = 42

    for li, line in enumerate(visible):
        y       = 48 + li * LINE_H
        abs_num = start_line + li + 1
        draw.text((PAD, y + 1), str(abs_num), font=font_lnum, fill=(68, 76, 86))

        stripped = line.lstrip()
        color    = CODE_DEFAULT
        for kw, col in SYNTAX_COLORS:
            if stripped.startswith(kw):
                color = col
                break

        if color == CODE_DEFAULT and stripped.startswith(("'", '"')):
            color = (206, 145, 80)

        draw.text((PAD + line_num_w, y), line, font=font_code, fill=color)

    if show_cursor:
        cursor_y  = 48 + min(len(visible) - 1, max_lines - 1) * LINE_H
        last_line = visible[-1] if visible else ""
        cx = PAD + line_num_w + len(last_line) * 10
        cx = min(cx, card_w - PAD - 14)
        draw.rectangle([cx, cursor_y + 2, cx + 11, cursor_y + LINE_H - 3],
                       fill=(200, 200, 200, 200))

    return card

# ══════════════════════════════════════════════════════════════════════════
# BUTTON ANIMATION FRAMES
# ══════════════════════════════════════════════════════════════════════════

def draw_start_button(base, progress_idle):
    draw = ImageDraw.Draw(base)
    bx, by = W // 2, int(H * 0.82)
    pulse  = 0.5 + 0.5 * math.sin(progress_idle * math.pi * 4)
    glow_r = int(80 + 20 * pulse)
    for r in range(glow_r, glow_r - 25, -5):
        a = max(0, int(50 * (1 - (glow_r - r) / 25) * pulse))
        draw.ellipse([bx - r * 1.5, by - r // 2, bx + r * 1.5, by + r // 2],
                     fill=(*BUTTON_GLOW, a))
    bw, bh = 240, 72
    draw.rounded_rectangle(
        [bx - bw//2, by - bh//2, bx + bw//2, by + bh//2],
        radius=36, fill=BUTTON_COLOR, outline=BUTTON_GLOW, width=3
    )
    draw.text((bx - 68, by - 20), "▶  START", font=cached_font(34), fill=(255, 255, 255))
    return base

def draw_click_anim(base, progress):
    draw  = ImageDraw.Draw(base)
    bx, by = W // 2, int(H * 0.82)
    scale  = 1.0 - 0.35 * progress
    bw, bh = int(240 * scale), int(72 * scale)
    draw.rounded_rectangle(
        [bx - bw//2, by - bh//2, bx + bw//2, by + bh//2],
        radius=int(36 * scale), fill=(25, 100, 40), outline=BUTTON_GLOW, width=2
    )
    fs = max(14, int(34 * scale))
    draw.text((bx - int(68 * scale), by - int(20 * scale)), "▶  START",
              font=cached_font(fs), fill=(180, 255, 180))
    return base

def draw_loading(base, progress):
    draw  = ImageDraw.Draw(base)
    cx, cy = W // 2, int(H * 0.82)
    r      = 38
    n_dot  = 10
    angle  = progress * 360 * 2.5
    for i in range(n_dot):
        a  = math.radians(angle + i * (360 / n_dot))
        x  = int(cx + r * math.cos(a))
        y  = int(cy + r * math.sin(a))
        sz = max(5, int(12 * (i / n_dot)))
        col = (*BUTTON_GLOW, int(255 * (i / n_dot)))
        draw.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col)
    draw.text((cx - 56, cy + 52), "Loading...", font=cached_font(24),
              fill=(*BUTTON_GLOW[:3], 200))
    return base

def draw_reveal(base, screenshot_rgba, progress):
    alpha   = min(255, int(255 * progress))
    overlay = screenshot_rgba.copy()
    overlay.putalpha(alpha)
    base.paste(overlay, (0, 0), overlay)
    return base

# ══════════════════════════════════════════════════════════════════════════
# RENDER SEMUA FRAME
# ══════════════════════════════════════════════════════════════════════════

def render_frames(bg_frames, stickers, code_text, screenshot_img,
                  total_frames, card_rect):
    frames_dir = os.path.join(TEMP_DIR, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    cx1, cy1, cx2, cy2 = card_rect
    card_w = cx2 - cx1
    card_h = cy2 - cy1

    anim_idle_f  = int(1.0 * FPS)
    anim_click_f = int(0.8 * FPS)
    anim_load_f  = int(1.5 * FPS)
    anim_rev_f   = int(1.5 * FPS)
    anim_total   = anim_idle_f + anim_click_f + anim_load_f + anim_rev_f
    typing_frames = total_frames - anim_total

    chars_per_frame = len(code_text) / max(typing_frames, 1)
    dim_layer = Image.new("RGBA", (W, H), (0, 0, 0, 100))

    for i in range(total_frames):
        if i % FPS == 0:
            print(f"  Frame {i:05d}/{total_frames}  ({100*i//total_frames}%)", end="\r")

        bg = bg_frames[i].copy()
        bg = Image.alpha_composite(bg, dim_layer)

        if i < typing_frames:
            chars       = int(i * chars_per_frame)
            code_so_far = code_text[:chars]
            blink       = (i // (FPS // 2)) % 2 == 0
            card        = make_card_image(code_so_far, card_w, card_h, show_cursor=blink)
            bg.paste(card, (cx1, cy1), card)
            bg          = place_stickers(bg, stickers, card_rect, i)
        else:
            card = make_card_image(code_text, card_w, card_h, show_cursor=False)
            bg.paste(card, (cx1, cy1), card)
            bg   = place_stickers(bg, stickers, card_rect, i)

            anim_i = i - typing_frames

            if anim_i < anim_idle_f:
                bg = draw_start_button(bg, anim_i / anim_idle_f)
            elif anim_i < anim_idle_f + anim_click_f:
                bg = draw_click_anim(bg, (anim_i - anim_idle_f) / anim_click_f)
            elif anim_i < anim_idle_f + anim_click_f + anim_load_f:
                bg = draw_loading(bg, (anim_i - anim_idle_f - anim_click_f) / anim_load_f)
            else:
                prog = (anim_i - anim_idle_f - anim_click_f - anim_load_f) / anim_rev_f
                bg   = draw_reveal(bg, screenshot_img, min(1.0, prog))

        out_path = os.path.join(frames_dir, f"frame_{i:05d}.jpg")
        bg.convert("RGB").save(out_path, "JPEG", quality=85)

    print(f"\n  ✓ {total_frames} frame selesai dirender")
    return frames_dir

# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "═" * 52)
    print("  CODING VIDEO CREATOR  ─  YouTube Shorts")
    print("═" * 52)

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg tidak ada — jalankan: pkg install ffmpeg")
        sys.exit(1)

    for d in [BG_DIR, MUSIK_DIR, BAHAN_DIR, STICKER_DIR, RESULT_DIR, TEMP_DIR]:
        os.makedirs(d, exist_ok=True)

    # ── Load coding.txt ──────────────────────────────────────────────────
    if not os.path.exists(CODE_FILE):
        print(f"ERROR: {CODE_FILE} tidak ditemukan!")
        sys.exit(1)
    with open(CODE_FILE, "r", encoding="utf-8") as f:
        code_text = f.read().rstrip()
    print(f"\n  Code   : {len(code_text)} karakter, {code_text.count(chr(10))+1} baris")

    # ── Pilih musik ──────────────────────────────────────────────────────
    AUDIO_EXT  = {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac"}
    music_file = pick_random(MUSIK_DIR, AUDIO_EXT)
    if not music_file:
        print("ERROR: tidak ada musik di folder musik/")
        sys.exit(1)
    music_path = os.path.join(MUSIK_DIR, music_file)
    raw_dur    = get_duration(music_path)
    music_dur  = min(raw_dur, MAX_DUR)
    if raw_dur > MAX_DUR:
        print(f"  Musik  : {music_file} ({raw_dur:.1f}s → dipotong {MAX_DUR}s)")
    else:
        print(f"  Musik  : {music_file} ({music_dur:.1f}s)")

    # ── Pilih background video ───────────────────────────────────────────
    VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    bg_file   = pick_random(BG_DIR, VIDEO_EXT)
    if not bg_file:
        print("ERROR: tidak ada video di folder background/")
        sys.exit(1)
    bg_path = os.path.join(BG_DIR, bg_file)
    print(f"  BG     : {bg_file}")

    # ── Screenshot website ───────────────────────────────────────────────
    print("\n  [1/5] Screenshot website...")
    ss_path         = screenshot_website()
    screenshot_rgba = Image.open(ss_path).convert("RGBA").resize((W, H), Image.LANCZOS)

    # ── Extract background frames ────────────────────────────────────────
    total_frames = int(music_dur * FPS)
    print(f"\n  [2/5] Extract background frames ({total_frames} frames)...")
    bg_frames = extract_bg_frames(bg_path, total_frames)
    print(f"        {len(bg_frames)} frames loaded")

    # ── Load sticker GIF ─────────────────────────────────────────────────
    print("\n  [3/5] Load sticker GIF...")
    stickers = load_stickers()
    if not stickers:
        print("        Tidak ada sticker, lanjut tanpa sticker")
    else:
        print(f"        {len(stickers)} sticker loaded")

    # ── Card position ────────────────────────────────────────────────────
    card_w    = int(W * 0.84)
    card_h    = int(H * 0.58)
    card_x    = (W - card_w) // 2
    card_y    = int(H * 0.17)
    card_rect = (card_x, card_y, card_x + card_w, card_y + card_h)

    # ── Render frames ────────────────────────────────────────────────────
    print(f"\n  [4/5] Render {total_frames} frame video...")
    frames_dir = render_frames(
        bg_frames, stickers, code_text, screenshot_rgba,
        total_frames, card_rect
    )

    # ── Encode video ─────────────────────────────────────────────────────
    print(f"\n  [5/5] Encode video dengan FFmpeg...")
    ts      = int(time.time())
    out_vid = os.path.join(RESULT_DIR, f"coding_{ts}.mp4")

    music_trim = os.path.join(TEMP_DIR, "music.aac")
    run([
        "ffmpeg", "-y", "-i", music_path,
        "-t", str(music_dur),
        "-c:a", "aac", "-b:a", "192k",
        music_trim
    ])

    run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.jpg"),
        "-i", music_trim,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        out_vid
    ])

    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    if os.path.exists(out_vid):
        size_mb = os.path.getsize(out_vid) / (1024 * 1024)
        print(f"\n  ✅  Video berhasil dibuat!")
        print(f"     File  : {out_vid}")
        print(f"     Size  : {size_mb:.1f} MB")
        print(f"     Durasi: {music_dur:.1f} detik")
    else:
        print("\n  ❌  Video gagal dibuat! Cek log FFmpeg.")

    print("\n" + "═" * 52 + "\n")


if __name__ == "__main__":
    main()
