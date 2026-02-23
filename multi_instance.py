"""
VRBOT Multi-Instance Manager
Discovers and manages multiple LDPlayer instances for parallel farming.
"""
import threading
import time
import logging
from adb.controller import ADBController

log = logging.getLogger("vrbot.multi")


class FarmInstance:
    """Represents one LDPlayer instance = one farm."""

    def __init__(self, index, name, port, status="stopped"):
        self.index = index
        self.name = name
        self.port = port
        self.device = f"127.0.0.1:{port}"
        self.status = status  # stopped, running, error
        self.current_task = None
        self.adb = None
        self.tasks_completed = 0
        self.last_activity = None

    def connect(self, ldplayer_path=None):
        """Create and connect ADB controller for this instance."""
        self.adb = ADBController(
            host="127.0.0.1",
            port=self.port,
            ldplayer_path=ldplayer_path,
        )
        if self.adb.connect(retries=2):
            self.status = "running"
            return True
        self.status = "error"
        return False

    def to_dict(self):
        return {
            "index": self.index,
            "name": self.name,
            "port": self.port,
            "device": self.device,
            "status": self.status,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
        }


class MultiInstanceManager:
    """Manages multiple LDPlayer instances for parallel farming."""

    def __init__(self, ldplayer_path=None):
        self.ldplayer_path = ldplayer_path or r"C:\LDPlayer\LDPlayer9"
        self.instances: dict[int, FarmInstance] = {}
        self._lock = threading.Lock()
        self._threads: dict[int, threading.Thread] = {}

    def discover_instances(self):
        """Auto-discover all LDPlayer instances via ldconsole."""
        adb = ADBController(ldplayer_path=self.ldplayer_path)
        raw_instances = adb.ld_list_instances()

        with self._lock:
            for inst in raw_instances:
                idx = inst["index"]
                port = adb.ld_get_adb_port(idx)
                farm = FarmInstance(
                    index=idx,
                    name=inst["name"],
                    port=port,
                    status=inst["status"],
                )
                self.instances[idx] = farm

        log.info(f"Discovered {len(self.instances)} instances: {[i.name for i in self.instances.values()]}")
        return list(self.instances.values())

    def connect_all(self):
        """Connect ADB to all running instances."""
        connected = 0
        for farm in self.instances.values():
            if farm.status == "running":
                if farm.connect(self.ldplayer_path):
                    connected += 1
                    log.info(f"Connected: {farm.name} ({farm.device})")
                else:
                    log.warning(f"Failed to connect: {farm.name}")
        log.info(f"Connected to {connected}/{len(self.instances)} instances")
        return connected

    def get_instance(self, index):
        """Get instance by index."""
        return self.instances.get(index)

    def get_by_name(self, name):
        """Get instance by name."""
        for farm in self.instances.values():
            if farm.name == name:
                return farm
        return None

    def get_running(self):
        """Get all connected/running instances."""
        return [f for f in self.instances.values() if f.status == "running" and f.adb and f.adb.connected]

    def run_task_on(self, farm_index, task_class, bot_wrapper):
        """Run a task on a specific instance in a thread."""
        farm = self.instances.get(farm_index)
        if not farm or not farm.adb:
            log.error(f"Instance {farm_index} not available")
            return False

        def _run():
            try:
                farm.current_task = task_class.name
                farm.status = "running"
                wrapper = bot_wrapper(farm.adb)
                task = task_class(wrapper)
                result = task.run()
                farm.tasks_completed += 1
                farm.current_task = None
                farm.last_activity = time.time()
                log.info(f"[{farm.name}] Task {task_class.name} done: {result}")
            except Exception as e:
                farm.status = "error"
                farm.current_task = None
                log.error(f"[{farm.name}] Task error: {e}")

        thread = threading.Thread(target=_run, name=f"farm-{farm_index}", daemon=True)
        self._threads[farm_index] = thread
        thread.start()
        return True

    def run_tasks_parallel(self, task_classes, bot_wrapper, farm_indices=None):
        """Run tasks on multiple instances in parallel."""
        targets = farm_indices or [f.index for f in self.get_running()]

        for idx in targets:
            farm = self.instances.get(idx)
            if not farm or not farm.adb or not farm.adb.connected:
                continue

            def _run_all(farm_inst):
                for task_cls in task_classes:
                    if farm_inst.status == "error":
                        break
                    try:
                        farm_inst.current_task = task_cls.name
                        wrapper = bot_wrapper(farm_inst.adb)
                        task = task_cls(wrapper)
                        task.run()
                        farm_inst.tasks_completed += 1
                    except Exception as e:
                        log.error(f"[{farm_inst.name}] {task_cls.name} error: {e}")
                farm_inst.current_task = None
                farm_inst.last_activity = time.time()

            thread = threading.Thread(target=_run_all, args=(farm,), name=f"farm-{idx}", daemon=True)
            self._threads[idx] = thread
            thread.start()

        log.info(f"Started parallel tasks on {len(targets)} instances")

    def stop_all(self):
        """Stop all running tasks (sets status to trigger task exit)."""
        for farm in self.instances.values():
            farm.status = "stopped"
            farm.current_task = None
        log.info("All instances stopped")

    def get_status(self):
        """Get status of all instances."""
        return {
            "total": len(self.instances),
            "running": len(self.get_running()),
            "instances": [f.to_dict() for f in self.instances.values()],
        }
