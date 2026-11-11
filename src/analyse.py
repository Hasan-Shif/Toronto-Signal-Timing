"""
Run the Webster + pedestrian calculation on every intersection and save
the results to data/processed/timings.csv.

Approach volumes go in as passenger car equivalents, with trucks and buses
counted as two cars each. Each intersection also gets an HCM control delay
and a level of service, both at the timing it ends up with and at the timing
that would suit vehicles alone.

Run build_dataset.py first. The charts come from figures.py.
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from webster import heavy_adjust, time_intersection

ROOT = pathlib.Path(__file__).resolve().parent.parent

DIRS = ["n", "e", "s", "w"]
MOVES = ["l", "t", "r"]
LANES = 2            # assumed. The data doesn't have lane counts (see README)
CROSSING_M = 14.0    # assumed too


def main():
    df = pd.read_csv(ROOT / "data/processed/intersections.csv")

    out = []
    for _, r in df.iterrows():
        # left + through + right = everything arriving from that side
        tot = {d: sum(r[f"{d}_{m}"] for m in MOVES) for d in DIRS}
        heavy = {d: sum(r[f"{d}_{m}_hv"] for m in MOVES) for d in DIRS}

        # A bus holds the queue up longer than a car, so count it as two.
        # The saturation flow of 1900 is a passenger-car figure, and the
        # demand it gets compared against has to be in the same units.
        pce = {d: heavy_adjust(tot[d], heavy[d]) for d in DIRS}

        # two phases: north/south go together, then east/west
        res = time_intersection(
            phase_volumes=[[pce["n"], pce["s"]], [pce["e"], pce["w"]]],
            lanes=LANES,
            crossing_widths_m=[CROSSING_M, CROSSING_M],
        )
        vehicles = sum(tot.values())
        out.append({**r[["px", "location_name", "longitude", "latitude",
                         "period", "peak_vehicle"]].to_dict(),
                    "heavy_share": sum(heavy.values()) / vehicles if vehicles else 0.0,
                    "Y": res["Y"],
                    "cycle_webster": res["cycle_webster"],
                    "cycle": res["cycle"],
                    "governed_by": res["governed_by"],
                    "delay": res["delay"],
                    "los": res["los"],
                    "delay_webster": res["delay_webster"]})

    res = pd.DataFrame(out)
    res.to_csv(ROOT / "data/processed/timings.csv", index=False)

    am = res[res.period == "am"]
    print(f"{len(am)} intersections, AM peak")
    print(am.governed_by.value_counts().to_string())
    print(f"heavy vehicles: {am.heavy_share.median():.1%} of peak traffic "
          f"at the median site, up to {am.heavy_share.max():.1%}")

    cost = am.delay - am.delay_webster
    print(f"\nmedian delay {am.delay.median():.1f} s/veh")
    print(am.los.value_counts().sort_index().to_string())
    print(f"waiting for people to cross costs drivers "
          f"{cost.median():.1f} s/veh at the median site, "
          f"up to {cost.max():.1f} s")


if __name__ == "__main__":
    main()
