package com.zcode.jersey;

import android.content.Context;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Append-only diagnostic log.
 *
 * Every user action (button, drag, search, number change) and every internal step
 * (root command, save read, checksum, write, read-back verification) is written here
 * with a timestamp, thread name and result. The file lives in the app's own external
 * files dir so it can be pulled with adb or opened by any file manager:
 *
 *     /sdcard/Android/data/com.zcode.jersey/files/jersey.log
 */
final class Log {

    private static final Object LOCK = new Object();
    private static final long MAX_BYTES = 2 * 1024 * 1024;
    private static final SimpleDateFormat FMT =
            new SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US);

    private static File file;
    private static String session = "";

    private Log() {}

    static synchronized void init(Context ctx) {
        if (file != null) return;
        File dir = ctx.getExternalFilesDir(null);
        if (dir == null) dir = ctx.getFilesDir();
        if (dir != null && !dir.exists()) dir.mkdirs();
        File f = new File(dir, "jersey.log");
        if (f.length() > MAX_BYTES) {
            File old = new File(dir, "jersey.log.1");
            if (old.exists()) old.delete();
            f.renameTo(old);
        }
        file = f;
        session = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        i("================ session " + session + " ================");
        i("app start: android " + android.os.Build.VERSION.SDK_INT
                + " (" + android.os.Build.VERSION.RELEASE + ") device "
                + android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL);
        i("log file: " + path());
    }

    static String path() {
        return file == null ? "(not initialised)" : file.getAbsolutePath();
    }

    static void i(String msg) { write("I", msg, null); }

    static void w(String msg) { write("W", msg, null); }

    static void e(String msg) { write("E", msg, null); }

    static void e(String msg, Throwable t) { write("E", msg, t); }

    /** Kept for older call sites. */
    static void write(Context ctx, String msg) {
        init(ctx);
        i(msg);
    }

    /** Kept for older call sites. */
    static void indexError(Context ctx, Exception ex) {
        init(ctx);
        e("index load failed: " + ex.getClass().getSimpleName() + ": " + ex.getMessage(), ex);
    }

    private static void write(String level, String msg, Throwable t) {
        String line = FMT.format(new Date()) + " " + level + " [" + Thread.currentThread().getName()
                + "] " + msg;
        if (level.equals("E")) android.util.Log.e("JerseyApp", msg, t);
        else android.util.Log.i("JerseyApp", msg);
        synchronized (LOCK) {
            if (file == null) return;
            FileWriter w = null;
            try {
                w = new FileWriter(file, true);
                w.write(line);
                w.write('\n');
                if (t != null) {
                    StringWriter sw = new StringWriter();
                    t.printStackTrace(new PrintWriter(sw));
                    w.write(sw.toString());
                }
                w.flush();
            } catch (Exception ignored) {
            } finally {
                if (w != null) try { w.close(); } catch (Exception ignored) {}
            }
        }
    }
}