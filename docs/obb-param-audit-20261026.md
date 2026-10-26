# OBB `[CAREER]` 参数审计（2026-10-26）

对比对象：

- 原版 `D:/FIFA14/work/obb_original.bin`，md5 `4207c3ce8b1ca6b7793d7e5de432207f`
- 平板上的 v2 `modified_copy_20261025/main.136...obb`，md5 `2eea673ac58cdb1fb35c60ecba74dfa3`
- 本次 v3 `modified_copy_20261026/main.136...obb`，md5 `ec2cd8b36448188c575f2a98a198fdda`

三个文件**字节数完全相同**（1,386,236,976），差异只出现在
`0x371984B4` – `0x37198CA4` 这一段文本 INI 里（`[CAREER]` 段，键名顺序 805 个全一致）。
没有改过任何数据库、姓名、球员属性。

## 逐键对照

| 键 | 原版 | v2（已装过平板） | v3（2026-10-26 已推） | 作用 |
|---|---|---|---|---|
| `RATING_DIFF_FOR_CPU_SCOUT` | 10 | 40 | 40 | CPU 球探跨多少评分差去挖人 |
| `MAX_PER_TEAM_SALES` | 3 | 12 | 12 | 每队每窗最多卖几人 |
| `PROB_SELLING_RANDOM_PLAYER` | 30 | 60 | 60 | 随机卖出球员的概率 |
| `MAX_PER_TEAM_BUYS` | 3 | 12 | 12 | 每队每窗最多买几人 |
| `PROB_BUYING_PLAYER` | 70 | 95 | 95 | CPU 买人动作的触发概率 |
| `SMALL_TEAM_SIGNING_CHANCE` | 80 | 99 | 99 | 小球队签约成功率 |
| `SIGNING_CHANCE` | 50 | 95 | 95 | 签约成功率 |
| `PROB_CPU_APPROACH` | 6 | 90 | 90 | CPU 主动接触球员的概率 |
| `PROB_CPU_OFFER` | 40 | 95 | 95 | CPU 出价的概率 |
| `CHANCE_OF_BOSMAN` | 3 | 90 | 90 | 免签（博斯曼）概率 |
| `WAGE_OFFER_DIVIDER` | 10 | 05 | 05 | 工资报价除数（越小工资越高） |
| `WAGE_OFFER_DIVIDER`（第二处） | 15 | 05 | 05 | 同上，另一调用点 |
| `PROB_OF_OFFER_WITHDRAWL` | 50 | 10 | 10 | 撤回报价的概率 |
| **`CPU_BUY_PRICE_RANGE`** | **40** | **99** | **40** | **CPU 买普通球员的溢价上限** |
| **`CPU_RANDOM_BUY_PRICE_RANGE`** | **75** | **99** | **75** | **CPU 随机买人的溢价上限** |
| **`CPU_GOOD_PLAYER_BUY_PRICE_RANGE`** | **100** | **300** | **100** | **CPU 买好球员的溢价上限** |
| **`CPU_BAD_PLAYER_BUY_PRICE_RANGE`** | **50** | **99** | **50** | **CPU 买差球员的溢价上限** |

v3 = v2 回退最后四行（价格类），共 **13 个键**仍与原版不同，其余 792 个键、以及整份 OBB 的
其它部分与原版逐字节相同。

## 早期改过、后来已回原版的键（v2/v3 里都是原版值）

`IDEAL_NUM_PLAYERS` 23、`MAX_PLAYERS` 30、`STAR_INTEREST_THRESHOLD` 70、
`TRANSFER_PLAYER_DIF_BUY_MULT` 0.75、`BUYING_PLAYER_RATING_DIF` 10、
`PROB_BUY_FIRST_PLAYER` 30、`BID_VARIATION_DIVIDER_LISTED` 39、
`BID_VARIATION_DIVIDER_POACHED` 20、`FOR_LOAN_DIVIDER` 2。

## `libFIFA14.so` 里到底认不认这些键

`work/libFIFA14_live.so`（18,187,340 B）字符串统计：

- 上表 17 行对应的键名都存在（1–2 次），说明引擎确实读它们；
- `FOR_LOAN_DIVIDER` **0 次** → 改了也是空转；
- `SIGNING_CHANCE`、`WAGE_OFFER_DIVIDER`、四个 `CPU_*_BUY_PRICE_RANGE`、
  `TRANSFER_MIN_TEAM_SIZE` 各出现 **2 次**（两个调用点共用同名键）。

## 结论

“未挂牌球员报 1.4 倍还被嫌弃”最可能的原因是四个 `CPU_*_BUY_PRICE_RANGE`
（尤其好球员 100→300、普通 40→99）加上 `PROB_CPU_APPROACH 6→90`：
CPU 俱乐部敢出 2–3 倍身价抢人，卖方期望被抬高，人类的 1.41 倍只值一半满意度。
v3 已把这四个价格键回原版，保留“球员流动”类参数。

若 v3 下报价仍被拒，则下一个怀疑对象是竞争类参数
（`PROB_CPU_APPROACH` / `PROB_CPU_OFFER` / `RATING_DIFF_FOR_CPU_SCOUT`），
需要再出一版只回退这三项的 OBB 做 A/B。