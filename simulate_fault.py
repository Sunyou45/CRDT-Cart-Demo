from crdt_cart import CartReplica
import os

# 清理之前的持久化文件
for f in ["phone_data.json", "pc_data.json"]:
    if os.path.exists(f): os.remove(f)

def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")

# ==================== 演示开始 ====================
phone = CartReplica("Phone", "phone_data.json")
pc = CartReplica("PC", "pc_data.json")

print_separator("场景 1: 正常同步")
phone.add("milk"); pc.add("milk")
phone.merge(pc); pc.merge(phone)
print(f"同步后，两端视图是否一致: {phone.view() == pc.view()} (牛奶: {phone.view().get('milk')})")

print_separator("场景 2: 网络分区与并发冲突")
print("【网络断开】手机和电脑失去连接，各自离线操作...")
# 手机端操作
phone.remove_qty("milk") # 手机喝掉了一瓶
phone.add("bread")       # 手机加了面包

# 电脑端操作
pc.add("milk", 2)        # 电脑又加了2瓶牛奶
pc.delete_item("milk")   # 电脑觉得太贵，把牛奶全删了
pc.add("eggs")           # 电脑买了鸡蛋

# 手机端又加了一次牛奶（与电脑的删除并发）
phone.add("milk")

print("\n【网络恢复】开始合并数据...")
phone.merge(pc)
pc.merge(phone)

print(f"\n最终结果：{phone.view()}")
print(f"两端数据是否最终一致: {phone.view() == pc.view()}")

print_separator("场景 3: 故障注入 —— 节点突然宕机")
print("【故障注入】PC 节点突然断电宕机 (数据丢失内存)...")
del pc # 模拟进程死亡

print("【恢复】PC 节点重新拉起，从本地 JSON 文件恢复状态...")
pc_recovered = CartReplica("PC", "pc_data.json")

print(f"\n宕机恢复后，PC 的购物车数据: {pc_recovered.view()}")
print(f"与 Phone 数据是否一致: {pc_recovered.view() == phone.view()}")

print_separator("场景 4: 消息重复发送（幂等性测试）")
print("模拟网络抖动，同一份数据发送了三次...")
snapshot = phone.view()
phone.merge(pc_recovered)
phone.merge(pc_recovered)
phone.merge(pc_recovered)
print(f"连续合并3次后，数据是否发生异常变化: {phone.view() != snapshot}")