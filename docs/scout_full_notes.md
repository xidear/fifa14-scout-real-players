# FIFA14 Android 球探全真实球员池 — 全量经验总结（仅原版 14）

日期：2026-10-20
设备：小米平板 4（Mi Pad 4，Android 8.1，ADB 89e96829）
包名：com.ea.game.fifa14_row（原版 1.3.6 + 原版 OBB）
工作目录：`D:\FIFA14\work\scout_real_fifa14\`
最终产物：主库 md5 `02dbbda0f5b40fbf49d86f1b62035eae`，New DB md5 `017f17335b5805db112f100438c019fe`

> 本文只分析原版 FIFA14 的 `fifa.db` 与 `New DB/fifa.db`，不使用任何其它版本的游戏数据。

---

## 1. 当前结论

- 原版两个库 `400000–416281` 的 **16,282 个假球员全部覆盖为真实职业球员**；400k 段无假名。
- 主库 72B/行；New DB 76B/行；同 pid 同球员，两库分别写入。
- 1,826 名原版已有球员按 FIFA15–FC26 最高 Overall 改潜力，不动当前能力。
- 10 个板块：英格兰、法国、德国、荷兰、意大利、西班牙、欧洲其他、美洲、非洲、亚太。
- 位置按 FC26 真实主位置 + 第一个副位置逐人显式写入，不再继承 donor 的位置位。
- 用户在**原版 14 开档**亲眼确认：南锡有 Lenglet，马竞有 Lucas Hernández（27 号），本菲卡有 Bernardo Silva；这三人按“原版已有”处理，不再加入 400k 新增池，避免重复。
- 旧存档与最新 pid 不兼容：必须新建生涯；旧存档已移到平板 `save_backup_20261020/`。

最终产物：

| 文件 | 大小 | md5 |
|---|---:|---|
| `out/main_fifa.db` | 4,141,594B | `02dbbda0f5b40fbf49d86f1b62035eae` |
| `out/newdb_fifa.db` | 4,742,554B | `017f17335b5805db112f100438c019fe` |

平板路径：

- `/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/fifa.db`
- `/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/New DB/fifa.db`

第二份：`D:\FIFA14\modified_copy_20261019\scout_real_fifa14\`

---

## 2. 原版 14 数据架构

### 2.1 主库 `data/cmn/fifa.db`

- 90 张表；头部 = 90 个 u32 表偏移，偏移从字节 12 开始。
- 球员表 `offs[79]`：`[count u32][schema ptr u32]`，行 72B，基址 `offs[79]+8`，32,564 条。
- 假人池 pid `400000–416281` 共 16,282 条，全部无俱乐部挂靠。
- 字段：pid@0；姓名指针 +4/+8/+12；DOB +16（1582-10-14 起天数）；meta 20:36；打包属性 36:72。
- 潜力 bit374（7-bit LSB）；国籍 bit518（8-bit MSB）；pref1 bit179（5-bit）；pref2 bit189（5-bit）。
- 球队链接表 `offs[80]+12`，16B 行 `(pid, packed, alt, teamid)`；球衣号 = `(packed & 0xFF)//2 + 1`。
- 球队表 `offs[81]+8`，44B 行 `(teamid u32, nameptr u32, ...)`。
- 国家表（T66）：12B 行 `(countryid u32, nameptr u32, continentid u32)`；**球员国籍码 = countryid − 1**，不是行号。

### 2.2 New DB `data/cmn/New DB/fifa.db`

- 123 张表；球员表 `offs[112]`，行 76B，32,565 条。
- 姓名指针 +4/+8/+12/+16；DOB +20；属性块 24:76。
- 所有位偏移相对主库 **+32**：潜力 bit406；国籍 bit550；pref1 bit211；pref2 bit221。

### 2.3 字符串与读库

- 姓名 = `u16 长度 + UTF-8`；指针是相对本库起点的绝对偏移；新增姓名追加到文件尾。
- 经验上 sdcard `data/cmn/fifa.db` 优先于 OBB 内嵌库；原版 OBB 主库头在偏移 `314,289,744`，New DB 头在 `318,158,784`。
- OBB 里还有姓名池（约 317–319MB 与 952.8–954.2MB），含假名与真实名；**姓名池不是球员记录**，不能当查重依据，也不能用来证明球员存在或不存在。
- 生涯模式实际读取的完整数据源尚未 100% 定位；遇到“某个文件里没有、游戏里有”，先承认用户观察，再查全部 14 数据源（主库 / New DB / 存档 / OBB），不能只查一个文件就下结论。

---

## 3. 10 个板块与国籍映射

| 板块 | 人数 |
|---|---:|
| 欧洲其他 | 4,640 |
| 美洲 | 4,168 |
| 英格兰 | 1,623 |
| 亚太 | 1,121 |
| 西班牙 | 999 |
| 非洲 | 961 |
| 法国 | 944 |
| 意大利 | 744 |
| 德国 | 687 |
| 荷兰 | 395 |

规则：

- 先按真实国籍找 FIFA14 同名板块：England/France/Germany/Netherlands/Italy/Spain 独立成板。
- 其余欧洲国家 → 欧洲其他；挪威→欧洲其他（没有挪威板）。
- continentid：32=欧洲；64/96=美洲；128/192=亚太；160=非洲。
- 美洲/非洲/亚太按 country 表 continentid 归属。
- 不在库里的国家用同板块代理国码（安道尔/圣马力诺→奥地利，卡塔尔→沙特，科索沃→阿尔巴尼亚等）。
- 亚太保留约 280 名中国/中华台北/香港/澳门球员。

关键落位（最终版）：

| 球员 | pid | 板块 | 位置 | 潜力 |
|---|---:|---|---|---:|
| Rodri | 407184 | 西班牙 | CDM/CB | 90 |
| Pedri | 407615 | 西班牙 | CM/CDM | 89 |
| Lamine Yamal | 407965 | 西班牙 | RM/RW | 89 |
| Eric García | 407625 | 西班牙 | CB/RB | 79 |
| Donnarumma | 410433 | 意大利 | GK | 89 |
| Barella | 410435 | 意大利 | CM | 87 |
| Chiesa | 410438 | 意大利 | RM/ST | 84 |
| Mbappé | 412577 | 法国 | ST/LW | 91 |
| Bellingham | 414319 | 英格兰 | CAM/CM | 90 |
| Saka | 414320 | 英格兰 | RW/RM | 88 |
| Foden | 414321 | 英格兰 | RW/CM | 88 |
| Vinícius Júnior | 404514 | 美洲 | LW/ST | 89 |
| Raphinha | 402353 | 美洲 | LM/LW | 89 |
| Haaland | 409613 | 欧洲其他 | ST | 91 |
| Kimmich | 411850 | 德国 | CDM/RB | 89 |

---

## 4. 数据管线

### 4.1 数据源

- 2014–2026 大赛名单：Wikipedia 决赛圈 squad 页（经 VPS 抓取），7,053 名唯一球员。
- 评分：Kaggle FC24 完整集（FIFA15–24）+ FC25 + FC26；Sofifa ID = `player_id`。
- 原版 14 库 ↔ Sofifa 映射：`build_db_sofifa_map.py`，13,109 人命中，高置信 12,299。

### 4.2 脚本顺序

1. `extract_original_dbs.py`：从 OBB 偏移 314,289,744 提取主库和 New DB 到 `base/`。
2. `build_db_sofifa_map.py`：原版库球员 → Sofifa ID，输出 `db_sofifa_map.csv` / `db_sofifa_ids*.json`。
3. `build_candidate_pool.py`：合并大赛名单 + FC24/25/26，按板块/年龄带选 16,282 人，输出 `candidate_pool.csv`。
4. `build_donor_pool.py`：从原版库真实球员建 donor 池（位置/当前能力），输出 `donor_pool.csv`。
5. `build_real_pool.py`：写主库 + New DB（姓名追加到 EOF、DOB、国籍、潜力、位置、donor 属性块）。
6. `validate_real_pool.py`：16,282 条回读 + 字节 diff 允许区检查。
7. `make_scout_guide.py`：按 10 板块 × 2013–2026 赛季生成 `scout_guide.md/csv`。

### 4.3 选人规则

- 板块按国籍；年龄带 A(≤1999)/B(2000–04)/C(≥2005) 约 45/35/20。
- 优先大赛球员、年轻球员、高 Overall。
- 已有球员只改潜力（1,826 人）；新球员填 400k 槽位。
- 同名不同人：评分最高者保留常用名，其余用全名区分。

---

## 5. 查重：有效做法与踩过的坑

### 5.1 有效做法

- 建原版两个库 **全部 32,565 名球员**的姓名字段索引（全名、首名+姓、common name）。
- Sofifa ID 高置信集合（12,299）优先。
- 规范化：去重音、去标点、小写。
- 双姓/长名：首名 + **任意后续姓 token**（如 `Lucas François Bernard Hernández Pi`、`Luis Fernando Díaz Marulanda`）。
- 缩写：`L. Díaz` 用全名首名还原。
- 生日/国籍加分；生日差超过 1 年直接拒绝。

### 5.2 踩过的坑

- 只用 13,109 个 Sofifa 映射会漏掉没有 ID 的球员和姓名变体。
- 用 OBB 姓名池当“已存在”依据会 **误删真实球员**：姓名池只是引擎取名来源，不是球员记录。
- 同名不等于同人：`Marquinhos Cipriano`（1999，LB）与巴黎 Marquinhos 不是一人；`Lucas Camilo Hernández Perdomo`（1992，乌拉圭）与法国 Lucas Hernández 不是一人。
- 用户实测优先：用户在原版 14 开档看到 Lenglet/Lucas/Bernardo，就按“原版已有”处理，不再新增；**禁止用单一 DB 缺失去否定用户**。

### 5.3 用户确认原版已有的三人

在 `build_candidate_pool.py` 的 `USER_CONFIRMED_EXISTING` 中显式排除（含变体）：

- `Clément Nicolas Laurent Lenglet` / `Clément Lenglet`
- `Lucas François Bernard Hernández Pi` / `Lucas Hernández`
- `Bernardo Mota Veiga de Carvalho e Silva` / `Bernardo Mota Carvalho e Silva` / `Bernardo Silva`

真正的原版库重复仍剔除：Marquinhos（PSG）、Fabinho（Monaco）、Xavi、Isco、Diego Costa。

---

## 6. 位置：donor 位置位串位与修正

### 6.1 根因

`build_real_pool.py` 原来执行 `rm[20:72] = dm[20:72]`，把 donor 的 **pref1/pref2 位置位**一起复制，又没有重写位置：

- Haaland donor Jeje Lalpekhlua：pref1=28(ST)、pref2=18(CAM) → 哈兰德显示 ST/CAM；
- Vinícius donor Fabrice Olinga：pref1=6(RB) → 显示后卫；
- Raphinha donor Bryan Ruiz：位置位异常 → 显示 CDM。

### 6.2 修正

复制属性块后显式写：

- 主库：`write_bits(rm,179,5,p1)`、`write_bits(rm,189,5,p2)`
- New DB：`write_bits(rn,211,5,p1)`、`write_bits(rn,221,5,p2)`

位置来源：

- 主位置 = FC26 `position`。
- 副位置 = FC26 `alternatePositions` 第一个。
- 不拼旧版位置；不按“CDM→CB”一刀切。
- 特例：Rodri → CDM/CB（用户要求）。
- 边锋只有 FC26 副位置含 ST/CF 时才给前锋位。

### 6.3 位置码

玩家 pref 字段代码（由原版 14 数据与 Ober/Dinescu=16=LWB 反推）：

`GK0 SW1 CM14 CAM3 RM30 LM7 RB6 LB15 CB10 CDM22 CF23 ST28 RW29 LW8 LWB16 RWB6`

注意：位置标签理论上还受属性块内部数据/宿主 meta 影响；这版是“按 FC26 显式写 pref”，仍需游戏内验收。

---

## 7. 校验与部署

### 7.1 校验

- 16,282 条逐条回读：姓名/生日/潜力/国籍/位置 0 错误。
- 主库与 New DB 位置位一致。
- 字节 diff 只允许落在：400k 记录、1,826 个潜力字节、文件尾追加字符串。
- 表头、表偏移、行数不变。

### 7.2 部署

```bash
MSYS_NO_PATHCONV=1 adb push out/main_fifa.db \
  "/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/fifa.db"
MSYS_NO_PATHCONV=1 adb push out/newdb_fifa.db \
  "/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/New DB/fifa.db"
MSYS_NO_PATHCONV=1 adb shell md5sum \
  "/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/fifa.db" \
  "/sdcard/Android/data/com.ea.game.fifa14_row/data/cmn/New DB/fifa.db"
```

- 改动前备份；第二份放 `modified_copy_<date>`。
- 不要 `pm clear`（会擦掉首启设置）。
- 改库后强制停止游戏，再让用户新建生涯。
- 旧存档与最新 pid 不兼容：旧档移到 `save_backup_20261020/`，不要直接删。

---

## 8. 崩溃日志排查

- `logcat -b crash` 没有 FIFA 的 FATAL/SIGSEGV/tombstone。
- dropbox 没有 `data_app_crash`；事件日志没有 FIFA 的 `am_crash`。
- 游戏进程有一段时间存活（pid 1696/1697），后来在点大名单时退回桌面。
- 系统里 `com.android.se`（SecureElementService）每约 20 秒 ANR 一次，被反复 kill/restart；这是系统服务问题，会拖慢/干扰前台游戏。
- `mtx.log` 只有 EA 在线商店目录错误 `10001`，与单机生涯无关。
- 最可能的人为因素：旧存档在最新 DB 下 pid/数据不匹配；已备份旧档并要求新建生涯。
- 若复现：**不要重启游戏**，立刻抓 `adb logcat -d -b crash -t 200`、`dumpsys dropbox --print`、当前界面截图。

---

## 9. 未解问题（不要假装知道）

1. 原版 14 生涯模式实际读取的完整数据源（主库 / New DB / 存档 / OBB）——未定位。
2. 400k 池是否就是生涯球探池——Oberlechner/Dinescu 的 pid/属性对照支持，但未覆盖全部路径。
3. 主库与 New DB 的优先级/使用场景——未完全证明。
4. 位置位写入后的游戏内显示——文件层一致，仍需截图验收。
5. 2 号球衣 bug 的分配函数——静态分析未定位；用户规则：新援能力 < 原 #2 不抢，≥ 原 #2 抢 #2；需 Frida 动态 trace 或存档差分。

---

## 10. 经验/铁律

1. **用户亲眼看到的游戏内容优先于任何文件推断。** 文件里没有，只能说明来源不是那个文件，不能说明游戏里不存在。
2. 发现矛盾先承认用户观察，再查全部数据源；不要用“我查过数据库”去否定用户。
3. 不要把无法证明来源的球员说成“我们自己加的”；也不要用 OBB 姓名池当查重依据。
4. 改库前备份；改完第二份副本 + md5；每次修改立刻更新笔记。
5. 长任务设超时/后台跑；adb 用 `MSYS_NO_PATHCONV=1`。
6. 文件层回读通过 ≠ 游戏内修好；关键结论必须游戏内截图/用户确认。
7. 未知就写未知，不要编机制（生成/重生、读库顺序等）。
8. 不整体替换别人的 mod；只把资源/思路合并进自己的产物。

---

## 11. 关键路径

- 工作目录：`D:\FIFA14\work\scout_real_fifa14\`
  - `base/`：原版主库 + New DB
  - `data/`：候选池、donor、索引、Kaggle
  - `out/`：最终 DB、assignment、report、validation、scout_guide、README
- 脚本：`D:\FIFA14\work\scripts\`
- 本文档：`D:\FIFA14\work\docs\FIFA14_球探全真实池_全量经验_20261020.md`
- 第二份：`D:\FIFA14\modified_copy_20261019\scout_real_fifa14\`
- OBB 原文件：`D:\FIFA14\work\obb_original.bin`（1,386,236,976B）


---

## 12. 最终增补（2026-10-20 晚，以本节为准）

### 12.1 查重规则（用户明确）
- **不能宁可多删**：不知名球员可宽筛；知名球员必须逐个核对，绝不多删。
- 知名标准：历年金球奖前 30/50（2014–2025，140 个不重复姓名）+ 评分 ≥85 + 用户点名球星。
- 处理：
  - 原版两库有精确记录 → 只改潜力，不新增；
  - 用户确认原版开档已有（Lenglet / Lucas Hernández / Bernardo Silva）→ 不新增；
  - 其余知名 → 默认保留，不被 OBB 姓名池一刀切删除；
  - 不知名 → 原版两库姓名 + OBB 姓名池宽筛。
- 核对表：`D:\FIFA14\work\scout_real_fifa14\dataallon_verification.csv`（140 行）。
- 结果：87 人原版库已有、52 人新增池、1 人（Bernardo Silva）用户确认原版已有。

### 12.2 亚洲球员姓名 bug 与 Kim Min-jae
- FC24/26 的 CJK 长名规范化后 key 为空，dedupe 会误合并；已改用拉丁短名。
- Kim Min-jae（sofifa 237086）此前被漏掉，现已强制加入：pid 400584，亚太，CB，潜力 84。
- 金球奖球员若未被选中，用同板块最低评分非强制球员替换，保证必在池中。

### 12.3 最终产物
- 主库 4,141,714B md5 `3a8a4b70420f36e305009f2d02def18c`。
- New DB 4,742,674B md5 `20492d18892da29e99bce4e8be9b2797`。
- 增强 OBB md5 `cc3ba879d7f859439f4f7a1fe5dfe194`（原版 `4207c3ce8b1ca6b7793d7e5de432207f`），大小不变。
- 已推送平板并设备端 md5 核对；旧存档与最新 pid 不兼容，必须新建生涯。

### 12.4 CPU 签约增强（职业模式 OBB 配置）
| 参数 | 原值 | 新值 |
|---|---:|---:|
| MAX_PER_TEAM_BUYS | 3 | 12 |
| PROB_BUYING_PLAYER | 70 | 95 |
| PROB_BUY_FIRST_PLAYER | 30 | 95 |
| SIGNING_CHANCE | 50 | 95 |
| SMALL_TEAM_SIGNING_CHANCE | 80 | 99 |
| PROB_CPU_APPROACH | 6 | 90 |
| PROB_CPU_OFFER | 40 | 95 |
| CHANCE_OF_BOSMAN | 3 | 90 |
| BUYING_PLAYER_RATING_DIF | 10 | 40 |
| RATING_DIFF_FOR_CPU_SCOUT | 10 | 40 |
| MAX_PER_TEAM_SALES | 3 | 12 |
| PROB_SELLING_RANDOM_PLAYER | 30 | 60 |
| MAX_PLAYERS | 30 | 40 |
| IDEAL_NUM_PLAYERS | 23 | 28 |
| STAR_INTEREST_THRESHOLD | 70 | 55 |
| PROB_OF_OFFER_WITHDRAWL | 50 | 10 |
| CPU_BUY_PRICE_RANGE | 40 | 99 |
| CPU_RANDOM_BUY_PRICE_RANGE | 75 | 99 |
| CPU_GOOD_PLAYER_BUY_PRICE_RANGE | 100 | 300 |
| CPU_BAD_PLAYER_BUY_PRICE_RANGE | 50 | 99 |
| TRANSFER_PLAYER_DIF_BUY_MULT | 0.75 | 1.00 |
| WAGE_OFFER_DIVIDER | 15/10 | 05/05 |

- 作用按字段名推断；必须新开生涯实测。若 CPU 转会过猛/破坏平衡，用原版 OBB 回滚。
- 原版 OBB 备份：`D:\FIFA14\work\obb_original.bin`、`D:\FIFA14ackups\original_2013\obb\...`。
