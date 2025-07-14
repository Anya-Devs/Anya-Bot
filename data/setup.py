import sys
import asyncio
import subprocess
import time
import os
os.system('pip install rich')

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
        # Use token if present for private submodules
        token = os.getenv("GIT_ACCESS_TOKEN")
        if token:
            self.submodule_url = f"https://{token}:x-oauth-basic@github.com/senko-sleep/Poketwo-AutoNamer.git"
        else:
            self.submodule_url = "https://github.com/senko-sleep/Poketwo-AutoNamer.git"
        self.submodule_path = "submodules/poketwo_autonamer"
        self.essential_packages = [
            "urllib3", "pipreqs", "onnxruntime",
            "opencv-python-headless", "python-Levenshtein"
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
            console=self.console
        )

    def log_time(self, task_name, start_time):
        elapsed = time.time() - start_time
        self.task_times[task_name] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

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
        # No-op: handled by submodule_url with token
        return True

    async def sync_submodule(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Git auth check...", completed=10)
        if not self.ensure_git_login():
            self.progress.update(task_id, description="→ ❌ Git auth failed", completed=100)
            self.console.print(Panel(
                "[bold red]Git authorization failed.[/bold red]\n• Check your token or SSH key\n• Did you forget to set up .env or ~/.netrc?",
                title="Git Error",
                border_style="red"))
            return
        self.progress.update(task_id, description="□ Submodule sync...", completed=30)
        try:
            if not os.path.exists(os.path.join(self.submodule_path, ".git")):
                await self.run_cmd_ultra_fast("git", "submodule", "add", self.submodule_url, self.submodule_path)
            self.progress.update(task_id, description="□ Parallel submodule update...", completed=60)
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
        if not os.path.exists(self.requirements_file):
            elapsed = self.log_time("conflicts", start)
            self.progress.update(task_id, description=f"✅ No conflicts {elapsed}", completed=100)
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
        elapsed = self.log_time("conflicts", start)
        self.progress.update(task_id, description=f"✅ Conflicts fixed {elapsed}", completed=100)

    async def upgrade_pip(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ pip --upgrade...", completed=0)
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pip", "install", "--upgrade", "pip",
            "--no-cache-dir", "--disable-pip-version-check", "--quiet"
        )
        elapsed = self.log_time("pip", start)
        status = "✅" if retcode == 0 else "→ ❌"
        self.progress.update(task_id, description=f"{status} pip {elapsed}", completed=100)

    async def mega_install(self, packages, task_id, task_name):
        start = time.time()
        total = len(packages)
        self.progress.update(task_id, description=f"□ Installing {total} {task_name}...", completed=0)
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
            "--disable-pip-version-check", "--quiet", "--no-warn-script-location",
            *packages
        )
        elapsed = self.log_time(task_name, start)
        status = "✅" if retcode == 0 else "→ ❌"
        self.progress.update(task_id, description=f"{status} {total} {task_name} {elapsed}", completed=100)

    async def install_essentials(self, task_id):
        await self.mega_install(self.essential_packages, task_id, "essentials")

    async def update_outdated(self, task_id):
        start = time.time()
        self.progress.update(task_id, description="□ Checking outdated...", completed=0)
        result = await self.run_cmd_with_output(sys.executable, "-m", "pip", "list", "--outdated", "--format=columns")
        if result.returncode != 0:
            elapsed = self.log_time("outdated", start)
            self.progress.update(task_id, description=f"→ ❌ Check failed {elapsed}", completed=100)
            self.console.print(Panel(result.stderr or "[red]Unknown error[/red]", title="Outdated Check Error", border_style="red"))
            return
        lines = result.stdout.strip().splitlines()
        packages = []
        for line in lines[2:]:  # skip header lines
            parts = line.split()
            if parts:
                packages.append(parts[0])
        if not packages:
            elapsed = self.log_time("outdated", start)
            self.progress.update(task_id, description=f"✅ All current {elapsed}", completed=100)
            return
        self.progress.update(task_id, description=f"□ Updating {len(packages)} packages...", completed=30)
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
            "--disable-pip-version-check", "--quiet", "--no-warn-script-location",
            *packages
        )
        elapsed = self.log_time("outdated", start)
        status = "✅" if retcode == 0 else "→ ❌"
        self.progress.update(task_id, description=f"{status} {len(packages)} updated {elapsed}", completed=100)

    def add_missing_init_py(self):
        # Walk all folders and add __init__.py if missing
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
        # Add missing __init__.py files before running pipreqs
        self.add_missing_init_py()
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore",
            "venv,.venv,submodules,node_modules", "."
        )
        if retcode != 0:
            elapsed = self.log_time("clean_req", start)
            self.progress.update(task_id, description=f"→ ❌ pipreqs failed {elapsed}", completed=100)
            self.console.print(Panel(f"[bold red]pipreqs failed. Possible causes:[/bold red]\n• Missing __init__.py\n• Syntax error in .py files", title="pipreqs Error", border_style="red"))
            return
        self.progress.update(task_id, description="□ Deduplicating...", completed=60)
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
        if not os.path.exists(self.requirements_file):
            elapsed = self.log_time("install_req", start)
            self.progress.update(task_id, description=f"→ ❌ No requirements.txt {elapsed}", completed=100)
            return
        self.progress.update(task_id, description="□ Batch requirements install...", completed=30)
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
            "--disable-pip-version-check", "--quiet", "--no-warn-script-location",
            "-r", self.requirements_file
        )
        if retcode == 0:
            elapsed = self.log_time("install_req", start)
            self.progress.update(task_id, description=f"✅ Requirements installed {elapsed}", completed=100)
            return
        self.progress.update(task_id, description="□ Individual package install...", completed=60)
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
        retcode = await self.run_cmd_ultra_fast(
            sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
            "--disable-pip-version-check", "--quiet", "--no-warn-script-location",
            *packages
        )
        elapsed = self.log_time("install_req", start)
        status = "✅" if retcode == 0 else "→ ❌"
        self.progress.update(task_id, description=f"{status} Requirements {elapsed}", completed=100)

    async def run_setup(self):
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
                self.update_outdated(tasks[5]),
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