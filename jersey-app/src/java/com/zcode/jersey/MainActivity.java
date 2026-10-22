package com.zcode.jersey;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

/** Launcher: one button to start the floating panel, plus a short status line. */
public class MainActivity extends Activity {

    private static final int REQ_OVERLAY = 1001;
    private TextView status;
    private Button start;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);
        status = findViewById(R.id.status);
        start = findViewById(R.id.start);
        start.setOnClickListener(v -> go());
        findViewById(R.id.remove).setOnClickListener(v -> {
            startService(new Intent(this, PanelService.class).setAction(PanelService.ACTION_REMOVE));
            status.postDelayed(this::refreshStatus, 300);
            Toast.makeText(this, "已从屏幕移除按钮（通知栏仍可恢复）", Toast.LENGTH_SHORT).show();
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    private void refreshStatus() {
        boolean root = RootUtil.hasRoot();
        if (Build.VERSION.SDK_INT >= 26 && !Settings.canDrawOverlays(this)) {
            try {
                startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName())), REQ_OVERLAY);
            } catch (Exception ignored) {}
        }
        int pid = RootUtil.fifaPid();
        StringBuilder sb = new StringBuilder();
        sb.append(root ? "root: 已授权\n" : "root: 未授权（请在 Magisk 里允许本应用）\n");
        sb.append(pid > 0 ? ("FIFA: 运行中 (pid " + pid + ")\n") : "FIFA: 未运行\n");
        sb.append(PanelService.isRunning() ? "面板: 已开启" : "面板: 未开启");
        status.setText(sb.toString());
        start.setText(PanelService.isRunning() ? "面板已开启（点此重新打开）" : "开启改号面板");
    }

    private void go() {
        if (!RootUtil.hasRoot()) {
            Toast.makeText(this, "需要 root：Magisk → 超级用户 里给本应用授权（或插电脑运行 root_bridge.py）",
                    Toast.LENGTH_LONG).show();
            return;
        }
        if (Build.VERSION.SDK_INT >= 26 && !Settings.canDrawOverlays(this)) {
            try {
                startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName())), REQ_OVERLAY);
            } catch (Exception e) {
                startPanel();
            }
            return;
        }
        startPanel();
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_OVERLAY) startPanel();
    }

    private void startPanel() {
        try {
            Intent s = new Intent(this, PanelService.class).setAction(PanelService.ACTION_SHOW);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(s); else startService(s);
            Toast.makeText(this, "面板已开启：回到游戏，左侧会出现“改”按钮", Toast.LENGTH_LONG).show();
            refreshStatus();
            status.postDelayed(this::refreshStatus, 800);
        } catch (Exception e) {
            Toast.makeText(this, "启动失败: " + e, Toast.LENGTH_LONG).show();
        }
    }
}