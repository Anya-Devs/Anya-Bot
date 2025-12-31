"""
installing onnxruntime:
& c:/Users/Owner/Anya-Bot-1/.venv/Scripts/python.exe -m pip install --pre onnxruntime --extra-index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/ort-nightly/pypi/simple/
& c:/Users/Owner/Anya-Bot-1/.venv/Scripts/python.exe -m pip install python-Levenshtein
& c:/Users/Owner/Anya-Bot-1/.venv/Scripts/python.exe -m pip install yt-dlp
"""

import sys, os, time, subprocess, asyncio
from concurrent.futures import ThreadPoolExecutor


def ensure_rich():
    """Ensure rich and dotenv are installed before importing."""
    try:
        import rich
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich", "python-dotenv"])
ensure_rich()


from rich.console import Console
from rich.panel import Panel
from rich.box import ROUNDED
from rich.text import Text
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    TaskProgressColumn, TimeRemainingColumn
)


class SetupManager:
    def __init__(self):
        self.console = Console()
        # Default to your GitHub repo if environment variable missing
        self.submodule_url = os.environ.get(
            "SUBMODULE_URL",
            "https://github.com/EnterNameBros/poketwo_autonamer.git"
        )
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
            "emoji": ["emoji==1.7.0"],
            "heavy": ["onnxruntime", "opencv-python-headless"],
            "medium": ["python-Levenshtein", "cloudinary"],
            "common": [
                "pip", "setuptools", "wheel", "urllib3", "pipreqs",
                "Flask", "rapidfuzz", "aiocache", "aiokafka",
                "cachetools", "orjson"
            ]
        }

    def log_time(self, key, start):
        elapsed = time.time() - start
        self.task_times[key] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    async def _exec(self, args, check=False):
        """Run a command asynchronously using subprocess."""
        loop = asyncio.get_event_loop()

        def run():
            try:
                return subprocess.run(
                    args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, check=check
                )
            except subprocess.CalledProcessError as e:
                return e

        return await loop.run_in_executor(self.executor, run)

    async def run_cmd(self, *args):
        cp = await self._exec(list(args))
        return 0 if cp.returncode == 0 else 1

    async def ensure_pip(self):
        start = time.time()
        try:
            await self._exec([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)
            await self._exec([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            msg = e.stderr or str(e)
            self.console.print(Panel(f"[red]pip repair failed:[/red]\n{msg}", title="pip Error"))
            self.task_times["ensure_pip"] = time.time() - start
            return False

    async def sync_submodule(self, task_id):
        start = time.time()

        if not os.path.isdir(".git"):
            self.progress.update(task_id, description=f"⚠️ Not a git repo {self.log_time('submodule', start)}", completed=100)
            return

        # Auto-skip if URL missing or invalid
        if not self.submodule_url or not self.submodule_url.startswith("http"):
            self.progress.update(task_id, description=f"⚠️ Skipped (no SUBMODULE_URL){self.log_time('submodule', start)}", completed=100)
            return

        try:
            if os.path.isdir(self.submodule_path):
                git_meta = os.path.join(self.submodule_path, ".git")
                if os.path.isdir(git_meta) or os.path.islink(git_meta):
                    self.progress.update(task_id, description="□ Updating existing submodule...", completed=15)
                    await self._exec(["git", "submodule", "sync", "--recursive"], check=True)
                    await self._exec([
                        "git", "submodule", "update", "--init", "--recursive",
                        "--remote", "--jobs", "16", "--depth", "1"
                    ], check=True)
                    self.progress.update(task_id, description=f"✅ Submodule updated {self.log_time('submodule', start)}", completed=100)
                    return

            self.progress.update(task_id, description="□ Cloning submodule...", completed=10)
            await self._exec(["git", "submodule", "add", "--force", self.submodule_url, self.submodule_path], check=True)
            await self._exec(["git", "submodule", "sync", "--recursive"], check=True)
            await self._exec([
                "git", "submodule", "update", "--init", "--recursive",
                "--remote", "--jobs", "16", "--depth", "1"
            ], check=True)
            self.progress.update(task_id, description=f"✅ Submodule cloned {self.log_time('submodule', start)}", completed=100)

        except subprocess.CalledProcessError as e:
            stderr = e.stderr or str(e)
            self.progress.update(task_id, description=f"❌ Submodule failed {self.log_time('submodule', start)}", completed=100)
            self.console.print(Panel(f"[red]Git error:[/red]\n{stderr}", title="Git Error"))

    async def install_pkg_group(self, group_name, pkgs, task_id):
        start = time.time()
        self.progress.update(task_id, description=f"□ Installing {group_name}...", completed=10)
        try:
            await self._exec([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs, check=True)
            self.progress.update(task_id, description=f"✅ {group_name} {self.log_time(group_name, start)}", completed=100)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or str(e)
            self.progress.update(task_id, description=f"❌ {group_name} failed {self.log_time(group_name, start)}", completed=100)
            self.console.print(Panel(stderr, title=f"{group_name.title()} Error"))

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
            self.progress.update(task_id, description="⚠️ No requirements.txt", completed=100)
            return
        try:
            await self._exec([sys.executable, "-m", "pip", "install", "-r", self.requirements_file, "--upgrade"], check=True)
            self.progress.update(task_id, description=f"✅ Installed {self.log_time('requirements', start)}", completed=100)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or str(e)
            self.progress.update(task_id, description=f"❌ Install failed {self.log_time('requirements', start)}", completed=100)
            self.console.print(Panel(stderr, title="Requirements Error"))

    async def run_setup(self):
        if not await self.ensure_pip():
            return

        self.console.print(Panel(
            Text("⚡ Optimized Setup v3", justify="center"),
            title="Setup", box=ROUNDED, border_style="bright_blue"
        ))

        with self.progress:
            tasks = {
                "submodule": self.progress.add_task("Git submodule", total=100),
                "emoji": self.progress.add_task("Emoji 1.7.0", total=100),
                "conflict": self.progress.add_task("Package conflicts", total=100),
                "common": self.progress.add_task("Common packages", total=100),
                "medium": self.progress.add_task("Medium packages", total=100),
                "heavy": self.progress.add_task("Heavy packages", total=100),
                "requirements": self.progress.add_task("Install requirements", total=100)
            }

            # Run submodule + emoji first
            await self.sync_submodule(tasks["submodule"])
            await self.install_pkg_group("emoji", self.pkg_groups["emoji"], tasks["emoji"])

            # Then run others concurrently
            await asyncio.gather(
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
