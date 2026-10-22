package com.zcode.jersey;

import android.content.Context;
import java.io.File;

/** Writes diagnostics into the FIFA external data folder (readable via adb or a file manager). */
final class Log {

    private static final String PATH = "/sdcard/Android/data/com.ea.game.fifa14_row/files/app_bridge.log";

    private Log() {}

    static void indexError(Context ctx, Exception e) {
        String msg = "INDEX LOAD FAILED: " + e.getClass().getSimpleName() + ": " + e.getMessage();
        try (java.io.FileWriter w = new java.io.FileWriter(PATH, true)) {
            w.write("[" + System.currentTimeMillis() + "] " + msg + String.valueOf((char) 10));
            java.io.StringWriter sw = new java.io.StringWriter();
            e.printStackTrace(new java.io.PrintWriter(sw));
            w.write(sw.toString());
        } catch (Exception ignored) {}
        try {
            File assets = new File(ctx.getApplicationInfo().sourceDir);
            android.util.Log.e("JerseyApp", msg + " apk=" + assets.length());
        } catch (Exception ignored) {}
    }
}
