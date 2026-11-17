"""Create paired hourly SNOWPACK forcing files for Look Eyrie AWS (SNOTEL 768)."""

import argparse
from pathlib import Path
import re

import numpy as np
import pandas as pd
from pyproj import CRS, Geod, Transformer
import xarray as xr

from station_observations import read_look_eyrie

ROOT = Path(__file__).resolve().parents[1]
LOOK = ROOT / "data" / "look_eyrie"
NETCDF = ROOT / "data" / "hrrrak_canwell_f567_WY2020-WY2026.nc"
OUTPUT = ROOT / "data" / "snowpack_forcing" / "look_eyrie"
FIELDS = ["TA", "RH", "VW", "DW", "ISWR", "ILWR", "PSUM", "P"]
NODATA = -999


def station_location(folder):
    header = (folder / "SMET-HEADER_LookEyrieSta_v1.txt").read_text()
    return {key: float(re.search(rf"^{key} = ([-.0-9]+)", header, re.MULTILINE)[1])
            for key in ("latitude", "longitude", "altitude")}


def hrrr_forcing(netcdf, location):
    with xr.open_dataset(netcdf, engine="netcdf4", decode_timedelta=False) as ds:
        geod = Geod(a=ds.crs.earth_radius, b=ds.crs.earth_radius)
        lat, lon = ds.latitude.values, ds.longitude.values
        _, _, distance = geod.inv(np.full_like(lon, location["longitude"]),
                                  np.full_like(lat, location["latitude"]), lon, lat)
        y, x = np.unravel_index(distance.argmin(), distance.shape)
        cell = ds.isel(y=y, x=x)
        native = CRS.from_cf(ds.crs.attrs)
        inverse = Transformer.from_crs(native, native.geodetic_crs, always_xy=True)
        north_lon, north_lat = inverse.transform(cell.x.item(), cell.y.item() + 1)
        grid_north, _, _ = geod.inv(cell.longitude.item(), cell.latitude.item(),
                                     north_lon, north_lat)
        # Meteorological direction from which the wind blows, relative to true north.
        direction = (np.degrees(np.arctan2(-cell["10u"].values, -cell["10v"].values))
                     + grid_north) % 360
        frame = pd.DataFrame({
            "TA": cell.temp.values, "RH": cell.rh.values / 100, "VW": cell.wind.values,
            "DW": direction, "ISWR": cell.swrad.values.clip(min=0), "ILWR": cell.lwrad.values,
            "PSUM": cell.precip_hourly.values, "P": cell.pressure.values,
        }, index=pd.DatetimeIndex(ds.time.values).tz_localize("UTC"))
        print(f"Nearest HRRR-AK cell (y, x) = ({y}, {x}), {distance[y, x]/1000:.2f} km away, "
              f"elevation {cell.orog.isel(time=0).item():.1f} m")
    return frame


def write_smet(path, forcing, location, source):
    header = {
        "station_id": path.stem,
        "station_name": "Look Eyrie AWS (NRCS SNOTEL 768)",
        **location,
        "nodata": NODATA,
        "tz": 0,
        "source": source,
        "fields": "timestamp " + " ".join(FIELDS),
    }
    with path.open("w") as out:
        out.write("SMET 1.1 ASCII\n[HEADER]\n")
        for key, value in header.items():
            out.write(f"{key} = {value}\n")
        out.write("[DATA]\n")
        forcing.to_csv(out, sep=" ", index_label="timestamp", header=False,
                       float_format="%.5f", date_format="%Y-%m-%dT%H:%M")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netcdf", type=Path, default=NETCDF)
    parser.add_argument("--look-eyrie", type=Path, default=LOOK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    location = station_location(args.look_eyrie)
    observations = read_look_eyrie(args.look_eyrie, max_precip_mm=40)
    snow_depth = observations.snow_depth.dropna()
    if snow_depth.empty:
        raise ValueError("Look Eyrie has no usable snow-depth observations")
    model = hrrr_forcing(args.netcdf, location)
    # Use snow-depth coverage to define the same evaluation period for both forcings.
    start = max(model.index.min(), snow_depth.index.min())
    end = min(model.index.max(), snow_depth.index.max())
    index = pd.date_range(start, end, freq="h", name="timestamp")
    model = model.reindex(index)
    station = observations.reindex(index)
    wind_available = station[["wind", "wind_direction"]].notna().all(axis=1)
    preferred = pd.DataFrame({
        "TA": station.temp + 273.15,
        "VW": station.wind.where(wind_available),
        "DW": station.wind_direction.where(wind_available),
        "PSUM": station.precip_hourly,
    })
    mixed = model.copy()
    mixed[preferred.columns] = preferred.combine_first(model[preferred.columns])

    for name, frame in (("HRRR-AK", model), ("station-first", mixed)):
        if frame.empty or not np.isfinite(frame.to_numpy()).all():
            raise ValueError(f"{name} forcing is empty or has missing/nonfinite values")
        if not frame.RH.between(0, 1).all() or not frame.DW.between(0, 360, inclusive="left").all():
            raise ValueError(f"{name} forcing contains invalid RH or wind direction")
        if not (frame[["VW", "ISWR", "ILWR", "PSUM"]] >= 0).all().all():
            raise ValueError(f"{name} forcing contains negative wind, radiation, or precipitation")
    args.output.mkdir(parents=True, exist_ok=True)
    write_smet(args.output / "look_eyrie_hrrrak.smet", model, location, "Nearest HRRR-AK grid cell")
    write_smet(args.output / "look_eyrie_station_hrrrak.smet", mixed, location,
               "NRCS 768 TA, VW, DW, PSUM with HRRR-AK fallback; HRRR-AK RH, ISWR, ILWR, P")
    station.snow_depth.rename("snow_depth_m").to_csv(
        args.output / "look_eyrie_snow_depth.csv", float_format="%.4f",
        date_format="%Y-%m-%dT%H:%M:%SZ"
    )

    print(f"{len(index):,} hours from {index[0]} to {index[-1]}")
    print(f"{station.snow_depth.count():,} snow-depth observations in that period")
    print("Observed hours used in station-first forcing:")
    print(preferred.count().to_string())
    print(args.output)


if __name__ == "__main__":
    main()
