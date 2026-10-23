# FIFA14 改号 App（生涯模式悬浮改号）

在原版 FIFA14 生涯模式里给球员改球衣号。不修改游戏 APK、不改数据库，直接改生涯存档；号码被占用时与对方交换。

## 功能

- 屏幕上只有一个 46dp 的圆形「改」按钮，点开才是面板。
- 面板显示当前球队名单：**按号码排序**，每行显示原号码与球员名。
- 点球员后面的「改」→ 输入 1–99 → 确定；被占用时自动交换两人号码。
- 改完列表自动刷新；「收起」只留小按钮，比赛中不挡画面。
- 长按小按钮：「移除按钮」（通知栏可恢复）/「恢复改号前的备份」/「退出面板」。
- 首次写入前自动把原存档备份为 `<存档>.bak_jersey`。
- 球队可切换（按名称筛选，默认曼城 id 10）。

## 环境

- 已 root（Magisk 授权本应用）。
- 允许「显示在其他应用上层」（App 首次进入会自己申请）。
- 游戏为原版 FIFA14，包名 `com.ea.game.fifa14_row`，存档在
  `/sdcard/Android/data/com.ea.game.fifa14_row/SAVECAREER.*`。
- 实测：小米平板 4（Android 8.1 / crDroid 6.12）、Magisk 30.7。

## 安装

```bash
python tools/install_app.py --adb adb
# 或手动：adb install -r jersey-app/apk/jersey-app.apk
```

安装后打开「FIFA14 改号」：
- 确认三行状态都是 `已授权 / 运行中 / 已开启`；
- 点「开启改号面板」。

## 使用

1. 先进入 FIFA14 的生涯「读取选项」界面（还没进生涯）。
2. 屏幕左下角出现「改」按钮，点开。
3. 默认球队是曼城（id 10）。点「球队」可按名称筛选切换，例如搜 `Manchester`。
4. 在列表里找到球员，点右侧「改」，输入新号码，确定。
   - 号码被别人占用：两人号码互换，提示「已与 XXX 交换 a↔b」。
5. 点「收起」，面板消失，只剩小按钮；长按小按钮可把按钮也移除。
6. 回到游戏，进入生涯，号码已更新。

> 如果改号时生涯已经载入，需要退出到「读取选项」再重新进入，游戏才会重新读存档。

## 原理（简要）

存档里的 roster 表是 16 字节一条：`team id / player id / flags / alt`，球衣号在 flags 低字节：

```
jersey = ((flags & 0xFF) >> 1) + 1
```

改一个号码只改 1 个字节。写回时 App 会继承原文件的属主（`media_rw:u0_aXXXXX` / `660`），并**重算整档尾部 CRC**——最后 4 字节是 `[0, len-4)` 的 CRC-32（poly `0x04C11DB7`、非反射、init/xorout `0xFFFFFFFF`）。不重算会让游戏提示「无游戏存档可用」。细节见 [`../docs/save_format.md`](../docs/save_format.md)。

## 源码结构

```
src/AndroidManifest.xml
src/java/com/zcode/jersey/
  MainActivity.java    启动页、状态、开启/移除
  PanelService.java    前台服务：悬浮按钮、面板、球队选择、号码弹窗
  SaveBackend.java     存档读写：发现球队块、改/换号码、属主保持、自动备份
  PlayerIndex.java     读取 assets/fifa.db（pid→姓名、球队→名单）
  RootUtil.java        su 封装
  RootBridge.java      PC 桥接回退（可选）
src/assets/fifa.db     856 KB 索引：32,564 名球员、631 支球队
apk/jersey-app.apk     已签名可安装包
```

## 重新编译

不需要 Gradle。安装 Android SDK（build-tools + platform android-35）与 JDK 17 后：

```bash
set ANDROID_HOME=C:\Users\you\AppData\Local\Android\Sdk
set KEYSTORE=C:\path\my.keystore
set KEY_ALIAS=mykey
set KEY_PASS=mypass
python jersey-app/build_apk.py
```

Windows 下也可以直接用 Git Bash。产物在 `jersey-app/out/jersey-app.apk`。

## 已知限制

- 只实测过 `com.ea.game.fifa14_row` 与原版存档；其他版本需改 `SaveBackend.DIR`。
- 名字来自随包的 `assets/fifa.db`（由球探球员池生成）；未收录的 pid 会显示 `pid N`。
- 号码范围 1–99。
- 存档写入在后台线程完成，界面会提示「重新读档后生效」。

## 免责

仅供个人离线使用。改存档前请自行备份；因使用本工具造成的存档损坏/丢失由使用者自行承担。