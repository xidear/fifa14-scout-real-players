# 原版 FIFA14 球探全真实球员池 — 构建说明（2026-10-20，10 板块 + 知名球员保护 + CPU 签约增强）

基座：原版 FIFA14 主库 + New DB（**只使用原版 14，不使用其它版本数据**）
工作目录：`D:\FIFA14\work\scout_real_fifa14\`

## 核心内容

- 原版两个库 `400000–416281` 的 **16,282 个假球员全部覆盖为真实职业球员**。
- 主库 72B/行；New DB 76B/行；同 pid 同球员，两库分别写入。
- 1,826 名原版已有球员按 FIFA15–FC26 最高 Overall 改潜力。
- 10 个板块：英格兰、法国、德国、荷兰、意大利、西班牙、欧洲其他、美洲、非洲、亚太。
- 位置按 FC26 真实主位置 + 第一个副位置逐人显式写入。

## 查重规则（按用户要求：不知名可宽筛，知名必须精确）

### 知名球员

- 标准：历年金球奖前 30/50（2014–2025，共 140 个不重复姓名）+ 评分 ≥85 的球员 + 用户点名球星。
- 处理：
  - 原版两个库有**精确记录** → 只改潜力，不新增；
  - 用户确认原版开档已有（Lenglet / Lucas Hernández / Bernardo Silva）→ 不新增；
  - 其余知名球员 → **默认保留**，不被 OBB 姓名池一刀切删除。
- 核对表：`data/ballon_verification.csv`（140 行，逐人状态）。
- 本轮结果：87 人原版库已有、52 人加入新增池、1 人（Bernardo Silva）用户确认原版已有；无遗漏。
- 修正了一个亚洲球员 bug：CJK 长名规范化后 key 为空，会被 dedupe 误合并；已改用拉丁短名，**Kim Min-jae 已加入**（pid 400584，亚太，CB，84）。

### 不知名球员

- 原版两库姓名精确匹配 → 剔除；
- 原版 OBB 姓名池出现过的姓名 → 剔除（宁可多删，不影响知名球员）。

### 用户确认原版已有的三人

`build_candidate_pool.py` 的 `USER_CONFIRMED_EXISTING` 显式排除（含变体）：

- `Clément Nicolas Laurent Lenglet` / `Clément Lenglet`
- `Lucas François Bernard Hernández Pi` / `Lucas Hernández`
- `Bernardo Mota Veiga de Carvalho e Silva` / `Bernardo Mota Carvalho e Silva` / `Bernardo Silva`

真正的原版库重复仍剔除：Marquinhos（PSG）、Fabinho（Monaco）、Xavi、Isco、Diego Costa。

## 位置

- 根因：整块复制 donor 的 `20:72` 会把 donor 的位置一起复制；而游戏**真正显示的位置字段不是** bit179/189，而是 4 位字段：主库 **bit175**、New DB **bit207**（高位在前）。
- 修正：donor 只从同位置组里选（GK/GK；CB/CB；LB/RB/LWB/RWB；CM/CDM/CAM；LM/RM/LW/RW；ST/CF），并在复制后把目标位置写进 **bit175/207**。
- 码表（2026-01-25 用游戏内球员简历逐个核对）：GK0 RB1 CB2 LB3 CDM5 RM7 CM8 LM9 LW10 CAM11 RW13 ST15；LWB→LB、RWB→RB、CF→ST。
- 校验：16,282 人主库与 New DB 的位置字段与目标位置 **0 误差**；游戏内 Raya 已显示 GK。
- 主位置 = FC26 `position`；副位置 = FC26 `alternatePositions` 第一个；Rodri 特例 CDM/CB。
- 位置码：`GK0 SW1 CM14 CAM3 RM30 LM7 RB6 LB15 CB10 CDM22 CF23 ST28 RW29 LW8 LWB16 RWB6`。

## CPU 签约增强（职业模式配置，OBB 内）

原版 OBB 的 `[CAREER]` 配置已改（同长度原地替换，OBB 大小不变）：

| 参数 | 原值 | 新值 | 作用 |
|---|---:|---:|---|
| MAX_PER_TEAM_BUYS | 3 | 12 | 每队每窗最多买入 |
| PROB_BUYING_PLAYER | 70 | 95 | 买人概率 |
| PROB_BUY_FIRST_PLAYER | 30 | 95 | 首个签约概率 |
| SIGNING_CHANCE | 50 | 95 | 签约成功率 |
| SMALL_TEAM_SIGNING_CHANCE | 80 | 99 | 小球队签约率 |
| PROB_CPU_APPROACH | 6 | 90 | CPU 主动接触概率 |
| PROB_CPU_OFFER | 40 | 95 | CPU 报价概率 |
| CHANCE_OF_BOSMAN | 3 | 90 | 自由球员/博斯曼签约概率 |
| BUYING_PLAYER_RATING_DIF | 10 | 40 | 允许买低于球队平均的年轻球员 |
| RATING_DIFF_FOR_CPU_SCOUT | 10 | 40 | CPU 球探评分差 |
| MAX_PER_TEAM_SALES | 3 | 12 | 每队最多卖出（腾位置） |
| PROB_SELLING_RANDOM_PLAYER | 30 | 60 | 随机卖人概率 |
| MAX_PLAYERS | 30 | 40 | 球队最大人数 |
| IDEAL_NUM_PLAYERS | 23 | 28 | 理想人数 |
| STAR_INTEREST_THRESHOLD | 70 | 55 | 对非顶级球员也感兴趣 |
| PROB_OF_OFFER_WITHDRAWL | 50 | 10 | 少撤回报价 |
| CPU_BUY_PRICE_RANGE | 40 | 99 | 买价上限 |
| CPU_RANDOM_BUY_PRICE_RANGE | 75 | 99 | 随机买价上限 |
| CPU_GOOD_PLAYER_BUY_PRICE_RANGE | 100 | 300 | 好球员买价上限 |
| CPU_BAD_PLAYER_BUY_PRICE_RANGE | 50 | 99 | 一般球员买价上限 |
| TRANSFER_PLAYER_DIF_BUY_MULT | 0.75 | 1.00 | 评分差买入系数 |
| WAGE_OFFER_DIVIDER | 15/10 | 5/5 | 工资报价更慷慨 |

> 这些是按字段名推断的作用；必须新开生涯实测。若 CPU 转会过猛/破坏平衡，可用原始 OBB 回滚。

## 关键球员 pid（最终版）

| 球员 | pid | 板块 | 位置 | 潜力 |
|---|---:|---|---|---:|
| Rodri | 407184 | 西班牙 | CDM/CB | 90 |
| Pedri | 407615 | 西班牙 | CM/CDM | 89 |
| Lamine Yamal | 407965 | 西班牙 | RM/RW | 89 |
| Kim Min-jae | 400584 | 亚太 | CB | 84 |
| Mbappé | 412577 | 法国 | ST/LW | 91 |
| Bellingham | 414319 | 英格兰 | CAM/CM | 90 |
| Saka | 414320 | 英格兰 | RW/RM | 88 |
| Foden | 414321 | 英格兰 | RW/CM | 88 |
| Vinícius Júnior | 404501 | 美洲 | LW/ST | 89 |
| Raphinha | 402364 | 美洲 | LM/LW | 89 |
| Haaland | 409614 | 欧洲其他 | ST | 91 |

## 文件与 md5

- `out/main_fifa.db` → 平板 `data/cmn/fifa.db`，md5 `a74a7e8acfd93b71068a96d094d8c32f`（4,141,714B）
- `out/newdb_fifa.db` → 平板 `data/cmn/New DB/fifa.db`，md5 `ca6bf1280bd559c6613e581c53269903`（4,742,674B）
- 增强 OBB → 平板 `Android/obb/com.ea.game.fifa14_row/main.136...obb`，md5 `cc3ba879d7f859439f4f7a1fe5dfe194`（原版 `4207c3ce8b1ca6b7793d7e5de432207f`）
- `data/ballon_verification.csv`：140 名金球奖球员逐人核对
- `out/assignment.csv`、`out/report.json`、`out/validation.json`、`out/scout_guide.md/csv`

- 按年份/板块总表：`out/FIFA14_球探球员_按年份板块.xlsx`

## 校验

- 16,282 条逐条回读：姓名/生日/潜力/国籍/位置 0 错误；主库与 New DB 位置位一致。
- 字节 diff 只落在 400k 记录、1,826 个潜力字节、追加字符串；表头/行数不变。
- 旧存档与最新 DB 的 pid 不一致，**必须新建生涯**；旧档已备份到平板 `save_backup_20261020/`。