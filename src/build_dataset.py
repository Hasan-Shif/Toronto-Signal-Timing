"""
Builds the dataset for the Toronto signal-timing project.

Reads   data/raw/tmc_most_recent_summary_data.csv  (one row per intersection)
        data/raw/tmc_raw_data_2020_2029.csv        (one row per 15-minute slice)
Writes  data/processed/intersections.csv           (peak-hour movements)

Which intersections I keep, and why:
  1. Signalised: px isn't blank. Webster only makes sense for signals.
  2. 14-hour counts: count_duration == '14'. Those are the continuous counts
     from Sept 2023 on. The older '8R' and '8S' counts were done differently
     so I left them out.
  3. Four legs: traffic on all four approaches. Three-leg junctions would
     need different phasing, so that's for later.
"""

import pandas as pd
import pathlib

# project root, so paths work from any launch folder
ROOT = pathlib.Path(__file__).resolve().parent.parent

RAW = str(ROOT / "data" / "raw") + "/"
OUT = str(ROOT / "data" / "processed") + "/"
DIRS = ["n", "e", "s", "w"]
MOVES = ["l", "t", "r"]            # left, through, right
TYPES = ["cars", "truck", "bus"]


def load_summary():
    """One row per intersection. Keep the ones I can model."""
    df = pd.read_csv(RAW + "tmc_most_recent_summary_data.csv")

    # explicit day-month-year; without a format pandas guesses, and 06-10
    # could be June or October
    df["count_date"] = pd.to_datetime(df["latest_count_date"], format="%d-%m-%y")
    df["am_peak_start"] = pd.to_datetime(df["am_peak_start"])
    df["pm_peak_start"] = pd.to_datetime(df["pm_peak_start"])

    n0 = len(df)

    df = df[df["px"].notna()]          # signalized only
    n1 = len(df)
    df = df[df["count_duration"] == "14"]   # == tests equality
    n2 = len(df)

    # number of legs with traffic, per row
    legs = sum((df[f"{d}_appr_vehicle"] > 0).astype(int) for d in DIRS)
    df = df[legs == 4]
    n3 = len(df)

    print(f"  {n0:5} intersections in file")
    print(f"  {n1:5} after keeping signalized only      (-{n0-n1})")
    print(f"  {n2:5} after keeping 14-hour counts only  (-{n1-n2})")
    print(f"  {n3:5} after keeping 4-leg only           (-{n2-n3})")
    return df


def peak_hour_movements(g, peak_start):
    """
    Add up the four 15-minute slices that start at peak_start.
    Gives back something like {'n_l': 12, 'n_t': 643, ...}, plus the
    heavy-vehicle counts.
    """
    # rows from peak_start up to one hour later
    window = g[(g.start_time >= peak_start) &
               (g.start_time < peak_start + pd.Timedelta(hours=1))]

    # four 15-minute slices make an hour. Fewer means the count stopped
    # early, and I'd rather skip it than report a wrong total.
    if len(window) != 4:
        return None

    out = {}

    # pedestrians over the same hour. The City counts them with the
    # vehicles, and most signal studies just throw that column away.
    out["peak_peds"] = int(window[[f"{d}_appr_peds" for d in DIRS]]
                           .to_numpy().sum())

    for d in DIRS:
        for m in MOVES:
            out[f"{d}_{m}"] = int(window[[f"{d}_appr_{t}_{m}" for t in TYPES]]
                                  .to_numpy().sum())
            # trucks and buses only
            out[f"{d}_{m}_hv"] = int(window[[f"{d}_appr_{t}_{m}"
                                             for t in ("truck", "bus")]]
                                     .to_numpy().sum())
    return out


def add_movements(sel):
    """Get the peak-hour turning movements from the raw file."""
    wanted = set(sel["latest_count_id"])

    # only load the columns I need (38 of the 55), to save memory
    cols = (["count_id", "start_time"] +
            [f"{d}_appr_peds" for d in DIRS] +
            [f"{d}_appr_{t}_{m}" for d in DIRS for t in TYPES for m in MOVES])

    # The raw file is 89 MB, so read it 200,000 rows at a time, keep
    # what I want from each block, and stitch the pieces together.
    chunks = []
    for chunk in pd.read_csv(RAW + "tmc_raw_data_2020_2029.csv",
                             usecols=cols, chunksize=200_000):
        chunks.append(chunk[chunk["count_id"].isin(wanted)])
    raw = pd.concat(chunks)
    raw["start_time"] = pd.to_datetime(raw["start_time"])
    print(f"  {len(raw):,} raw slices kept for {raw.count_id.nunique()} counts")

    rows = []
    for cid, g in raw.groupby("count_id"):
        s = sel[sel.latest_count_id == cid].iloc[0]
        for period in ("am", "pm"):
            mv = peak_hour_movements(g, s[f"{period}_peak_start"])
            if mv is None:
                continue
            rows.append({                             # add one finished row
                "count_id": cid,
                "px": int(s["px"]),
                "location_name": s["location_name"],
                "longitude": s["longitude"],
                "latitude": s["latitude"],
                "count_date": s["count_date"].date(),
                "period": period,
                "peak_start": s[f"{period}_peak_start"],
                "peak_vehicle": int(s[f"{period}_peak_vehicle"]),
                "total_vehicle_14h": int(s["total_vehicle"]),
                "total_peds_14h": int(s["total_pedestrian"]),
                **mv,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Selecting intersections:")
    sel = load_summary()

    print("\nPulling peak-hour movements from raw file:")
    df = add_movements(sel)

    # Sanity check. The movements I just added up should match the peak
    # count in the summary file. The two come from different files, so if
    # they agree I can trust the code.
    df["movement_sum"] = df[[f"{d}_{m}" for d in DIRS for m in MOVES]].sum(axis=1)
    bad = (df["movement_sum"] != df["peak_vehicle"]).sum()
    print(f"\n  rows where movements != summary peak count: {bad} of {len(df)}")

    df.to_csv(OUT + "intersections.csv", index=False)
    print(f"\nWrote {OUT}intersections.csv  ({len(df)} rows, "
          f"{df.px.nunique()} intersections x 2 periods)")
