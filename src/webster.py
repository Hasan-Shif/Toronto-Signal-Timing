"""
Webster's method for one intersection, plus a pedestrian check.

It's all plain arithmetic. No library needed.
"""

# Assumptions live up here so they only need changing in one place.
SAT_FLOW_PER_LANE = 1900   # vehicles per hour per lane, once the queue is moving
LOST_TIME_PER_PHASE = 4.0  # seconds lost to yellow + all-red each time the phase changes
WALK_INTERVAL = 7.0        # seconds the walk symbol stays on
WALK_SPEED = 1.07          # m/s, the slow-walker speed (3.5 ft/s)
PCE_HEAVY = 2.0            # a truck or bus takes up about as much road as 2 cars


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
    Shortest green that lets someone walk across safely:
    the walk interval plus the time to cover the crossing.

    >>> round(pedestrian_time(14), 1)
    20.1
    """
    return WALK_INTERVAL + crossing_m / WALK_SPEED


def pedestrian_min_cycle(crossing_widths_m):
    """
    Every phase has to fit the crossing that happens during it, so the
    shortest allowed cycle is those times added together.

    >>> round(pedestrian_min_cycle([14, 14]), 1)
    40.2
    """
    return sum(pedestrian_time(w) for w in crossing_widths_m)


def green_splits(phase_volumes, lanes, cycle, n_phases):
    """
    Divide the usable green between phases in proportion to what each
    phase's busiest approach needs. Returns seconds, one per phase.

    >>> [round(g, 1) for g in green_splits([[643,421],[485,516]], 2, 40.2, 2)]
    [17.9, 14.3]
    """
    ys = [flow_ratio(max(p), lanes) for p in phase_volumes]
    usable = cycle - lost_time(n_phases)   # whatever is left after the yellows
    total = sum(ys)                        # dividing by this makes the shares add to 1
    return [usable * y / total for y in ys]


def time_intersection(phase_volumes, lanes, crossing_widths_m):
    """
    Run everything for one intersection and return a dict with Y, both
    candidate cycles, which one wins, the final cycle and the green times.
    """
    n_phases = len(phase_volumes)
    Y = critical_Y(phase_volumes, lanes)
    c_veh = webster_cycle(Y, n_phases)               # what the cars want
    c_ped = pedestrian_min_cycle(crossing_widths_m)  # what people on foot need

    if c_veh is None:
        governed_by, cycle = "over capacity", None
        greens = None
    else:
        governed_by = "vehicles" if c_veh >= c_ped else "pedestrians"
        cycle = max(c_veh, c_ped)
        greens = green_splits(phase_volumes, lanes, cycle, n_phases)

    return {
        "Y": Y,
        "cycle_webster": c_veh,
        "cycle_pedestrian": c_ped,
        "governed_by": governed_by,
        "cycle": cycle,
        "greens": greens,
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
