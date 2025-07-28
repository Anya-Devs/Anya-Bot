import sys, os, re, time, subprocess, asyncio
from concurrent.futures import ThreadPoolExecutor

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

class SetupManager:
    def __init__(self):
        self.console = Console()
        self.submodule_url = "https://github.com/senko-sleep/Poketwo-AutoNamer.git"
        self.submodule_path = "submodules/poketwo_autonamer"
        self.requirements_file = "requirements.txt"
        self.executor = ThreadPoolExecutor(max_workers=16)
        self.task_times = {}
        self.start_time = time.time()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        )
        self.pkg_groups = {
            "heavy": ["onnxruntime", "opencv-python-headless"],
            "medium": ["emoji==1.7.0", "python-Levenshtein"],
            "common": ["pip", "setuptools", "wheel", "urllib3", "pipreqs", "Flask"]
        }

    def log_time(self, key, start):
        elapsed = time.time() - start
        self.task_times[key] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    def ensure_pip(self):
        try:
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True, capture_output=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True, capture_output=True)
            return True
        except Exception as e:
            self.console.print(Panel(f"[red]pip repair failed:[/red] {e}", title="pip Error"))
            return False

    async def run_cmd(self, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, lambda: subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode)

    async def sync_submodule(self, task_id):
        start = time.time()
        if os.path.exists(os.path.join(self.submodule_path, ".git")):
            self.progress.update(task_id, description=f"✅ Already exists {self.log_time('submodule', start)}", completed=100)
            return
        self.progress.update(task_id, description="□ Cloning submodule...", completed=10)
        await self.run_cmd("git", "submodule", "add", self.submodule_url, self.submodule_path)
        await self.run_cmd("git", "submodule", "sync")
        await self.run_cmd("git", "submodule", "update", "--init", "--remote", "--jobs", "16", "--depth", "1")
        self.progress.update(task_id, description=f"✅ Submodules {self.log_time('submodule', start)}", completed=100)

    async def install_pkg_group(self, group_name, pkgs, task_id):
        start = time.time()
        self.progress.update(task_id, description=f"□ Installing {group_name}...", completed=10)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs, check=True, capture_output=True)
            self.progress.update(task_id, description=f"✅ {group_name} {self.log_time(group_name, start)}", completed=100)
        except Exception as e:
            self.progress.update(task_id, description=f"❌ {group_name} failed {self.log_time(group_name, start)}", completed=100)
            self.console.print(Panel(str(e), title=f"{group_name.title()} Error"))

    async def resolve_conflicts(self, task_id):
        start = time.time()
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"✅ No conflicts {self.log_time('conflicts', start)}", completed=100)
            return
        with open(self.requirements_file) as f:
            lines = f.read().splitlines()
        fixed = []
        for line in lines:
            if "numpy" in line:
                fixed.append("numpy>=2.0.0,<2.3.0")
            elif "opencv-python-headless" in line:
                fixed.append("opencv-python-headless")
            elif line.strip() and not line.startswith("#"):
                fixed.append(line.strip())
        with open(self.requirements_file, "w") as f:
            f.write("\n".join(fixed) + "\n")
        self.progress.update(task_id, description=f"✅ Conflicts resolved {self.log_time('conflicts', start)}", completed=100)

    async def install_requirements(self, task_id):
        start = time.time()
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"⚠️ No requirements.txt", completed=100)
            return
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", self.requirements_file, "--upgrade"], check=True, capture_output=True)
            self.progress.update(task_id, description=f"✅ Installed {self.log_time('requirements', start)}", completed=100)
        except Exception as e:
            self.progress.update(task_id, description=f"❌ Install failed {self.log_time('requirements', start)}", completed=100)
            self.console.print(Panel(str(e), title="Requirements Error"))

    async def run_setup(self):
        if not self.ensure_pip():
            return
        self.console.print(Panel(Text("⚡ Optimized Setup v3", justify="center"), title="Setup", box=ROUNDED, border_style="bright_blue"))

        with self.progress:
            tasks = {
                "submodule": self.progress.add_task("Git submodule", total=100),
                "conflict": self.progress.add_task("Package conflicts", total=100),
                "common": self.progress.add_task("Common packages", total=100),
                "medium": self.progress.add_task("Medium packages", total=100),
                "heavy": self.progress.add_task("Heavy packages", total=100),
                "requirements": self.progress.add_task("Install requirements", total=100)
            }
            await asyncio.gather(
                self.sync_submodule(tasks["submodule"]),
                self.resolve_conflicts(tasks["conflict"]),
                self.install_pkg_group("common", self.pkg_groups["common"], tasks["common"]),
                self.install_pkg_group("medium", self.pkg_groups["medium"], tasks["medium"]),
                self.install_pkg_group("heavy", self.pkg_groups["heavy"], tasks["heavy"]),
                self.install_requirements(tasks["requirements"])
            )

        total = time.time() - self.start_time
        report = "\n".join(f"[cyan]{k}[/cyan]: {v:.2f}s" for k, v in self.task_times.items())
        self.console.print(Panel(Text(f"🚀 Completed in {total:.1f}s", justify="center"), title="Done", border_style="green"))
        self.console.print(Panel(report, title="Task Timing", border_style="cyan"))

if __name__ == "__main__":
    asyncio.run(SetupManager().run_setup())
