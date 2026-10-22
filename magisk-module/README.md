# Magisk 模块：FIFA14 改号自动悬浮

作用：**每次 FIFA14 启动时，自动把改号悬浮按钮显示出来**，不需要先打开「FIFA14 改号」App。按钮只在游戏进程启动时出现一次；你在长按菜单里「退出面板」后不会自动复活，直到下次重新启动游戏。

这是「把改号功能并进游戏体验」的可行方案。为什么不直接改 APK 本体，见文末。

## 前置

- 已安装 `jersey-app/apk/jersey-app.apk`，并在 Magisk 里给它 root 授权。
- Magisk 已启用（本项目实测 Magisk 30.7 / Android 8.1）。
- 游戏包名 `com.ea.game.fifa14_row`；其他版本改 `service.sh` 里的 `PKG`。

## 安装

```bash
python tools/install_module.py --adb adb
```

或手动：

```bash
adb push magisk-module /data/local/tmp/fifa14_jersey_auto
adb shell su -c "mkdir -p /data/adb/modules/fifa14_jersey_auto && cp /data/local/tmp/fifa14_jersey_auto/* /data/adb/modules/fifa14_jersey_auto/ && chmod 755 /data/adb/modules/fifa14_jersey_auto/service.sh"
```

立即生效（不重启）：

```bash
adb shell su -c "nohup sh /data/adb/modules/fifa14_jersey_auto/service.sh >/dev/null 2>&1 &"
```

模块在下次开机时由 Magisk 自动加载。

## 卸载

```bash
adb shell su -c "rm -rf /data/adb/modules/fifa14_jersey_auto /data/local/tmp/fifa14_jersey_auto*"
```

## 为什么没有直接改 APK 本体

调研结论（2026-10）：

1. **签名**：Android 只允许同签名 APK 覆盖安装。任何对 `base.apk` 的修改（加 Activity/Service、改 manifest、合 dex）都必须重新签名，必须卸载原游戏再装修改版。卸载会连同
   `/sdcard/Android/data/com.ea.game.fifa14_row`（生涯存档）和 `Android/obb/...`（1.4 GB OBB）一起删除，风险远大于收益。
2. **UI 没有扩展点**：FIFA14 的界面是 EA 私有的 Apt 编译脚本（OBB 内的 `.apt/.const`），没有公开编译器，无法在球员界面里「加一个按钮」。原生层也没有可供脚本调用的 UI 注册接口。
3. **原生改法**：真正要改只能 patch `libFIFA14.so` 的转会选号逻辑（例如禁止抢 2 号），这需要先定位转会完成时计算号码的函数；该函数尚未定位（现有研究只到 `MGRSetPlayerJerseyNumber` 的 setter），且 patched `.so` 仍受第 1 条签名限制，只能通过 Zygisk 注入，复杂度和稳定性都不可控。

因此采用「Magisk 自动拉起悬浮按钮」：功能与「改本体」等价（进游戏就有改号入口），但不碰 APK 签名、不动 `Android/data`、可随时卸载。