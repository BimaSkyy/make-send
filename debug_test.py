#!/usr/bin/env python3
import os, sys, time, requests, base64, json
from jose import jwt

# ==============================================
# CONFIG GITHUB APP
# ==============================================
APP_ID = "3262899"
INSTALLATION_ID = "121131797"
PRIVATE_KEY_PATH = "key.pem"
REPO_OWNER = "BimaSkyy"
REPO_NAME = "make-send"
TARGET_FOLDER = "background" # Folder tujuan di GitHub

# ==============================================
# FUNGSI AUTH GITHUB APP
# ==============================================
with open(PRIVATE_KEY_PATH, 'r') as f:
    private_key = f.read()

def get_jwt():
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + (10 * 60),
        "iss": APP_ID
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

def get_github_token():
    try:
        jwt_token = get_jwt()
        url = f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        token = response.json()["token"]
        print(f"✅ Token GitHub App berhasil didapatkan!")
        print(f"📈 Limit sekarang: 15.000 request/jam\n")
        return token
    except Exception as e:
        print(f"❌ Gagal ambil token: {e}")
        sys.exit(1)

GITHUB_TOKEN = get_github_token()
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ==============================================
# FUNGSI UTAMA
# ==============================================

def get_existing_files():
    """Ambil daftar file yang sudah ada di GitHub"""
    existing = set()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TARGET_FOLDER}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                if item["type"] == "file":
                    existing.add(item["name"])
        print(f"📋 Sudah ada di GitHub: {len(existing)} file")
        return existing
    except Exception as e:
        print(f"⚠️ Gagal cek file: {e}")
        return set()

def upload_file(file_path, file_name):
    """Upload satu file ke GitHub"""
    try:
        # Baca file dan encode base64
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode()

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TARGET_FOLDER}/{file_name}"
        
        # Cek dulu file udah ada apa belum (ambil SHA)
        check = requests.get(url, headers=HEADERS)
        data = {"message": f"Upload {file_name}", "content": content}
        
        if check.status_code == 200:
            # Update file
            data["sha"] = check.json()["sha"]

        resp = requests.put(url, headers=HEADERS, data=json.dumps(data))
        
        if resp.status_code in [201, 200]:
            print(f"✅ BERHASIL: {file_name}")
            return True
        else:
            print(f"❌ GAGAL: {file_name} | {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ ERROR: {file_name} | {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 GITHUB UPLOADER TEST - MODE BACKGROUND")
    print(f"📦 Repo: {REPO_OWNER}/{REPO_NAME}")
    print(f"📂 Folder tujuan: {TARGET_FOLDER}")
    print("=" * 60)

    # Folder lokal tempat file kamu
    LOCAL_FOLDER = "./background"

    if not os.path.exists(LOCAL_FOLDER):
        print(f"❌ Folder {LOCAL_FOLDER} tidak ditemukan!")
        sys.exit(1)

    # Ambil daftar file lokal
    local_files = [f for f in os.listdir(LOCAL_FOLDER) if os.path.isfile(os.path.join(LOCAL_FOLDER, f))]
    print(f"📁 Total file lokal: {len(local_files)}")

    # Ambil daftar file di GitHub
    existing_files = get_existing_files()

    # Cari yang belum ada
    to_upload = []
    skipped = []
    for f in local_files:
        if f in existing_files:
            skipped.append(f)
        else:
            to_upload.append(f)

    print(f"⏭️  Dilewati (sudah ada): {len(skipped)} file")
    print(f"📤 Akan diupload: {len(to_upload)} file\n")

    if len(to_upload) == 0:
        print("🎉 Semua file sudah ada di GitHub! Selesai.")
        sys.exit(0)

    # Mulai upload
    success = 0
    failed = 0
    for i, filename in enumerate(to_upload, 1):
        print(f"\n[{i}/{len(to_upload)}] Uploading: {filename}")
        full_path = os.path.join(LOCAL_FOLDER, filename)
        
        if upload_file(full_path, filename):
            success += 1
        else:
            failed += 1
        
        time.sleep(1) # Jeda biar aman

    # Rekap
    print("\n" + "=" * 60)
    print("📊 REKAP HASIL UPLOAD")
    print("=" * 60)
    print(f"✅ Berhasil: {success}")
    print(f"❌ Gagal: {failed}")
    print(f"⏭️  Skip: {len(skipped)}")
    print(f"📁 Total: {len(local_files)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
