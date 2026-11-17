"""Read the Look Eyrie NRCS annual exports as hourly UTC observations."""

from datetime import timedelta, timezone

import numpy as np
import pandas as pd

LOOK_CLOCK = timezone(timedelta(hours=-8), "YST")


def read_look_eyrie(folder, *, max_precip_mm=None):
    """Return temperature (°C), wind (m/s and degrees), precip (mm), and snow depth (m)."""
    files = sorted(folder.glob("768_ALL_YEAR=*.csv"))
    if not files:
        raise FileNotFoundError(f"No annual Look Eyrie exports in {folder}")
    annual = []
    for path in files:
        with path.open(encoding="utf-8-sig") as source:
            for i, line in enumerate(source):
                if line.startswith("Site Id,"):
                    break
            else:
                raise ValueError(f"Missing NRCS CSV header in {path}")
        raw = pd.read_csv(path, skiprows=i, skipinitialspace=True, na_values=[-99.9, -999])
        raw.columns = raw.columns.str.strip()
        timestamps = pd.to_datetime(raw.Date + " " + raw.Time, errors="coerce")
        raw = raw.loc[timestamps.notna()].copy()
        raw.index = pd.DatetimeIndex(timestamps.dropna()).tz_localize(LOOK_CLOCK).tz_convert("UTC")
        raw = raw.sort_index()
        if raw.index.has_duplicates:
            raise ValueError(f"Repeated observation timestamps in {path}")
        consecutive = raw.index.to_series().diff().eq(pd.Timedelta(hours=1))
        increments = pd.Series(np.nan, index=raw.index)
        for gauge in ("PREC.I-2 (in)", "PREC.I-1 (in)"):
            if gauge in raw:
                change = pd.to_numeric(raw[gauge], errors="coerce").diff() * 25.4
                valid = consecutive & change.ge(0)
                if max_precip_mm is not None:
                    valid &= change.le(max_precip_mm)
                increments = increments.combine_first(change.where(valid))
        wind = pd.to_numeric(raw["WSPDV.H-1 (mph)"], errors="coerce")
        direction = pd.to_numeric(raw["WDIRV.H-1 (degr)"], errors="coerce")
        depth = pd.to_numeric(raw["SNWD.I-1 (in)"], errors="coerce")
        annual.append(pd.DataFrame({
            "temp": pd.to_numeric(raw["TOBS.I-1 (degC)"], errors="coerce"),
            "wind": wind.where(wind.ge(0)) * 0.44704,
            "wind_direction": direction.where(direction.between(0, 360)) % 360,
            "precip_hourly": increments,
            "snow_depth": depth.where(depth.ge(0)) * 0.0254,
        }))
    return pd.concat(annual, verify_integrity=True).sort_index()
