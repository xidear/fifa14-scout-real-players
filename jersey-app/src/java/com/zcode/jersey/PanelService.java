package com.zcode.jersey;

import android.app.AlertDialog;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Floating jersey editor that edits the career save file (SAVECAREER.*).
 *
 * The save is read/written through root; the number lives in the flags byte of the
 * 16-byte roster row. The floating button can be hidden or removed entirely so nothing
 * stays on screen during a match.
 */
public class PanelService extends Service {

    public static final String ACTION_SHOW = "com.zcode.jersey.SHOW";
    public static final String ACTION_START = "com.zcode.jersey.START";
    public static final String ACTION_TOGGLE = "com.zcode.jersey.TOGGLE";
    public static final String ACTION_REMOVE = "com.zcode.jersey.REMOVE";
    public static final String ACTION_STOP = "com.zcode.jersey.STOP";
    private static final String CH = "jersey_panel";
    private static final int NOTI = 4711;
    private static final String PREFS = "jersey";
    private static final String KEY_TEAM = "team_id";

    private static volatile boolean running = false;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private WindowManager wm;
    private Button fab;
    private LinearLayout panelRoot;
    private WindowManager.LayoutParams fabLp, panelLp;
    private boolean open = false;

    private TextView statusView;
    private LinearLayout listView;
    private List<SaveBackend.Block> blocks = new ArrayList<>();
    private SaveBackend.Block teamBlock;
    private byte[] saveData;
    private String savePath;

    public static boolean isRunning() { return running; }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public void onCreate() {
        super.onCreate();
        running = true;
        startForegroundCompat();
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        makeFab();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String a = intent == null ? null : intent.getAction();
        if (ACTION_REMOVE.equals(a)) {
            removeFab();
        } else if (ACTION_STOP.equals(a)) {
            stopSelf();
        } else if (ACTION_START.equals(a)) {
            if (fab == null) makeFab();
        } else if (ACTION_SHOW.equals(a) || ACTION_TOGGLE.equals(a)) {
            if (fab == null) makeFab();
            if (!open) showPanel(); else if (ACTION_TOGGLE.equals(a)) hidePanel();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        running = false;
        try { if (panelRoot != null) wm.removeView(panelRoot); } catch (Exception ignored) {}
        try { if (fab != null) wm.removeView(fab); } catch (Exception ignored) {}
        super.onDestroy();
    }

    // ------------------------------------------------------------ notification
    private void startForegroundCompat() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CH, "改号面板",
                    NotificationManager.IMPORTANCE_LOW));
        }
        int pf = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent toggle = PendingIntent.getService(this, 1,
                new Intent(this, PanelService.class).setAction(ACTION_TOGGLE),
                PendingIntent.FLAG_UPDATE_CURRENT | pf);
        PendingIntent stop = PendingIntent.getService(this, 2,
                new Intent(this, PanelService.class).setAction(ACTION_STOP),
                PendingIntent.FLAG_UPDATE_CURRENT | pf);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CH) : new Notification.Builder(this);
        b.setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("改号面板")
                .setContentText("点这里显示/隐藏面板")
                .setOngoing(true)
                .setContentIntent(toggle)
                .addAction(new Notification.Action.Builder(null, "显示/隐藏", toggle).build())
                .addAction(new Notification.Action.Builder(null, "退出", stop).build());
        startForeground(NOTI, b.build());
    }

    // ------------------------------------------------------------ floating button
    private WindowManager.LayoutParams overlayLp() {
        int type = Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT, type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        return lp;
    }

    private int dp(float v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void makeFab() {
        fab = new Button(this);
        fab.setText("改");
        fab.setTextSize(15);
        fab.setTextColor(Color.WHITE);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xB31A1A1A);
        bg.setCornerRadius(dp(24));
        bg.setStroke(dp(2), 0xFF4CAF50);
        fab.setBackground(bg);
        fabLp = overlayLp();
        fabLp.width = dp(46);
        fabLp.height = dp(46);
        fabLp.x = dp(6);
        fabLp.y = dp(300);
        fab.setOnClickListener(v -> { if (open) hidePanel(); else showPanel(); });
        fab.setOnLongClickListener(v -> { fabMenu(); return true; });
        try { wm.addView(fab, fabLp); } catch (Exception e) { toast("浮窗被拒绝: " + e); }
    }

    private void fabMenu() {
        LinearLayout box = newModalBox();
        TextView t = new TextView(this);
        t.setText("改号按钮");
        t.setTextColor(Color.WHITE);
        t.setTextSize(15);
        t.setPadding(dp(4), 0, 0, dp(8));
        box.addView(t);
        box.addView(btn("移除按钮（通知里可恢复）", v -> { closeModal(); removeFab(); }));
        box.addView(btn("恢复改号前的备份", v -> {
            closeModal();
            new Thread(() -> {
                String p = SaveBackend.newestPath();
                boolean ok = p != null && SaveBackend.restoreBackup(p);
                ui.post(() -> {
                    toast(ok ? "已恢复备份；重新读档后生效" : "没有找到备份");
                    if (ok) loadSave();
                });
            }).start();
        }));
        box.addView(btn("退出面板", v -> { closeModal(); stopSelf(); }));
        box.addView(btn("取消", v -> closeModal()));
        showModal(box);
    }

    private void removeFab() {
        hidePanel();
        if (fab != null) {
            try { wm.removeView(fab); } catch (Exception ignored) {}
            fab = null;
        }
        toast("按钮已移除；通知栏可随时恢复");
    }

    private void showPanel() {
        if (panelRoot == null) buildPanel();
        open = true;
        panelRoot.setVisibility(View.VISIBLE);
        if (fab != null) fab.setAlpha(0.15f);
        loadSave();
    }

    private void hidePanel() {
        closeModal();
        open = false;
        if (panelRoot != null) {
            try { wm.removeView(panelRoot); } catch (Exception ignored) {}
            panelRoot = null;
        }
        if (fab != null) fab.setAlpha(1f);
    }

    private Button btn(String text, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(11);
        b.setOnClickListener(l);
        return b;
    }

    private void buildPanel() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xF0191919);
        bg.setCornerRadius(dp(10));
        bg.setStroke(dp(1), 0xFF4CAF50);
        root.setBackground(bg);
        root.setPadding(dp(10), dp(8), dp(10), dp(8));

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = new TextView(this);
        title.setText("改号");
        title.setTextColor(Color.WHITE);
        title.setTextSize(16);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setPadding(dp(4), 0, dp(8), 0);
        head.addView(title);
        head.addView(btn("球队", v -> pickTeam()));
        head.addView(btn("刷新", v -> loadSave()));
        head.addView(btn("收起", v -> hidePanel()));
        root.addView(head);

        statusView = new TextView(this);
        statusView.setTextColor(0xFFB0BEC5);
        statusView.setTextSize(11);
        statusView.setPadding(dp(4), dp(2), dp(4), dp(4));
        root.addView(statusView);

        ScrollView sc = new ScrollView(this);
        listView = new LinearLayout(this);
        listView.setOrientation(LinearLayout.VERTICAL);
        sc.addView(listView);
        root.addView(sc, new LinearLayout.LayoutParams(dp(320), dp(430)));

        panelLp = overlayLp();
        panelLp.width = WindowManager.LayoutParams.WRAP_CONTENT;
        panelLp.flags = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL;
        panelLp.x = dp(56);
        panelLp.y = dp(96);
        panelRoot = root;
        try { wm.addView(panelRoot, panelLp); }
        catch (Exception e) { toast("面板显示失败: " + e); panelRoot = null; }
    }

    // ------------------------------------------------------------ data
    private SharedPreferences prefs() { return getSharedPreferences(PREFS, MODE_PRIVATE); }

    private void loadSave() {
        if (statusView != null) statusView.setText("读取存档…");
        final int team = prefs().getInt(KEY_TEAM, 10);
        new Thread(() -> {
            String path = SaveBackend.newestPath();
            if (path == null) { ui.post(() -> statusView.setText("找不到 SAVECAREER 存档")); return; }
            byte[] data = SaveBackend.read(this, path);
            if (data == null) {
                ui.post(() -> statusView.setText("读取失败（需要 root）"));
                return;
            }
            List<SaveBackend.Block> bs = SaveBackend.parse(data);
            SaveBackend.Block tb = SaveBackend.teamBlock(bs, team);
            ui.post(() -> {
                savePath = path;
                saveData = data;
                blocks = bs;
                teamBlock = tb;
                render();
            });
        }).start();
    }

    private void pickTeam() {
        PlayerIndex ix = PlayerIndex.get(this);
        if (ix == null) { toast("索引未加载"); return; }
        final int current = prefs().getInt(KEY_TEAM, 10);

        LinearLayout box = newModalBox();
        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = new TextView(this);
        title.setText("选择球队（当前 id " + current + "）");
        title.setTextColor(Color.WHITE);
        title.setTextSize(15);
        title.setPadding(dp(4), 0, dp(4), dp(6));
        head.addView(title, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        head.addView(btn("关闭", v -> closeModal()));
        box.addView(head);

        EditText filter = new EditText(this);
        filter.setHint("筛选，例如 Manchester");
        filter.setSingleLine(true);
        filter.setTextColor(Color.WHITE);
        filter.setHintTextColor(0xFF9E9E9E);
        box.addView(filter);

        ScrollView sc = new ScrollView(this);
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        sc.addView(list);
        box.addView(sc, new LinearLayout.LayoutParams(dp(320), dp(420)));

        final List<PlayerIndex.Team> all = new ArrayList<>(ix.teams());
        all.sort((a, b) -> a.name.compareToIgnoreCase(b.name));
        Runnable fill = () -> {
            list.removeAllViews();
            String q = filter.getText().toString().trim().toLowerCase();
            int shown = 0;
            for (PlayerIndex.Team t : all) {
                if (!q.isEmpty() && !t.name.toLowerCase().contains(q)) continue;
                Button b = btn(t.name + "  #" + t.id, v -> {
                    prefs().edit().putInt(KEY_TEAM, t.id).apply();
                    closeModal();
                    toast("已选 " + t.name + " (id " + t.id + ")");
                    loadSave();
                });
                if (t.id == current) b.setText("▶ " + t.name + "  #" + t.id);
                list.addView(b);
                if (++shown >= 40) break;
            }
            if (shown == 0) {
                TextView none = new TextView(this);
                none.setText("没有匹配的球队");
                none.setTextColor(0xFFB0BEC5);
                none.setPadding(dp(6), dp(8), 0, 0);
                list.addView(none);
            }
        };
        filter.addTextChangedListener(new android.text.TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
            public void onTextChanged(CharSequence s, int a, int b, int c) {}
            public void afterTextChanged(android.text.Editable s) { fill.run(); }
        });
        fill.run();

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.addView(btn("关闭", v -> closeModal()));
        box.addView(bar);
        showModal(box);
        filter.requestFocus();
    }

    private void render() {
        if (listView == null) return;
        listView.removeAllViews();
        PlayerIndex ix = PlayerIndex.get(this);
        if (ix == null) {
            if (statusView != null) statusView.setText("球员索引加载失败：assets/fifa.db 读取异常");
            return;
        }
        if (teamBlock == null) {
            if (statusView != null) {
                statusView.setText("存档里有 " + blocks.size()
                        + " 段名单，但没有球队 " + prefs().getInt(KEY_TEAM, 10) + "；点“球队”选择");
            }
            return;
        }
        List<SaveBackend.Row> rows = new ArrayList<>(teamBlock.list);
        rows.sort(Comparator.comparingInt(SaveBackend.Row::jersey));
        if (statusView != null) {
            statusView.setText("队 " + teamBlock.team + " · " + rows.size() + " 人 · "
                    + (savePath == null ? "" : new java.io.File(savePath).getName()));
        }
        for (SaveBackend.Row r : rows) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            TextView tv = new TextView(this);
            tv.setText(String.format("#%-3d %s", r.jersey(), ix.name(r.pid)));
            tv.setTextColor(Color.WHITE);
            tv.setTextSize(13);
            tv.setPadding(dp(4), dp(9), dp(4), dp(9));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
            row.addView(tv, lp);
            row.addView(btn("改", v -> askNumber(r)));
            listView.addView(row);
        }
    }

    private void askNumber(SaveBackend.Row row) {
        PlayerIndex ix0 = PlayerIndex.get(this);
        String nm0 = ix0 == null ? ("pid " + row.pid) : ix0.name(row.pid);

        LinearLayout box = newModalBox();
        TextView title = new TextView(this);
        title.setText("新号码 · " + nm0 + "（当前 #" + row.jersey() + "）");
        title.setTextColor(Color.WHITE);
        title.setTextSize(15);
        title.setPadding(dp(4), 0, 0, dp(6));
        box.addView(title);

        EditText et = new EditText(this);
        et.setInputType(InputType.TYPE_CLASS_NUMBER);
        et.setText(String.valueOf(row.jersey()));
        et.selectAll();
        et.setTextColor(Color.WHITE);
        et.setTextSize(22);
        box.addView(et);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.addView(btn("取消", v -> closeModal()));
        bar.addView(btn("确定", v -> {
            int want;
            try { want = Integer.parseInt(et.getText().toString().trim()); }
            catch (Exception e) { toast("号码无效"); return; }
            if (want < 1 || want > 99) { toast("号码 1-99"); return; }
            if (want == row.jersey()) { closeModal(); return; }
            closeModal();
            apply(row, want);
        }));
        box.addView(bar);

        showModalIme(box);
        et.requestFocus();
        et.postDelayed(() -> {
            InputMethodManager im = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (im != null) im.showSoftInput(et, InputMethodManager.SHOW_IMPLICIT);
        }, 250);
    }

    private void apply(SaveBackend.Row row, int want) {
        if (row.jersey() == want) return;
        SaveBackend.Row found = null;
        for (SaveBackend.Row r : teamBlock.list) if (r.jersey() == want) found = r;
        final SaveBackend.Row owner = found;
        final int old = row.jersey();
        SaveBackend.setJersey(saveData, row.offset, want);
        if (owner != null) SaveBackend.setJersey(saveData, owner.offset, old);
        new Thread(() -> {
            boolean ok = SaveBackend.write(this, savePath, saveData);
            PlayerIndex ix = PlayerIndex.get(this);
            String ownerName = owner == null ? "" : (ix == null ? ("pid " + owner.pid) : ix.name(owner.pid));
            ui.post(() -> {
                String msg = ok
                        ? (owner != null
                           ? ("已与 " + ownerName + " 交换 " + old + "↔" + want)
                           : ("#" + want + " 已写入存档"))
                        : "写入失败（需要 root）";
                toast(msg + (ok ? "；重新读档后生效" : ""));
                loadSave();
            });
        }).start();
    }

    // ------------------------------------------------------------ overlay dialogs
    private LinearLayout modal;

    /** Service context cannot show an AlertDialog, so every dialog is an overlay view. */
    private LinearLayout newModalBox() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xFF202020);
        bg.setCornerRadius(dp(10));
        bg.setStroke(dp(1), 0xFF4CAF50);
        box.setBackground(bg);
        box.setPadding(dp(12), dp(10), dp(12), dp(10));
        return box;
    }

    private void closeModal() {
        if (modal != null) {
            try { wm.removeView(modal); } catch (Exception ignored) {}
            modal = null;
        }
    }

    private void showModal(LinearLayout box) { showModal(box, false); }

    private void showModalIme(LinearLayout box) { showModal(box, true); }

    private void showModal(LinearLayout box, boolean withKeyboard) {
        closeModal();
        WindowManager.LayoutParams lp = overlayLp();
        lp.width = dp(340);
        lp.height = WindowManager.LayoutParams.WRAP_CONTENT;
        lp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        lp.y = dp(56);
        lp.flags = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN;
        lp.softInputMode = withKeyboard
                ? WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE
                : WindowManager.LayoutParams.SOFT_INPUT_STATE_HIDDEN;
        modal = box;
        try { wm.addView(modal, lp); }
        catch (Exception e) { toast("弹窗失败: " + e); modal = null; }
    }

    private void toast(String s) {
        ui.post(() -> Toast.makeText(this, s, Toast.LENGTH_SHORT).show());
    }
}