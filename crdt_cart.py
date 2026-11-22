import json
import os
from copy import deepcopy


# ================= 向量时钟工具函数 =================
def vunion(a, b):
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b)}


def vdominates(a, b):
    return all(a.get(k, 0) >= v for k, v in b.items())


def vconcurrent(a, b):
    return not vdominates(a, b) and not vdominates(b, a)


# ================= 购物车节点 =================
class CartReplica:
    def __init__(self, rid, storage_path=None):
        self.rid = rid
        self.storage_path = storage_path
        self.clock = {rid: 0}
        self.entries = {}
        self._load_from_disk()  # 模拟节点启动时恢复状态

    def _touch(self):
        self.clock[self.rid] += 1
        return deepcopy(self.clock)

    def _save_to_disk(self):
        if self.storage_path:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({"clock": self.clock, "entries": self.entries}, f)

    def _load_from_disk(self):
        if self.storage_path and os.path.exists(self.storage_path):
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.clock = data["clock"]
                self.entries = data["entries"]
                print(f"[{self.rid}] 从本地磁盘恢复状态成功。当前购物车: {self.view()}")

    # ---------- 本地写操作 ----------
    def add(self, sku, n=1):
        e = self.entries.setdefault(sku, {"adds": {}, "removes": {}, "clock": {}, "tomb": None})
        if e["tomb"] and vdominates(e["tomb"], self.clock):
            e["tomb"] = None  # 复活
        e["adds"][self.rid] = e["adds"].get(self.rid, 0) + n
        e["clock"] = self._touch()
        self._save_to_disk()
        print(f"[{self.rid}] 添加 {sku} x{n}。当前本地视图: {self.view()}")

    def remove_qty(self, sku, n=1):
        e = self.entries.get(sku)
        if not e: return
        e["removes"][self.rid] = e["removes"].get(self.rid, 0) + n
        e["clock"] = self._touch()
        self._save_to_disk()
        print(f"[{self.rid}] 减少 {sku} x{n}。当前本地视图: {self.view()}")

    def delete_item(self, sku):
        e = self.entries.get(sku)
        if not e: return
        e["tomb"] = self._touch()
        e["clock"] = deepcopy(e["tomb"])
        self._save_to_disk()
        print(f"[{self.rid}] 彻底删除商品 {sku}。当前本地视图: {self.view()}")

    # ---------- 状态视图 ----------
    def view(self):
        out = {}
        for sku, e in self.entries.items():
            if e["tomb"] and vdominates(e["tomb"], e["clock"]) and not vconcurrent(e["tomb"], e["clock"]):
                continue
            qty = sum(e["adds"].values()) - sum(e["removes"].values())
            if qty > 0:
                out[sku] = qty
        return out

    # ---------- 核心：网络合并（幂等、处理冲突） ----------
    def merge(self, other):
        print(f"\n>>> [{self.rid}] 开始与 [{other.rid}] 同步数据...")
        old_view = self.view()
        self.clock = vunion(self.clock, other.clock)

        for sku, b in other.entries.items():
            e = self.entries.setdefault(sku, {"adds": {}, "removes": {}, "clock": {}, "tomb": None})

            # 记录合并前的状态，方便打印冲突日志
            was_concurrent = False

            # 1. 合并数量（加法/减法）
            e["adds"] = vunion(e["adds"], b["adds"])
            e["removes"] = vunion(e["removes"], b["removes"])
            e["clock"] = vunion(e["clock"], b["clock"])

            # 2. 合并墓碑（删除操作）
            if b["tomb"]:
                if e["tomb"] is None or vdominates(b["tomb"], e["tomb"]):
                    e["tomb"] = deepcopy(b["tomb"])
                elif vconcurrent(e["tomb"], b["tomb"]):
                    e["tomb"] = vunion(e["tomb"], b["tomb"])
                    was_concurrent = True  # 标记发生了并发删除冲突

            if was_concurrent:
                print(f"  [冲突解决] 发现 {sku} 并发删除与加购，采用 Add-Wins 策略（条目保留）！")

        new_view = self.view()
        if old_view != new_view:
            print(f"  [同步结果] 合并前: {old_view} -> 合并后: {new_view}")
        else:
            print(f"  [同步结果] 无变化，当前仍为: {new_view}")

        self._save_to_disk()