import sys
import asyncio
import subprocess
import time
import os
import re
import multiprocessing  # Added multiprocessing import
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

TIMEOUT = 300  # global timeout in seconds for subprocess calls

def ensure_rich():
    try:
        import rich
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])

ensure_rich()

from rich.console import Console
from rich.panel import Panel
from rich.box import ROUNDED
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

def blocking_compile():
    return subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "."],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=TIMEOUT,
    )

class SetupManager:
    def __init__(self):
        self.console = Console()
        self.submodule_url = "https://github.com/senko-sleep/Poketwo-AutoNamer.git"
        self.submodule_path = "submodules/poketwo_autonamer"
        self.essential_packages = [
            "urllib3", "pipreqs", "onnxruntime",
            "opencv-python-headless", "python-Levenshtein",
            "pip", "setuptools", "wheel", "emoji==1.7.0"
        ]
        self.requirements_file = "requirements.txt"
        self.start_time = time.time()
        self.task_times = {}

        self.thread_executor = ThreadPoolExecutor(max_workers=16)
        self.process_executor = ProcessPoolExecutor(max_workers=4)

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        )

    def log_time(self, name, start):
        elapsed = time.time() - start
        self.task_times[name] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    def ensure_pip(self):
        try:
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
                capture_output=True,
                timeout=TIMEOUT
            )
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
                check=True,
                capture_output=True,
                timeout=TIMEOUT
            )
            return True
        except Exception as e:
            self.console.print(Panel(f"[bold red]Failed to repair pip: {e}[/bold red]", title="pip Error", border_style="red"))
            return False

    async def run_subprocess(self, *args, capture_output=True):
        loop = asyncio.get_event_loop()
        def blocking_call():
            return subprocess.run(
                args,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                timeout=TIMEOUT,
                check=False
            )
        result = await loop.run_in_executor(self.thread_executor, blocking_call)
        return result

    async def run_subprocess_quiet(self, *args):
        loop = asyncio.get_event_loop()
        def blocking_call():
            return subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TIMEOUT,
                check=False
            )
        result = await loop.run_in_executor(self.thread_executor, blocking_call)
        return result

    async def sync_submodule(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Git auth check...", completed=10)
        if not os.path.exists(os.path.join(self.submodule_path, ".git")):
            res = await self.run_subprocess("git", "submodule", "add", self.submodule_url, self.submodule_path)
            if res.returncode != 0:
                self.console.print(Panel("[bold red]Failed to add submodule[/bold red]", title="Git Error", border_style="red"))
        self.progress.update(task_id, description="□ Parallel submodule update...", completed=60)
        await asyncio.gather(
            self.run_subprocess_quiet("git", "submodule", "sync"),
            self.run_subprocess_quiet("git", "submodule", "update", "--init", "--remote", "--jobs", "16", "--depth", "1"),
        )
        elapsed = self.log_time("submodule", start)
        self.progress.update(task_id, description=f"✅ Submodules {elapsed}", completed=100)

    async def resolve_conflicts(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Conflict check...", completed=20)
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"✅ No conflicts {self.log_time('conflicts', start)}", completed=100)
            return
        with open(self.requirements_file, "r") as f:
            content = f.read()
        if "numpy" in content and "opencv-python-headless" in content:
            self.progress.update(task_id, description="□ Numpy/OpenCV fix...", completed=70)
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
        self.progress.update(task_id, description=f"✅ Conflicts fixed {self.log_time('conflicts', start)}", completed=100)

    async def upgrade_pip(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ pip --upgrade...", completed=0)
        try:
            res = await self.run_subprocess(sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
            if res.returncode == 0:
                self.progress.update(task_id, description=f"✅ pip {self.log_time('pip', start)}", completed=100)
            else:
                self.progress.update(task_id, description=f"→ ❌ pip failed {self.log_time('pip', start)}", completed=100)
                self.console.print(Panel(res.stderr.decode() if res.stderr else "Unknown error", title="pip Error", border_style="red"))
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ pip failed {self.log_time('pip', start)}", completed=100)
            self.console.print(Panel(str(e), title="pip Error", border_style="red"))

    async def mega_install(self, packages, task_id, task_name):
        start = time.time()
        total = len(packages)
        self.progress.update(task_id, description=f"□ Installing {total} {task_name}...", completed=0)
        try:
            res = await self.run_subprocess(sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "--disable-pip-version-check", *packages)
            if res.returncode == 0:
                self.progress.update(task_id, description=f"✅ {total} {task_name} {self.log_time(task_name, start)}", completed=100)
            else:
                raise subprocess.CalledProcessError(res.returncode, res.args, output=res.stdout, stderr=res.stderr)
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ {task_name} failed {self.log_time(task_name, start)}", completed=100)
            self.console.print(Panel(str(e), title=f"{task_name.title()} Error", border_style="red"))

    async def install_essentials(self, task_id):
        await self.mega_install(self.essential_packages, task_id, "essentials")

    async def check_syntax_errors_async(self):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.process_executor, blocking_compile)
        return result

    def add_missing_init_py(self):
        for root, dirs, files in os.walk("."):
            if any(x in root for x in ("__pycache__", "venv", "submodules", "node_modules")):
                continue
            if any(f.endswith(".py") for f in files):
                init_path = os.path.join(root, "__init__.py")
                if not os.path.exists(init_path):
                    open(init_path, "a").close()

    async def clean_requirements(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Generating requirements...", completed=0)
        self.add_missing_init_py()
        result = await self.check_syntax_errors_async()
        if result.returncode != 0:
            self.progress.update(task_id, description=f"→ ❌ Syntax error {self.log_time('clean_req', start)}", completed=100)
            self.console.print(Panel(f"[bold red]Syntax errors detected in your Python files.[/bold red]\n{result.stdout}\n{result.stderr}", title="Syntax Error", border_style="red"))
            return
        try:
            res1 = await self.run_subprocess(sys.executable, "-m", "pip", "install", "--upgrade", "pipreqs")
            res2 = await self.run_subprocess(sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore", "venv,.venv,submodules,node_modules", ".")
            if res1.returncode != 0 or res2.returncode != 0:
                raise Exception("pipreqs command failed")
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ pipreqs failed {self.log_time('clean_req', start)}", completed=100)
            self.console.print(Panel(f"[bold red]pipreqs failed: {e}[/bold red]\n• Missing __init__.py\n• Syntax error in .py files", title="pipreqs Error", border_style="red"))
            return
        self.progress.update(task_id, description="□ Deduplicating...", completed=60)
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"→ ❌ No requirements.txt {self.log_time('clean_req', start)}", completed=100)
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
        self.progress.update(task_id, description=f"✅ {len(deduped)} packages cleaned {self.log_time('clean_req', start)}", completed=100)

    async def install_requirements(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Installing requirements...", completed=0)
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"→ ❌ No requirements.txt {self.log_time('install_req', start)}", completed=100)
            return
        try:
            res = await self.run_subprocess(sys.executable, "-m", "pip", "install", "-r", self.requirements_file, "--upgrade", "--no-cache-dir")
            if res.returncode == 0:
                self.progress.update(task_id, description=f"✅ Requirements installed {self.log_time('install_req', start)}", completed=100)
                return
            raise Exception("Failed to install requirements via -r")
        except Exception:
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
                res2 = await self.run_subprocess(sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", *packages)
                if res2.returncode == 0:
                    self.progress.update(task_id, description=f"✅ Requirements {self.log_time('install_req', start)}", completed=100)
                else:
                    raise Exception("Fallback install failed")
            except Exception as e2:
                self.progress.update(task_id, description=f"→ ❌ Install failed {self.log_time('install_req', start)}", completed=100)
                self.console.print(Panel(str(e2), title="Requirements Error", border_style="red"))

    async def run_setup(self):
        if not self.ensure_pip():
            return
        self.console.print(Panel(Text("⚡ Setup Manager v2", justify="center"), title="Setup", box=ROUNDED, border_style="bright_blue"))
        with self.progress:
            tasks = [
                self.progress.add_task("Git submodules", total=100),
                self.progress.add_task("pip upgrade", total=100),
                self.progress.add_task("Package conflicts", total=100),
                self.progress.add_task("Essential packages", total=100),
                self.progress.add_task("Clean requirements", total=100),
                self.progress.add_task("Outdated packages", total=100),  # Placeholder
                self.progress.add_task("Install requirements", total=100)
            ]
            await asyncio.gather(
                self.sync_submodule(tasks[0]),
                self.upgrade_pip(tasks[1]),
                self.resolve_conflicts(tasks[2]),
                self.install_essentials(tasks[3]),
                self.clean_requirements(tasks[4]),
                self.install_requirements(tasks[6]),
            )
        self.thread_executor.shutdown(wait=False)
        self.process_executor.shutdown(wait=False)
        total_time = time.time() - self.start_time
        self.console.print(Panel(Text(f"🚀 Setup completed in {total_time:.1f}s", justify="center"), title="Complete", box=ROUNDED, border_style="green"))

if __name__ == "__main__":
    asyncio.run(SetupManager().run_setup())
