#!/usr/bin/env python3
"""
Deploy Posta Stack (API, Worker, Postgres, Redis, Postfix SMTP).
Supports local deployment or automated remote deployment via SSH.
"""

import os
import sys
import argparse
import subprocess
import tarfile
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def load_env(env_path=None):
    """Parse .env file into a dictionary without external dependencies."""
    if env_path is None:
        env_path = PROJECT_ROOT / ".env"
    
    env_vars = {}
    if not env_path.exists():
        print(f"[WARN] .env file not found at {env_path}")
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            env_vars[key] = val
    return env_vars

def validate_env(env_vars):
    """Validate mandatory environment variables."""
    required = [
        "POSTA_JWT_SECRET",
        "POSTA_ADMIN_EMAIL",
        "POSTA_ADMIN_PASSWORD",
        "MAIL_DOMAIN",
    ]
    missing = [k for k in required if not env_vars.get(k)]
    if missing:
        print(f"[ERROR] Missing required environment variables in .env: {', '.join(missing)}")
        print("Please edit .env and configure these before deploying.")
        sys.exit(1)

def print_dns_guidance(env_vars, server_ip):
    """Print DNS instructions for the configured domain."""
    domain = env_vars.get("MAIL_DOMAIN", "example.com")
    hostname = env_vars.get("MAIL_HOSTNAME", f"mail.{domain}")
    
    print("\n" + "=" * 65)
    print("  REQUIRED DNS RECORDS FOR EMAIL DELIVERABILITY")
    print("=" * 65)
    print(f"Domain: {domain}")
    print(f"Server IP: {server_ip}")
    print("-" * 65)
    print(f"1. A Record (DNS-Only / Not Proxied):")
    print(f"   Name:  {hostname}")
    print(f"   Value: {server_ip}")
    print(f"\n2. MX Record:")
    print(f"   Name:  @ (or {domain})")
    print(f"   Value: {hostname}  (Priority: 10)")
    print(f"\n3. SPF (TXT Record):")
    print(f"   Name:  @")
    print(f"   Value: v=spf1 ip4:{server_ip} ~all")
    print(f"\n4. DMARC (TXT Record):")
    print(f"   Name:  _dmarc")
    print(f"   Value: v=DMARC1; p=none;")
    print(f"\n5. Reverse DNS (PTR Record - Set in VPS Control Panel):")
    print(f"   IP {server_ip} ➔ {hostname}")
    print("=" * 65 + "\n")

def deploy_local(env_vars):
    """Deploy stack locally using Docker Compose."""
    print("=== Starting Local Deployment ===")
    cmd = ["docker", "compose", "up", "-d", "--build"]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("[ERROR] Docker Compose failed to start services.")
        sys.exit(res.returncode)

    port = env_vars.get("POSTA_PORT", "9000")
    print(f"\n[INFO] Waiting for Posta to become healthy on port {port}...")
    url = f"http://localhost:{port}/healthz"
    for i in range(15):
        time.sleep(2)
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    print(f"[SUCCESS] Posta is healthy and responding at {url}")
                    print_dns_guidance(env_vars, "127.0.0.1")
                    return
        except Exception:
            print(f"  Attempt {i+1}/15: waiting...")

    print("[WARN] Healthcheck timed out. Check logs with 'docker compose logs'.")

def create_tarball():
    """Package project files into a tarball for remote transfer."""
    tmp_dir = PROJECT_ROOT / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_dir / "posta_deploy.tar.gz"

    excludes = {
        ".git", ".tmp", "node_modules", "dist", ".vscode",
        "posta_deploy.tar.gz", "db_data", "redis_data", "smtp_data"
    }

    def filter_func(tarinfo):
        for part in Path(tarinfo.name).parts:
            if part in excludes or part.endswith(".log"):
                return None
        return tarinfo

    print("[INFO] Creating deployment archive...")
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in PROJECT_ROOT.iterdir():
            if item.name not in excludes:
                tar.add(item, arcname=item.name, filter=filter_func)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Archive created: {archive_path} ({size_mb:.2f} MB)")
    return archive_path

def deploy_remote(env_vars):
    """Deploy stack to remote server via SSH."""
    host = env_vars.get("REMOTE_HOST")
    user = env_vars.get("REMOTE_USER", "root")
    password = env_vars.get("REMOTE_PASSWORD")
    remote_dir = env_vars.get("REMOTE_DIR", "/opt/posta")

    if not host:
        print("[ERROR] REMOTE_HOST is not defined in .env.")
        sys.exit(1)

    print(f"=== Starting Remote Deployment to {user}@{host}:{remote_dir} ===")

    # 1. Package code
    archive_path = create_tarball()

    # 2. Setup Askpass helper if password is provided on Windows
    askpass_bat = None
    if password and os.name == "nt":
        tmp_dir = PROJECT_ROOT / ".tmp"
        askpass_bat = tmp_dir / "askpass.bat"
        with open(askpass_bat, "w", encoding="utf-8") as f:
            f.write(f"@echo off\necho {password}\n")

    def run_remote(cmd_str):
        if askpass_bat:
            ps_script = f'''
            $env:SSH_ASKPASS = "{askpass_bat}"
            $env:SSH_ASKPASS_REQUIRE = "force"
            $env:DISPLAY = "dummy:0"
            ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR {user}@{host} "{cmd_str}"
            '''
            return subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
        else:
            return subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{host}", cmd_str], capture_output=True, text=True)

    def scp_file(local_path, remote_path):
        if askpass_bat:
            ps_script = f'''
            $env:SSH_ASKPASS = "{askpass_bat}"
            $env:SSH_ASKPASS_REQUIRE = "force"
            $env:DISPLAY = "dummy:0"
            scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "{local_path}" {user}@{host}:{remote_path}
            '''
            return subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
        else:
            return subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_path), f"{user}@{host}:{remote_path}"], capture_output=True, text=True)

    # 3. Create remote directory
    print(f"[INFO] Ensuring remote directory {remote_dir} exists...")
    res = run_remote(f"mkdir -p {remote_dir}")
    if res.returncode != 0:
        print(f"[ERROR] Failed to create remote directory: {res.stderr}")
        sys.exit(1)

    # 4. Upload archive and .env
    print(f"[INFO] Uploading deployment archive to {host}:/tmp/posta_deploy.tar.gz...")
    res = scp_file(archive_path, "/tmp/posta_deploy.tar.gz")
    if res.returncode != 0:
        print(f"[ERROR] SCP upload failed: {res.stderr}")
        sys.exit(1)

    env_path = PROJECT_ROOT / ".env"
    print(f"[INFO] Uploading .env to {remote_dir}/.env...")
    res = scp_file(env_path, f"{remote_dir}/.env")
    if res.returncode != 0:
        print(f"[ERROR] SCP .env upload failed: {res.stderr}")
        sys.exit(1)

    # 5. Extract and deploy on remote host
    remote_cmds = (
        f"tar -xzf /tmp/posta_deploy.tar.gz -C {remote_dir} && "
        f"rm -f /tmp/posta_deploy.tar.gz && "
        f"cd {remote_dir} && "
        f"docker compose down || true && "
        f"docker compose up -d --build"
    )
    print(f"[INFO] Extracting archive and running 'docker compose up -d --build' on {host}...")
    res = run_remote(remote_cmds)
    if res.returncode != 0:
        print(f"[ERROR] Remote compose execution failed:\n{res.stderr}\n{res.stdout}")
        sys.exit(1)
    print(res.stdout)

    # 6. Verify remote health
    port = env_vars.get("POSTA_PORT", "9000")
    print(f"\n[INFO] Checking remote health at http://{host}:{port}/healthz...")
    time.sleep(5)
    url = f"http://{host}:{port}/healthz"
    healthy = False
    for i in range(10):
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                if resp.status == 200:
                    print(f"[SUCCESS] Remote Posta is healthy and responding at {url}")
                    healthy = True
                    break
        except Exception:
            time.sleep(3)

    if not healthy:
        print(f"[WARN] Remote health check did not respond yet. Check logs on the server with:\n  ssh {user}@{host} 'cd {remote_dir} && docker compose logs'")

    print_dns_guidance(env_vars, host)

def main():
    parser = argparse.ArgumentParser(description="Deploy Posta & Postfix SMTP Stack")
    parser.add_argument("--remote", action="store_true", help="Deploy to remote server specified in .env")
    parser.add_argument("--local", action="store_true", help="Deploy locally using Docker Compose")
    args = parser.parse_args()

    env_vars = load_env()
    validate_env(env_vars)

    if args.remote:
        deploy_remote(env_vars)
    elif args.local or not env_vars.get("REMOTE_HOST"):
        deploy_local(env_vars)
    else:
        # Default to remote if REMOTE_HOST is defined, else local
        print(f"[INFO] Detected REMOTE_HOST={env_vars.get('REMOTE_HOST')}. Use --remote to deploy to server, or --local for local.")
        deploy_local(env_vars)

if __name__ == "__main__":
    main()
