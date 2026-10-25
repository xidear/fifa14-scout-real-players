package com.zcode.jersey;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Finds the career world's team-player-links rows inside the running FIFA process
 * and rewrites one player's jersey number.
 *
 * Row layout (16 bytes): teamid, playerid, flags, alt
 * jersey = ((flags & 0xff) >> 1) + 1
 *
 * Verified on device (Frida): Manchester City team id 10, rows at 0xbc7ba978 (Richards),
 * 0xbc7ba988 (Sturridge), 0xbc7ba9d8 (Obiang). The cmn copy of the same rows lives at a
 * different address, so candidate blocks are scored by how many of the team's real pids
 * they contain and how many jersey numbers still match the cmn table.
 */
public final class JerseyCore {

    private JerseyCore() {}

    public static final class Row {
        public int pid;
        public int jersey;
        public long addr;      // address of the flags word
    }

    public static final class Block {
        public int teamId;
        public long base;
        public List<Row> rows = new ArrayList<>();
        public int known;       // rows whose pid belongs to this team in cmn
        public int matching;    // rows whose jersey equals cmn
        public int foreign;     // pids not in this team (transfer ins, free agents)
        public int score;
    }

    static long u32(byte[] b, int o) {
        return (b[o] & 0xffL) | ((b[o + 1] & 0xffL) << 8) | ((b[o + 2] & 0xffL) << 16)
                | ((b[o + 3] & 0xffL) << 24);
    }

    // ------------------------------------------------------------- maps

    public static final class MapEntry {
        public long start, end;
        public boolean rw;
        public String name;
    }

    public static List<MapEntry> readMaps(int pid) {
        List<MapEntry> out = new ArrayList<>();
        java.io.BufferedReader r = null;
        try {
            r = new java.io.BufferedReader(new java.io.FileReader("/proc/" + pid + "/maps"));
            String line;
            while ((line = r.readLine()) != null) {
                MapEntry e = parseMap(line);
                if (e != null) out.add(e);
            }
        } catch (Exception ignored) {
        } finally {
            if (r != null) try { r.close(); } catch (Exception ignored) {}
        }
        if (out.isEmpty() && RootBridge.alive()) {
            String txt = RootBridge.exec("cat /proc/" + pid + "/maps");
            if (txt != null) {
                for (String line : txt.split(String.valueOf((char) 10))) {
                    MapEntry e = parseMap(line);
                    if (e != null) out.add(e);
                }
            }
        }
        if (out.isEmpty()) {
            java.io.BufferedReader r2 = null;
            try {
                Process p = RootUtil.sh("cat /proc/" + pid + "/maps");
                r2 = new java.io.BufferedReader(new java.io.InputStreamReader(p.getInputStream()));
                String line;
                while ((line = r2.readLine()) != null) {
                    MapEntry e = parseMap(line);
                    if (e != null) out.add(e);
                }
                p.waitFor();
            } catch (Exception ignored) {
            } finally {
                if (r2 != null) try { r2.close(); } catch (Exception ignored) {}
            }
        }
        return out;
    }

    private static MapEntry parseMap(String line) {
        try {
            String[] sp = line.trim().split("\\s+");
            String[] rg = sp[0].split("-");
            MapEntry e = new MapEntry();
            e.start = Long.parseUnsignedLong(rg[0], 16);
            e.end = Long.parseUnsignedLong(rg[1], 16);
            String perm = sp[1];
            e.rw = perm.length() >= 2 && perm.charAt(0) == 'r' && perm.charAt(1) == 'w';
            e.name = sp.length >= 6 ? sp[5] : "";
            return e;
        } catch (Exception e) {
            return null;
        }
    }

    /** Base address of a loaded .so in the target process. */
    public static long moduleBase(int pid, String so) {
        for (MapEntry e : readMaps(pid)) {
            if (e.name != null && e.name.endsWith(so)) return e.start;
        }
        return -1;
    }

    // ----------------------------------------------------------- scanning

    /** Raw candidate runs of at least 5 consecutive rows with the same team id. */
    static List<long[]> findRuns(byte[] buf, long base, int teamId) {
        List<long[]> out = new ArrayList<>();
        int n = buf.length;
        for (int i = 0; i + 16 * 5 <= n; i += 4) {
            if ((int) u32(buf, i) != teamId) continue;
            int s = i;
            while (s >= 16 && (int) u32(buf, s - 16) == teamId && u32(buf, s - 12) != 0) s -= 16;
            int cnt = 0, j = s;
            while (j + 16 <= n && (int) u32(buf, j) == teamId && u32(buf, j + 4) != 0) {
                cnt++;
                j += 16;
            }
            if (cnt >= 5) out.add(new long[]{base + s, cnt});
            i = s + cnt * 16;
        }
        return out;
    }

    /**
     * Locate the career block for one cmn team.
     * Returns the best block, or null when the team's roster is not in memory.
     */
    public static Block locate(int pid, PlayerIndex.Team team) {
        if (team == null) return null;
        Map<Integer, Integer> cmn = new HashMap<>();
        for (int i = 0; i < team.pids.length; i++) cmn.put(team.pids[i], team.jerseys[i]);

        Block best = null;
        List<MapEntry> maps = readMaps(pid);
        for (MapEntry e : maps) {
            if (!e.rw) continue;
            if (e.name != null && (e.name.endsWith(".so") || e.name.endsWith(".ttf")
                    || e.name.endsWith(".odex") || e.name.endsWith(".vdex") || e.name.endsWith(".apk"))) {
                continue;
            }
            long size = e.end - e.start;
            if (size <= 0 || size > (192L << 20)) continue;
            byte[] buf = MemAccess.read(pid, e.start, (int) size);
            if (buf == null) continue;
            for (long[] run : findRuns(buf, e.start, team.id)) {
                Block b = new Block();
                b.teamId = team.id;
                b.base = run[0];
                int cnt = (int) run[1];
                int off = (int) (run[0] - e.start);
                for (int k = 0; k < cnt; k++) {
                    int o = off + k * 16;
                    Row r = new Row();
                    r.pid = (int) u32(buf, o + 4);
                    r.jersey = (int) ((u32(buf, o + 8) & 0xff) >> 1) + 1;
                    r.addr = b.base + (long) k * 16 + 8;
                    b.rows.add(r);
                    Integer c = cmn.get(r.pid);
                    if (c != null) {
                        b.known++;
                        if (c == r.jersey) b.matching++;
                    } else {
                        b.foreign++;
                    }
                }
                // Prefer blocks that still look like the career roster: most pids known,
                // jerseys mostly matching cmn, and a sane squad size.
                b.score = b.matching * 10 + b.known * 4 - b.foreign * 2
                        + Math.min(b.rows.size(), 40);
                if (best == null || b.score > best.score) best = b;
            }
        }
        return best;
    }

    /** Try to locate any block for the given single player (unknown team). */
    public static Block locateByPlayer(int pid, int playerId) {
        Map<Integer, Integer> none = new HashMap<>();
        Block best = null;
        for (MapEntry e : readMaps(pid)) {
            if (!e.rw) continue;
            if (e.name != null && (e.name.endsWith(".so") || e.name.endsWith(".apk"))) continue;
            long size = e.end - e.start;
            if (size <= 0 || size > (192L << 20)) continue;
            byte[] buf = MemAccess.read(pid, e.start, (int) size);
            if (buf == null) continue;
            int n = buf.length;
            for (int i = 0; i + 16 <= n; i += 4) {
                if ((int) u32(buf, i) != 0 && (int) u32(buf, i + 4) == playerId) {
                    int s = i;
                    int teamId = (int) u32(buf, i);
                    while (s >= 16 && (int) u32(buf, s - 16) == teamId) s -= 16;
                    int cand = i - s;
                    if (cand >= 0 && cand < 40) {
                        Block b = new Block();
                        b.teamId = teamId;
                        b.base = e.start + s;
                        int j = s;
                        while (j + 16 <= n && (int) u32(buf, j) == teamId && u32(buf, j + 4) != 0) {
                            Row r = new Row();
                            r.pid = (int) u32(buf, j + 4);
                            r.jersey = (int) ((u32(buf, j + 8) & 0xff) >> 1) + 1;
                            r.addr = b.base + (j - s) + 8;
                            b.rows.add(r);
                            j += 16;
                        }
                        if (b.rows.size() > 20) b.rows = b.rows.subList(0, 20);
                        b.matching = 0;
                        b.score = -cand + b.rows.size();
                        if (best == null || b.score > best.score) best = b;
                    }
                }
            }
        }
        return best;
    }


    /**
     * Scan every writable region once and score runs against all cmn teams.
     * Returns the block that best matches any career roster (i.e. the user's own squad or
     * whichever team is resident in memory).
     */
    public static Block scanForBest(int pid, PlayerIndex ix) {
        if (ix == null) return null;
        java.util.List<PlayerIndex.Team> teams = ix.teams();
        // index: pid -> team (a pid can only be in one cmn team for our purposes)
        java.util.Map<Integer, PlayerIndex.Team> pidTeam = new HashMap<>();
        for (PlayerIndex.Team t : teams) {
            for (int p : t.pids) {
                if (!pidTeam.containsKey(p)) pidTeam.put(p, t);
            }
        }
        Block best = null;
        for (MapEntry e : readMaps(pid)) {
            if (!e.rw) continue;
            if (e.name != null && (e.name.endsWith(".so") || e.name.endsWith(".apk"))) continue;
            long size = e.end - e.start;
            if (size <= 0 || size > (192L << 20)) continue;
            byte[] buf = MemAccess.read(pid, e.start, (int) size);
            if (buf == null) continue;
            int n = buf.length;
            for (int i = 0; i + 16 * 5 <= n; i += 4) {
                int teamId = (int) u32(buf, i);
                if (teamId <= 0 || teamId > 1000000) continue;
                int s = i;
                while (s >= 16 && (int) u32(buf, s - 16) == teamId && u32(buf, s - 12) != 0) s -= 16;
                int cnt = 0, j = s;
                while (j + 16 <= n && (int) u32(buf, j) == teamId && u32(buf, j + 4) != 0) {
                    cnt++;
                    j += 16;
                }
                if (cnt < 8) { i = s + Math.max(cnt, 1) * 16; continue; }
                int known = 0, matching = 0, foreign = 0;
                PlayerIndex.Team matchedTeam = null;
                java.util.Map<Integer, Integer> seen = new HashMap<>();
                for (int k = 0; k < cnt; k++) {
                    int o = s + k * 16;
                    int rowPid = (int) u32(buf, o + 4);
                    int jn = (int) ((u32(buf, o + 8) & 0xff) >> 1) + 1;
                    PlayerIndex.Team t = pidTeam.get(rowPid);
                    if (t == null) { foreign++; continue; }
                    known++;
                    int idx = -1;
                    for (int q = 0; q < t.pids.length; q++) if (t.pids[q] == rowPid) { idx = q; break; }
                    if (idx >= 0 && t.jerseys[idx] == jn) matching++;
                    if (matchedTeam == null && t.id == teamId) matchedTeam = t;
                }
                int score = matching * 12 + known * 5 - foreign * 3 + Math.min(cnt, 40);
                if (best == null || score > best.score) {
                    Block b = new Block();
                    b.teamId = teamId;
                    b.base = e.start + s;
                    b.known = known;
                    b.matching = matching;
                    b.foreign = foreign;
                    b.score = score;
                    for (int k = 0; k < cnt; k++) {
                        int o = s + k * 16;
                        Row r = new Row();
                        r.pid = (int) u32(buf, o + 4);
                        r.jersey = (int) ((u32(buf, o + 8) & 0xff) >> 1) + 1;
                        r.addr = b.base + (long) k * 16 + 8;
                        b.rows.add(r);
                    }
                    best = b;
                }
                i = s + cnt * 16;
            }
        }
        return best;
    }

    /**
     * Preferred write path: call the game's own DB setter inside the target process
     * (libFIFA14.so+0x603DDC, signature (table, key, id, field, value)). Requires Frida.
     * Returns null when Frida is unavailable, true/false from the setter result.
     */
    public static Boolean setJerseyLib(int pid, int playerId, int jersey) {
        if (FridaBridge.setJersey(pid, playerId, jersey)) return Boolean.TRUE;
        return null;
    }

    /** Writes the jersey for row index i, preserving the rest of the flags word. */
    public static boolean setJersey(int pid, Block b, int index, int jersey) {
        if (index < 0 || index >= b.rows.size()) return false;
        Row r = b.rows.get(index);
        byte[] cur = MemAccess.read(pid, r.addr, 4);
        if (cur == null) return false;
        int flags = (int) u32(cur, 0);
        int newFlags = (flags & ~0xff) | (((jersey - 1) * 2) & 0xfe);
        if (!MemAccess.write(pid, r.addr, newFlags)) return false;
        byte[] chk = MemAccess.read(pid, r.addr, 4);
        if (chk == null) return false;
        int got = (int) ((u32(chk, 0) & 0xff) >> 1) + 1;
        if (got != jersey) return false;
        r.jersey = jersey;
        return true;
    }
}