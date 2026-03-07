"""
Auto Provisioner - Hetzner + Cloud-Init + Redroid
==================================================
التزويد التلقائي الكامل:

أنت (كليك واحد)
       ↓
  Orchestrator (FastAPI)
       ↓
  Hetzner API (ينشئ سيرفرات تلقائياً)
       ↓
  Cloud-Init Script (يثبت كل شيء تلقائياً)
       ↓
  Redroid × 40 farm / server
"""

import asyncio
import math
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("auto_provisioner")


# ══════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════

HETZNER_TOKEN = os.getenv("HETZNER_TOKEN", "")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "https://api.vrbot.me")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


class ServerType(str, Enum):
    AX41 = "ax41"    # Ryzen 5 3600, 64GB  → ~35 farms
    AX42 = "ax42"    # Ryzen 7 PRO 8700GE, 64GB DDR5 → ~40 farms


# سعة المزارع لكل نوع سيرفر
SERVER_CAPACITY = {
    ServerType.AX41: 35,
    ServerType.AX42: 40,
}

SERVER_MONTHLY_COST = {
    ServerType.AX41: 44,   # ~$44/month
    ServerType.AX42: 55,   # ~$55/month
}


# ══════════════════════════════════════════
#  Cloud-Init Script
# ══════════════════════════════════════════

CLOUD_INIT_TEMPLATE = """#cloud-config
package_update: true
package_upgrade: true

packages:
  - docker.io
  - docker-compose
  - linux-modules-extra-$(uname -r)
  - curl
  - git

runcmd:
  # ─── تفعيل Docker ───
  - systemctl enable docker
  - systemctl start docker

  # ─── تحميل Kernel Modules لـ Redroid ───
  - modprobe binder_linux devices="binder,hwbinder,vndbinder"
  - modprobe ashmem_linux

  # ─── إضافة modules للتحميل التلقائي عند إعادة التشغيل ───
  - echo "binder_linux" >> /etc/modules-load.d/redroid.conf
  - echo "ashmem_linux" >> /etc/modules-load.d/redroid.conf
  - echo 'options binder_linux devices="binder,hwbinder,vndbinder"' >> /etc/modprobe.d/redroid.conf

  # ─── تحميل VRBOT Node Agent ───
  - mkdir -p /opt/vrbot
  - git clone https://github.com/{repo}/vrbot-agent /opt/vrbot || true

  # ─── تشغيل Node Agent (يتصل بـ Orchestrator) ───
  - docker pull vrbot/node-agent:latest
  - docker run -d
      --name vrbot-node-agent
      --restart always
      -v /var/run/docker.sock:/var/run/docker.sock
      -e ORCHESTRATOR_URL={orchestrator_url}
      -e SERVER_TOKEN={server_token}
      -e SERVER_ID={server_id}
      -e MAX_FARMS={max_farms}
      vrbot/node-agent:latest

  # ─── إبلاغ الـ Orchestrator أن السيرفر جاهز ───
  - |
    for i in $(seq 1 30); do
      STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" \\
        -X POST {orchestrator_url}/api/servers/ready \\
        -H "Content-Type: application/json" \\
        -H "Authorization: Bearer {server_token}" \\
        -d '{{"server_id": "{server_id}", "ip": "'$(curl -s ifconfig.me)'", "max_farms": {max_farms}}}')

      if [ "$STATUS" = "200" ]; then
        echo "✅ Server registered successfully"
        break
      fi
      echo "⏳ Attempt $i: Orchestrator not ready (status: $STATUS), retrying..."
      sleep 10
    done

write_files:
  - path: /etc/vrbot/config.yaml
    content: |
      server_id: {server_id}
      orchestrator_url: {orchestrator_url}
      max_farms: {max_farms}
      redroid_image: redroid/redroid:11.0.0-latest
      adb_port_start: 5555
      vnc_port_start: 5900
"""


# ══════════════════════════════════════════
#  Server Model
# ══════════════════════════════════════════

class ServerStatus(str, Enum):
    PROVISIONING = "provisioning"
    INSTALLING = "installing"   # cloud-init يشتغل
    READY = "ready"             # جاهز للمزارع
    FULL = "full"               # كل الـ slots مشغولة
    ERROR = "error"
    DECOMMISSIONING = "decommissioning"


@dataclass
class ServerNode:
    """نموذج السيرفر"""
    server_id: str
    hetzner_id: Optional[int] = None
    ip: Optional[str] = None
    server_type: ServerType = ServerType.AX42
    status: ServerStatus = ServerStatus.PROVISIONING
    max_farms: int = 40
    active_farms: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    ready_at: Optional[datetime] = None
    monthly_cost: float = 55.0
    token: str = ""

    @property
    def available_slots(self) -> int:
        return self.max_farms - self.active_farms

    @property
    def utilization(self) -> float:
        if self.max_farms == 0:
            return 0
        return self.active_farms / self.max_farms


# ══════════════════════════════════════════
#  Auto Provisioner
# ══════════════════════════════════════════

class AutoProvisioner:
    """
    التزويد التلقائي الكامل

    الاستخدام:
      provisioner = AutoProvisioner()
      await provisioner.deploy_farms(count=200)

    ما يحصل:
      1. يحسب كم سيرفر مطلوب
      2. ينشئ السيرفرات عبر Hetzner API
      3. Cloud-Init يثبت كل شيء تلقائياً
      4. بعد جهوز السيرفر → يُنشئ Redroid containers
      5. المزارع جاهزة للعمل ✅
    """

    def __init__(self):
        self.servers: Dict[str, ServerNode] = {}
        self._hetzner_client = None

    def _get_hetzner_client(self):
        """الاتصال بـ Hetzner API"""
        if not self._hetzner_client:
            try:
                from hcloud import Client
                self._hetzner_client = Client(token=HETZNER_TOKEN)
            except ImportError:
                logger.error("hcloud package not installed: pip install hcloud")
                raise
        return self._hetzner_client

    # ══════════════════════════════════════
    #  Deploy Pipeline
    # ══════════════════════════════════════

    async def deploy_farms(self, count: int,
                           server_type: ServerType = ServerType.AX42,
                           customer_id: str = None) -> dict:
        """
        🚀 نشر مزارع جديدة — كليك واحد

        Args:
            count: عدد المزارع المطلوبة
            server_type: نوع السيرفر
            customer_id: الزبون (اختياري)

        Returns:
            تقرير النشر
        """
        capacity = SERVER_CAPACITY[server_type]
        cost = SERVER_MONTHLY_COST[server_type]

        # ─── الخطوة 1: حساب الاحتياج ───
        # أولاً: هل فيه slots متاحة في سيرفرات موجودة؟
        available_slots = sum(
            s.available_slots for s in self.servers.values()
            if s.status == ServerStatus.READY
        )

        farms_needing_new_servers = max(0, count - available_slots)
        new_servers_needed = math.ceil(farms_needing_new_servers / capacity)

        logger.info(f"""
╔══════════════════════════════════════╗
║        🚀 DEPLOYMENT PLAN           ║
╠══════════════════════════════════════╣
║  Farms requested:    {count:>5}          ║
║  Available slots:    {available_slots:>5}          ║
║  New servers needed: {new_servers_needed:>5}          ║
║  Server type:        {server_type.value:>5}          ║
║  Monthly cost:       ${new_servers_needed * cost:>5}/mo      ║
║  Cost per farm:      ${cost/capacity:>5.2f}/mo      ║
╚══════════════════════════════════════╝
        """)

        # ─── الخطوة 2: إنشاء السيرفرات ───
        new_servers = []
        if new_servers_needed > 0:
            new_servers = await self._create_servers(
                new_servers_needed, server_type
            )

        # ─── الخطوة 3: انتظار الجاهزية ───
        if new_servers:
            logger.info(f"⏳ Waiting for {len(new_servers)} servers to be ready...")
            await self._wait_for_servers(new_servers)

        # ─── الخطوة 4: توزيع المزارع ───
        farm_assignments = await self._assign_farms(count, customer_id)

        # ─── الخطوة 5: إنشاء Redroid containers ───
        await self._spawn_redroid_containers(farm_assignments)

        # ─── التقرير ───
        report = {
            "status": "success",
            "farms_deployed": count,
            "new_servers_created": len(new_servers),
            "server_type": server_type.value,
            "monthly_cost": new_servers_needed * cost,
            "cost_per_farm": cost / capacity,
            "customer_id": customer_id,
            "assignments": farm_assignments,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"✅ Deployment complete: {count} farms ready!")
        return report

    # ══════════════════════════════════════
    #  Server Creation (Hetzner API)
    # ══════════════════════════════════════

    async def _create_servers(self, count: int,
                               server_type: ServerType) -> List[ServerNode]:
        """إنشاء سيرفرات عبر Hetzner API"""
        import uuid

        servers = []

        for i in range(count):
            server_id = f"vrbot-{uuid.uuid4().hex[:8]}"
            server_token = uuid.uuid4().hex

            # تجهيز Cloud-Init
            cloud_init = CLOUD_INIT_TEMPLATE.format(
                repo="ahmed885q",
                orchestrator_url=ORCHESTRATOR_URL,
                server_token=server_token,
                server_id=server_id,
                max_farms=SERVER_CAPACITY[server_type]
            )

            node = ServerNode(
                server_id=server_id,
                server_type=server_type,
                max_farms=SERVER_CAPACITY[server_type],
                monthly_cost=SERVER_MONTHLY_COST[server_type],
                token=server_token
            )

            try:
                # ─── Hetzner API Call ───
                # client = self._get_hetzner_client()
                # response = client.servers.create(
                #     name=server_id,
                #     server_type=client.server_types.get_by_name(
                #         server_type.value + "-nvme"
                #     ),
                #     image=client.images.get_by_name("ubuntu-22.04"),
                #     user_data=cloud_init,
                #     location=client.locations.get_by_name("fsn1"),
                #     labels={
                #         "project": "vrbot",
                #         "role": "farm-node",
                #         "max_farms": str(node.max_farms)
                #     }
                # )
                # node.hetzner_id = response.server.id
                # node.ip = response.server.public_net.ipv4.ip

                logger.info(
                    f"  🖥️ Server {i+1}/{count}: {server_id} "
                    f"(type: {server_type.value}) — creating..."
                )

                node.status = ServerStatus.INSTALLING

                # ─── حفظ في Supabase ───
                # await supabase.table("cloud_servers").insert({
                #     "server_id": server_id,
                #     "hetzner_id": node.hetzner_id,
                #     "ip": node.ip,
                #     "server_type": server_type.value,
                #     "status": "installing",
                #     "max_farms": node.max_farms,
                #     "token": server_token,
                # })

            except Exception as e:
                node.status = ServerStatus.ERROR
                logger.error(f"  ❌ Failed to create server: {e}")

            self.servers[server_id] = node
            servers.append(node)

            # تأخير بين الطلبات (Hetzner rate limit)
            await asyncio.sleep(2)

        return servers

    async def _wait_for_servers(self, servers: List[ServerNode],
                                 timeout_minutes: int = 15):
        """انتظار جاهزية السيرفرات (Cloud-Init يكمل)"""
        import time

        deadline = time.time() + (timeout_minutes * 60)
        pending = set(s.server_id for s in servers)

        while pending and time.time() < deadline:
            for server_id in list(pending):
                server = self.servers[server_id]

                # التحقق عبر الـ Orchestrator API
                # (السيرفر يرسل POST /servers/ready عند الجاهزية)
                # ready = await check_server_ready(server_id)
                # if ready:
                #     server.status = ServerStatus.READY
                #     server.ready_at = datetime.utcnow()
                #     pending.discard(server_id)

                # محاكاة
                await asyncio.sleep(1)

            if pending:
                elapsed = timeout_minutes * 60 - (deadline - time.time())
                logger.info(
                    f"  ⏳ {len(pending)} servers still installing "
                    f"({elapsed:.0f}s elapsed)..."
                )
                await asyncio.sleep(30)

        if pending:
            logger.warning(
                f"  ⚠️ {len(pending)} servers didn't finish in time"
            )

    # ══════════════════════════════════════
    #  Farm Assignment
    # ══════════════════════════════════════

    async def _assign_farms(self, count: int,
                             customer_id: str = None) -> List[dict]:
        """توزيع المزارع على السيرفرات المتاحة"""
        import uuid

        assignments = []
        farms_remaining = count

        # ترتيب السيرفرات: الأقل امتلاءً أولاً
        available_servers = sorted(
            [s for s in self.servers.values()
             if s.status in (ServerStatus.READY, ServerStatus.INSTALLING)
             and s.available_slots > 0],
            key=lambda s: s.utilization
        )

        for server in available_servers:
            if farms_remaining <= 0:
                break

            can_add = min(farms_remaining, server.available_slots)

            for i in range(can_add):
                farm_id = f"farm_{uuid.uuid4().hex[:8]}"
                port_offset = server.active_farms + i
                adb_port = 5555 + port_offset
                vnc_port = 5900 + port_offset

                assignments.append({
                    "farm_id": farm_id,
                    "server_id": server.server_id,
                    "server_ip": server.ip,
                    "adb_port": adb_port,
                    "vnc_port": vnc_port,
                    "customer_id": customer_id,
                })

            server.active_farms += can_add
            farms_remaining -= can_add

            if server.available_slots <= 0:
                server.status = ServerStatus.FULL

        if farms_remaining > 0:
            logger.warning(
                f"  ⚠️ {farms_remaining} farms couldn't be assigned "
                f"(no available slots)"
            )

        return assignments

    # ══════════════════════════════════════
    #  Redroid Container Spawning
    # ══════════════════════════════════════

    async def _spawn_redroid_containers(self, assignments: List[dict]):
        """
        إنشاء Redroid containers على السيرفرات

        كل مزرعة = container واحد
        40 مزرعة × سيرفر = 40 container
        """
        # تجميع حسب السيرفر
        by_server: Dict[str, List[dict]] = {}
        for a in assignments:
            sid = a["server_id"]
            if sid not in by_server:
                by_server[sid] = []
            by_server[sid].append(a)

        # تنفيذ بالتوازي لكل سيرفر
        tasks = []
        for server_id, farms in by_server.items():
            tasks.append(
                self._spawn_on_server(server_id, farms)
            )

        await asyncio.gather(*tasks)

    async def _spawn_on_server(self, server_id: str, farms: List[dict]):
        """إنشاء containers على سيرفر واحد"""
        server = self.servers.get(server_id)
        if not server:
            return

        logger.info(
            f"  🐳 Spawning {len(farms)} containers on {server_id} "
            f"({server.ip})"
        )

        for i, farm in enumerate(farms):
            cmd = f"""
docker run -d \\
  --name {farm['farm_id']} \\
  --privileged \\
  --restart unless-stopped \\
  -p {farm['adb_port']}:5555 \\
  -p {farm['vnc_port']}:5900 \\
  -e FARM_ID={farm['farm_id']} \\
  -e CUSTOMER_ID={farm.get('customer_id', 'unassigned')} \\
  --memory=1.5g \\
  --cpus=1.5 \\
  redroid/redroid:11.0.0-latest \\
  androidboot.redroid_gpu_mode=guest
"""
            # TODO: تنفيذ عبر SSH أو Node Agent API
            # async with asyncssh.connect(server.ip) as conn:
            #     result = await conn.run(cmd)

            logger.debug(f"    Container {i+1}/{len(farms)}: {farm['farm_id']}")

            # ─── تسجيل في Supabase ───
            # await supabase.table("cloud_farms").insert({
            #     "farm_id": farm["farm_id"],
            #     "server_id": server_id,
            #     "customer_id": farm.get("customer_id"),
            #     "adb_port": farm["adb_port"],
            #     "vnc_port": farm["vnc_port"],
            #     "status": "created",
            # })

            # تأخير بين الـ containers
            await asyncio.sleep(3)

        logger.info(f"  ✅ {len(farms)} containers ready on {server_id}")

    # ══════════════════════════════════════
    #  Scale Management
    # ══════════════════════════════════════

    async def scale_up(self, additional_farms: int,
                        server_type: ServerType = ServerType.AX42) -> dict:
        """توسيع: إضافة مزارع جديدة"""
        return await self.deploy_farms(additional_farms, server_type)

    async def scale_down(self, farm_ids: List[str]):
        """تقليص: إزالة مزارع"""
        for farm_id in farm_ids:
            # TODO: إيقاف container + تحديث Supabase
            logger.info(f"  🗑️ Removing farm {farm_id}")

        # تحقق: هل فيه سيرفرات فارغة يمكن حذفها؟
        for server in self.servers.values():
            if server.active_farms == 0 and server.status != ServerStatus.PROVISIONING:
                logger.info(f"  🖥️ Server {server.server_id} is empty — can decommission")

    def get_infrastructure_status(self) -> dict:
        """حالة البنية التحتية الكاملة"""
        total_capacity = sum(s.max_farms for s in self.servers.values())
        total_active = sum(s.active_farms for s in self.servers.values())
        total_cost = sum(s.monthly_cost for s in self.servers.values())

        return {
            "servers": {
                "total": len(self.servers),
                "ready": sum(1 for s in self.servers.values()
                           if s.status == ServerStatus.READY),
                "installing": sum(1 for s in self.servers.values()
                                if s.status == ServerStatus.INSTALLING),
                "error": sum(1 for s in self.servers.values()
                           if s.status == ServerStatus.ERROR),
            },
            "farms": {
                "total_capacity": total_capacity,
                "active": total_active,
                "available_slots": total_capacity - total_active,
                "utilization": f"{(total_active/total_capacity*100) if total_capacity else 0:.1f}%",
            },
            "cost": {
                "monthly_total": f"${total_cost:.0f}",
                "per_farm": f"${total_cost/total_active:.2f}" if total_active else "$0",
            },
            "servers_detail": [
                {
                    "id": s.server_id,
                    "type": s.server_type.value,
                    "ip": s.ip,
                    "status": s.status.value,
                    "farms": f"{s.active_farms}/{s.max_farms}",
                    "utilization": f"{s.utilization:.0%}",
                }
                for s in self.servers.values()
            ]
        }


# ══════════════════════════════════════════
#  مثال استخدام
# ══════════════════════════════════════════

async def example():
    """
    مثال: نشر 200 مزرعة بكليك واحد

    النتيجة:
      - 5 سيرفرات AX42 (200/40 = 5)
      - تكلفة: $275/شهر
      - تكلفة/مزرعة: $1.375
    """
    provisioner = AutoProvisioner()

    # 🚀 كليك واحد!
    report = await provisioner.deploy_farms(
        count=200,
        server_type=ServerType.AX42,
        customer_id="customer_001"
    )

    print(f"\n📊 Deployment Report:")
    print(f"  Farms: {report['farms_deployed']}")
    print(f"  Servers: {report['new_servers_created']}")
    print(f"  Cost: ${report['monthly_cost']}/month")
    print(f"  Per farm: ${report['cost_per_farm']:.2f}/month")

    # 📊 حالة البنية التحتية
    status = provisioner.get_infrastructure_status()
    print(f"\n🖥️ Infrastructure: {status}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example())
