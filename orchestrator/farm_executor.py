"""
Farm Executor - SSH/Docker/ADB Remote Execution
================================================
ينفذ المهام على المزارع عبر SSH → Docker → ADB

Flow per farm:
  1. SSH to farm.server_ip
  2. docker start farm_{farm_id} (redroid container)
  3. Wait for ADB readiness on farm.adb_port
  4. Run vrbot_main.py with task_type via ADB shell
  5. Monitor execution (timeout, health checks)
  6. docker stop farm_{farm_id}

Requires:
  - SSH key or password access to farm servers
  - Docker + redroid containers pre-configured on servers
  - vrbot_main.py deployed on each server at /opt/vrbot/agent/
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict

from models import Farm, FarmStatus, TaskRequest, TaskType

logger = logging.getLogger("farm_executor")

# ── Configuration ──
SSH_TIMEOUT = 30        # seconds for SSH connection
ADB_WAIT_MAX = 60      # seconds to wait for ADB readiness
DOCKER_STOP_TIMEOUT = 30
VRBOT_AGENT_PATH = "/opt/vrbot/agent"
VRBOT_VENV_PYTHON = "/opt/vrbot/agent/venv/bin/python3"  # or system python

# Task type → vrbot_main.py task list
TASK_TYPE_MAP = {
    TaskType.FARMING: "gather",              # Auto-gather (5 marches, 5.5h cycle)
    TaskType.DAILY: "daily_tasks",           # All daily tasks (construction, research, etc.)
    TaskType.NIFLING: "niflung",             # Nifling battle
}

# Extended task lists for daily
DAILY_TASK_LIST = [
    "construction", "research", "train_troops", "heal_troops",
    "claim_vip", "claim_free_chest", "alliance_help",
    "alliance_gifts", "arena_battles", "heroes",
]


class FarmExecutor:
    """Executes bot tasks on remote farm containers via SSH + Docker + ADB."""

    def __init__(self, ssh_password: str = None, ssh_key_path: str = None):
        """
        Args:
            ssh_password: SSH password for farm servers (from env or secrets)
            ssh_key_path: Path to SSH private key (alternative to password)
        """
        self.ssh_password = ssh_password or os.getenv("SERVER_PASSWORD", "")
        self.ssh_key_path = ssh_key_path or os.getenv("SSH_KEY_PATH", "")
        self.active_executions: Dict[str, asyncio.Task] = {}

    # ══════════════════════════════════════
    #  SSH Command Execution
    # ══════════════════════════════════════

    async def _ssh_run(self, server_ip: str, command: str,
                       timeout: int = SSH_TIMEOUT) -> tuple:
        """Execute a command on a remote server via SSH.

        Returns:
            (stdout, stderr, return_code)
        """
        ssh_args = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=30",
        ]

        # Authentication
        if self.ssh_key_path and os.path.exists(self.ssh_key_path):
            ssh_args.extend(["-i", self.ssh_key_path])
        # If using password, we use sshpass
        elif self.ssh_password:
            ssh_args = [
                "sshpass", "-p", self.ssh_password
            ] + ssh_args

        ssh_args.extend([f"root@{server_ip}", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return (
                stdout.decode("utf-8", errors="replace").strip(),
                stderr.decode("utf-8", errors="replace").strip(),
                proc.returncode,
            )
        except asyncio.TimeoutError:
            logger.error(f"SSH timeout to {server_ip} ({timeout}s)")
            return "", "SSH timeout", -1
        except FileNotFoundError:
            logger.error("sshpass not installed — install with: apt install sshpass")
            return "", "sshpass not found", -1
        except Exception as e:
            logger.error(f"SSH error to {server_ip}: {e}")
            return "", str(e), -1

    # ══════════════════════════════════════
    #  Container Management
    # ══════════════════════════════════════

    async def start_container(self, farm: Farm) -> bool:
        """Start the Docker redroid container for a farm.

        Container naming convention: farm_{farm_id}
        ADB port: farm.adb_port (e.g., 5555, 5557, etc.)
        """
        container_name = farm.container_name or f"farm_{farm.id}"
        farm.status = FarmStatus.STARTING

        logger.info(f"  🐳 Starting container {container_name} on {farm.server_ip}")

        # Check if container exists and is running
        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"docker inspect -f '{{{{.State.Running}}}}' {container_name} 2>/dev/null || echo 'notfound'"
        )

        if "true" in stdout.lower():
            logger.info(f"  🐳 Container {container_name} already running")
            farm.status = FarmStatus.RUNNING
            return True

        if "notfound" in stdout or "false" in stdout.lower():
            # Container exists but stopped — start it
            if "false" in stdout.lower():
                stdout, stderr, rc = await self._ssh_run(
                    farm.server_ip,
                    f"docker start {container_name}",
                    timeout=60
                )
            else:
                # Container doesn't exist — create it
                adb_port = farm.adb_port or 5555
                stdout, stderr, rc = await self._ssh_run(
                    farm.server_ip,
                    f"docker run -d --name {container_name} "
                    f"--privileged "
                    f"-p {adb_port}:5555 "
                    f"-v /opt/vrbot/agent:/opt/vrbot/agent:ro "
                    f"redroid/redroid:12.0.0-latest "
                    f"androidboot.redroid_gpu_mode=guest "
                    f"androidboot.redroid_width=1280 "
                    f"androidboot.redroid_height=720",
                    timeout=120
                )

            if rc != 0:
                logger.error(f"  ❌ Failed to start container: {stderr}")
                farm.status = FarmStatus.ERROR
                return False

        # Wait for ADB readiness
        adb_ready = await self._wait_for_adb(farm)
        if adb_ready:
            farm.status = FarmStatus.RUNNING
            logger.info(f"  ✅ Container {container_name} ready (ADB port {farm.adb_port})")
            return True
        else:
            logger.warning(f"  ⚠️ Container started but ADB not ready")
            farm.status = FarmStatus.ERROR
            return False

    async def stop_container(self, farm: Farm) -> bool:
        """Stop the Docker container for a farm."""
        container_name = farm.container_name or f"farm_{farm.id}"
        farm.status = FarmStatus.STOPPING

        logger.info(f"  🐳 Stopping container {container_name}")

        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"docker stop -t {DOCKER_STOP_TIMEOUT} {container_name}",
            timeout=DOCKER_STOP_TIMEOUT + 10
        )

        farm.status = FarmStatus.IDLE

        if rc != 0:
            logger.warning(f"  ⚠️ Container stop returned {rc}: {stderr}")
            # Force kill if graceful stop failed
            await self._ssh_run(
                farm.server_ip,
                f"docker kill {container_name} 2>/dev/null; true"
            )

        return True

    async def _wait_for_adb(self, farm: Farm) -> bool:
        """Wait for ADB to become ready on the container."""
        adb_port = farm.adb_port or 5555
        elapsed = 0
        interval = 5

        while elapsed < ADB_WAIT_MAX:
            stdout, stderr, rc = await self._ssh_run(
                farm.server_ip,
                f"adb connect localhost:{adb_port} && "
                f"adb -s localhost:{adb_port} shell getprop sys.boot_completed 2>/dev/null",
                timeout=15
            )

            if "1" in stdout:
                return True

            elapsed += interval
            await asyncio.sleep(interval)

        return False

    # ══════════════════════════════════════
    #  Task Execution
    # ══════════════════════════════════════

    async def run_task_on_farm(self, farm: Farm, task: TaskRequest) -> bool:
        """Execute a bot task on a farm via SSH → ADB.

        The actual execution runs vrbot_main.py in single-task mode:
          python3 vrbot_main.py --task <task_name> --adb-serial localhost:<port>

        For FARMING: runs the 'gather' task
        For DAILY: runs all daily tasks in sequence
        For NIFLING: runs the 'niflung' task
        """
        adb_port = farm.adb_port or 5555
        adb_serial = f"localhost:{adb_port}"

        # Determine which tasks to run
        if task.task_type == TaskType.DAILY:
            # Daily = run multiple tasks in sequence
            task_list = ",".join(DAILY_TASK_LIST)
            task_arg = f"--tasks {task_list}"
        else:
            task_name = TASK_TYPE_MAP.get(task.task_type, "gather")
            task_arg = f"--task {task_name}"

        # Build the remote command
        # The bot runs on the server where the container is
        cmd = (
            f"cd {VRBOT_AGENT_PATH} && "
            f"ADB_SERIAL={adb_serial} "
            f"FARM_ID={farm.id} "
            f"CUSTOMER_ID={farm.customer_id} "
            f"python3 vrbot_main.py {task_arg} --adb-serial {adb_serial} "
            f"--single-run 2>&1 | tail -50"
        )

        # Timeout based on task type
        timeouts = {
            TaskType.FARMING: 35 * 60,    # 35 minutes
            TaskType.DAILY: 25 * 60,       # 25 minutes
            TaskType.NIFLING: 45 * 60,     # 45 minutes
        }
        timeout = timeouts.get(task.task_type, 30 * 60)

        logger.info(f"  🎮 Running {task.task_type.value} on farm {farm.id} "
                     f"(ADB: {adb_serial}, timeout: {timeout//60}min)")

        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip, cmd, timeout=timeout
        )

        # Parse result
        if rc == 0:
            logger.info(f"  ✅ Task {task.task_type.value} completed on farm {farm.id}")
            # Log last few lines of output
            for line in stdout.split("\n")[-5:]:
                if line.strip():
                    logger.debug(f"    → {line.strip()}")
            return True
        else:
            logger.error(f"  ❌ Task failed on farm {farm.id} (rc={rc})")
            if stderr:
                logger.error(f"    stderr: {stderr[:200]}")
            if stdout:
                # Check for known error patterns
                if "captcha" in stdout.lower():
                    task.error_message = "captcha_detected"
                elif "freeze" in stdout.lower() or "frozen" in stdout.lower():
                    task.error_message = "app_frozen"
                elif "timeout" in stdout.lower():
                    task.error_message = "task_timeout"
                else:
                    task.error_message = f"exit_code_{rc}"
            return False

    # ══════════════════════════════════════
    #  Health Check
    # ══════════════════════════════════════

    async def check_farm_health(self, farm: Farm) -> dict:
        """Check the health of a farm's container and game state.

        Returns:
            {
                "container_running": bool,
                "adb_connected": bool,
                "game_running": bool,
                "screen": str,  # current screen detected
            }
        """
        adb_port = farm.adb_port or 5555
        container_name = farm.container_name or f"farm_{farm.id}"

        # Check container
        stdout, _, rc = await self._ssh_run(
            farm.server_ip,
            f"docker inspect -f '{{{{.State.Running}}}}' {container_name} 2>/dev/null"
        )
        container_running = "true" in stdout.lower()

        if not container_running:
            return {
                "container_running": False,
                "adb_connected": False,
                "game_running": False,
                "screen": "offline",
            }

        # Check ADB
        stdout, _, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s localhost:{adb_port} shell getprop sys.boot_completed 2>/dev/null"
        )
        adb_connected = "1" in stdout

        # Check if Viking Rise is running
        stdout, _, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s localhost:{adb_port} shell dumpsys activity activities 2>/dev/null | "
            f"grep -i 'viking\\|com.igg' | head -1"
        )
        game_running = bool(stdout.strip())

        return {
            "container_running": container_running,
            "adb_connected": adb_connected,
            "game_running": game_running,
            "screen": "game" if game_running else "launcher",
        }

    async def restart_game(self, farm: Farm) -> bool:
        """Force restart the Viking Rise game on a farm."""
        adb_port = farm.adb_port or 5555
        adb_serial = f"localhost:{adb_port}"

        # Kill the game
        await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_serial} shell am force-stop com.igg.android.vikingrise"
        )
        await asyncio.sleep(3)

        # Restart it
        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_serial} shell monkey -p com.igg.android.vikingrise "
            f"-c android.intent.category.LAUNCHER 1"
        )

        if rc == 0:
            logger.info(f"  🔄 Game restarted on farm {farm.id}")
            return True
        else:
            logger.error(f"  ❌ Failed to restart game on farm {farm.id}: {stderr}")
            return False


# ══════════════════════════════════════════
#  Singleton instance
# ══════════════════════════════════════════

_executor: Optional[FarmExecutor] = None


def get_executor() -> FarmExecutor:
    """Get or create the global FarmExecutor instance."""
    global _executor
    if _executor is None:
        _executor = FarmExecutor()
    return _executor
