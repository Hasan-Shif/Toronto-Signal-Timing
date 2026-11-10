"""
Run the Webster + pedestrian calculation on every intersection and save
the results to data/processed/timings.csv.

Run build_dataset.py first. The charts come from figures.py.
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from webster import time_intersection

ROOT = pathlib.Path(__file__).resolve().parent.parent

DIRS = ["n", "e", "s", "w"]
LANES = 2            # assumed. The data doesn't have lane counts (see README)
CROSSING_M = 14.0    # assumed too


def main():
    df = pd.read_csv(ROOT / "data/processed/intersections.csv")

    out = []
    for _, r in df.iterrows():
        # left + through + right = everything arriving from that side
        tot = {d: r[f"{d}_l"] + r[f"{d}_t"] + r[f"{d}_r"] for d in DIRS}

        # two phases: north/south go together, then east/west
        res = time_intersection(
            phase_volumes=[[tot["n"], tot["s"]], [tot["e"], tot["w"]]],
            lanes=LANES,
            crossing_widths_m=[CROSSING_M, CROSSING_M],
        )
        out.append({**r[["px", "location_name", "longitude", "latitude",
                         "period", "peak_vehicle"]].to_dict(),
                    "Y": res["Y"],
                    "cycle_webster": res["cycle_webster"],
                    "cycle": res["cycle"],
                    "governed_by": res["governed_by"]})

    res = pd.DataFrame(out)
    res.to_csv(ROOT / "data/processed/timings.csv", index=False)

    am = res[res.period == "am"]
    print(f"{len(am)} intersections, AM peak")
    print(am.governed_by.value_counts().to_string())


if __name__ == "__main__":
    main()
