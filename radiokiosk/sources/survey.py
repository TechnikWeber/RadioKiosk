"""Radio survey: sweep a range again and again for a set time and report what was on the air.

rtl_power measures the power in every slice of the range. One sweep says how
strong something is; many sweeps say whether it is always there (a broadcast
transmitter, or a device nearby that interferes) or comes and goes (somebody
talking). The report sorts what it found by that, band by band, and looks at
the frequencies where activity is to be expected.
"""

import asyncio
import json
import shutil
import time

import numpy as np

from .. import rtlsdr
from ..qsolog import documents_dir
from ..util import kill, sdr_devices, spawn

# what can be swept: id -> (lowest, highest frequency in Hz, width of a slice in Hz)
RANGES = {
    "all": (24e6, 1766e6, 25e3),
    "hf": (0.5e6, 30e6, 5e3),
    "vhf": (30e6, 300e6, 12.5e3),
    "uhf": (300e6, 1000e6, 25e3),
    "air": (118e6, 137e6, 12.5e3),
    "2m": (144e6, 146e6, 2.5e3),
    "70cm": (430e6, 440e6, 5e3),
    "pmr": (445.9e6, 446.3e6, 1e3),
}
HF_BELOW = 24e6      # below this only a Blog V4 tunes by itself; other sticks sample directly
# Every second sweep is tuned differently: cropping the edges of each step moves the
# centres the stick tunes to. What the stick produces itself (a spike in the middle of a
# step, mirror images of strong signals) moves along; a real transmission stays where it is.
TUNINGS = ([], ["-c", "0.25"])
THRESHOLD = 8        # dB above the noise floor for a slice to count as occupied
STEADY = 0.9         # share of the sweeps from which a signal counts as always there
SWING = 6            # dB a slice must rise and fall by to count as coming and going
LISTED = 40          # signals per list in the report
# Who uses what, roughly, in Europe (ITU region 1): (from, to in MHz, name, kind).
# Kinds: "broadcast" is expected to be always on, "ham" and "talk" are where people
# speak now and then, "data" bursts by its nature.
SERVICES = [
    (0.5265, 1.6065, "Medium wave broadcast", "broadcast"), (1.81, 2.0, "160 m amateur", "ham"),
    (3.5, 3.8, "80 m amateur", "ham"), (5.9, 6.2, "49 m broadcast", "broadcast"), (7.0, 7.2, "40 m amateur", "ham"),
    (7.2, 7.45, "41 m broadcast", "broadcast"), (9.4, 9.9, "31 m broadcast", "broadcast"),
    (10.1, 10.15, "30 m amateur", "ham"), (11.6, 12.1, "25 m broadcast", "broadcast"),
    (14.0, 14.35, "20 m amateur", "ham"), (15.1, 15.8, "19 m broadcast", "broadcast"),
    (18.068, 18.168, "17 m amateur", "ham"), (21.0, 21.45, "15 m amateur", "ham"),
    (24.89, 24.99, "12 m amateur", "ham"), (26.565, 27.405, "CB radio", "talk"), (28.0, 29.7, "10 m amateur", "ham"),
    (50.0, 52.0, "6 m amateur", "ham"), (70.15, 70.21, "4 m amateur", "ham"), (87.5, 108.0, "FM broadcast", "broadcast"),
    (108.0, 118.0, "Air navigation", "data"), (118.0, 137.0, "Air band voice", "talk"),
    (137.0, 138.0, "Weather satellites", "data"), (144.0, 146.0, "2 m amateur", "ham"),
    (149.0, 149.12, "Freenet", "talk"), (156.0, 162.05, "Marine VHF", "talk"), (165.0, 174.0, "Business and public radio", "talk"),
    (174.0, 230.0, "DAB+ broadcast", "broadcast"), (380.0, 400.0, "TETRA (authorities)", "data"),
    (430.0, 440.0, "70 cm amateur", "ham"), (433.05, 434.79, "ISM 433 MHz (remotes, sensors)", "data"),
    (446.0, 446.2, "PMR446", "talk"), (450.0, 470.0, "Business radio", "talk"), (470.0, 694.0, "Television (DVB-T2)", "broadcast"),
    (703.0, 788.0, "Mobile phones 700 MHz", "broadcast"), (791.0, 862.0, "Mobile phones 800 MHz", "broadcast"),
    (863.0, 870.0, "ISM 868 MHz (sensors, LoRa)", "data"), (880.0, 960.0, "Mobile phones 900 MHz", "broadcast"),
    (960.0, 1215.0, "Air navigation (DME, ADS-B)", "data"), (1240.0, 1300.0, "23 cm amateur", "ham"),
    (1452.0, 1492.0, "Mobile phones 1500 MHz", "broadcast"), (1559.0, 1610.0, "Satellite navigation", "data"),
]
# where to look first whether somebody is on the air: (MHz, what)
CENTRES = [
    (3.573, "80 m FT8"), (7.074, "40 m FT8"), (14.074, "20 m FT8"), (14.230, "20 m SSTV"), (21.074, "15 m FT8"),
    (27.065, "CB channel 9"), (27.185, "CB channel 19"), (28.074, "10 m FT8"), (29.6, "10 m FM calling"),
    (50.313, "6 m FT8"), (121.5, "Air band emergency"), (144.174, "2 m FT8"), (144.3, "2 m SSB calling"),
    (144.8, "2 m APRS"), (145.5, "2 m FM calling"), (145.6, "2 m repeater outputs 145.600–145.7875"),
    (149.025, "Freenet channel 1"), (156.8, "Marine channel 16"), (432.2, "70 cm SSB calling"),
    (433.5, "70 cm FM calling"), (433.92, "ISM 433.92 MHz"), (438.65, "70 cm repeater outputs 438.650–439.425"),
    (446.00625, "PMR446 channel 1"), (446.09375, "PMR446 channel 8"), (868.3, "ISM 868.3 MHz"),
]
# the two repeater entries cover a block, everything else one channel
BLOCKS = {145.6: 145.7875, 438.65: 439.425}


def limits(v4, tuner=None):
    """From where to where the connected stick can be swept, in Hz."""
    _, low, high = tuner or rtlsdr.TUNERS[5]   # unknown: assume the usual R820T
    return (0.5e6 if v4 else low * 1e6), min(high * 1e6, 2200e6)


def ranges_for(v4, tuner=None):
    """RANGES as this stick can do them: "all" as wide as it tunes, the rest cut to what it reaches.

    Shortwave is left in for every stick: without a V4 it is swept with direct sampling,
    which works on sticks built for it (Blog V3) and shows little on others.
    """
    lowest, highest = limits(v4, tuner)
    fitted = {}
    for name, (low, high, step) in RANGES.items():
        if name == "all":
            low, high = lowest, highest
        elif name != "hf":
            low, high = max(low, lowest), min(high, highest)
        if high - low >= 10 * step:
            fitted[name] = (low, high, step)
    return fitted


def service_at(mhz):
    """The most specific entry of SERVICES that covers a frequency."""
    found = [s for s in SERVICES if s[0] <= mhz <= s[1]]
    return min(found, key=lambda s: s[1] - s[0]) if found else None


def parse_sweep(text):
    """One run of rtl_power as (frequencies in Hz, levels in dB), sorted by frequency."""
    freqs, levels = [], []
    for line in text.splitlines():
        fields = line.split(",")
        try:
            low, step = float(fields[2]), float(fields[4])
            values = [float(v) for v in fields[6:] if v.strip()]
        except (IndexError, ValueError):
            continue
        freqs.append(low + step * np.arange(len(values)))
        levels.append(np.array(values))
    if not freqs:
        return np.array([]), np.array([])
    freqs, levels = np.concatenate(freqs), np.concatenate(levels)
    order = np.argsort(freqs, kind="stable")
    return freqs[order], np.nan_to_num(levels[order], nan=-120.0, neginf=-120.0)


def noise_floor(levels, slice_hz, block_hz=500e3, widest_hz=20e6):
    """The level between the signals, slice by slice.

    The stick is not equally sensitive everywhere, so one figure for the whole
    range would call entire bands occupied. The floor is therefore followed along
    the range: a low percentile of every half megahertz, then lowered to the
    smallest value nearby and raised again to the largest of those. That keeps
    steps in the noise that are wider than `widest_hz` and ignores everything
    narrower, which is every transmission there is, television and mobile phone
    carriers included.
    """
    per_block = max(8, int(block_hz / slice_hz))
    if len(levels) < 2 * per_block:
        return np.full(len(levels), np.percentile(levels, 20) if len(levels) else 0.0)
    blocks = len(levels) // per_block
    low = np.percentile(levels[:blocks * per_block].reshape(blocks, per_block), 20, axis=1)
    reach = max(1, int(widest_hz / (per_block * slice_hz)) // 2)

    def slide(values, pick):
        padded = np.pad(values, reach, mode="edge")
        return pick(np.lib.stride_tricks.sliding_window_view(padded, 2 * reach + 1), axis=1)

    low = slide(slide(low, np.min), np.max)
    centres = (np.arange(blocks) + 0.5) * per_block
    return np.interp(np.arange(len(levels)), centres, low)


def own_oscillator(mhz, width_khz):
    """Is this the stick hearing itself? Its 28.8 MHz crystal shows up on every multiple of that."""
    multiple = round(mhz / 28.8)
    return multiple >= 1 and abs(mhz - multiple * 28.8) <= max(0.03, width_khz / 2000)


def _widen(mask, by=2):
    """A mask with every hit spread to its neighbours: the two tunings do not share exact slices."""
    padded = np.pad(mask, by)
    return np.lib.stride_tricks.sliding_window_view(padded, 2 * by + 1).any(axis=1)


def analyse(freqs, sweeps, slice_hz, tunings=None):
    """The report for a stack of sweeps (one row per sweep).

    tunings says for each sweep which of TUNINGS it was made with.
    """
    sweeps = np.asarray(sweeps)
    floor = noise_floor(np.median(sweeps, axis=0), slice_hz)
    above = sweeps - floor
    occupied = above > THRESHOLD
    share = occupied.mean(axis=0)              # how often each slice was occupied
    peak = above.max(axis=0)
    ghosts = 0
    if tunings is not None:
        tunings = np.asarray(tunings)
        first, second = occupied[tunings == 0], occupied[tunings == 1]
        if len(first) >= 2 and len(second) >= 2:
            # seen with one tuning but never with the other: made by the stick, not received
            real = _widen(first.any(axis=0)) & _widen(second.any(axis=0))
            ghosts = int(np.count_nonzero(np.diff(np.flatnonzero((share > 0) & ~real), prepend=-9) > 1))
            share = np.where(real, share, 0.0)
            peak = np.where(real, peak, 0.0)
    # Noise that lies just at the threshold crosses it now and then without anything
    # happening. Something that really comes and goes also changes its level a lot.
    swing = np.percentile(sweeps, 90, axis=0) - np.percentile(sweeps, 10, axis=0)
    signals = []
    active = np.flatnonzero(share > 0)
    if len(active):
        # neighbouring occupied slices are one signal
        for run in np.split(active, np.flatnonzero(np.diff(active) > 1) + 1):
            strongest = run[np.argmax(peak[run])]
            mhz = float(freqs[strongest]) / 1e6
            service = service_at(mhz)
            steady = share[run].max() >= STEADY and len(sweeps) >= 3
            if not steady and len(sweeps) >= 3 and swing[run].max() < SWING:
                continue   # hovering around the threshold, not a transmission
            kind = service[3] if service else "unknown"
            width_khz = round(len(run) * float(slice_hz) / 1e3, 1)
            own = steady and width_khz <= 100 and own_oscillator(mhz, width_khz)
            signals.append({
                "mhz": round(mhz, 4), "width_khz": width_khz,
                "db": round(float(peak[strongest]), 1), "share": round(float(share[run].max()), 2),
                "steady": bool(steady), "service": "Receiver's own oscillator" if own else service[2] if service else "",
                # always there, narrow, and in a band where people talk: a carrier that does not belong
                "suspect": bool(steady and not own and width_khz <= 50 and kind in ("ham", "talk", "unknown")),
            })
    bands = []
    for low, high, name, kind in SERVICES:
        inside = (freqs >= low * 1e6) & (freqs <= high * 1e6)
        if inside.sum() < 2:
            continue
        mine = [s for s in signals if low <= s["mhz"] <= high]
        bands.append({"name": name, "kind": kind, "from": low, "to": high,
                      "occupied": round(float((share[inside] > 0).mean()) * 100, 1),
                      "signals": len(mine), "steady": sum(s["steady"] for s in mine),
                      "strongest": max(mine, key=lambda s: s["db"])["mhz"] if mine else None})
    centres = []
    for mhz, name in CENTRES:
        top = BLOCKS.get(mhz, mhz)
        reach = max(slice_hz, 7.5e3)   # a channel is wider than one fine slice
        inside = (freqs >= mhz * 1e6 - reach) & (freqs <= top * 1e6 + reach)
        if not inside.any() or mhz * 1e6 < freqs[0] or mhz * 1e6 > freqs[-1]:
            continue
        heard = float(share[inside].max())
        if heard < STEADY and len(sweeps) >= 3 and swing[inside].max() < SWING:
            heard = 0.0
        centres.append({"mhz": mhz, "name": name, "share": round(heard, 2), "db": round(float(peak[inside].max()), 1),
                        # never off in several sweeps is a carrier, not a conversation
                        "steady": bool(heard >= STEADY and len(sweeps) >= 3)})
    by_strength = lambda found: sorted(found, key=lambda s: -s["db"])[:LISTED]
    return {
        "from": round(float(freqs[0]) / 1e6, 4), "to": round(float(freqs[-1]) / 1e6, 4),
        "slice_khz": round(float(slice_hz) / 1e3, 2),
        "sweeps": len(sweeps), "slices": len(freqs), "signals": len(signals), "ghosts": ghosts,
        "floor_db": round(float(floor.mean()), 1),
        "now_and_then": by_strength([s for s in signals if not s["steady"]]),
        "steady": by_strength([s for s in signals if s["steady"] and not s["suspect"]]),
        "suspects": by_strength([s for s in signals if s["suspect"]]),
        "bands": bands, "centres": centres,
    }


def as_text(report):
    """The report as plain text, to keep or pass on."""
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(report["started"]))
    lines = [f"RadioKiosk radio survey, {stamp}",
             f"{report['from']}-{report['to']} MHz in slices of {report['slice_khz']} kHz, "
             f"{report['sweeps']} sweeps in {round(report['seconds'])} s, {report['signals']} signals"
             + (f", {report['ghosts']} left out as made by the receiver itself" if report.get("ghosts") else ""), ""]

    def table(title, signals):
        lines.extend([title, "  MHz         width kHz  dB over noise  share of sweeps  service"])
        lines.extend(f"  {s['mhz']:<11} {s['width_khz']:<10} {s['db']:<14} {round(s['share'] * 100):>3} %"
                     f"            {s['service']}" for s in signals)
        lines.append("  (none)" if not signals else "")

    lines.append("Where activity is expected")
    lines.extend(f"  {c['mhz']:<10} {c['name']:<42} "
                 + ("quiet" if not c["share"] else f"always occupied (a carrier?), {c['db']} dB" if c["steady"]
                    else f"active in {round(c['share'] * 100)} % of the sweeps, {c['db']} dB")
                 for c in report["centres"])
    lines.append("")
    table("On the air now and then (somebody transmitting)", report["now_and_then"])
    table("Narrow and always there where people talk (possible interference)", report["suspects"])
    table("Always there (broadcast, data links)", report["steady"])
    lines.append("Bands")
    lines.extend(f"  {b['from']:>9}-{b['to']:<9} {b['name']:<34} {b['occupied']:>5} % occupied, "
                 f"{b['signals']} signals, {b['steady']} of them always there" for b in report["bands"])
    return "\n".join(lines) + "\n"


class Survey:
    name = "survey"

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.task = None
        self.report = None
        self.progress = None
        self.span = None

    @staticmethod
    def available():
        return shutil.which("rtl_power") is not None

    @staticmethod
    def ranges():
        """What the interface offers: by the kind of stick, without opening it."""
        devices = sdr_devices()
        return ranges_for(bool(devices) and devices[0]["v4"])

    async def start(self, range_id, seconds):
        if range_id not in RANGES:
            raise ValueError("unknown range")
        if not self.available():
            raise RuntimeError("rtl_power is not installed")
        self.core.need_sdr()
        devices = sdr_devices()
        await self.core.stop()
        # now that nothing uses the stick it can be asked what tuner it has
        fitted = ranges_for(devices[0]["v4"], await asyncio.to_thread(rtlsdr.tuner))
        if range_id not in fitted:
            raise RuntimeError("this stick cannot tune to that range")
        self.span = (*fitted[range_id], devices[0]["v4"])
        async with self.core.lock:
            await self.core.take(self)
            self.progress = {"range": range_id, "seconds": seconds, "sweeps": 0, "started": time.time()}
            self.core.update(source=self.name, status="playing", title="Survey", text="", error=None,
                             detail={"survey": dict(self.progress)})
            self.task = asyncio.create_task(self._run(range_id, seconds))

    async def _run(self, range_id, seconds):
        low, high, slice_hz, v4 = self.span
        gain = self.core.gains.known("fm", 29.7)
        started, freqs, sweeps, tunings = time.time(), None, [], []

        async def sweep(part_low, part_high, extra):
            self.proc = await spawn("rtl_power", "-f", f"{part_low:.0f}:{part_high:.0f}:{slice_hz:.0f}", "-i", "1", "-1",
                                    "-g", str(gain), *extra, "-", stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.DEVNULL)
            out, _ = await self.proc.communicate()
            return parse_sweep(out.decode(errors="replace"))

        # always one complete sweep; after that, as many as fit into the time
        while not sweeps or time.time() - started < seconds:
            tuning = len(tunings) % len(TUNINGS)
            if v4 or low >= HF_BELOW:
                sweep_freqs, levels = await sweep(low, high, TUNINGS[tuning])
            else:
                # the part below the tuner's range goes past the tuner, by direct sampling
                parts = [await sweep(low, min(high, HF_BELOW), ["-D", *TUNINGS[tuning]])]
                if high > HF_BELOW:
                    parts.append(await sweep(HF_BELOW, high, TUNINGS[tuning]))
                sweep_freqs, levels = (np.concatenate(column) for column in zip(*parts))
            if not len(levels):
                self.core.fail("rtl_power could not open the SDR stick")
                return
            if freqs is None:
                freqs = sweep_freqs
            if tuning or len(levels) != len(freqs):
                # the other tuning measures slightly different slices: bring it onto the first one's
                levels = np.interp(freqs, sweep_freqs, levels)
            sweeps.append(levels)
            tunings.append(tuning)
            self.progress["sweeps"] = len(sweeps)
            self.core.update(detail={"survey": dict(self.progress)})
        self.report = {"range": range_id, "started": started, "seconds": time.time() - started,
                       **await asyncio.to_thread(analyse, freqs, sweeps, freqs[1] - freqs[0], tunings)}
        self.proc = None
        if self.core.active is self:
            self.core.active = None
            self.core.update(source=None, status="idle", title="", detail={})

    def save(self):
        """Keep the report in the documents folder, as text to read and as JSON to work with."""
        if not self.report:
            raise RuntimeError("there is no report yet")
        folder = documents_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M", time.localtime(self.report["started"]))
        base = folder / f"survey_{stamp}_{self.report['range']}"
        base.with_suffix(".txt").write_text(as_text(self.report), encoding="utf-8")
        base.with_suffix(".json").write_text(json.dumps(self.report, indent=1), encoding="utf-8")
        return str(base.with_suffix(".txt"))

    def on_title(self, title):
        pass

    async def stop(self):
        if self.task and not self.task.done() and self.task is not asyncio.current_task():
            self.task.cancel()
        self.task = None
        proc, self.proc = self.proc, None
        await kill(proc)
