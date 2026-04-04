#!/usr/bin/env python3
"""
runner.py — Auto-restart wrapper untuk app.py
- Pertama kali: input manual seperti biasa
- Kalau app.py crash/error: langsung restart pakai input yang sama
- Hanya berhenti kalau kamu Ctrl+C di sini
"""

import subprocess
import sys
import os
import time
import json

SAVE_FILE   = "./runner_state.json"
APP_SCRIPT  = "app.py"
PYTHON      = sys.executable  # pakai python yang sama

# ──────────────────────────────────────────────
# Tampilkan menu & ambil input dari user
# ──────────────────────────────────────────────
def tanya_input():
    print("\n" + "═"*40)
    print("  RUNNER — Auto-restart app.py")
    print("═"*40)
    print("""
  1. Buat video
  2. Upload ke API Koyeb
  3. Auto (buat → upload → hapus → loop)
  4. Upload projek ke GitHub
  5. Update background/sticker dari GitHub
""")

    inputs = []

    pilihan = input("Pilih menu [1-5]: ").strip()
    inputs.append(pilihan)

    if pilihan == "3":
        jumlah = input("Buat berapa video per loop? (default 1): ").strip()
        inputs.append(jumlah if jumlah else "1")

    elif pilihan == "2":
        konfirm = input("Upload semua video yang belum terupload? [y/n]: ").strip().lower()
        inputs.append(konfirm)

    return inputs

# ──────────────────────────────────────────────
# Simpan & load state
# ──────────────────────────────────────────────
def simpan_state(inputs: list):
    with open(SAVE_FILE, "w") as f:
        json.dump({"inputs": inputs}, f)

def load_state() -> list | None:
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
            return data.get("inputs")
        except:
            pass
    return None

def hapus_state():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

# ──────────────────────────────────────────────
# Jalankan app.py dengan input tertentu
# ──────────────────────────────────────────────
def jalankan(inputs: list) -> int:
    """Jalankan app.py, kirim inputs lewat stdin. Return exit code."""
    input_str = "\n".join(inputs) + "\n"

    proc = subprocess.Popen(
        [PYTHON, APP_SCRIPT],
        stdin=subprocess.PIPE,
        # stdout & stderr tetap ke terminal langsung
        stdout=None,
        stderr=None,
    )

    try:
        proc.stdin.write(input_str.encode())
        proc.stdin.flush()
        # Biarkan app.py berjalan sampai selesai/crash
        # stdin ditutup supaya app.py tidak nunggu input lagi
        proc.stdin.close()
        proc.wait()
    except BrokenPipeError:
        # app.py sudah crash sebelum baca semua input
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        raise  # teruskan ke loop utama

    return proc.returncode

# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────
def main():
    restart_delay = 5  # detik tunggu sebelum restart

    # Cek apakah ada state tersimpan dari sesi sebelumnya
    saved = load_state()
    if saved:
        print(f"\n[Runner] Ditemukan state tersimpan: input = {saved}")
        pakai = input("[Runner] Pakai input tersimpan? [y/n] (default y): ").strip().lower()
        if pakai == "n":
            hapus_state()
            saved = None

    if saved:
        inputs = saved
        print(f"[Runner] Menggunakan input: {inputs}")
    else:
        inputs = tanya_input()
        simpan_state(inputs)
        print(f"\n[Runner] Input disimpan: {inputs}")

    attempt = 0

    print("\n[Runner] Memulai app.py... (Ctrl+C di sini untuk benar-benar berhenti)\n")
    print("─"*40)

    try:
        while True:
            attempt += 1
            print(f"\n[Runner] ▶ Menjalankan app.py (percobaan #{attempt})")

            exit_code = jalankan(inputs)

            if exit_code == 0:
                print(f"\n[Runner] app.py selesai normal (exit 0).")
                print("[Runner] Loop selesai, runner berhenti.")
                break
            else:
                print(f"\n[Runner] ⚠ app.py berhenti dengan exit code {exit_code}.")
                print(f"[Runner] Restart dalam {restart_delay} detik... (Ctrl+C untuk batal)")
                time.sleep(restart_delay)

    except KeyboardInterrupt:
        print("\n\n[Runner] Dihentikan oleh user (Ctrl+C).")
        hapus_state()
        print("[Runner] State dihapus. Selesai.")

if __name__ == "__main__":
    if not os.path.exists(APP_SCRIPT):
        print(f"[Runner] ERROR: {APP_SCRIPT} tidak ditemukan di direktori ini.")
        sys.exit(1)
    main()
