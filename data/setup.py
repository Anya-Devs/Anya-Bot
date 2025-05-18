import os
import sys
import subprocess

submodule_url = "https://github.com/cringe-neko-girl/Poketwo-AutoNamer.git"
submodule_path = "submodules/poketwo_autonamer"


def run_python(*args, **kwargs):
    """Run commands with the current Python interpreter."""
    return subprocess.run([sys.executable, *args], check=True, **kwargs)


def install_package(package):
    run_python("-m", "pip", "install", "--quiet", "--upgrade", package)


def update_all_packages():
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=freeze'],
        capture_output=True, text=True
    )
    outdated_packages = result.stdout.strip().splitlines()
    for line in outdated_packages:
        pkg = line.split('==')[0]
        install_package(pkg)

    subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True)


def clean_requirements():
    run_python("-m", "pipreqs", "--force", "--ignore", "venv,.venv,submodules", ".")

    if not os.path.exists('requirements.txt'):
        return

    with open('requirements.txt', 'r') as f:
        lines = f.readlines()

    deduped = {}
    for line in lines:
        if '==' in line:
            pkg, ver = line.strip().split('==')
            deduped[pkg] = ver

    with open('requirements.txt', 'w') as f:
        for pkg, ver in deduped.items():
            f.write(f"{pkg}=={ver}\n")


def ensure_git_login():
    try:
        subprocess.run(
            ['git', 'ls-remote', submodule_url],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ GitHub access already authenticated.")
    except subprocess.CalledProcessError:
        print("🔐 GitHub authentication missing. Logging in using token...")
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.join(".github", ".env"))
        token = os.environ.get('GIT_ACCESS_TOKEN')
        username = os.environ.get('GIT_USERNAME')
        if not token:
            raise EnvironmentError("❌ GIT_ACCESS_TOKEN not set in environment!")

        netrc_path = os.path.expanduser("~/.netrc")
        with open(netrc_path, 'w') as netrc:
            netrc.write(f"machine github.com\nlogin {username}\npassword {token}\n")
        os.chmod(netrc_path, 0o600)
        print("✅ Token written to ~/.netrc")


def sync_submodule():
    def run(*args):
        subprocess.run(args, check=True)

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


def fix_requests_urllib3():
    run_python("-m", "pip", "uninstall", "urllib3", "requests", "-y")
    run_python("-m", "pip", "install", "--upgrade", "pip")
    run_python("-m", "pip", "install", "--no-cache-dir", "urllib3", "requests")


def start():
    run_python("-m", "pip", "install", "--upgrade", "pip")
    fix_requests_urllib3()

    # Core dependencies
    for pkg in [
        'urllib3',
        'pipreqs',
        'onnxruntime',
        'opencv-python-headless',
        'python-Levenshtein'
    ]:
        install_package(pkg)

    sync_submodule()
    update_all_packages()

    try:
        clean_requirements()
    except subprocess.CalledProcessError as e:
        print("❌ pipreqs failed. Likely due to missing dependencies.")
        print(e)

    if os.path.exists("requirements.txt"):
        run_python("-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", "requirements.txt")


if __name__ == "__main__":
    start()
