"""
Farm Executor - SSH/Docker/ADB Remote Execution
================================================
ينفذ المهام على المزارع عبر SSH → Docker → ADB

Flow per farm:
  1. SSH to farm.server_ip
  2. Get container Docker bridge IP via docker inspect
  3. Connect ADB to container_ip:5555
  4. Run vrbot_main.py with task_type via ADB shell
  5. Monitor execution (timeout, health checks)
  6. Container stays running (restart: unless-stopped)

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
VRBOT_VENV_PYTHON = "/opt/vrbot/agent/venv/bin/python3"

# Game package — correct global version
GAME_PACKAGE = "com.igg.android.vikingriseglobal"

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
        self.ssh_password = ssh_password or os.getenv("CLOUD_SERVER_PASSWORD", "") or os.getenv("SERVER_PASSWORD", "")
        self.ssh_key_path = ssh_key_path or os.getenv("SSH_KEY_PATH", "")
        self.active_executions: Dict[str, asyncio.Task] = {}
        # Cache container IPs to avoid repeated docker inspect calls
        self._container_ip_cache: Dict[str, str] = {}

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
    #  Docker Bridge IP Resolution
    # ══════════════════════════════════════

    async def _get_container_ip(self, farm: Farm) -> Optional[str]:
        """Get the Docker bridge IP for a farm's container.

        Our containers use Docker bridge networking (not port mapping),
        so we need to get the container IP via docker inspect.
        """
        container_name = farm.container_name or f"farm_{farm.id}"

        # Check cache first
        if container_name in self._container_ip_cache:
            return self._container_ip_cache[container_name]

        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"docker inspect --format '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container_name} 2>/dev/null"
        )

        ip = stdout.strip()
        if ip and rc == 0:
            self._container_ip_cache[container_name] = ip
            return ip

        # Fallback: try .NetworkSettings.IPAddress
        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"docker inspect --format '{{{{.NetworkSettings.IPAddress}}}}' {container_name} 2>/dev/null"
        )

        ip = stdout.strip()
        if ip and rc == 0:
            self._container_ip_cache[container_name] = ip
            return ip

        logger.error(f"Could not get IP for container {container_name}")
        return None

    def _clear_ip_cache(self, container_name: str = None):
        """Clear cached container IP(s)."""
        if container_name:
            self._container_ip_cache.pop(container_name, None)
        else:
            self._container_ip_cache.clear()

    # ══════════════════════════════════════
    #  Container Management
    # ══════════════════════════════════════

    async def ensure_container_running(self, farm: Farm) -> bool:
        """Ensure the Docker redroid container is running.

        Containers use restart: unless-stopped, so they should normally
        already be running. This just verifies and starts if needed.
        """
        container_name = farm.container_name or f"farm_{farm.id}"
        farm.status = FarmStatus.STARTING

        logger.info(f"  🐳 Checking container {container_name} on {farm.server_ip}")

        # Check if container is running
        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"docker inspect -f '{{{{.State.Running}}}}' {container_name} 2>/dev/null || echo 'notfound'"
        )

        if "true" in stdout.lower():
            logger.info(f"  🐳 Container {container_name} already running")
            farm.status = FarmStatus.RUNNING
            return True

        if "false" in stdout.lower():
            # Container exists but stopped — start it
            logger.info(f"  🐳 Starting stopped container {container_name}")
            stdout, stderr, rc = await self._ssh_run(
                farm.server_ip,
                f"docker start {container_name}",
                timeout=60
            )
            if rc != 0:
                logger.error(f"  ❌ Failed to start container: {stderr}")
                farm.status = FarmStatus.ERROR
                return False

            # Clear IP cache since IP may have changed
            self._clear_ip_cache(container_name)
            await asyncio.sleep(10)  # Wait for container to initialize

        elif "notfound" in stdout:
            logger.error(f"  ❌ Container {container_name} does not exist")
            farm.status = FarmStatus.ERROR
            return False

        # Verify we can get an IP
        ip = await self._get_container_ip(farm)
        if not ip:
            logger.error(f"  ❌ Container {container_name} has no IP")
            farm.status = FarmStatus.ERROR
            return False

        # Wait for ADB readiness
        adb_ready = await self._wait_for_adb(farm)
        if adb_ready:
            farm.status = FarmStatus.RUNNING
            logger.info(f"  ✅ Container {container_name} ready (IP: {ip})")
            return True
        else:
            logger.warning(f"  ⚠️ Container started but ADB not ready")
            farm.status = FarmStatus.ERROR
            return False

    # Keep old name as alias for compatibility
    async def start_container(self, farm: Farm) -> bool:
        return await self.ensure_container_running(farm)

    async def stop_container(self, farm: Farm) -> bool:
        """Mark farm as idle but DON'T stop the container.

        Containers have restart: unless-stopped policy and should
        stay running so the game stays loaded between cycles.
        """
        farm.status = FarmStatus.IDLE
        logger.info(f"  🐳 Farm {farm.id} marked idle (container stays running)")
        return True

    async def _wait_for_adb(self, farm: Farm) -> bool:
        """Wait for ADB to become ready on the container via Docker bridge IP."""
        container_ip = await self._get_container_ip(farm)
        if not container_ip:
            return False

        adb_addr = f"{container_ip}:5555"
        elapsed = 0
        interval = 5

        while elapsed < ADB_WAIT_MAX:
            stdout, stderr, rc = await self._ssh_run(
                farm.server_ip,
                f"adb connect {adb_addr} 2>/dev/null && "
                f"adb -s {adb_addr} shell getprop sys.boot_completed 2>/dev/null",
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

        Uses Docker bridge IP to connect ADB (not localhost port mapping).
        """
        container_ip = await self._get_container_ip(farm)
        if not container_ip:
            task.error_message = "no_container_ip"
            return False

        adb_serial = f"{container_ip}:5555"

        # Ensure ADB is connected
        await self._ssh_run(
            farm.server_ip,
            f"adb connect {adb_serial} 2>/dev/null",
            timeout=10
        )

        # Determine which tasks to run
        if task.task_type == TaskType.DAILY:
            # Daily = run multiple tasks in sequence
            task_list = ",".join(DAILY_TASK_LIST)
            task_arg = f"--tasks {task_list}"
        else:
            task_name = TASK_TYPE_MAP.get(task.task_type, "gather")
            task_arg = f"--task {task_name}"

        # Build the remote command
        # Set VRBOT_CONTAINER for docker exec mode + ADB_SERIAL for direct ADB mode
        container_name = farm.container_name or f"farm_{farm.id}"
        cmd = (
            f"cd {VRBOT_AGENT_PATH} && "
            f"VRBOT_BACKEND=docker "
            f"VRBOT_CONTAINER={container_name} "
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
            for line in stdout.split("\n")[-5:]:
                if line.strip():
                    logger.debug(f"    → {line.strip()}")
            return True
        else:
            logger.error(f"  ❌ Task failed on farm {farm.id} (rc={rc})")
            if stderr:
                logger.error(f"    stderr: {stderr[:200]}")
            if stdout:
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
        """Check the health of a farm's container and game state."""
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

        # Get container IP
        container_ip = await self._get_container_ip(farm)
        if not container_ip:
            return {
                "container_running": True,
                "adb_connected": False,
                "game_running": False,
                "screen": "no_ip",
            }

        adb_addr = f"{container_ip}:5555"

        # Check ADB
        stdout, _, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_addr} shell getprop sys.boot_completed 2>/dev/null"
        )
        adb_connected = "1" in stdout

        # Check if Viking Rise is running (correct package name)
        stdout, _, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_addr} shell dumpsys activity activities 2>/dev/null | "
            f"grep -i 'vikingriseglobal\\|com.igg' | head -1"
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
        container_ip = await self._get_container_ip(farm)
        if not container_ip:
            return False

        adb_addr = f"{container_ip}:5555"

        # Ensure ADB connected
        await self._ssh_run(
            farm.server_ip,
            f"adb connect {adb_addr} 2>/dev/null",
            timeout=10
        )

        # Kill the game
        await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_addr} shell am force-stop {GAME_PACKAGE}"
        )
        await asyncio.sleep(3)

        # Restart it
        stdout, stderr, rc = await self._ssh_run(
            farm.server_ip,
            f"adb -s {adb_addr} shell monkey -p {GAME_PACKAGE} "
            f"-c android.intent.category.LAUNCHER 1"
        )

        if rc == 0:
            logger.info(f"  🔄 Game restarted on farm {farm.id}")
            return True
        else:
            logger.error(f"  ❌ Failed to restart game on farm {farm.id}: {stderr}")
            return False

    # ══════════════════════════════════════
    #  Farm Discovery
    # ══════════════════════════════════════

    async def discover_farms(self, server_ip: str) -> list:
        """Discover all farm containers on a server via SSH.

        Returns list of dicts: [{name, ip, status}, ...]
        """
        stdout, stderr, rc = await self._ssh_run(
            server_ip,
            "for c in $(docker ps --format '{{.Names}}' | grep '^farm_' | sort); do "
            "  ip=$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $c 2>/dev/null); "
            "  status=$(docker inspect --format '{{.State.Status}}' $c 2>/dev/null); "
            "  echo \"$c|$ip|$status\"; "
            "done",
            timeout=30
        )

        farms = []
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                parts = line.strip().split("|")
                if len(parts) == 3:
                    name, ip, status = parts
                    farms.append({
                        "name": name,
                        "ip": ip,
                        "status": status,
                    })

        logger.info(f"  🔍 Discovered {len(farms)} farms on {server_ip}")
        return farms


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
