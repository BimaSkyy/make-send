#!/usr/bin/env python3
"""
getmp3.py - Download dari TikTok
  Mode 1: Audio MP3 -> ./musik/
  Mode 2: Video MP4 -> ./background/

pip install requests --break-system-packages
python getmp3.py
"""

import os, re, sys
import requests

API_BASE  = "https://api.zenzxz.my.id/download/tiktok"
MUSIK_DIR = "./musik"
BG_DIR    = "./background"
TIMEOUT   = 30

def sanitize(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(" ", "_")
    return name[:80] or "tiktok"

def fetch_info(url):
    print("  Fetching info...", end="", flush=True)
    try:
        resp = requests.get(API_BASE, params={"url": url}, timeout=TIMEOUT)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print("\n  Error: Tidak bisa konek ke API."); return None
    except requests.exceptions.Timeout:
        print("\n  Error: API timeout."); return None
    except Exception as e:
        print(f"\n  Error: {e}"); return None

    if not data.get("status"):
        print(f"\n  API gagal: {data}"); return None

    print(" OK")
    return data.get("result", {})

def download_file(dl_url, out_path):
    try:
        r = requests.get(dl_url, timeout=60, stream=True)
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r  Downloading... {pct}%  ", end="", flush=True)
        print(f"\r  Selesai! {downloaded/1024:.1f} KB tersimpan.      ")
        return True
    except Exception as e:
        print(f"\n  Gagal download: {e}")
        if os.path.exists(out_path):
            os.remove(out_path)
        return False

def unique_path(folder, base, ext):
    path = os.path.join(folder, f"{base}{ext}")
    counter = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{counter}{ext}")
        counter += 1
    return path

def mode_musik(url):
    result = fetch_info(url)
    if not result:
        return

    music_info = result.get("music_info", {})
    music_url  = result.get("music") or music_info.get("play")
    raw_title  = music_info.get("title") or result.get("title") or "tiktok_audio"
    author     = music_info.get("author", "")

    if not music_url:
        print("  Error: URL audio tidak ditemukan."); return

    safe_title  = sanitize(raw_title)
    safe_author = sanitize(author) if author else ""
    base_name   = f"{safe_title}__{safe_author}" if safe_author else safe_title
    out_path    = unique_path(MUSIK_DIR, base_name, ".mp3")

    print(f"  Judul  : {raw_title}")
    if author:
        print(f"  Author : {author}")
    print(f"  Durasi : {music_info.get('duration', '?')}s")
    print(f"  Simpan : {out_path}")

    download_file(music_url, out_path)

def mode_background(url):
    result = fetch_info(url)
    if not result:
        return

    video_url = result.get("play")
    raw_title = result.get("title") or "tiktok_video"
    duration  = result.get("duration", "?")

    if not video_url:
        print("  Error: URL video tidak ditemukan."); return

    base_name = sanitize(raw_title)
    out_path  = unique_path(BG_DIR, base_name, ".mp4")

    print(f"  Judul  : {raw_title}")
    print(f"  Durasi : {duration}s")
    print(f"  Simpan : {out_path}")

    download_file(video_url, out_path)

def main():
    print("="*40)
    print("  TikTok Downloader")
    print("="*40)
    print("  1. Musik      -> ./musik/")
    print("  2. Background -> ./background/")
    print("="*40)

    pilihan = input("Mau mode apa? [1/2]: ").strip()
    if pilihan == "1":
        mode = "musik"
        os.makedirs(MUSIK_DIR, exist_ok=True)
        print(f"\n  Mode: Musik | Output: {MUSIK_DIR}/")
    elif pilihan == "2":
        mode = "background"
        os.makedirs(BG_DIR, exist_ok=True)
        print(f"\n  Mode: Background | Output: {BG_DIR}/")
    else:
        print("Pilihan tidak valid."); sys.exit(1)

    print("  (ketik 'q' untuk keluar)\n" + "-"*40)

    while True:
        try:
            url = input("\nMasukan URL tiktok: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nKeluar."); break

        if url.lower() in ("q", "quit", "exit", "keluar"):
            print("Keluar."); break

        if not url:
            print("  URL kosong, coba lagi."); continue

        if "tiktok.com" not in url and "vt.tiktok" not in url:
            print("  Bukan URL TikTok yang valid, coba lagi."); continue

        if mode == "musik":
            mode_musik(url)
        else:
            mode_background(url)

if __name__ == "__main__":
    main()
