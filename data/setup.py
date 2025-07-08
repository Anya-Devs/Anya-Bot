import os
import sys
import subprocess
import re

submodule_url = "https://github.com/cringe-neko-girl/Poketwo-AutoNamer.git"
submodule_path = "submodules/poketwo_autonamer"


def run_python(*args, **kwargs):
    return subprocess.run([sys.executable, *args], check=True, **kwargs)


def install_package(package, force=False):
    cmd = ["-m", "pip", "install", "--quiet", "--upgrade"]
    if force:
        cmd.append("--force-reinstall")
    cmd.append(package)
    run_python(*cmd)


def update_all_packages():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=freeze"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            install_package(line.split("==")[0])
        subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Package update failed: {e}")


def clean_requirements():
    try:
        subprocess.run(
            [sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore", "venv,.venv,submodules", "."],
            check=True
        )
        if not os.path.exists("requirements.txt"):
            return

        with open("requirements.txt") as f:
            lines = f.readlines()

        deduped = {}
        for line in lines:
            if "==" in line:
                name, version = line.strip().split("==")
                deduped[name] = version

        with open("requirements.txt", "w") as f:
            for name, version in deduped.items():
                f.write(f"{name}=={version}\n")

    except subprocess.CalledProcessError as e:
        print(f"[!] pipreqs failed: {e}")


def ensure_git_login():
    try:
        subprocess.run(["git", "ls-remote", submodule_url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[✓] GitHub access verified.")
    except subprocess.CalledProcessError:
        print("[!] GitHub authentication missing. Attempting token login...")
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=os.path.join(".github", ".env"))

            token = os.getenv("GIT_ACCESS_TOKEN")
            user = os.getenv("GIT_USERNAME")

            if not token:
                raise EnvironmentError("Missing GIT_ACCESS_TOKEN")

            with open(os.path.expanduser("~/.netrc"), "w") as netrc:
                netrc.write(f"machine github.com\nlogin {user}\npassword {token}\n")

            os.chmod(os.path.expanduser("~/.netrc"), 0o600)
            print("[✓] Token written to ~/.netrc")

        except Exception as e:
            print(f"[!] Git authentication failed: {e}")


def sync_submodule():
    def run_git(*args):
        subprocess.run(args, check=True)

    try:
        ensure_git_login()

        if not os.path.exists(os.path.join(submodule_path, ".git")):
            print(f"[~] Adding missing submodule: {submodule_path}")
            try:
                run_git("git", "submodule", "add", submodule_url, submodule_path)
            except subprocess.CalledProcessError:
                print("[!] Submodule add failed. Forcing update.")
                run_git("git", "submodule", "update", "--force", "--init", "--recursive")

        print("[~] Syncing submodules...")
        run_git("git", "submodule", "foreach", "--recursive", "git reset --hard")
        run_git("git", "submodule", "foreach", "--recursive", "git clean -fd")
        run_git("git", "submodule", "sync", "--recursive")
        run_git("git", "submodule", "update", "--init", "--remote", "--recursive")

    except subprocess.CalledProcessError as e:
        print(f"[!] Submodule sync failed: {e}")


def fix_requests_urllib3():
    try:
        run_python("-m", "pip", "uninstall", "urllib3", "requests", "-y")
        run_python("-m", "pip", "install", "--upgrade", "pip")
        run_python("-m", "pip", "install", "--no-cache-dir", "urllib3", "requests")
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to fix requests/urllib3: {e}")


def fix_dependency_conflicts():
    try:
        run_python("-m", "pip", "install", "--upgrade", "numpy<2.3.0")
        print("[✓] Applied compatibility fix for numpy.")
    except subprocess.CalledProcessError:
        print("[!] Failed to resolve numpy conflict.")


def install_requirements_with_auto_fix():
    if not os.path.exists("requirements.txt"):
        print("[!] No requirements.txt found.")
        return

    print("[~] Installing dependencies...")

    try:
        run_python("-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", "requirements.txt")
        print("[✓] All requirements installed.")
        return
    except subprocess.CalledProcessError:
        print("[!] Installation failed. Attempting auto-fix...")

    fix_dependency_conflicts()

    try:
        with open("requirements.txt") as f:
            lines = f.readlines()

        cleaned = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                if any(pkg in line for pkg in ["numpy", "opencv-python-headless"]):
                    cleaned.append(re.split(r"[<=>]", line)[0])
                else:
                    cleaned.append(line)

        for req in cleaned:
            try:
                run_python("-m", "pip", "install", "--upgrade", req)
                print(f"[✓] Installed: {req}")
            except subprocess.CalledProcessError:
                print(f"[!] Failed: {req}")

    except Exception as e:
        print(f"[!] Auto-fix failed: {e}")
        raise


def start():
    print("=== Initializing Setup ===")

    run_python("-m", "pip", "install", "--upgrade", "pip")
    fix_requests_urllib3()

    essentials = [
        "urllib3",
        "pipreqs",
        "onnxruntime",
        "opencv-python-headless",
        "python-Levenshtein"
    ]

    for pkg in essentials:
        try:
            install_package(pkg)
            print(f"[✓] Installed: {pkg}")
        except subprocess.CalledProcessError:
            print(f"[!] Failed to install: {pkg}")

    sync_submodule()
    update_all_packages()
    clean_requirements()
    install_requirements_with_auto_fix()

    print("| Setup Complete ✅ ")


if __name__ == "__main__":
    start()
