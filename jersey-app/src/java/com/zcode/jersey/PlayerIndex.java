package com.zcode.jersey;

import android.content.Context;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Player / team index bundled as assets/fifa.db (little endian).
 *
 *   u32 magic 0x4A523034, u32 playerCount
 *   playerCount x { u32 pid, u16 nameLen, name }
 *   u32 teamCount
 *   teamCount x { u32 teamId, u32 n, u16 nameLen, name, n x { u32 pid, u32 jersey } }
 *   u32 conflictCount, conflictCount x { u32 teamId, u32 jersey }
 */
public final class PlayerIndex {

    private static PlayerIndex INSTANCE;

    public static final class Team {
        public int id;
        public String name;
        public int[] pids;
        public int[] jerseys;

        public int size() { return pids.length; }
    }

    private final Map<Integer, String> pidName = new HashMap<>();
    private final List<Team> teamList = new ArrayList<>();
    private final int[] sortedPids;

    private PlayerIndex(Context ctx) throws IOException {
        InputStream in = ctx.getAssets().open("fifa.db", android.content.res.AssetManager.ACCESS_STREAMING);
        DataInputStream d = new DataInputStream(new java.io.BufferedInputStream(in, 1 << 16));
        if (le32(d) != 0x4A523034) throw new IOException("bad index magic");
        int n = le32(d);
        int[] pids = new int[n];
        for (int i = 0; i < n; i++) {
            pids[i] = le32(d);
            int len = le16(d);
            byte[] b = new byte[len];
            d.readFully(b);
            pidName.put(pids[i], new String(b, "UTF-8"));
        }
        int tn = le32(d);
        for (int i = 0; i < tn; i++) {
            Team t = new Team();
            t.id = le32(d);
            int cnt = le32(d);
            int len = le16(d);
            byte[] nb = new byte[len];
            d.readFully(nb);
            t.name = new String(nb, "UTF-8");
            t.pids = new int[cnt];
            t.jerseys = new int[cnt];
            for (int k = 0; k < cnt; k++) {
                t.pids[k] = le32(d);
                t.jerseys[k] = le32(d);
            }
            if (!t.name.isEmpty()) teamList.add(t);
        }
        int cn = le32(d);
        for (int i = 0; i < cn; i++) { le32(d); le32(d); }
        d.close();
        java.util.Collections.sort(teamList, (a, b) -> a.name.compareToIgnoreCase(b.name));
        sortedPids = pids;
        java.util.Arrays.sort(sortedPids);
    }

    public static synchronized PlayerIndex get(Context ctx) {
        if (INSTANCE == null) {
            try {
                INSTANCE = new PlayerIndex(ctx);
            } catch (Exception e) {
                Log.indexError(ctx, e);
            }
        }
        return INSTANCE;
    }

    public static int size() { return INSTANCE == null ? 0 : INSTANCE.sortedPids.length; }

    public String name(int pid) {
        String s = pidName.get(pid);
        return s == null ? ("pid " + pid) : dedupe(s);
    }

    /** "Lucas Piazon Piazon" -> "Lucas Piazon"; keeps names that merely repeat a word apart. */
    private static String dedupe(String s) {
        String[] t = s.trim().split("\\s+");
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < t.length; i++) {
            if (i > 0 && t[i].equalsIgnoreCase(t[i - 1])) continue;
            if (b.length() > 0) b.append(' ');
            b.append(t[i]);
        }
        return b.toString();
    }

    public boolean knows(int pid) { return pidName.containsKey(pid); }

    public int pid(String exact) {
        for (int pid : sortedPids) if (exact.equalsIgnoreCase(pidName.get(pid))) return pid;
        return -1;
    }

    public List<Team> teams() { return teamList; }

    public Team team(int id) {
        for (Team t : teamList) if (t.id == id) return t;
        return null;
    }

    /**
     * Fuzzy team search that ignores word order and short prefixes, so "ac milan",
     * "milan ac" and "milan" all find "AC Milan".  Every query token must match the
     * start of one of the team's words (or the whole word sequence).
     */
    /** Every query token must appear in the name (order-independent, case-insensitive). */
    static boolean nameMatches(String name, String[] tokens) {
        if (tokens == null || tokens.length == 0) return true;
        String low = name.toLowerCase();
        for (String t : tokens) {
            if (t == null || t.isEmpty()) continue;
            if (!low.contains(t)) return false;
        }
        return true;
    }

    static boolean teamMatches(String teamName, String[] tokens) {
        if (tokens == null || tokens.length == 0) return true;
        String name = teamName.toLowerCase();
        for (String tok : tokens) {
            if (tok.isEmpty()) continue;
            if (name.contains(tok)) continue;
            boolean hit = false;
            for (String w : name.split("[^a-z0-9]+")) {
                if (!w.isEmpty() && (w.startsWith(tok) || tok.startsWith(w))) { hit = true; break; }
            }
            if (!hit) return false;
        }
        return true;
    }

    /** Looks a team up by (partial) name; exact match wins, then prefix, then contains. */
    public Team team(String query) {
        if (query == null) return null;
        String q = query.trim().toLowerCase();
        if (q.isEmpty()) return null;
        for (Team t : teamList) if (t.name.toLowerCase().equals(q)) return t;
        for (Team t : teamList) if (t.name.toLowerCase().startsWith(q)) return t;
        for (Team t : teamList) if (t.name.toLowerCase().contains(q)) return t;
        return null;
    }

    public List<int[]> search(String q, int limit) {
        ArrayList<int[]> out = new ArrayList<>();
        String qq = q.toLowerCase().trim();
        if (qq.isEmpty()) return out;
        String[] toks = qq.split("\\s+");
        for (int pid : sortedPids) {
            String s = pidName.get(pid);
            if (s == null) continue;
            String ln = s.toLowerCase();
            boolean ok = true;
            for (String t : toks) if (!ln.contains(t)) { ok = false; break; }
            if (ok) {
                out.add(new int[]{pid});
                if (out.size() >= limit) break;
            }
        }
        return out;
    }

    private static int le32(DataInputStream d) throws IOException {
        return d.readUnsignedByte()
                | (d.readUnsignedByte() << 8)
                | (d.readUnsignedByte() << 16)
                | (d.readUnsignedByte() << 24);
    }

    private static int le16(DataInputStream d) throws IOException {
        return d.readUnsignedByte() | (d.readUnsignedByte() << 8);
    }

    /** Teams whose cmn jersey table contains the given pid. */
    public List<Team> teamsOf(int pid) {
        ArrayList<Team> out = new ArrayList<>();
        for (Team t : teamList) {
            for (int p : t.pids) if (p == pid) { out.add(t); break; }
        }
        return out;
    }
}