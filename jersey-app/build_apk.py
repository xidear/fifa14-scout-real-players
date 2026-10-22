#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the jersey editor APK without Gradle.

Requirements: JDK 17, Android SDK build-tools and a platform (android.jar).
Environment:
    ANDROID_HOME (or ANDROID_SDK_ROOT), JAVA_HOME
    KEYSTORE, KEY_ALIAS, KEY_PASS   (keystore to sign with)
Optional:
    BUILD_TOOLS   explicit build-tools directory
    PLATFORM_JAR  explicit android.jar
    ADB           adb executable (for --install)

    python build_apk.py [--install]
"""
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(HERE, "out")
IS_WIN = os.name == "nt"


def exe(name):
    return name + ".exe" if IS_WIN else name


def batch(name):
    return name + ".bat" if IS_WIN else name


def newest_dir(parent, prefix=None):
    if not os.path.isdir(parent):
        return None
    cands = [os.path.join(parent, d) for d in os.listdir(parent)
             if os.path.isdir(os.path.join(parent, d))]
    if prefix:
        cands = [c for c in cands if os.path.basename(c).startswith(prefix)]
    return sorted(cands)[-1] if cands else None


def find_tools():
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        sys.exit("set ANDROID_HOME (or ANDROID_SDK_ROOT)")
    bt = os.environ.get("BUILD_TOOLS") or newest_dir(os.path.join(sdk, "build-tools"))
    if not bt:
        sys.exit("no build-tools under " + sdk)
    aj = os.environ.get("PLATFORM_JAR")
    if not aj:
        plat = newest_dir(os.path.join(sdk, "platforms"), "android-")
        if not plat:
            sys.exit("no platforms/android-* under " + sdk)
        aj = os.path.join(plat, "android.jar")
    jh = os.environ.get("JAVA_HOME")
    javac = os.path.join(jh, "bin", exe("javac")) if jh else shutil.which("javac")
    if not javac or not os.path.isfile(javac):
        sys.exit("javac not found; set JAVA_HOME")
    return bt, aj, javac


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        print("FAILED:", " ".join(cmd))
        print(r.stdout)
        print(r.stderr)
        sys.exit(r.returncode)
    return r.stdout


def main():
    install = "--install" in sys.argv
    bt, aj, javac = find_tools()
    ks = os.environ.get("KEYSTORE")
    alias = os.environ.get("KEY_ALIAS", "jersey")
    pw = os.environ.get("KEY_PASS")
    if not ks or not pw:
        sys.exit("set KEYSTORE and KEY_PASS (KEY_ALIAS defaults to 'jersey')")

    if os.path.isdir(OUT):
        shutil.rmtree(OUT, ignore_errors=True)
    for d in ("gen", "classes"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    run([os.path.join(bt, exe("aapt2")), "compile", "--dir", os.path.join(SRC, "res"),
         "-o", os.path.join(OUT, "res.zip")])
    run([os.path.join(bt, exe("aapt2")), "link", "-I", aj,
         "--manifest", os.path.join(SRC, "AndroidManifest.xml"),
         "-o", os.path.join(OUT, "res.apk"),
         "--java", os.path.join(OUT, "gen"),
         "-A", os.path.join(SRC, "assets"), os.path.join(OUT, "res.zip")])

    java_files = []
    for base in (os.path.join(SRC, "java"), os.path.join(OUT, "gen")):
        for dirpath, _, files in os.walk(base):
            java_files += [os.path.join(dirpath, f) for f in files if f.endswith(".java")]
    run([javac, "-nowarn", "-encoding", "UTF-8", "--release", "8",
         "-cp", aj, "-d", os.path.join(OUT, "classes")] + java_files)

    classes = []
    for dirpath, _, files in os.walk(os.path.join(OUT, "classes")):
        classes += [os.path.join(dirpath, f) for f in files if f.endswith(".class")]
    run([os.path.join(bt, batch("d8")), "--min-api", "23", "--lib", aj,
         "--output", OUT] + classes)

    shutil.copy(os.path.join(OUT, "res.apk"), os.path.join(OUT, "unsigned.apk"))
    with zipfile.ZipFile(os.path.join(OUT, "unsigned.apk"), "a", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(OUT, "classes.dex"), "classes.dex")
    run([os.path.join(bt, exe("zipalign")), "-f", "-p", "4",
         os.path.join(OUT, "unsigned.apk"), os.path.join(OUT, "aligned.apk")])
    apk = os.path.join(OUT, "jersey-app.apk")
    run([os.path.join(bt, batch("apksigner")), "sign", "--ks", ks,
         "--ks-pass", "pass:" + pw, "--key-pass", "pass:" + pw,
         "--ks-key-alias", alias, "--out", apk, os.path.join(OUT, "aligned.apk")])
    print("BUILT", apk, os.path.getsize(apk), "bytes")

    if install:
        adb = os.environ.get("ADB", "adb")
        run([adb, "install", "-r", apk])
        print("INSTALLED")


if __name__ == "__main__":
    main()