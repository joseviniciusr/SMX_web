"""Build the Sandbox's CWRU bearing recordings, static/sandbox/data/cwru_bearing.npz.

The Sandbox notebook computes envelope spectra in the browser from raw vibration, so this file holds the raw
drive-end accelerometer signals (12 kHz) of eight recordings from the Case Western Reserve University (CWRU)
Bearing Data Center, https://engineering.case.edu/bearingdatacenter:

    normal baseline          97, 98, 99, 100   (motor load 0, 1, 2, 3 HP)
    outer-race fault @6:00  130, 131, 132, 133  (0.007 in fault, motor load 0, 1, 2, 3 HP)

Each recording keeps WINDOWS windows of 4096 samples after the first SKIP samples (the start-up transient),
stored as int16 with one scale per recording (about 2 MB in all; the quantisation error is about 90 dB below the
signal). Cite the data as the CWRU Bearing Data Center and Smith & Randall (2015), doi:10.1016/j.ymssp.2015.04.021.

    python scripts/export_cwru.py                   # downloads the .mat files into ~/.cache/cwru_bearing
    python scripts/export_cwru.py --mat-dir DIR     # or uses DIR/<number>.mat if present

Needs numpy and scipy.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import loadmat

FS = 12_000
SKIP = 2048                # start-up transient, as in SMX_research's real_datasets/cwru_bearing
WINDOWS = 29               # 4096-sample windows per recording: all that the shortest fault recording holds
LENGTH = WINDOWS * 4096
URL = "https://engineering.case.edu/sites/default/files/{}.mat"

# (file number, class, fault, motor load in HP, nominal shaft speed in rpm)
RECORDINGS = [
    (97, "Normal", "none", 0, 1797),
    (98, "Normal", "none", 1, 1772),
    (99, "Normal", "none", 2, 1750),
    (100, "Normal", "none", 3, 1730),
    (130, "Faulty", "outer race 0.007 in @6:00", 0, 1797),
    (131, "Faulty", "outer race 0.007 in @6:00", 1, 1772),
    (132, "Faulty", "outer race 0.007 in @6:00", 2, 1750),
    (133, "Faulty", "outer race 0.007 in @6:00", 3, 1730),
]
OUT = Path(__file__).resolve().parent.parent / "static" / "sandbox" / "data" / "cwru_bearing.npz"


def mat_path(number: int, mat_dir: Path) -> Path:
    path = mat_dir / f"{number}.mat"
    if not path.exists():
        mat_dir.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL.format(number)}")
        urllib.request.urlretrieve(URL.format(number), path)
    return path


def drive_end_signal(path: Path, number: int) -> np.ndarray:
    """The drive-end accelerometer channel of recording ``number``.

    Picked by name: some files carry other recordings' channels too (99.mat also holds X098_DE_time, first).
    """
    mat = loadmat(path)
    key = f"X{number:03d}_DE_time"
    if key not in mat:
        raise KeyError(f"{path} has no {key}; keys: {[k for k in mat if not k.startswith('__')]}")
    return mat[key].ravel()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mat-dir", type=Path, default=Path.home() / ".cache" / "cwru_bearing",
                        help="folder with (or for) the CWRU .mat files")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    signals, scales = [], []
    for number, *_ in RECORDINGS:
        x = drive_end_signal(mat_path(number, args.mat_dir), number)[SKIP:SKIP + LENGTH]
        if len(x) < LENGTH:
            raise ValueError(f"{number}.mat: {len(x)} samples after the transient, need {LENGTH}")
        scale = np.abs(x).max() / 32767
        signals.append(np.round(x / scale).astype(np.int16))
        scales.append(scale)

    numbers, labels, faults, loads, rpms = zip(*RECORDINGS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        signals=np.stack(signals),                    # (recordings, samples) int16; signal = signals * scales
        scales=np.array(scales, dtype=np.float64),
        fs=np.int64(FS),
        file_number=np.array(numbers, dtype=np.int64),
        label=np.array(labels),
        fault=np.array(faults),
        load_hp=np.array(loads, dtype=np.int64),
        rpm=np.array(rpms, dtype=np.int64),
    )
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.2f} MB): {len(RECORDINGS)} recordings × {LENGTH} samples")


if __name__ == "__main__":
    main()
