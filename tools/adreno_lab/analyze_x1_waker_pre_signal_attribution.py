#!/usr/bin/env python3
"""Summarize [X1-WAKER] dynamically latched waker pre-signal attribution."""

from pathlib import Path
import re
import sys


ROW = re.compile(
    r"\[X1-WAKER\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) "
    r"wall=(?P<wall>[0-9.]+)ms wakerTid=(?P<tid>0x[0-9a-fA-F]+) signals=(?P<signals>\d+) "
    r"intervals=(?P<intervals>\d+) inter=(?P<inter>[0-9.]+)ms "
    r"interAvg=(?P<inter_avg>[0-9.]+)ms interMax=(?P<inter_max>[0-9.]+)ms "
    r"wait=(?P<wait>[0-9.]+)ms waitShare=(?P<wait_share>[0-9.]+)% "
    r"residual=(?P<residual>[0-9.]+)ms residualAvg=(?P<residual_avg>[0-9.]+)ms "
    r"residualMax=(?P<residual_max>[0-9.]+)ms "
    r"noneN=(?P<none_n>\d+) none=(?P<none>[0-9.]+)ms "
    r"sleepN=(?P<sleep_n>\d+) sleep=(?P<sleep>[0-9.]+)ms "
    r"ipcN=(?P<ipc_n>\d+) ipc=(?P<ipc>[0-9.]+)ms "
    r"syncN=(?P<sync_n>\d+) sync=(?P<sync>[0-9.]+)ms "
    r"condN=(?P<cond_n>\d+) cond=(?P<cond>[0-9.]+)ms "
    r"arbN=(?P<arb_n>\d+) arb=(?P<arb>[0-9.]+)ms "
    r"suspN=(?P<susp_n>\d+) susp=(?P<susp>[0-9.]+)ms "
    r"lastWaitSvc=(?P<svc>0x[0-9a-fA-F]+) "
    r"pc=(?P<pc>0x[0-9a-fA-F]+)/var(?P<pc_var>\d+) "
    r"lr=(?P<lr>0x[0-9a-fA-F]+)/var(?P<lr_var>\d+) "
    r"latestPc=(?P<latest_pc>0x[0-9a-fA-F]+) latestLr=(?P<latest_lr>0x[0-9a-fA-F]+) "
    r"begins=(?P<begins>\d+) ends=(?P<ends>\d+) orphanEnd=(?P<orphan>\d+) "
    r"nestedBegin=(?P<nested>\d+) malformedWait=(?P<malformed_wait>\d+) "
    r"malformedInterval=(?P<malformed_interval>\d+) wakerSwitch=(?P<switch>\d+)"
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_waker_pre_signal_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ROW.search(line)
        if match:
            rows.append(match.groupdict())

    if not rows:
        raise SystemExit("no [X1-WAKER] records found")

    print(
        "frame waker signals intervals interAvg interMax waitShare residualAvg "
        "none sleep ipc sync cond arb susp lastSvc pc pcVar lr lrVar switch malformed"
    )
    for row in rows:
        malformed = int(row["malformed_wait"]) + int(row["malformed_interval"])
        print(
            f"{int(row['frame']):5d} {row['tid']:>6} {int(row['signals']):7d} "
            f"{int(row['intervals']):9d} {float(row['inter_avg']):8.3f} "
            f"{float(row['inter_max']):8.3f} {float(row['wait_share']):9.2f} "
            f"{float(row['residual_avg']):11.3f} {float(row['none']):7.1f} "
            f"{float(row['sleep']):7.1f} {float(row['ipc']):7.1f} "
            f"{float(row['sync']):7.1f} {float(row['cond']):7.1f} "
            f"{float(row['arb']):7.1f} {float(row['susp']):7.1f} "
            f"{row['svc']:>7} {row['pc']:>12} {int(row['pc_var']):5d} "
            f"{row['lr']:>12} {int(row['lr_var']):5d} {int(row['switch']):6d} "
            f"{malformed:9d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
