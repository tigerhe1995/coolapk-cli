# REDMI K90 临时root → 永久root 方案调研报告

调研日期：2026-11-17
数据来源：酷安（用本机 coolapk MCP 抓取，登录态）

---

## 一、目标设备

| 项 | 值 |
|---|---|
| 机型 | REDMI K90（认证型号 2510DRK44c） |
| 代号 | annibale |
| SoC | 骁龙 8 至尊版（8 Elite / 8e 系） |
| 系统 | HyperOS 4 · 4.0.6.0XPKCNXM.D02 |
| Android | 17 |
| 安全补丁 | 2026-10-01 |
| 内核 | 6.6.118-android15-8-g0908354dac1b-ab161433-4k |
| 内存/存储 | 12GB / 528GB（扩容 16GB） |
| 当前状态 | 已临时root（免解BL，开机有效） |

---

## 二、关键判断

### 1. 内核 6.6.118 未被修复 → 临时root 可用且持久性够长

酷安多帖一致给出 GhostLock（CVE-2026-43499）内核修复线：

```
6.1 ≥ 6.1.175 / 6.6 ≥ 6.6.140 / 6.12 ≥ 6.12.86
```

**你的 6.6.118 < 6.6.140，漏洞仍然开放。**

GhostLock 适配总表（酷安 feed 75077874 / 75098529 / 74948636）里明确列有：

```
- ✅ 红米 K90｜OS4.0.27
- ✅ 红米 K90 Ultra / Pro Max｜支持临时 Root
```

⚠️ 注意版本写法差异：适配表写「OS4.0.27」，你的版本是 **4.0.6.0**。
「4.0.27」与「4.0.6.0」应是同一版本的不同写法（27 ↔ 6.0），但需实机确认。
**结论：临时root 当前可用，可作为后续解锁流程的提权手段。**

### 2. K90 已被官方级工具收录 → 永久root 有成熟路线

| 来源 | 帖子 | 关键内容 |
|---|---|---|
| 莫离然然（@官方级工具作者，2598赞） | feed 74800795 | **小米QC解锁BL工具 v2.5Plus**：新增 64560/98260 提权，**支持澎湃OS4正式版一键解锁BL**，明确写「**K90正式版OS4一键提权解锁**」 |
| 同上 | feed 72862529 | v1.5：支持 8E/8E5 高版本，无视铠侠 |
| 同上 | feed 73558933 | v2.2（7626赞）：8E 机型解锁**无需刷包**（工程包+官方包都不用刷） |
| 莫离然然 | feed 72805607 | 小米8E系基于 CVE-2026-43499 提权进展：**测试成功机型含 K90**，「高版本无需再9008」 |
| Dev苏 | feed 71517523 | **Termux 手机给手机解锁BL**（重制版）：**红米k90 已测试，最新系统依旧可以解锁** |
| 睡Zzzz / 谁取了我吴彦祖这个名 | feed 74853407 | 小米红米天玑永久解锁（adb/fb 双模式），支持机型含 k90max 等，带永久伪回锁 |
| 零零QWQ | feed 75055155 | **k90max 双机解锁无需电脑**（两台手机 + 双C线） |
| 梵依（接单帖） | feed 74890471 | 骁龙8e机型秒解BL列表含 **红米K90** |

### 3. K90 Max ≠ K90

多个帖子的「K90 支持」其实是 **K90 Max**（代号 prague，2604FRK1EC）。
**K90 本机（annibale）的明确支持证据是：**
- feed 74800795（QC工具 v2.5Plus）：「K90正式版OS4一键提权解锁」
- feed 71517523（Termux方案）：「红米k90（已测试无需刷入降级小包解锁）（最新系统依旧可以解锁）」
- feed 72805607：「测试成功的机型有15Pro，15Ultra，K80Pro，K90，K90Ultra」
- feed 74890471：骁龙8e秒解BL列表含「红米K90」

---

## 三、三条可行路线对比

### 路线 A：QC解锁BL工具 v2.5Plus（PC一键，最推荐）

**原理**：临时root 提权 → 工具用临时root 写解锁文件（宽恕引导 / 免授权工程 abl）→ 双槽刷入解锁 lk → 官方包线刷 → 刷入 KernelSU/Magisk。

**步骤**
1. 装好 fastboot + 9008 驱动（工具箱 `Tools\Driver` 目录，无需重启）
2. 临时root 给 KSU「超级用户」授权 **shell**
3. 工具箱选对应机型（K90 / 8E），走「一键解锁」
4. 解锁后线刷官方包（`flash_all.bat`，**不能选 lock 脚本**）
5. 刷入 KernelSU（推荐，8e 内核 6.6 系列）或 Magisk

**资源**
- 工具+资料：https://1812230881.share.123pan.cn/123pan/Id6rVv-BN1g3 （提取码 `mlrr`）
- 资源站：https://moliranran.com:5245/
- 官方线刷包：https://rom.oppo.help/

**优点**：不需要 9008 工程线；8E 机型的 v2.0+ 版本不用刷包。
**风险**：解锁会**清空全部数据**。

### 路线 B：Termux 手机自解锁（无需电脑）

**原理**：用 Termux 直接操作手机自己的 fastboot/ADB，通过 `miui.mqsas.IMQSNative` 服务写工程 abl。

**步骤**（feed 71517523 原文）
```bash
pkg install termux-usb android-tools -y

# 进 fastboot，OTA 数据线连手机（连自己）
termux-usb -l          # 得到 /dev/bus/usb/001/002
termux-usb -r -e $SHELL -E /dev/bus/usb/001/002

fastboot oem set-gpu-preemption 0 androidboot.selinux=permissive
fastboot continue
adb shell getenforce
adb devices
adb push abl.elf /data/local/tmp/abl
adb shell service call miui.mqsas.IMQSNative 21 i32 1 s16 "dd" i32 1 s16 'if=/data/local/tmp/abl of=/dev/block/by-name/abl_a' s16 '/data/mqsas/log.txt' i32 60
adb shell service call miui.mqsas.IMQSNative 21 i32 1 s16 "dd" i32 1 s16 'if=/data/local/tmp/abl of=/dev/block/by-name/abl_b' s16 '/data/mqsas/log.txt' i32 60
adb reboot bootloader

# 再次 termux-usb -l / -r -e $SHELL -E <路径>
fastboot flash partition:4 jiesuo_gpt_both4.bin
fastboot boot boot.img
# 花屏等 10 秒，手动重启进 bootloader，查询 unlocked 状态
fastboot getvar unlocked    # 出现 unlocked=yes 即成功

# 刷完整包（MT 管理器执行）
sh /storage/emulated/0/Alarms/h/k90/img/flash_all.sh
# 若卡 fastboot：
fastboot flash partition:4 mi_gpt_both4.bin
fastboot erase userdata
fastboot erase metadata
fastboot reboot
```

**文件**：http://pan.ieml.cn/#s/ECroGtIL （提取码 `68Rc1`）
**完整包**：https://hyperos.fans/

**优点**：完全不需要电脑。
**注意**：路径不能有空格和括号；`jiesuo_gpt_both4.bin` 与 `boot.img` 路径需替换成实际位置。

### 路线 C：9008 免授权写工程 abl（最原始，资料最全）

**步骤**（feed 72612030 原文，K90至尊版）
1. **先查字库类型**：用澎湃工具箱/逸风工具箱抓日志看存储信息
   - **铠侠字库 → 免授权引导不可用（会变大黑砖），立即停止**
   - 非铠侠（东芝/海力士/三星）→ 可继续
2. 进 9008：需二代工程线，或花钱「算码踢 9008」
3. OneToolBox → 刷机 → 高通模式 → 选引导文件 → 读取分区表 → 选 6 个 xml → 写入分区 → 重启到系统
4. 花屏/白屏等 10 秒别拔线 → 手动进 fastboot → 查 `unlocked: yes`
5. **还原分区表**（必做，否则线刷报错）
6. 线刷官方包：`flash_all.bat`（**别选 lock**）

**资源**：https://1812230881.share.123pan.cn/123pan/Id6rVv-XyOg3 （提取码 `mlrr`）

---

## 四、永久root 的两种形态

| 形态 | 实现 | 特点 |
|---|---|---|
| **KernelSU（内核级）** | 刷入 KSU 内核/镜像 | 内核级 root，不写分区、不动 boot，隐藏最强、可随系统升级不掉 root。酷安 K90 玩家主流选择（feed 74471671：「root方式：ksu 内核级root更省电」） |
| Magisk（patch） | patch boot.img | 通用，隐藏 root 需要额外模块（ZygiskNext / Shamiko 等） |

**K90 玩家实际配置参考**（feed 74471671）：
```
1. 调度：scene / lp
2. fas引擎：scene fas
3. 调速器：schedutil 或 walt
4. 内核：A17官核 / 潘多拉 25w43g（A17别刷）
5. 核心分配：scene 自带 / asoul
6. 温控：scene 深度定制 pro
7. rom：枫城念旧 / 江南
8. 墓碑：noactive 最新版
9. root方式：ksu 内核级root更省电，潘多拉能用
```

---

## 五、开始前必须做的检查（缺一不可）

| # | 检查项 | 为什么 | 怎么查 |
|---|---|---|---|
| 1 | **字库类型**（铠侠/东芝/海力士） | 铠侠用免授权引导会**大黑砖** | 澎湃工具箱 / 逸风工具箱 → 抓日志 → 存储信息 |
| 2 | 备份 IMEI / MIUI 码 / 基带信息 | 刷机失败丢基带要靠这个恢复 | 拨号盘 `*#06#` 截图 |
| 3 | **备份字库** | 字库存着基带 IMEI，刷机必先备 | 解锁成功后第一件事 |
| 4 | 备份个人数据 | 解锁会清空全部数据 | 云同步 / 电脑拷贝 |
| 5 | 确认系统版本对应包 | K90 4.0.6.0 要对应的官方线刷包 | 官方包版本与当前一致或更高 |
| 6 | 确认 `uname -r` 精确匹配 | 临时root 工具**按内核完整版本号匹配**，不是按机型 | Termux `uname -r` |
| 7 | 电脑环境干净 | 只用一位作者的工具箱，避免冲突 | 关杀软/网吧机不用 |

---

## 六、风险与不可逆点

| 风险 | 等级 | 说明 |
|---|---|---|
| **解锁清空数据** | 确定 | 所有路线都会 wipe |
| 刷 lk 变砖 | 高 | lk 是整包替换 bootloader，起不来只能 BROM/9008/售后 |
| 铠侠字库黑砖 | 高 | 必须先查字库 |
| 丢基带 | 中 | 提前存 IMEI，9008 可写回 |
| 系统升级失效 | 低 | 解锁后 OTA 会失败/回锁，需关闭系统更新 |
| 小米账号风险 | 中 | 售后检测到解锁可能影响保修 |
| 临时root 中途重启 | 低 | 重启即失效，流程中别手贱重启 |

---

## 七、推荐执行顺序

```
第 0 步  查字库（澎湃工具箱）→ 铠侠则停，走售后或换方案
第 1 步  备份 IMEI/MIUI码/数据；准备官方线刷包（对应 4.0.6.0 或更高）
第 2 步  确认临时root 工具支持当前 uname -r（6.6.118-android15-8-...）
第 3 步  临时root → KSU 授权 shell
第 4 步  【路线A】QC解锁BL工具 v2.5Plus 一键解锁
         （无电脑则改【路线B】Termux 方案）
第 5 步  查 fastboot getvar unlocked → unlocked=yes
第 6 步  还原分区表 + 线刷官方包 flash_all
第 7 步  刷 KernelSU（内核级）或 Magisk
第 8 步  备份字库（必做）
第 9 步  关闭系统更新；装隐藏模块（ZygiskNext/伪装BL）
第 10 步  验证 root 持久性 → 重启后再确认
```

---

## 八、酷安原帖索引

| feedId | 标题 | 作者 | 用途 |
|---|---|---|---|
| 74800795 | 小米QC解锁BL工具v2.5Plus | 莫离然然 | **主工具帖**，K90正式版OS4一键提权解锁 |
| 73558933 | 小米QC解锁BL工具v2.2 | 莫离然然 | 8E 无需刷包方案说明 |
| 72862529 | 小米QC解锁BL工具v1.5 | 莫离然然 | 8E/8E5 高版本无视铠侠 |
| 72805607 | 小米8E系CVE-2026-43499提权进展 | 莫离然然 | K90 提权测试成功记录 |
| 71517523 | Termux手机给手机解锁BL（重制版） | Dev苏 | **无电脑方案**，K90已测试 |
| 72612030 | 红米K90至尊版解锁Bootloader教程 | 莫离然然 | 9008 免授权写 abl 完整流程 |
| 75077874 | GhostLock 临时root全机型适配清单 | 额看手机就是就是 | 内核版本匹配表 |
| 75055155 | k90max双机解锁无需电脑 | 零零QWQ | 双机方案 |
| 74853407 | 小米红米天玑永久解锁 | 谁取了我吴彦祖这个名 | 永久解锁+伪回锁 |
| 74890471 | 接单刷root（秒解BL机型表） | 梵依 | K90 在 8e 支持列表 |
| 71949771 | K90 玩机思路 | vip378root | 完整玩机流程与备份清单 |
| 74471671 | K90 优化教程（root方式/模块配置） | 北の湖湖湖湖 | 永久root后的模块配置 |

---

## 九、待实机确认项

1. **字库类型**（最关键，卡在这里）
2. **适配表「OS4.0.27」与你的「4.0.6.0」是否同一版本** —— 若临时root 工具报内核不匹配，可能是版本写法差异
3. `uname -r` 完整串在 GhostLock payload 列表里的精确匹配项
4. K90（annibale）对应的 `jiesuo_gpt_both4.bin` / `mi_gpt_both4.bin` / `abl.elf` 是否在分享包内
5. QC 工具 v2.5Plus 是否已内置 6.6.118 的 98260/64560 提权 payload
