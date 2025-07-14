import sys
import asyncio
import subprocess
import time
import os

def ensure_rich():
    try:
        import rich
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])

ensure_rich()

import re
from rich.console import Console
from rich.panel import Panel
from rich.box import ROUNDED
from rich.text import Text
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    TaskProgressColumn, TimeRemainingColumn
)
from concurrent.futures import ThreadPoolExecutor

class SetupManager:
    def __init__(self):
        self.console = Console()
        token = os.getenv("GIT_ACCESS_TOKEN")
        if token:
            self.submodule_url = f"https://{token}:x-oauth-basic@github.com/senko-sleep/Poketwo-AutoNamer.git"
        else:
            self.submodule_url = "https://github.com/senko-sleep/Poketwo-AutoNamer.git"
        self.submodule_path = "submodules/poketwo_autonamer"
        self.essential_packages = [
            "urllib3", "pipreqs", "onnxruntime",
            "opencv-python-headless", "python-Levenshtein",
            "pip", "setuptools", "wheel"  # Added essential system packages
        ]
        self.requirements_file = "requirements.txt"
        self.start_time = time.time()
        self.task_times = {}
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        )

    def log_time(self, task_name, start_time):
        elapsed = time.time() - start_time
        self.task_times[task_name] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    def ensure_pip(self):
        try:
            # First try to repair pip installation
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], 
                         check=True, capture_output=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
                          "pip", "setuptools", "wheel"], 
                         check=True, capture_output=True)
            return True
        except Exception as e:
            self.console.print(Panel(
                f"[bold red]Failed to repair pip: {e}[/bold red]",
                title="pip Error",
                border_style="red"
            ))
            return False

    async def run_cmd_ultra_fast(self, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300
            ).returncode
        )

    async def run_cmd_with_output(self, *args):
        loop = asyncio.get_event_loop()
        def run_and_capture():
            return subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
                text=True
            )
        return await loop.run_in_executor(self.executor, run_and_capture)

    def ensure_git_login(self):
        return True

    async def sync_submodule(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Git auth check...", completed=10)
        await asyncio.sleep(0.2)
        if not self.ensure_git_login():
            self.progress.update(task_id, description="→ ❌ Git auth failed", completed=100)
            self.console.print(Panel(
                "[bold red]Git authorization failed.[/bold red]\n• Check your token or SSH key\n• Did you forget to set up .env or ~/.netrc?",
                title="Git Error",
                border_style="red"))
            return
        self.progress.update(task_id, description="□ Submodule sync...", completed=30)
        await asyncio.sleep(0.2)
        try:
            if not os.path.exists(os.path.join(self.submodule_path, ".git")):
                await self.run_cmd_ultra_fast("git", "submodule", "add", self.submodule_url, self.submodule_path)
            self.progress.update(task_id, description="□ Parallel submodule update...", completed=60)
            await asyncio.sleep(0.2)
            await asyncio.gather(
                self.run_cmd_ultra_fast("git", "submodule", "sync"),
                self.run_cmd_ultra_fast("git", "submodule", "update", "--init", "--remote", "--jobs", "8", "--depth", "1")
            )
            elapsed = self.log_time("submodule", start)
            self.progress.update(task_id, description=f"✅ Submodules {elapsed}", completed=100)
        except Exception as e:
            self.progress.update(task_id, description="→ ❌ Submodule failed", completed=100)
            self.console.print(Panel(str(e), title="Submodule Error", border_style="red"))

    async def resolve_conflicts(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Conflict check...", completed=20)
        await asyncio.sleep(0.2)
        if not os.path.exists(self.requirements_file):
            elapsed = self.log_time("conflicts", start)
            self.progress.update(task_id, description=f"✅ No conflicts {elapsed}", completed=100)
            return
        with open(self.requirements_file, "r") as f:
            content = f.read()
        if "numpy" in content and "opencv-python-headless" in content:
            self.progress.update(task_id, description="□ Numpy/OpenCV fix...", completed=70)
            await asyncio.sleep(0.2)
            lines = content.strip().split("\n")
            fixed_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("numpy=="):
                    fixed_lines.append("numpy>=2.0.0,<2.3.0")
                elif line.startswith("opencv-python-headless"):
                    fixed_lines.append("opencv-python-headless")
                elif line and not line.startswith("#"):
                    fixed_lines.append(line)
            with open(self.requirements_file, "w") as f:
                f.write("\n".join(fixed_lines) + "\n")
        elapsed = self.log_time("conflicts", start)
        self.progress.update(task_id, description=f"✅ Conflicts fixed {elapsed}", completed=100)

    async def upgrade_pip(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ pip --upgrade...", completed=0)
        await asyncio.sleep(0.2)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
                          "pip", "setuptools", "wheel"], check=True, capture_output=True)
            elapsed = self.log_time("pip", start)
            self.progress.update(task_id, description=f"✅ pip {elapsed}", completed=100)
        except Exception as e:
            elapsed = self.log_time("pip", start)
            self.progress.update(task_id, description=f"→ ❌ pip failed {elapsed}", completed=100)
            self.console.print(Panel(str(e), title="pip Error", border_style="red"))

    async def mega_install(self, packages, task_id, task_name):
        start = time.time()
        total = len(packages)
        self.progress.update(task_id, description=f"□ Installing {total} {task_name}...", completed=0)
        await asyncio.sleep(0.2)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
                          "--no-cache-dir", "--disable-pip-version-check"] + packages,
                         check=True, capture_output=True)
            elapsed = self.log_time(task_name, start)
            self.progress.update(task_id, description=f"✅ {total} {task_name} {elapsed}", completed=100)
        except Exception as e:
            elapsed = self.log_time(task_name, start)
            self.progress.update(task_id, description=f"→ ❌ {task_name} failed {elapsed}", completed=100)
            self.console.print(Panel(str(e), title=f"{task_name.title()} Error", border_style="red"))

    async def install_essentials(self, task_id):
        await self.mega_install(self.essential_packages, task_id, "essentials")

    def cleanup_invalid_distributions(self):
        import site
        try:
            site_packages = next(p for p in site.getsitepackages() if "site-packages" in p)
            for name in os.listdir(site_packages):
                if name.startswith("~") or (name.endswith(".dist-info") and not os.path.isdir(os.path.join(site_packages, name))):
                    try:
                        path = os.path.join(site_packages, name)
                        if os.path.isdir(path):
                            import shutil
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    except Exception:
                        pass
        except Exception:
            pass

    def check_syntax_errors(self):
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            self.console.print(Panel(
                f"[bold red]Syntax errors detected in your Python files.[/bold red]\n{result.stdout}\n{result.stderr}",
                title="Syntax Error",
                border_style="red"
            ))
            return False
        return True

    def add_missing_init_py(self):
        for root, dirs, files in os.walk("."):
            if "__pycache__" in root or "venv" in root or "submodules" in root or "node_modules" in root:
                continue
            if any(f.endswith(".py") for f in files):
                init_path = os.path.join(root, "__init__.py")
                if not os.path.exists(init_path):
                    open(init_path, "a").close()

    async def clean_requirements(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Generating requirements...", completed=0)
        await asyncio.sleep(0.2)
        self.add_missing_init_py()
        if not self.check_syntax_errors():
            elapsed = self.log_time("clean_req", start)
            self.progress.update(task_id, description=f"→ ❌ Syntax error {elapsed}", completed=100)
            return
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pipreqs"],
                         check=True, capture_output=True)
            subprocess.run([sys.executable, "-m", "pipreqs.pipreqs", "--force",
                          "--ignore", "venv,.venv,submodules,node_modules", "."],
                         check=True, capture_output=True)
        except Exception as e:
            elapsed = self.log_time("clean_req", start)
            self.progress.update(task_id, description=f"→ ❌ pipreqs failed {elapsed}", completed=100)
            self.console.print(Panel(
                f"[bold red]pipreqs failed: {e}[/bold red]\n• Missing __init__.py\n• Syntax error in .py files",
                title="pipreqs Error",
                border_style="red"
            ))
            return

        self.progress.update(task_id, description="□ Deduplicating...", completed=60)
        await asyncio.sleep(0.2)
        if not os.path.exists(self.requirements_file):
            elapsed = self.log_time("clean_req", start)
            self.progress.update(task_id, description=f"→ ❌ No requirements.txt {elapsed}", completed=100)
            return

        with open(self.requirements_file, "r") as f:
            lines = f.readlines()
        deduped = {}
        for line in lines:
            if "==" in line:
                name, version = line.strip().split("==", 1)
                deduped[name] = version
        with open(self.requirements_file, "w") as f:
            for name, version in deduped.items():
                f.write(f"{name}=={version}\n")
        elapsed = self.log_time("clean_req", start)
        self.progress.update(task_id, description=f"✅ {len(deduped)} packages cleaned {elapsed}", completed=100)

    async def install_requirements(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Installing requirements...", completed=0)
        await asyncio.sleep(0.2)
        if not os.path.exists(self.requirements_file):
            elapsed = self.log_time("install_req", start)
            self.progress.update(task_id, description=f"→ ❌ No requirements.txt {elapsed}", completed=100)
            return

        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                          self.requirements_file, "--upgrade", "--no-cache-dir"],
                         check=True, capture_output=True)
            elapsed = self.log_time("install_req", start)
            self.progress.update(task_id, description=f"✅ Requirements installed {elapsed}", completed=100)
        except Exception as e:
            self.progress.update(task_id, description="□ Individual package install...", completed=60)
            await asyncio.sleep(0.2)
            with open(self.requirements_file, "r") as f:
                lines = f.readlines()
            packages = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "numpy" in line or "opencv" in line:
                        packages.append(re.split(r"[<=>]", line)[0])
                    else:
                        packages.append(line)
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
                              "--no-cache-dir"] + packages,
                             check=True, capture_output=True)
                elapsed = self.log_time("install_req", start)
                self.progress.update(task_id, description=f"✅ Requirements {elapsed}", completed=100)
            except Exception as e2:
                elapsed = self.log_time("install_req", start)
                self.progress.update(task_id, description=f"→ ❌ Install failed {elapsed}", completed=100)
                self.console.print(Panel(str(e2), title="Requirements Error", border_style="red"))

    async def run_setup(self):
        # First ensure pip is working
        if not self.ensure_pip():
            return

        self.console.print(Panel(Text("⚡ Setup Manager v2", justify="center"),
                                title="Setup", box=ROUNDED, border_style="bright_blue"))
        with self.progress:
            tasks = [
                self.progress.add_task("Git submodules", total=100),
                self.progress.add_task("pip upgrade", total=100),
                self.progress.add_task("Package conflicts", total=100),
                self.progress.add_task("Essential packages", total=100),
                self.progress.add_task("Clean requirements", total=100),
                self.progress.add_task("Outdated packages", total=100),
                self.progress.add_task("Install requirements", total=100)
            ]
            await asyncio.gather(
                self.sync_submodule(tasks[0]),
                self.upgrade_pip(tasks[1]),
                self.resolve_conflicts(tasks[2]),
                self.install_essentials(tasks[3]),
                self.clean_requirements(tasks[4]),
                self.install_requirements(tasks[6])
            )
        total_time = time.time() - self.start_time
        self.executor.shutdown(wait=False)
        self.console.print(Panel(
            Text(f"🚀 Setup completed in {total_time:.1f}s", justify="center"),
            title="Complete", box=ROUNDED, border_style="green"
        ))

if __name__ == "__main__":
    asyncio.run(SetupManager().run_setup())