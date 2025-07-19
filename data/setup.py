import sys
import subprocess
import os
import time
import shutil
import re
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any

def ensure_essentials():
    essentials = ["pip", "setuptools", "wheel", "rich", "python-dotenv"]
    try:
        import rich  # noqa: F401
        import dotenv  # noqa: F401
    except ImportError:
        print("Installing essential packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *essentials])

ensure_essentials()

from dotenv import load_dotenv
from rich.traceback import install
from rich.console import Console
from rich.panel import Panel
from rich.box import ROUNDED
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

install(show_locals=True)
load_dotenv(dotenv_path=os.path.join(".github", ".env"))


class SetupManager:
    def __init__(self):
        self.console = Console()
        self.debug = bool(os.getenv("DEBUG"))
        token = os.getenv("GIT_ACCESS_TOKEN")
        base_url = "github.com/senko-sleep/Poketwo-AutoNamer.git"
        self.submodule_url = f"https://{token}:x-oauth-basic@{base_url}" if token else f"https://{base_url}"
        self.submodule_path = "submodules/poketwo_autonamer"
        self.requirements_file = "requirements.txt"
        self.start_time = time.time()
        self.task_times = {}
        self.executor = ThreadPoolExecutor(max_workers=32)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        )
        self.error_log = []
        self.essential_packages = [
            "pip", "setuptools", "wheel",
            "rich", "aiohttp", "python-dotenv",
            "pillow", "numpy", "opencv-python-headless"
        ]

    def log_error(self, error_type: str, details: Dict[str, Any]) -> None:
        self.error_log.append({
            "timestamp": time.time(),
            "type": error_type,
            **details
        })
        if self.debug:
            self.console.print(f"[red]DEBUG: {error_type}[/red]", details)

    async def run_cmd_with_details(self, *args, **kwargs):
        try:
            start_time = time.time()
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **kwargs
            )
            stdout, stderr = await proc.communicate()
            duration = time.time() - start_time
            stdout_str = stdout.decode('utf-8', errors='replace').strip()
            stderr_str = stderr.decode('utf-8', errors='replace').strip()
            if proc.returncode != 0:
                self.log_error("command_failed", {
                    "command": args,
                    "returncode": proc.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "duration": duration
                })
            return proc.returncode == 0, stdout_str, stderr_str, None
        except Exception as e:
            self.log_error("command_exception", {
                "command": args,
                "exception": str(e),
                "traceback": traceback.format_exc()
            })
            return False, "", "", e

    async def verify_git_setup(self):
        checks = [
            ("git", "--version"),
            ("git", "config", "--get", "user.name"),
            ("git", "config", "--get", "user.email"),
            ("git", "config", "--get", "remote.origin.url")
        ]
        results = {}
        all_passed = True
        for cmd in checks:
            success, stdout, stderr, exc = await self.run_cmd_with_details(*cmd)
            check_name = " ".join(cmd)
            results[check_name] = {
                "success": success,
                "output": stdout if success else stderr,
                "exception": exc
            }
            all_passed &= success
        return all_passed, results

    async def fast_clone_attempt(self, url: str, path: str):
        strategies = [
            {"name": "Shallow clone", "cmd": ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", url, path]},
            {"name": "Standard clone", "cmd": ["git", "clone", url, path]},
            {"name": "Fallback clone", "cmd": ["git", "clone", "--depth", "1", "--no-single-branch", url, path]}
        ]
        results = []
        for s in strategies:
            success, stdout, stderr, exc = await self.run_cmd_with_details(*s["cmd"])
            results.append({
                "strategy": s["name"],
                "command": " ".join(s["cmd"]),
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "exception": exc
            })
            if success:
                return True, {"successful": results[-1]}
        return False, {"attempts": results}

    async def sync_submodule(self, task_id):
        start = time.time()
        try:
            if os.path.exists(self.submodule_path) and any(os.scandir(self.submodule_path)):
                self.progress.update(task_id, description=f"✅ Using existing submodule {self.log_time('submodule', start)}", completed=100)
                return True

            self.progress.update(task_id, description="□ Verifying Git setup...", completed=5)
            git_ok, git_status = await self.verify_git_setup()
            if not git_ok:
                raise RuntimeError(f"Git setup verification failed:\n{git_status}")

            self.progress.update(task_id, description="□ Preparing workspace...", completed=15)
            if os.path.exists(self.submodule_path):
                shutil.rmtree(self.submodule_path)
            os.makedirs(os.path.dirname(self.submodule_path), exist_ok=True)

            self.progress.update(task_id, description="□ Cloning submodule...", completed=30)
            success, result = await self.fast_clone_attempt(self.submodule_url, self.submodule_path)
            if not success:
                error_details = "\n".join(
                    f"[bold]{a['strategy']}[/bold]\nCommand: {a['command']}\nError: {a['stderr']}"
                    for a in result.get("attempts", [])
                )
                raise RuntimeError(f"All clone attempts failed:\n{error_details}")

            self.progress.update(task_id, description="□ Initializing...", completed=70)
            init_cmds = [
                ["git", "submodule", "init"],
                ["git", "submodule", "update", "--init", "--recursive", "--depth=1"]
            ]
            for cmd in init_cmds:
                success, _, stderr, exc = await self.run_cmd_with_details(*cmd)
                if not success:
                    raise RuntimeError(f"Submodule init failed\nCommand: {' '.join(cmd)}\nError: {stderr}\nException: {exc}")

            self.progress.update(task_id, description=f"✅ Submodule ready {self.log_time('submodule', start)}", completed=100)
            return True

        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ Submodule failed {self.log_time('submodule', start)}", completed=100)
            error_report = Panel(
                f"[bold red]Submodule Error[/bold red]\n\n"
                f"[yellow]Error Type:[/yellow] {type(e).__name__}\n"
                f"[yellow]Message:[/yellow] {str(e)}\n\n"
                f"[blue]Debug Info:[/blue]\n"
                f"• Working Dir: {os.getcwd()}\n"
                f"• Python Version: {sys.version}\n"
                f"• Git Status: {git_status if 'git_status' in locals() else 'N/A'}\n"
                f"• Submodule Path: {self.submodule_path}\n"
                f"• URL: {self.submodule_url.replace(os.getenv('GIT_ACCESS_TOKEN', ''), '***')}\n\n"
                f"[blue]Error Log (last 5):[/blue]\n" +
                "\n".join(f"• {err['type']}: {err.get('command', 'N/A')} - {err.get('stderr', 'N/A')}" for err in self.error_log[-5:]) + "\n\n"
                f"[blue]Traceback:[/blue]\n{traceback.format_exc()}\n\n"
                f"[green]Suggestions:[/green]\n"
                "• Check network connection\n"
                "• Verify Git credentials\n"
                "• Manual clone: git clone {url} {path}\n"
                "• Set DEBUG=1 for more details\n"
                "• Check filesystem permissions",
                title="Detailed Error Report",
                border_style="red"
            )
            self.console.print(error_report)
            return False

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
            success, stdout, stderr, _ = await self.run_cmd_with_details(
                sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"
            )
            if success:
                self.progress.update(task_id, description=f"✅ pip {self.log_time('pip', start)}", completed=100)
            else:
                raise RuntimeError(f"pip upgrade failed: {stderr}")
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ pip failed {self.log_time('pip', start)}", completed=100)
            self.console.print(Panel(str(e), title="pip Error", border_style="red"))

    async def mega_install(self, packages, task_id, task_name):
        start = time.time()
        self.progress.update(task_id, description=f"□ Installing {len(packages)} {task_name}...", completed=0)
        try:
            # Bulk install with no cache and no version check
            success, stdout, stderr, _ = await self.run_cmd_with_details(
                sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
                "--disable-pip-version-check", *packages
            )
            # Retry without PIL if it fails due to PIL
            if not success and "No matching distribution found for PIL" in stderr:
                filtered_packages = [p for p in packages if not p.lower().startswith("pil")]
                if filtered_packages != packages:
                    success, stdout, stderr, _ = await self.run_cmd_with_details(
                        sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
                        "--disable-pip-version-check", *filtered_packages
                    )
            if success:
                self.progress.update(task_id, description=f"✅ {len(packages)} {task_name} {self.log_time(task_name, start)}", completed=100)
            else:
                raise RuntimeError(f"Installation failed: {stderr}")
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ {task_name} failed {self.log_time(task_name, start)}", completed=100)
            self.console.print(Panel(str(e), title=f"{task_name.title()} Error", border_style="red"))

    async def install_essentials(self, task_id):
        await self.mega_install(self.essential_packages, task_id, "essentials")

    def check_syntax_errors(self):
        # Synchronous, runs compileall quietly
        import compileall
        result = compileall.compile_dir('.', quiet=1)
        if not result:
            self.console.print(Panel(
                "[bold red]Syntax errors detected in your Python files.[/bold red]",
                title="Syntax Error",
                border_style="red"
            ))
            return False
        return True

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
        if not self.check_syntax_errors():
            self.progress.update(task_id, description=f"→ ❌ Syntax error {self.log_time('clean_req', start)}", completed=100)
            return
        try:
            success, _, stderr, _ = await self.run_cmd_with_details(
                sys.executable, "-m", "pip", "install", "--upgrade", "pipreqs"
            )
            if not success:
                raise RuntimeError(f"pipreqs installation failed: {stderr}")

            success, _, stderr, _ = await self.run_cmd_with_details(
                sys.executable, "-m", "pipreqs.pipreqs", "--force", "--ignore",
                "venv,.venv,submodules,node_modules", "."
            )
            if not success:
                raise RuntimeError(f"pipreqs generation failed: {stderr}")

        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ pipreqs failed {self.log_time('clean_req', start)}", completed=100)
            self.console.print(Panel(
                f"[bold red]pipreqs failed: {e}[/bold red]\n• Missing __init__.py\n• Syntax error in .py files",
                title="pipreqs Error",
                border_style="red"
            ))
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
            with open(self.requirements_file, "r") as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            await self.mega_install(packages, task_id, "requirements")
        except Exception as e:
            self.progress.update(task_id, description=f"→ ❌ Install failed {self.log_time('install_req', start)}", completed=100)
            self.console.print(Panel(str(e), title="Requirements Error", border_style="red"))

    def log_time(self, name: str, start: float) -> str:
        elapsed = time.time() - start
        self.task_times[name] = elapsed
        return f"[dim]({elapsed:.1f}s)[/dim]"

    async def run_setup(self):
        try:
            self.console.print(Panel(
                Text("⚡ Setup Manager v4", justify="center"),
                title="Setup",
                box=ROUNDED,
                border_style="bright_blue"
            ))

            with self.progress:
                pip_task = self.progress.add_task("Upgrading pip", total=100)
                essentials_task = self.progress.add_task("Installing essentials", total=100)
                submodule_task = self.progress.add_task("Git submodules", total=100)
                conflict_task = self.progress.add_task("Resolving conflicts", total=100)
                requirements_task = self.progress.add_task("Installing requirements", total=100)

                await self.upgrade_pip(pip_task)
                await self.install_essentials(essentials_task)
                if not await self.sync_submodule(submodule_task):
                    return
                await self.resolve_conflicts(conflict_task)
                await self.install_requirements(requirements_task)

            self.executor.shutdown(wait=False)
            total_time = time.time() - self.start_time
            self.console.print(Panel(
                Text(f"🚀 Setup completed in {total_time:.1f}s", justify="center"),
                title="Complete",
                box=ROUNDED,
                border_style="green"
            ))
        except Exception as e:
            self.console.print(Panel(
                f"[red]Setup failed: {e}[/red]\n{traceback.format_exc()}",
                title="Error",
                border_style="red"
            ))

if __name__ == "__main__":
    manager = SetupManager()
    asyncio.run(manager.run_setup())
