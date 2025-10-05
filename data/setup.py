import sys, os, time, subprocess, asyncio
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
            "common": ["pip", "setuptools", "wheel", "urllib3", "pipreqs", "Flask", "rapidfuzz", "aiocache", "aiokafka", "cachetools"]
        }

    def log_time(self, key, start):
        elapsed = time.time() - start
        self.task_times[key] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    async def _exec(self, args, check=False):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, lambda: subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=check))

    async def ensure_pip(self):
        start = time.time()
        try:
            await self._exec([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)
            await self._exec([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.console.print(Panel(f"[red]pip repair failed:[/red]\n{e}", title="pip Error"))
            self.task_times["ensure_pip"] = time.time() - start
            return False

    async def sync_submodule(self, task_id):
        start = time.time()
        if not os.path.isdir(".git"):
            self.progress.update(task_id, description=f"❌ Not a git repo {self.log_time('submodule', start)}", completed=100)
            return
        self.progress.update(task_id, description="□ Cloning/updating submodule...", completed=10)
        try:
            if os.path.isdir(self.submodule_path) and (os.path.isdir(os.path.join(self.submodule_path, ".git")) or os.path.islink(os.path.join(self.submodule_path, ".git"))):
                await self._exec(["git", "submodule", "sync", "--recursive"], check=True)
                await self._exec(["git", "submodule", "update", "--init", "--recursive", "--remote", "--jobs", "16", "--depth", "1"], check=True)
            else:
                await self._exec(["git", "submodule", "add", "--force", self.submodule_url, self.submodule_path], check=True)
                await self._exec(["git", "submodule", "sync", "--recursive"], check=True)
                await self._exec(["git", "submodule", "update", "--init", "--recursive", "--remote", "--jobs", "16", "--depth", "1"], check=True)
            self.progress.update(task_id, description=f"✅ Submodule ready {self.log_time('submodule', start)}", completed=100)
        except subprocess.CalledProcessError as e:
            self.progress.update(task_id, description=f"❌ Submodule failed {self.log_time('submodule', start)}", completed=100)
            self.console.print(Panel(f"[red]Git error:[/red]\n{e}", title="Git Error"))

    async def install_pkg_group(self, group_name, pkgs, task_id):
        start = time.time()
        self.progress.update(task_id, description=f"□ Installing {group_name}...", completed=10)
        try:
            await self._exec([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs, check=True)
            self.progress.update(task_id, description=f"✅ {group_name} {self.log_time(group_name, start)}", completed=100)
        except subprocess.CalledProcessError as e:
            self.progress.update(task_id, description=f"❌ {group_name} failed {self.log_time(group_name, start)}", completed=100)
            self.console.print(Panel(f"{e}", title=f"{group_name.title()} Error"))

    async def resolve_conflicts(self, task_id):
        start = time.time()
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"✅ No conflicts {self.log_time('conflicts', start)}", completed=100)
            return
        lines = open(self.requirements_file).read().splitlines()
        fixed = [("numpy>=2.0.0,<2.3.0" if "numpy" in l else "opencv-python-headless" if "opencv-python-headless" in l else l.strip()) for l in lines if l.strip() and not l.startswith("#")]
        open(self.requirements_file, "w").write("\n".join(fixed)+"\n")
        self.progress.update(task_id, description=f"✅ Conflicts resolved {self.log_time('conflicts', start)}", completed=100)

    async def install_requirements(self, task_id):
        start = time.time()
        if not os.path.exists(self.requirements_file):
            self.progress.update(task_id, description=f"⚠️ No requirements.txt", completed=100)
            return
        try:
            await self._exec([sys.executable, "-m", "pip", "install", "-r", self.requirements_file, "--upgrade"], check=True)
            self.progress.update(task_id, description=f"✅ Installed {self.log_time('requirements', start)}", completed=100)
        except subprocess.CalledProcessError as e:
            self.progress.update(task_id, description=f"❌ Install failed {self.log_time('requirements', start)}", completed=100)
            self.console.print(Panel(f"{e}", title="Requirements Error"))

    async def run_setup(self):
        if not await self.ensure_pip():
            return
        self.console.print(Panel(Text("⚡ Optimized Setup v4", justify="center"), title="Setup", box=ROUNDED, border_style="bright_blue"))
        with self.progress:
            tasks = {k:self.progress.add_task(k, total=100) for k in ["submodule","conflict","common","medium","heavy","requirements"]}
            await self.sync_submodule(tasks["submodule"])
            await asyncio.gather(
                self.resolve_conflicts(tasks["conflict"]),
                self.install_pkg_group("common", self.pkg_groups["common"], tasks["common"]),
                self.install_pkg_group("medium", self.pkg_groups["medium"], tasks["medium"]),
                self.install_pkg_group("heavy", self.pkg_groups["heavy"], tasks["heavy"]),
                self.install_requirements(tasks["requirements"])
            )
        total=time.time()-self.start_time
        report="\n".join(f"[cyan]{k}[/cyan]: {v:.2f}s" for k,v in self.task_times.items())
        self.console.print(Panel(Text(f"🚀 Completed in {total:.1f}s", justify="center"), title="Done", border_style="green"))
        self.console.print(Panel(report, title="Task Timing", border_style="cyan"))

if __name__=="__main__":
    asyncio.run(SetupManager().run_setup())
