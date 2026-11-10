# Who really sets the timing of Toronto's traffic signals?

I ran Webster's signal timing method on 1,078 signalised intersections in
Toronto, using the City's open turning movement counts. I expected the traffic
volumes to decide the answer. They mostly don't.

> At 95% of these intersections, the cycle length that gives cars the least
> delay is shorter than the time people need to walk across. So pedestrians,
> not traffic, decide the timing. Vehicles win at only 56 intersections, mostly
> highway ramps and outer arterials.

![Cycle length distribution](figures/1_cycle_distribution.png)

## Why I did this

A signal splits its time between directions. Webster (1958) worked out the
cycle length that keeps total vehicle delay lowest for a given set of volumes.
Textbooks run it on one intersection. I wanted to see what it says when you run
it on a whole city's worth of real counts, and what gets in the way of using
the answer.

## Where each one wins

![Map](figures/2_map.png)

The 56 vehicle-governed intersections aren't scattered at random. They're
Highway 401 collectors, the Gardiner, and wide suburban arterials: lots of
cars, hardly anyone walking. The model never knew what kind of road it was
looking at, so I take this as a good sign that it's behaving sensibly.

## Who the intersection is for

![Pedestrians versus vehicles](figures/3_who_is_served.png)

The City counts pedestrians as well as vehicles, and I'd guess most people
ignore that column. At 86 of the 1,078 intersections, more people cross on foot
than pass through in vehicles. Dundas and Yonge is the extreme: 91,808 people
on foot in 14 hours against 15,962 vehicles, about six to one.

The usual tools (Webster, the Highway Capacity Manual delay model, TRANSYT,
SCOOT) mostly optimise vehicle delay and treat pedestrians as a minimum time
to be satisfied. At these 86 places that minimum ends up being most of what the
signal does.

## How it works

1. **Critical movement.** In each phase the busiest approach sets the green.
   The green has to clear the worst queue, not the average one.
2. **Flow ratio**, `y = volume / (lanes x 1900)`. It's the share of the hour
   that movement needs green.
3. **Y** is the sum of the critical `y` across phases. If `Y >= 1`, more cars
   arrive than the signal can clear and no timing helps.
4. **Webster cycle**, `C = (1.5L + 5) / (1 - Y)`, where `L` is lost time at
   4 seconds per phase.
5. **Pedestrian minimum**: 7 s of WALK plus crossing distance / 1.07 m/s, for
   each phase, added up.
6. **Final cycle** is the longer of 4 and 5.

Nothing is fitted or trained here. It's an existing formula applied to real
counts.

## Data

City of Toronto, Transportation Services Division, *Traffic Volumes -
Multimodal Intersection Turning Movement Counts*. Open Government Licence -
Toronto, refreshed daily:
<https://open.toronto.ca/dataset/traffic-volumes-at-intersections-for-all-modes/>

The counts come from video, grouped into 15-minute slices, and the programme
goes back to 1984.

| File | One row is | I use it for |
|---|---|---|
| `tmc_most_recent_summary_data.csv` | an intersection | choosing sites, finding the peak hour |
| `tmc_raw_data_2020_2029.csv` | a 15-minute slice | turning movements and pedestrians |

### Which intersections made it in

| Step | Left |
|---|---|
| intersections in the file | 6,405 |
| signalised only (`px` present) | 2,661 |
| 14-hour continuous counts only | 1,411 |
| traffic on all four legs | **1,078** |

Webster is for signals, so unsignalised intersections are out. Counts before
September 2023 covered 8 hours that weren't continuous; the newer ones cover 14
continuous hours, so I only used the newer ones. Three-leg and irregular
junctions need different phasing, so I left them for later.

The counts I used are dated September 2023 to October 2026 (median July 2025),
over an area about 41 km east-west and 27 km north-south.

## Running it

```bash
pip install -r requirements.txt
# put the two CSVs from the link above into data/raw/
python src/build_dataset.py   # 6,405 intersections down to 1,078, with peak movements
python src/webster.py         # runs the built-in tests
python src/analyse.py         # cycle length for every intersection
python src/figures.py         # the three charts above
```

`build_dataset.py` works out each peak hour again from the raw 15-minute rows
and compares it with the peak count in the summary file. All 2,156 rows match.
`webster.py` has seven doctests, one for each formula.

## What's weak about it

- **Lanes are assumed.** I used 2 per approach because the data doesn't say.
  `Y` goes down as lanes go up, so individual intersections will shift. Real
  lane counts from OpenStreetMap are the first thing I want to add.
- **Crossing distance is assumed** at 14 m. The main result holds across a
  sensible range (pedestrians govern at 85% of intersections with 9 m and 98%
  with 20 m) but the exact percentage depends on it.
- **Two phases only.** Where left turns are heavy you'd want protected phases,
  which add lost time and lengthen the cycle. Left turns average 12% of peak
  traffic here and go up to 41%.
- **Trucks and buses aren't weighted yet.** The counts are extracted and the
  function exists (`heavy_adjust`), I just haven't plugged it in.
- **Webster assumes an isolated intersection that isn't overloaded.** It
  ignores neighbouring signals and says nothing useful once `Y >= 1`.
- **This isn't a random sample of Toronto's signals.** The City says counts are
  *"collected on an ad-hoc, as needed basis, therefore does not have
  comprehensive temporal or geographic coverage"*, and that some over- and
  under-counting may remain. So the results describe these 1,078 intersections,
  not every signal in the city.

## Licence

Code is MIT (see `LICENSE`). The data is under the Open Government Licence -
Toronto.
