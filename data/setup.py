import os, sys, subprocess
import re

submodule_url = "https://github.com/cringe-neko-girl/Poketwo-AutoNamer.git"
submodule_path = "submodules/poketwo_autonamer"

def run_python(*args, **kwargs):
    return subprocess.run([sys.executable, *args], check=True, **kwargs)

def install_package(pkg, ignore_conflicts=False):
    cmd = ["-m", "pip", "install", "--quiet", "--upgrade"]
    if ignore_conflicts:
        cmd.append("--force-reinstall")
    cmd.append(pkg)
    run_python(*cmd)

def update_all_packages():
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'list', '--outdated', '--format=freeze'], capture_output=True, text=True)
        for l in r.stdout.strip().splitlines():
            install_package(l.split('==')[0])
        subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Package update failed: {e}")

def clean_requirements():
    try:
        subprocess.run([sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore", "venv,.venv,submodules", "."], check=True)
        if not os.path.exists('requirements.txt'):
            return
        with open('requirements.txt') as f:
            lines = f.readlines()
        d = {}
        for l in lines:
            if '==' in l:
                p, v = l.strip().split('==')
                d[p] = v
        with open('requirements.txt', 'w') as f:
            for p, v in d.items():
                f.write(f"{p}=={v}\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ pipreqs failed: {e}")

def ensure_git_login():
    try:
        subprocess.run(['git', 'ls-remote', submodule_url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ GitHub access already authenticated.")
    except subprocess.CalledProcessError:
        print("🔐 GitHub authentication missing. Logging in using token...")
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=os.path.join(".github", ".env"))
            t, u = os.environ.get('GIT_ACCESS_TOKEN'), os.environ.get('GIT_USERNAME')
            if not t:
                raise EnvironmentError("❌ GIT_ACCESS_TOKEN not set in environment!")
            with open(os.path.expanduser("~/.netrc"), 'w') as n:
                n.write(f"machine github.com\nlogin {u}\npassword {t}\n")
            os.chmod(os.path.expanduser("~/.netrc"), 0o600)
            print("✅ Token written to ~/.netrc")
        except Exception as e:
            print(f"⚠️ Git authentication failed: {e}")

def sync_submodule():
    def run(*a):
        subprocess.run(a, check=True)
    try:
        ensure_git_login()
        if not os.path.exists(os.path.join(submodule_path, '.git')):
            print(f"🔧 Adding missing submodule: {submodule_path}")
            try:
                run("git", "submodule", "add", submodule_url, submodule_path)
            except subprocess.CalledProcessError:
                print("⚠️ Submodule add failed, forcing update instead...")
                run("git", "submodule", "update", "--force", "--init", "--recursive")
        print("🧹 Cleaning and syncing submodules...")
        run("git", "submodule", "foreach", "--recursive", "git reset --hard")
        run("git", "submodule", "foreach", "--recursive", "git clean -fd")
        run("git", "submodule", "sync", "--recursive")
        run("git", "submodule", "update", "--init", "--remote", "--recursive")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Submodule sync failed: {e}")

def fix_requests_urllib3():
    try:
        run_python("-m", "pip", "uninstall", "urllib3", "requests", "-y")
        run_python("-m", "pip", "install", "--upgrade", "pip")
        run_python("-m", "pip", "install", "--no-cache-dir", "urllib3", "requests")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to fix requests/urllib3: {e}")

def fix_dependency_conflicts():
    print("🔧 Fixing dependency conflicts...")
    try:
        run_python("-m", "pip", "install", "--upgrade", "numpy<2.3.0")
        print("✅ Fixed numpy version for OpenCV compatibility")
    except subprocess.CalledProcessError:
        print("⚠️ Failed to fix numpy version")

def install_requirements_with_auto_fix():
    if not os.path.exists("requirements.txt"):
        print("⚠️ No requirements.txt found")
        return
    print("📦 Installing requirements with conflict resolution...")
    try:
        run_python("-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", "requirements.txt")
        print("✅ Requirements installed successfully")
        return
    except subprocess.CalledProcessError:
        print("⚠️ Normal installation failed, trying conflict resolution...")
    fix_dependency_conflicts()
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.readlines()
        modified_reqs = []
        for req in requirements:
            req = req.strip()
            if req and not req.startswith('#'):
                if any(pkg in req for pkg in ['numpy', 'opencv-python-headless']):
                    package_name = req.split('==')[0].split('>=')[0].split('<=')[0]
                    modified_reqs.append(package_name)
                else:
                    modified_reqs.append(req)
        for req in modified_reqs:
            try:
                run_python("-m", "pip", "install", "--upgrade", req)
                print(f"✅ Installed: {req}")
            except subprocess.CalledProcessError:
                print(f"⚠️ Failed to install: {req}")
    except Exception as e:
        print(f"❌ Auto-fix failed: {e}")
        raise

def start():
    print("🚀 Starting setup process...")
    run_python("-m", "pip", "install", "--upgrade", "pip")
    fix_requests_urllib3()
    essential_packages = ['urllib3', 'pipreqs', 'onnxruntime', 'opencv-python-headless', 'python-Levenshtein']
    for pkg in essential_packages:
        try:
            install_package(pkg)
            print(f"✅ Installed: {pkg}")
        except subprocess.CalledProcessError:
            print(f"⚠️ Failed to install: {pkg}")
    sync_submodule()
    update_all_packages()
    clean_requirements()
    install_requirements_with_auto_fix()
    print("✅ Setup complete!")

if __name__ == "__main__":
    start()
