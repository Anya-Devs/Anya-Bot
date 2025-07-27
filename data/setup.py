import os, sys, subprocess

submodule_url = "https://github.com/senko-sleep/Poketwo-AutoNamer.git"
submodule_path = "submodules/poketwo_autonamer"

def run_python(*args, **kwargs): return subprocess.run([sys.executable, *args], check=True, **kwargs)
def install_package(pkg): run_python("-m", "pip", "install", "--quiet", "--upgrade", pkg)
def update_all_packages():
    r = subprocess.run([sys.executable, '-m', 'pip', 'list', '--outdated', '--format=freeze'], capture_output=True, text=True)
    for l in r.stdout.strip().splitlines(): install_package(l.split('==')[0])
    subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True)

def clean_requirements():
    subprocess.run([sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore", "venv,.venv,submodules", "."], check=True)
    if not os.path.exists('requirements.txt'): return
    with open('requirements.txt') as f: lines = f.readlines()
    d = {}
    for l in lines:
        if '==' in l: p, v = l.strip().split('=='); d[p] = v
    with open('requirements.txt', 'w') as f:
        for p, v in d.items(): f.write(f"{p}=={v}\n")

def sync_submodule():
    def run(*a): subprocess.run(a, check=True)
    if not os.path.exists(os.path.join(submodule_path, '.git')):
        print(f"🔧 Adding missing submodule: {submodule_path}")
        try: run("git", "submodule", "add", submodule_url, submodule_path)
        except subprocess.CalledProcessError:
            print("⚠️ Submodule add failed, forcing update instead...")
            run("git", "submodule", "update", "--force", "--init", "--recursive")
    print("🧹 Cleaning and syncing submodules...")
    run("git", "submodule", "foreach", "--recursive", "git reset --hard")
    run("git", "submodule", "foreach", "--recursive", "git clean -fd")
    run("git", "submodule", "sync", "--recursive")
    run("git", "submodule", "update", "--init", "--remote", "--recursive")

def fix_requests_urllib3():
    run_python("-m", "pip", "uninstall", "urllib3", "requests", "-y")
    run_python("-m", "pip", "install", "--upgrade", "pip")
    run_python("-m", "pip", "install", "--no-cache-dir", "urllib3", "requests")

def start():
    run_python("-m", "pip", "install", "--upgrade", "pip")
    fix_requests_urllib3()
    for p in ['urllib3', 'pipreqs', 'onnxruntime', 'opencv-python-headless', 'python-Levenshtein']: install_package(p)
    sync_submodule()
    update_all_packages()
    try: clean_requirements()
    except subprocess.CalledProcessError as e:
        print("❌ pipreqs failed. Likely due to missing dependencies.")
        print(e)
    if os.path.exists("requirements.txt"):
        run_python("-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", "requirements.txt")

if __name__ == "__main__": start()
