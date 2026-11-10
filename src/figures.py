"""
Makes the three charts used in the README.
Run build_dataset.py and analyse.py first.
"""
import pathlib
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"

# These colours passed a colour-blind check, so I kept them.
BLUE, RED, GREY = "#2E6FD9", "#E04B4B", "#9a9a97"
SURFACE = "#fcfcfb"
INK, MUTED = "#23231f", "#6b6b66"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": MUTED, "axes.edgecolor": "#d8d8d4",
    "xtick.color": MUTED, "ytick.color": MUTED,
    "font.size": 10, "axes.titlesize": 11,
})


def style(ax):
    """Remove the top and right borders and put the grid behind the data."""
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e8e8e4", linewidth=0.8)
    ax.set_axisbelow(True)


def load():
    t = pd.read_csv(ROOT / "data/processed/timings.csv")
    i = pd.read_csv(ROOT / "data/processed/intersections.csv")
    # merge on px AND period, otherwise an AM row could pick up a PM row
    df = t.merge(i[["px", "period", "peak_peds",
                    "total_vehicle_14h", "total_peds_14h"]],
                 on=["px", "period"], how="left")
    return df[df.period == "am"].copy()


def fig1_distribution(am):
    """How long a cycle does Webster want? A spread of values, so a histogram."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    d = am[am.cycle_webster.notna()]
    ax.hist(d.cycle_webster.clip(upper=120), bins=55,
            color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    floor = d.cycle.iloc[0]
    ax.axvline(floor, color=RED, linewidth=2)
    ax.annotate(f"pedestrian minimum  {floor:.0f} s",
                xy=(floor + 2, ax.get_ylim()[1] * 0.88),
                color=RED, fontsize=9.5, fontweight="bold")
    ax.set_xlabel("cycle length that minimises vehicle delay (seconds)")
    ax.set_ylabel("intersections")
    ax.set_title("Almost every intersection wants a shorter cycle than "
                 "pedestrians can safely use", loc="left", fontweight="bold")
    style(ax)
    fig.tight_layout(); fig.savefig(FIG / "1_cycle_distribution.png", dpi=170)


def fig2_map(am):
    """Where are they? Position is the point, so dots on lat/long."""
    fig, ax = plt.subplots(figsize=(8, 5.6))
    for label, colour, size in (("pedestrians", BLUE, 9), ("vehicles", RED, 34)):
        d = am[am.governed_by == label]
        ax.scatter(d.longitude, d.latitude, s=size, c=colour,
                   alpha=0.75 if label == "pedestrians" else 1.0,
                   linewidths=0.5, edgecolors=SURFACE,
                   label=f"{label} ({len(d)})")
    ax.set_aspect(1 / 0.72)                 # stretches the x axis so Toronto isn't squashed (43.7 N)
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.set_title("What governs the signal, across Toronto\n"
                 "vehicles only win at highway ramps and outer arterials",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "2_map.png", dpi=170)


def fig3_who_is_served(am):
    """Pedestrians vs vehicles at each intersection. Log scales because a few are huge."""
    d = am[(am.total_vehicle_14h > 0) & (am.total_peds_14h > 0)].copy()
    d["ratio"] = d.total_peds_14h / d.total_vehicle_14h
    more_peds = d[d.ratio > 1]

    fig, ax = plt.subplots(figsize=(7.4, 5.4))
    ax.scatter(d.total_vehicle_14h, d.total_peds_14h, s=11, c=GREY,
               alpha=0.55, linewidths=0)
    ax.scatter(more_peds.total_vehicle_14h, more_peds.total_peds_14h, s=22,
               c=BLUE, linewidths=0.5, edgecolors=SURFACE,
               label=f"more people on foot than in cars ({len(more_peds)})")

    lim = [d.total_vehicle_14h.min(), d.total_vehicle_14h.max()]
    ax.plot(lim, lim, color=RED, linewidth=1.6, linestyle=(0, (5, 3)),
            label="equal numbers")

    # only label the most extreme one, labelling all 1,000 would be a mess
    top = d.nlargest(1, "total_peds_14h").iloc[0]
    ax.annotate(f"  {top.location_name.split(' / ')[0]} / "
                f"{top.location_name.split(' / ')[1]}\n"
                f"  {top.total_peds_14h:,.0f} on foot vs "
                f"{top.total_vehicle_14h:,.0f} in cars",
                xy=(top.total_vehicle_14h, top.total_peds_14h),
                fontsize=8.5, color=INK, va="center")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("vehicles in 14 hours"); ax.set_ylabel("pedestrians in 14 hours")
    ax.set_title("Who the intersection actually serves", loc="left",
                 fontweight="bold")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    style(ax); ax.grid(axis="x", color="#e8e8e4", linewidth=0.8)
    fig.tight_layout(); fig.savefig(FIG / "3_who_is_served.png", dpi=170)
    return len(more_peds), top


if __name__ == "__main__":
    am = load()
    fig1_distribution(am)
    fig2_map(am)
    n, top = fig3_who_is_served(am)
    print(f"wrote 3 figures to {FIG}")
    print(f"  intersections with more pedestrians than vehicles: {n}")
    print(f"  busiest on foot: {top.location_name} "
          f"({top.total_peds_14h:,.0f} peds vs {top.total_vehicle_14h:,.0f} veh)")
