"""Flywheel stage 1: label new inbox episodes, publish the audit montage.

Scans artifacts/finetune_dataset/inbox/ for episode dirs (auto-banked by the
dashboard on every GO) that are not yet labeled, zero-shot labels them, and
publishes the review montage to the docs-hub so the owner can audit from a
phone. Stage 2 (flywheel_ship.ps1) trains/gates/deploys after the human ack.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

REPO = r"D:\dev\chasebot-hw-v0"
INBOX = os.path.join(REPO, "artifacts", "finetune_dataset", "inbox")
LABELER = os.path.join(REPO, "tools", "robot_factory_bridge", "finetune", "label_zeroshot.py")
HUB = r"D:\services\docs-hub\site\chasebot\flywheel"
HUB_URL = "http://127.0.0.1:8123/chasebot/flywheel"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-frames", type=int, default=20, help="skip episodes smaller than this")
    ap.add_argument("--conf", type=float, default=0.06)
    ap.add_argument("--extra-src", nargs="*", default=[], help="additional frame dirs (e.g. a recorder session)")
    args = ap.parse_args()

    eps = []
    for d in sorted(glob.glob(os.path.join(INBOX, "ep_*"))):
        if not os.path.isdir(d) or os.path.exists(os.path.join(d, ".labeled")):
            continue
        n = len(glob.glob(os.path.join(d, "*.jpg")))
        if n >= args.min_frames:
            eps.append((d, n))
    srcs = [d for d, _n in eps] + list(args.extra_src)
    if not srcs:
        print(json.dumps({"new_episodes": 0, "msg": "inbox empty; nothing to label"}))
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = os.path.join(REPO, "artifacts", "finetune_dataset", "labeled_inbox_%s" % stamp)
    cmd = [sys.executable, LABELER, "--src"] + srcs + [
        "--out", out, "--conf", str(args.conf), "--max-per-dir", "3000", "--review-n", "24"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        print(json.dumps({"error": "labeler_failed", "stderr": r.stderr[-500:]}))
        return 1
    stats = json.loads(r.stdout.strip().splitlines()[-1])

    web = os.path.join(HUB, stamp)
    os.makedirs(web, exist_ok=True)
    revs = sorted(glob.glob(os.path.join(out, "review", "*.jpg")))
    for f in revs:
        shutil.copy(f, web)
    with open(os.path.join(web, "index.html"), "w") as f:
        f.write("<!doctype html><meta name=viewport content='width=device-width'>"
                "<title>flywheel audit %s</title><body style='background:#111;margin:0'>" % stamp)
        f.write("<p style='color:#ccc;font:14px sans-serif;padding:8px'>Label audit %s — "
                "%d labeled / %d skipped. Boxes should sit ON the ball; reply 'ship it' if so.</p>" %
                (stamp, stats.get("labeled", 0), stats.get("skipped", 0)))
        for f2 in revs:
            f.write("<img src='%s' style='width:100%%;margin:2px 0'>" % os.path.basename(f2))

    for d, _n in eps:
        open(os.path.join(d, ".labeled"), "w").write(out)

    print(json.dumps({
        "new_episodes": len(eps), "extra_srcs": len(args.extra_src),
        "labeled": stats.get("labeled", 0), "skipped": stats.get("skipped", 0),
        "labeled_dir": out, "review_url": "%s/%s/" % (HUB_URL, stamp),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
