"""
Webster's method for one intersection, plus a pedestrian check and the
HCM delay the result works out at.

It's all plain arithmetic. No library needed.
"""

# Assumptions live up here so they only need changing in one place.
SAT_FLOW_PER_LANE = 1900   # vehicles per hour per lane, once the queue is moving
LOST_TIME_PER_PHASE = 4.0  # seconds lost to yellow + all-red each time the phase changes
# Toronto's Type A pedestrian timing, the one used for the general population.
# The city times the WALK plus the flashing hand so the whole crossing works
# out at 1.0 m/s, while the flashing hand on its own assumes 1.2 m/s.
WALK_INTERVAL = 7.0        # minimum seconds the walk symbol stays on
WALK_SPEED_FDW = 1.2       # m/s, assumed during the flashing hand
WALK_SPEED_TOTAL = 1.0     # m/s, what WALK + flashing hand has to average
PCE_HEAVY = 2.0            # a truck or bus takes up about as much road as 2 cars

# Control delay is scored over the busiest 15 minutes, not the whole hour.
ANALYSIS_PERIOD_H = 0.25
PRETIMED_K = 0.5           # fixed-time signals waste less green than actuated ones
ISOLATED_I = 1.0           # nothing upstream is metering the arrivals

# HCM grade boundaries, seconds of delay per vehicle. Anything worse than E is F.
LOS_BANDS = [(10, "A"), (20, "B"), (35, "C"), (55, "D"), (80, "E")]


def heavy_adjust(volume, heavy_count):
    """
    Turn a mixed stream into "car equivalents".

    A bus is slower to clear the stop line than a car, so 100 vehicles
    with 10 buses in them act more like 110 cars.

    >>> heavy_adjust(100, 10)   # 90 cars + 10 buses
    110.0
    """
    cars = volume - heavy_count
    return cars + heavy_count * PCE_HEAVY


def flow_ratio(volume, lanes):
    """
    y = demand / capacity: how much of the hour this movement needs green.

    >>> round(flow_ratio(643, 2), 3)
    0.169
    """
    # lanes * 1900 is how many vehicles those lanes can push through per hour
    return volume / (lanes * SAT_FLOW_PER_LANE)


def critical_Y(phase_volumes, lanes):
    """
    Y = the busiest movement's flow ratio in each phase, added up.

    phase_volumes is a list of lists, one inner list per phase, holding the
    volumes that get green together. Y >= 1 means more cars arrive than the
    signal can ever clear, and no timing fixes that.

    >>> round(critical_Y([[643, 421], [485, 516]], lanes=2), 3)
    0.305
    """
    # busiest approach in each phase -> flow ratio -> add up
    return sum(flow_ratio(max(p), lanes) for p in phase_volumes)


def lost_time(n_phases):
    """Seconds per cycle spent switching between phases."""
    return n_phases * LOST_TIME_PER_PHASE


def webster_cycle(Y, n_phases):
    """
    Cycle length (seconds) that gives the least vehicle delay.

        C = (1.5 L + 5) / (1 - Y)

    Returns None if Y >= 1. The formula blows up there, so there's no answer.

    >>> round(webster_cycle(0.305, 2), 1)
    24.5
    """
    if Y >= 1.0:
        return None
    L = lost_time(n_phases)
    return (1.5 * L + 5) / (1 - Y)


def pedestrian_time(crossing_m):
    """
    Shortest green that lets someone walk across safely, by Toronto's rule.

    Two conditions have to hold at once. The walk symbol gets its seven
    seconds and the flashing hand covers the crossing at 1.2 m/s, and the
    two together have to average 1.0 m/s over the whole width. Whichever
    binds is the answer. Below a 42 m crossing it is always the first.

    >>> round(pedestrian_time(14), 1)
    18.7
    """
    return max(WALK_INTERVAL + crossing_m / WALK_SPEED_FDW,
               crossing_m / WALK_SPEED_TOTAL)


def pedestrian_min_cycle(crossing_widths_m):
    """
    Every phase has to fit the crossing that happens during it, so the
    shortest allowed cycle is those times added together.

    >>> round(pedestrian_min_cycle([14, 14]), 1)
    37.3
    """
    return sum(pedestrian_time(w) for w in crossing_widths_m)


def green_splits(phase_volumes, lanes, cycle, n_phases):
    """
    Divide the usable green between phases in proportion to what each
    phase's busiest approach needs. Returns seconds, one per phase.

    >>> [round(g, 1) for g in green_splits([[643,421],[485,516]], 2, 37.3, 2)]
    [16.3, 13.0]
    """
    ys = [flow_ratio(max(p), lanes) for p in phase_volumes]
    usable = cycle - lost_time(n_phases)   # whatever is left after the yellows
    total = sum(ys)                        # dividing by this makes the shares add to 1
    return [usable * y / total for y in ys]


def control_delay(volume, lanes, green, cycle):
    """
    Seconds of delay the average driver on this approach puts up with.

    Two parts. The first assumes a steady stream of arrivals and is just
    the red time they have to sit through. The second adds what bunching
    and the odd overflowed cycle cost on top.

    >>> round(control_delay(643, 2, 16.3, 37.3), 1)
    7.8
    """
    capacity = lanes * SAT_FLOW_PER_LANE * green / cycle
    X = volume / capacity          # how close this approach runs to full
    g_c = green / cycle

    uniform = 0.5 * cycle * (1 - g_c) ** 2 / (1 - min(X, 1.0) * g_c)
    overflow = 900 * ANALYSIS_PERIOD_H * (
        (X - 1) + ((X - 1) ** 2 + 8 * PRETIMED_K * ISOLATED_I * X
                   / (capacity * ANALYSIS_PERIOD_H)) ** 0.5)
    return uniform + overflow


def level_of_service(delay):
    """
    The letter grade engineers quote alongside a delay figure.

    >>> level_of_service(7.8), level_of_service(42.0), level_of_service(95.0)
    ('A', 'D', 'F')
    """
    for limit, letter in LOS_BANDS:
        if delay <= limit:
            return letter
    return "F"


def intersection_delay(phase_volumes, lanes, cycle, greens):
    """
    One delay figure for the whole intersection, weighted by how many
    vehicles each approach carries. A quiet side street shouldn't drag
    the score around as much as the main road.

    >>> round(intersection_delay([[643, 421], [485, 516]], 2, 37.3, [16.3, 13.0]), 1)
    8.7
    """
    vehicles = 0.0
    weighted = 0.0
    for phase, green in zip(phase_volumes, greens):
        for v in phase:
            if v <= 0:
                continue
            vehicles += v
            weighted += v * control_delay(v, lanes, green, cycle)
    return weighted / vehicles if vehicles else 0.0


def time_intersection(phase_volumes, lanes, crossing_widths_m):
    """
    Run everything for one intersection. Returns Y, both candidate cycles,
    which one wins, the final cycle, the green times, and the delay and
    grade both at that cycle and at the one vehicles would have picked.
    """
    n_phases = len(phase_volumes)
    Y = critical_Y(phase_volumes, lanes)
    c_veh = webster_cycle(Y, n_phases)               # what the cars want
    c_ped = pedestrian_min_cycle(crossing_widths_m)  # what people on foot need

    if c_veh is None:
        governed_by, cycle = "over capacity", None
        greens = delay = delay_webster = los = None
    else:
        governed_by = "vehicles" if c_veh >= c_ped else "pedestrians"
        cycle = max(c_veh, c_ped)
        greens = green_splits(phase_volumes, lanes, cycle, n_phases)
        delay = intersection_delay(phase_volumes, lanes, cycle, greens)
        los = level_of_service(delay)

        # What drivers would have waited if nobody had to cross on foot.
        # Where vehicles already govern, this is the same number.
        delay_webster = intersection_delay(
            phase_volumes, lanes, c_veh,
            green_splits(phase_volumes, lanes, c_veh, n_phases))

    return {
        "Y": Y,
        "cycle_webster": c_veh,
        "cycle_pedestrian": c_ped,
        "governed_by": governed_by,
        "cycle": cycle,
        "greens": greens,
        "delay": delay,
        "los": los,
        "delay_webster": delay_webster,
    }


if __name__ == "__main__":
    import doctest
    fails, total = doctest.testmod()
    print(f"doctests: {total - fails} passed, {fails} failed")

    print("\nYonge St / Eglinton Ave, AM peak:")
    r = time_intersection(
        phase_volumes=[[643, 421], [485, 516]],   # north+south, then east+west
        lanes=2,
        crossing_widths_m=[14, 14],
    )
    print(f"  Y                 {r['Y']:.3f}")
    print(f"  Webster cycle     {r['cycle_webster']:.1f} s")
    print(f"  Pedestrian min    {r['cycle_pedestrian']:.1f} s")
    print(f"  governed by       {r['governed_by']}")
    print(f"  final cycle       {r['cycle']:.1f} s")
    print(f"  green N-S         {r['greens'][0]:.1f} s")
    print(f"  green E-W         {r['greens'][1]:.1f} s")
    print(f"  delay             {r['delay']:.1f} s/veh  (LOS {r['los']})")
    print(f"  delay if cars won {r['delay_webster']:.1f} s/veh")
