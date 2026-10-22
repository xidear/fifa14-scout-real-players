# FIFA14 2 号球衣 bug — 代码层研究进展（2026-10-20）

## 1. 结论先说

- 2 号球衣不是数据库字段问题，也不在 `fifa.db` 里。
- 游戏通过 Apt UI 脚本调用原生 API：
  `MGRSetPlayerJerseyNumber(playerid, jerseynum)`（2 个参数）。
- 这个 API 只是“把某个号码设置给某个球员”；**真正决定新援拿几号、是否抢 2 号的逻辑在调用它的管理器/转会流程里**，不在数据库。
- 已找到大量与号码/阵容/合同/转会相关的 UI 文件；`aOldRank`、`aNewRank`、`teamRank` 等变量说明号码与“队内排序/能力排序”有关，和用户实测“新援能力 ≥ 原 2 号就抢 2 号”一致。
- 尚未定位到最终计算 `jerseynum` 的原生函数；下一步是继续反编译管理器转会函数，或用 root/Frida 对 `MGRSetPlayerJerseyNumber` 做调用栈 trace。

## 2. 工具链（已跑通）

### 2.1 OBB 结构

- 原版 OBB：`D:\FIFA14\work\obb_original.bin`（1,386,236,976B）。
- 里面是大量 **BIG4** 归档：
  - magic `BIG4`
  - +4：u32 LE 归档总大小
  - +8：u32 BE 文件数
  - +12：u32 BE 数据起始偏移
  - 条目：u32 BE offset、u32 BE size、null 结尾文件名（无额外对齐）
- 例：`0x22d2ec90` = `checklineups` 归档，148,341B，6 个文件。

### 2.2 BIG4 提取

脚本逻辑：

```python
size = u32le(o+4); count = u32be(o+8); doff = u32be(o+12)
pos = o+16
for i in range(count):
    off = u32be(pos); sz = u32be(pos+4); pos += 8
    end = data.find(b'\0', pos)
    name = data[pos:end]; pos = end+1
    payload = data[o+off:o+off+sz]
```

### 2.3 EA RefPack 解压（已用 Gibbed 算法验证）

`.apt/.const/.geo/.tga` 条目是 RefPack：

- 头：`0x10 0xFB` + 3 字节 BE 未压缩大小（`isLong` 时 4 字节）。
- 命令流：

```
prefix < 0x80:
  plain = prefix & 3
  copy  = ((prefix & 0x1C) >> 2) + 3
  off   = (((prefix & 0x60) << 3) | next) + 1
0x80 <= prefix < 0xC0:
  plain = next1 >> 6
  copy  = (prefix & 0x3F) + 4
  off   = (((next1 & 0x3F) << 8) | next2) + 1
0xC0 <= prefix < 0xE0:
  plain = prefix & 3
  copy  = (((prefix & 0x0C) << 6) | next3) + 5
  off   = ((((prefix & 0x10) << 4) | next1) << 8 | next2) + 1
0xE0 <= prefix < 0xFC:
  plain = ((prefix & 0x1F) + 1) * 4
prefix >= 0xFC:
  plain = prefix & 3; stop
```

- 解压后 `.apt` 头为 `Apt Data:1:7:4` / `1:8:4`；`.const` 头为 `Apt constant file`。
- 解压结果已存 `D:\FIFA14\work\ui_dec\` 和 `ui_hits\`。

### 2.4 扫描结果

- 全 OBB 扫描到 **552 个 BIG4 候选**，成功解出 **1,632 个 UI 文件**。
- 与 jersey/number 相关的命中 47 个，重点：
  - `apistubdata.apt` / `apistubdata.const`
  - `playercontracts.const`
  - `transfermarket.apt` / `transfermarket.const`
  - `makeoffer.const`
  - `squad.apt` / `squad.const`
  - `playermanagementscreen.apt` / `.const`
  - `checklineups.apt` / `.const`
  - `matchfactsform.const`、`playerbiodetails.const`、`playerbiolist.const`
  - `tactics.const`、`playerstats.const`

## 3. API 证据

在 `apistubdata.apt` 中：

```
MGRSetPlayerJerseyNumber
...
playerid:
jerseynum:
```

在 `apistubdata.const` 中同名 API 附近：

```
MGRSetPlayerJerseyNumber
...
playerid
jerseynum
```

说明 UI 通过 `CallGameFunc` 调用原生：
`MGRSetPlayerJerseyNumber(playerid, jerseynum)`。

UI 中号码只是**显示**（`aJerseyNumber`、`jerseyNum`、`jerseyNr_tf`），没有看到“选择号码”的算法；算法应在原生管理器/转会完成逻辑。

## 4. 与 #2 规则的关系

用户实测：

- 新援能力 < 原 2 号：不抢 2 号；
- 新援能力 ≥ 原 2 号：抢 2 号，原 2 号被挤到别的号。

这与“按队内能力排序/明星槽位分配号码”一致：

- UI 中存在 `teamRank`、`aOldRank`、`aNewRank`、`aPlayerOverall` 等字段；
- #2 很可能是“非门将第一顺位/明星槽”，新援能力超过原 2 号后排序上升，号码跟着重排。
- 因此不是简单的“2 号偏好”字段，而是**排序 + 号码分配**的组合。

## 5. 下一步（不用打赛季）

1. **定位原生 handler**：
   - 在 `libFIFA14.so` 的 Apt API 注册表中找 `MGRSetPlayerJerseyNumber` 对应的函数指针；
   - 或反编译 `Blaze::GameManager`/career/transfer 相关函数，找调用 `MGRSetPlayerJerseyNumber` 的位置。
2. **动态 trace（需要 root 或可调试环境）**：
   - Hook `MGRSetPlayerJerseyNumber`，记录 `playerid`、`jerseynum` 和调用栈；
   - 对比“新援能力 < / ≥ 原 2 号”两次转会，看 `jerseynum` 由谁计算。
3. **改法优先级**：
   - 若能改原生：把“明星/排序抢 2 号”改成“保留原号码，只分配最小空号”；
   - 若不能改原生：在转会完成前通过 UI/脚本覆盖号码，或在数据库层面预置目标号码（但可能被管理器重排覆盖）。
4. 不做的事：不靠打几个赛季验证；不随便推平板。

## 6. 关键文件/路径

- OBB：`D:\FIFA14\work\obb_original.bin`
- 解包/解压脚本：`D:\FIFA14\work\scripts\`（本轮临时脚本可整理为 `big4_refpack.py`）
- 解压结果：`D:\FIFA14\work\ui_dec\`、`D:\FIFA14\work\ui_hits\`
- 原生库：`D:\FIFA14\work\jersey_research\libFIFA14.so`
- Ghidra：`D:\FIFA14\work\jersey_research\ghidra_11.4.3_PUBLIC`
- 旧静态报告：`ghidra_jersey_report.txt`
---

## 7. 2026-10-21 修正与突破（重要：上一轮地址全错）

### 7.1 上一轮为什么一无所获

- Ghidra 载入本 .so 时 **imagebase = 0x10000**；上一轮把“文件偏移”直接当 Ghidra 地址用，所有字符串地址都少了 0x10000，于是打印 `data=None`、`refs=0`。
- 正确换算：
  - 第一段（文件 < 0x10ac390）：`Ghidra 地址 = 文件偏移 + 0x10000`
  - 第二段（文件 ≥ 0x10ac390）：`Ghidra 地址 = 文件偏移 + 0x11000`
  - 节区实际 vaddr：`.text 0x338fd8`、`.rodata 0xff01f0`、`.data 0x10e8000`、`.bss 0x1158f70`。

### 7.2 API 名字不是没人引用，而是引用算错了

修正后，`MGRSetPlayerJerseyNumber`（Ghidra 0x10160F8）有 2 个直接引用：

| 引用地址 | 函数 | 作用 |
|---|---|---|
| 0x004eadac | FUN_004eac4c | 注册（RegisterLVHandler / RegisterFSHandler） |
| 0x004eaf70 | FUN_004eaeac | 注销（Unregister...） |

### 7.3 原生 API 注册机制（已完整解出）

以 FUN_004eac4c 为例（ARM 模式）：

```asm
push {r4,r5,fp,lr}
ldr  r0,[pc,#0x1ec]      ; 字面量 0x00c0cb74
ldr  r1,[pc,#0x1f0]      ; 字面量 0x00002708
add  r5,pc,r0            ; r5 = 名字表基址（Ghidra 0x10F77D8）
add  r4,r1,r5            ; r4 = 处理函数记录数组基址（Ghidra 0x10F9EE0）
ldr  r0,[pc,#0x1e0]      ; 相对名字偏移 0xfff1e7b8
add  r0,r0,r5            ; → 0x1015F90 = "MGRGetNationalityList"
add  r1,r4,#0            ; 第 1 个记录
bl   0xa30070            ; AIP::RegisterLVHandler
```

- **LV handler** = 有返回值的变量读取函数（`bl 0xa30070`）。
- **FS handler** = 无返回值的命令函数（`bl 0xa2ff78`，如 SetPlayerJerseyNumber、ClearSearch、SortSearch）。
- 名字 = `r5 + 字面量`，字面量是相对偏移；同一块内所有名字共用同一个 `r5`。
- 处理函数记录 = 12 字节 `{u32 函数指针, 0, 0}`，记录数组在 `.data`（部分块在 `.bss`，运行时初始化）。

### 7.4 MGRSetPlayerJerseyNumber 的真实实现

注册块 FUN_004eac4c 共 24 个 API，顺序与名字表一致；第 17 个就是它，记录偏移 **+0x2C**：

- 记录地址（Ghidra）= `0x10F9EE0 + 0x2C = 0x10F9F0C`
- 文件偏移 = `0x10E8F0C`（第二段换算 -0x11000）
- **handler = 0x004D8CC0**（Ghidra 0x4E8CC0）

反编译 FUN_004e8cc0：

```c
void FUN_004e8cc0(undefined4 a, undefined4 b, CmdDecomposer *cmd)
{
  int playerid = 0, jerseynum = 0;
  int base = DAT_004e8d3c + 0x4e8ce8;          // 名字表基址
  GetIntByName(cmd, base + DAT_004e8d40, &playerid);   // "playerid"
  GetIntByName(cmd, base + DAT_004e8d44, &jerseynum);  // "jerseynum"
  FUN_00404c78();                              // 取锁/事务
  FUN_00613ddc(base + DAT_004e8d48,            // "teamplayerlinks"（表名）
               base + DAT_004e8d40, playerid,  // 键名 "playerid" + 值
               base + DAT_004e8d4c, jerseynum);// 字段名 "jerseynumber" + 值
}
```

字面量解出的字符串（文件偏移）：

| 表达式 | 结果 | 内容 |
|---|---|---|
| DAT_004e8d44 + base | 0x1015EBD | `jerseynum`（命令参数名） |
| DAT_004e8d48 + base | 0x10028D7 | `teamplayerlinks`（表名） |
| DAT_004e8d4c + base | 0x1006E35 | `jerseynumber`（字段名） |

**结论：`MGRSetPlayerJerseyNumber` = `UPDATE teamplayerlinks SET jerseynumber=? WHERE playerid=?`。**
`FUN_00613ddc` 是被 37 个调用点共用的通用“按表名/键/字段写值”函数，不是号码分配算法。

### 7.5 转会相关 API（已定位注册块）

注册块 **FUN_00524478**（Ghidra 0x524478），共 9 个 API：

| API | 记录偏移 | 类型 |
|---|---|---|
| MGRTransferNewSeasonResetStart | +0x1A4 | LV |
| MGRTransferNewSeasonEnd | +0x1B0 | LV |
| MGRCareerSetPlayerTeamForTransfer | +0x1C0 | LV |

该块记录数组基址（Ghidra）经计算为 `0x118F038` + 偏移，落在 **.bss**（`0x1158f70` 之后），文件里全 0，说明：
- 这些 handler 是**运行时初始化**的；静态文件里读不到函数指针。
- 要找它们的实现，需要：①找 .bss 初始化函数（构造/init_array 或某个 init 流程）；②或动态 trace。

### 7.6 DB 球衣号编码复核（与代码一致）

`teamplayerlinks`（主库 T80，`offs[80]+8` 起，16B/行）：

```
row = (u32 teamid, u32 playerid, u32 flags, u32 alt)
jersey = ((flags & 0xFF) >> 1) + 1
bit0 = 独立标志位（不参与号码）
```

- 输出库 `scout_real_fifa14/main_fifa.db`：631 支 ≥5 人球队，**重复号码 0**；号码范围 1–99。
- 所以“2 号球衣”不是数据库里重复/缺号，仍是**引擎在转会/入队时重排号码**的行为。

### 7.7 平板 / root 状态（2026-10-21）

- 平板进入 fastboot 后 Windows 无 `VID_18D1&PID_D00D` 驱动（设备状态 Error）。已用自签 WinUSB 驱动解决：
  - `fastboot_winusb.inf`（Include=winusb.inf, Needs=WINUSB.NT）
  - `makecat` 生成 `.cat` → `signtool` 自签 → 证书装进 `LocalMachine\Root` + `TrustedPublisher` → `pnputil /add-driver /install`
  - 结果：设备状态从 Error 变 **OK / Class=USBDevice / Service=WinUSB**。
- 随后执行 `pnputil /restart-device`，设备从 USB 总线消失（所有 VID_18D1 实例变为 Unknown，adb 也看不到），疑似 fastboot 超时关机或需要重新插线。**下次插线/开机后先 `fastboot devices` 验证驱动。**
- 工具已留在 `D:\FIFA14\work\tools\`（signtool.exe / makecat.exe），驱动在 `D:\FIFA14\work\fastboot_drv\`。

### 7.8 下一步（按优先级）

1. 平板重新上线 → `fastboot devices` 确认；root 路线：`fastboot boot twrp_clover.img` → TWRP 里刷 Magisk（免改 boot），或 frida-gadget 重打包（免 root，但要重装）。
2. 静态：找 `.bss`（0x118F038 起）初始化函数，拿到三个转会 API 的 handler。
3. 静态：反编译引用 `jerseynumber` 的 30+ 函数，重点 FUN_004e7ee4 / FUN_0049e9a0 / FUN_004fd928 / FUN_0062e240，找“按能力/序号重排号码”的写点。
4. 不靠打赛季验证；不自动推平板。

### 7.9 转会三 API 的 handler 已拿到（但仍是 DB 包装层）

- 初始化函数 `_INIT_19 @ 0x525D60` 负责填 `.bss` 里 0x118F038 起的记录；它把 +0x1A4/+0x1B0/+0x1C0 写成“指针→对象”，对象首字才是函数：
  - `MGRTransferNewSeasonResetStart` → handler vaddr **0x00513A64**
  - `MGRTransferNewSeasonEnd` → handler vaddr **0x005143E4**
  - `MGRCareerSetPlayerTeamForTransfer` → handler vaddr **0x00513B28**
- Ghidra 自动分析把 0x513A64 吞进了 FUN_00613A18，需要手动 `createFunction` 才能按入口反编译。
- 反编译结果：三者仍是**通用 DB 读写包装**（拼表名/键/字段，调 FUN_009f5E5C / FUN_009f5DDC），没有“比较能力、重排序号”的逻辑。
- 结论：**API 层只做 DB CRUD；自动选号/重排是内部 manager 代码，不经这些 UI API。** 纯静态继续找的性价比很低，下一步应以动态 trace 为主（root+Frida 或 frida-gadget 重打包）。

---

## 8. 2026-10-21 动态验证：手动改号码已打通（root+Frida）

### 8.1 生涯球衣号在内存中的位置（实测）

用 Frida 在游戏进程里扫描 `(teamid=10, pid)` 记录，找到生涯世界库的 team-player 行（16B/行）：

| 球员 | pid | 内存地址 | flags | 号码 |
|---|---|---|---|---|
| Micah Richards | 169721 | 0xbc7ba978 | 0x808d1a14 | 11 |
| Daniel Sturridge | 171833 | 0xbc7ba988 | 0x600a03 | 2 |
| Pedro Obiang | 200054 | 0xbc7ba9d8 | 0x600217 | 12 |

- 同一 pid 在 cmn 主库里还有一份（0xb978cd58，flags 0x808d0a03 = #2），**生涯库和主库是两份独立内存**。
- 号码编码再次确认：`jersey = ((flags & 0xFF) >> 1) + 1`（0x1a14→11、0x600a03→2、0x600217→12）。

### 8.2 直接调用内部写库函数：成功

`libFIFA14.so + 0x603DDC`（Ghidra FUN_00613ddc）就是 `MGRSetPlayerJerseyNumber` 内部使用的写库函数，签名：

```c
void setter(const char *table, const char *keyname, int key,
            const char *field, int value);
```

用 Frida `NativeFunction` 调用：

```js
fn("teamplayerlinks", "playerid", 169721, "jerseynumber", 13);
```

实测：
- 生涯行 flags `0x808d1a14`（#11）→ `0x808d1a18`（#13）→ 还原 `0x808d1a14`（#11）；
- cmn 主库行 `0x808d0a03` **完全不变** → 在生涯模式下，该 setter 写的是生涯世界库，正是我们要的；
- 游戏不闪退，无需 UI、无需改任何文件。

### 8.3 手动改号码工具（PC 端，已可用）

`D:\FIFA14\work\jersey_cli.py`：

```
python D:\FIFA14\work\jersey_cli.py set "Micah Richards" 2
python D:\FIFA14\work\jersey_cli.py set 169721 2
python D:\FIFA14\work\jersey_cli.py find "Obiang"
```

- 名字→pid 用 `modified_copy_20261019\scout_real_fifa14\main_fifa.db`；
- 通过 Frida attach 到正在运行的 `FIFA 14`，调 0x603DDC 写生涯库；
- 前提：平板已 root（Magisk 30.7）、frida-server 16.5.9 在跑、游戏在生涯模式；
- 只改运行时内存，不碰 APK/OBB/存档文件；改完退回阵容界面即可看到。

### 8.4 关于“做成游戏内菜单”

- 全 OBB 的 UI 脚本里**没有任何一处调用** `MGRSetPlayerJerseyNumber`（只有 apistubdata 声明），所以游戏本身没有号码编辑入口。
- 要做成游戏内 UI，需要改 `squad.apt` 等 Apt 字节码新增按钮/输入框并调用该 API——工作量远大于本次 bug 本身，不建议。
- 现实方案：PC 端 CLI（已交付）；或后续做一个“转会完成后自动把号码改回”的 Frida 守护脚本。

### 8.5 仍未抓到“转会重排”的写入指令

- 在生涯行所在页（0xbc7ba000）挂 MemoryAccessMonitor 120 秒，用户把理查兹放进首发并模拟一场比赛：**该页 0 次写入**（阵容变更写的是别的结构）。
- 所以“新援抢 2 号”的重排写入仍未定位；需要在下一次转会发生时重新布控（页监控 + 事务窗口），或改用整页硬件/软件断点方案。

---

## 9. 游戏内“改号”按钮（Frida 注入 UI）— 2026-10-21 进展

### 9.1 结论

- 游戏 UI 脚本里没有号码编辑入口（全 OBB 无一处调用 `MGRSetPlayerJerseyNumber`），但可以在**运行时**用 Frida 往游戏进程里塞一个悬浮按钮：
  - `android.app.ActivityThread.currentApplication().getApplicationContext()`
  - `ViewManager.addView(Button, WindowManager.LayoutParams(TYPE_APPLICATION_OVERLAY=2038))`
  - 已用 `appops set com.ea.game.fifa14_row SYSTEM_ALERT_WINDOW allow` 授权
- 点击按钮 → 调 `libFIFA14.so+0x603DDC("teamplayerlinks","playerid",pid,"jerseynumber",n)` 改生涯库。

### 9.2 踩过的坑（都已解决）

| 现象 | 原因 | 解决 |
|---|---|---|
| 主线程读 4MB 数据库 → `false` 对话框 / ANR | `fopen/fread` 在主线程同步读 | 用 `pthread_create` + `NativeCallback` 开工作线程读文件 |
| 新线程里 `Thread.sleep` 不存在 | Frida 的 Thread 是高级对象，不是系统线程 | 改用 libc `usleep` |
| 工作线程里调 `Java.scheduleOnMainThread` → `JNI DETECTED ERROR / use of invalid jobject` + SIGSEGV | 该线程没有 Java 环境 | 工作线程只做纯 native 读；成功后在**发起调用的 JS 线程**里回调 |
| `vm.addView` 报 `TypeError: not a function` | `ViewManager.addView` 的两个重载在 Frida 里歧义 | `Object.getOwnPropertyNames(vm)` 找到 `addView` 并 `f.call(vm, b, lp)` |
| 按钮 `isAttachedToWindow=true` 却看不见 | 游戏 Activity 用 SurfaceView 盖住 window decor，叠加窗口在它下面 | 改用 `TYPE_APPLICATION_OVERLAY`（2038），直接叠在最上层 |

### 9.3 当前状态

- 脚本 `D:\FIFA14\work\jersey_ui.js`；开机服务 `/data/adb/service.d/fifa_jersey_ui.sh`（等 FIFA 启动后自动注入，保持只有一个注入器）。
- 配置 `.../files/jersey_ui.cfg` = `10 Manchester City`；日志 `.../files/jersey_ui.log`。
- 列表点选 → 输入号码 → 写生涯库 → 刷新列表。

---

## 10. 存档方案落地（2026-10-19 ~ 10-22）

内存扫描会让游戏 OOM（logcat OutOfMemoryError，FIFA 进程被杀），因此改走存档路线，最终完成外置 App。

### 10.1 存档结构（已实测）

- 文件：`/sdcard/Android/data/com.ea.game.fifa14_row/SAVECAREER.<日>.<月>.<年>.<时>.<分>.<秒>`，本档 3,423,800 字节。
- roster 行 16 字节：`team u32 / pid u32 / flags u32 / alt u32`（小端）。
- 球衣号：`jersey = ((flags & 0xFF) >> 1) + 1`；写回只改 flags 低字节。
- 行起点不对齐 16：本档 `offset % 16 == 4`，必须按 0/4/8/12 四种对齐各扫一遍。
- 连续 ≥5 行同一 team 视为一个球队块；本档 587 个块 / 586 队；曼城（team 10）在 0x5AF4，24 行。
- 交换两号（Richards 11 ↔ Sturridge 2）整个文件只变 2 字节：0x5BEC、0x5BFC（flags 低字节）。

### 10.2 游戏拒档的真正原因：文件属主

写入后游戏提示「无游戏存档可用」。原因不是校验和，而是文件属主/权限：

- 正确：`media_rw (1023) : u0_a20245 (30245)`，`660`。
- 错误：`root:root 660`（root 的 cp/mv 默认结果）。
- 必须 **先 chown/chmod 临时文件，再 mv 覆盖**；先 mv 再 chown 会留下错误属主的窗口。
- 尾部 4 字节 `0xb17aefc5` 不是校验和：最小改动后不改它也能读档；crc32/adler/md5 均不匹配。

### 10.3 App（com.zcode.jersey）

- 前台服务 + `TYPE_APPLICATION_OVERLAY` 悬浮按钮；服务上下文**不能**用 AlertDialog（BadTokenException），所有弹窗都是 WindowManager 加的 overlay View。
- 面板：球队选择（按名称筛选）、按号码排序的球员列表、逐人改号、冲突自动交换、刷新。
- 号码输入弹窗置顶（y=56dp）+ 自动弹键盘，避免按钮被 IME 挡住。
- 长按「改」按钮：移除按钮 / 恢复改号前备份 / 退出面板；通知栏也有显示-隐藏、退出。
- 首次写入自动备份 `<存档>.bak_jersey`。
- 读档/写档全部走 `su`；存档解析在 App 内用 ByteBuffer LE 完成。
- 球员姓名索引：`assets/fifa.db`（856KB，32,564 人 / 631 队，小端 + 魔数 0x4A523034）。
  - 坑：`DataInputStream.readInt()` 是大端，直接读这个索引会报 bad index magic，必须手写 LE 读取。
- 坑：`am startservice` 以 shell 身份调用会被 `exported=false` 拒绝；root（`su -c am ...`）可以。

### 10.4 与游戏本体的关系

- 未改 APK：签名限制导致任何 APK 修改都要卸载重装，会丢 `Android/data`（存档）和 1.4GB OBB。
- 未改 UI：FIFA14 界面是私有 Apt 编译脚本，无编译器、无扩展点。
- 替代：Magisk 模块 `fifa14_jersey_auto`，启动 FIFA14 时自动以 root 拉起 `PanelService`（ACTION_START，只显示按钮不展开面板），实现「进游戏就有改号入口」。

### 10.5 验证状态

- 已验证：面板读取存档、列表按号码排序、改号写入、冲突交换、仅 2 字节 diff、属主/权限正确、按钮可移除/恢复、球队选择、自动备份。
- 待用户验证：在游戏里点「继续职业生涯」，确认存档被接受且理查兹显示 #2（Sturridge #11）。
