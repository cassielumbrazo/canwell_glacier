"""Convert the Canwell f567 archive to one NetCDF on its native HRRR-AK grid."""

import argparse
from bisect import bisect_right
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from netCDF4 import Dataset
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/hdd/snow_hydrology/hrrrak/canwell_domain/f567")
OUTPUT = ROOT / "data" / "hrrrak_canwell_f567_WY2020-WY2026.nc"
FILE = re.compile(r"hrrr\.t(\d{2})z\.wrfsfcf(0[567])\.ak\.grib2")
EPOCH = datetime(1970, 1, 1)
HOUR = timedelta(hours=1)
TIME_UNITS = "hours since 1970-01-01 00:00:00"
FIELDS = {
    ("PRES", "surface"): ("pressure", "Surface air pressure", "Pa"),
    ("HGT", "surface"): ("orog", "Surface geopotential height", "m"),
    ("TMP", "surface"): ("temp_surface", "Surface temperature", "K"),
    ("TMP", "2 m above ground"): ("temp", "2 m air temperature", "K"),
    ("TMP", "10 m above ground"): ("temp_10m", "10 m air temperature", "K"),
    ("RH", "2 m above ground"): ("rh", "2 m relative humidity", "%"),
    ("RH", "10 m above ground"): ("rh_10m", "10 m relative humidity", "%"),
    ("UGRD", "10 m above ground"): ("10u", "10 m grid-eastward wind", "m s-1"),
    ("VGRD", "10 m above ground"): ("10v", "10 m grid-northward wind", "m s-1"),
    ("PRATE", "surface"): ("precip_rate", "Precipitation rate at valid time", "kg m-2 s-1"),
    ("APCP", "hour"): ("precip_hourly", "Precipitation in the hour ending at valid time", "kg m-2"),
    ("APCP", "run"): ("precip_total", "Precipitation since source forecast initialization", "kg m-2"),
    ("ASNOW", "surface"): ("snowfall_total", "Snowfall depth since source forecast initialization", "m"),
    ("SNOWC", "surface"): ("snow_cover", "Snow cover", "%"),
    ("TCDC", "entire atmosphere"): ("tcc", "Total cloud cover", "%"),
    ("DSWRF", "surface"): ("swrad", "Downward shortwave radiation flux", "W m-2"),
    ("DLWRF", "surface"): ("lwrad", "Downward longwave radiation flux", "W m-2"),
}


def inventory(source):
    forecasts = []
    for year in range(2020, 2027):
        folder = source / f"WY{year}"
        paths = sorted(folder.glob("hrrr.*/*.grib2"))
        if not paths:
            raise ValueError(f"No GRIB files in {folder}")
        for path in paths:
            match = FILE.fullmatch(path.name)
            if not match:
                raise ValueError(f"Unexpected GRIB filename: {path}")
            day = datetime.strptime(path.parent.name, "hrrr.%Y%m%d")
            run, lead = map(int, match.groups())
            forecasts.append((day + (run + lead) * HOUR, year, lead, path))
    forecasts.sort()
    times = np.array([(row[0] - EPOCH) // HOUR for row in forecasts], dtype="i4")
    if np.any(np.diff(times) <= 0):
        raise ValueError("Duplicate forecast valid times")
    return forecasts, times


def wgrib(path, *args):
    return subprocess.run(
        ["wgrib2", str(path), *args], check=True, capture_output=True, text=True,
        env={**os.environ, "OMP_NUM_THREADS": "1"},
    ).stdout


def grid(path):
    info = wgrib(path, "-d", "1", "-checksum", "3", "-grid", "-code_table_3.2")
    if ("polar stereographic" not in info or "output WE:SN" not in info
            or "winds(grid)" not in info or "code table 3.2=6" not in info):
        raise ValueError(info)
    nx, ny = map(int, re.search(r"\((\d+) x (\d+)\)", info).groups())
    lat1, lon1, lat_ts, lon0, dx, dy = map(float, re.search(
        r"lat1 (\S+) lon1 (\S+) latD (\S+) lonV (\S+) dx (\S+) m dy (\S+) m", info
    ).groups())
    radius = 6371229.0
    # Spherical north polar stereographic, with true scale at lat_ts.
    scale = radius * (1 + np.sin(np.deg2rad(lat_ts)))
    rho = scale * np.tan(np.deg2rad((90 - lat1) / 2))
    angle = np.deg2rad(lon1 - lon0)
    x = rho * np.sin(angle) + dx * np.arange(nx)
    y = -rho * np.cos(angle) + dy * np.arange(ny)
    xx, yy = np.meshgrid(x, y)
    lat = 90 - np.rad2deg(2 * np.arctan(np.hypot(xx, yy) / scale))
    lon = (lon0 + np.rad2deg(np.arctan2(xx, -yy)) + 180) % 360 - 180
    attrs = dict(grid_mapping_name="polar_stereographic", latitude_of_projection_origin=90.,
                 straight_vertical_longitude_from_pole=(lon0 + 180) % 360 - 180,
                 standard_parallel=lat_ts, earth_radius=radius, false_easting=0., false_northing=0.)
    return x, y, lat, lon, attrs, re.search(r"sec3_cksum=\d+", info)[0]


def decode(batch, scratch, shape, checksum):
    combined, binary = scratch / "batch.grib2", scratch / "values.bin"
    offsets = []
    with combined.open("wb") as out:
        for _, _, _, path in batch:
            offsets.append(out.tell())
            payload = path.read_bytes()
            if not payload.startswith(b"GRIB") or not payload.endswith(b"7777"):
                raise ValueError(f"Invalid GRIB file: {path}")
            out.write(payload)

    lines = wgrib(combined, "-s", "-vt", "-checksum", "3",
                  "-no_header", "-bin", str(binary)).splitlines()
    values = np.fromfile(binary, dtype="=f4").reshape(len(lines), *shape)
    values[np.abs(values) >= 9.99e20] = np.nan
    fields = {}
    reference = np.full(len(batch), -1, dtype="i4")
    leads = np.zeros(len(batch), dtype="i2")
    seen = set()
    for line, array in zip(lines, values):
        _, offset, init, var, level, period, _, valid, signature = line.split(":")
        i = bisect_right(offsets, int(offset)) - 1
        expected, _, nominal_lead, path = batch[i]
        if signature != checksum:
            raise ValueError(f"Grid changed in {path}: {line}")
        if valid != expected.strftime("vt=%Y%m%d%H"):
            raise ValueError(f"Unexpected valid time in {path}: {line}")
        actual_init = datetime.strptime(init, "d=%Y%m%d%H")
        lead = (expected - actual_init) // HOUR
        init_hour = (actual_init - EPOCH) // HOUR
        if lead not in (nominal_lead, nominal_lead - 3) or reference[i] not in (-1, init_hour):
            raise ValueError(f"Inconsistent forecast initialization in {path}: {line}")
        reference[i], leads[i] = init_hour, lead
        if var == "APCP" and level == "surface":
            if period == f"{lead - 1}-{lead} hour acc fcst":
                level = "hour"
            elif period == f"0-{lead} hour acc fcst":
                level = "run"
            else:
                raise ValueError(f"Unexpected precipitation window in {path}: {line}")
        if var == "ASNOW" and period != f"0-{lead} hour acc fcst":
            raise ValueError(f"Unexpected snowfall window in {path}: {line}")
        if (var, level) not in FIELDS:
            raise ValueError(f"Unexpected GRIB field in {path}: {line}")
        name = FIELDS[var, level][0]
        if (i, name) in seen:
            raise ValueError(f"Duplicate {name} in {path}: {line}")
        seen.add((i, name))
        if name not in fields:
            fields[name] = np.full((len(batch), *shape), np.nan, dtype="f4")
        fields[name][i] = array
    if np.any(reference == -1):
        raise ValueError("A forecast in the batch had no readable records")
    return fields, reference, leads


def write(output, forecasts, times, batch_size):
    x, y, lat, lon, crs, checksum = grid(forecasts[0][3])
    shape = lat.shape
    with TemporaryDirectory(prefix="canwell-grib-") as scratch, Dataset(output, "w") as nc:
        nc.setncatts(dict(
            title="Canwell Glacier HRRR-AK forecasts, source WY2020–WY2026",
            Conventions="CF-1.10", source="NOAA HRRR-AK regional surface forecasts",
            comment="UTC forecast valid times. Includes WY2020 August–September initialization spin-up. "
                    "Missing fields are fill values. Forecast lead and reference time come from the GRIB records.",
        ))
        for dim, size in (("time", len(times)), ("y", len(y)), ("x", len(x))):
            nc.createDimension(dim, size)
        nc.createVariable("crs", "i4").setncatts(crs)

        def coordinate(name, dtype, dims, data, **attrs):
            var = nc.createVariable(name, dtype, dims)
            var.setncatts(attrs)
            var[:] = data

        coordinate("x", "f8", "x", x, standard_name="projection_x_coordinate", units="m")
        coordinate("y", "f8", "y", y, standard_name="projection_y_coordinate", units="m")
        coordinate("latitude", "f8", ("y", "x"), lat, standard_name="latitude", units="degrees_north")
        coordinate("longitude", "f8", ("y", "x"), lon, standard_name="longitude", units="degrees_east")
        coordinate("time", "i4", "time", times, standard_name="time", units=TIME_UNITS)
        coordinate("source_water_year", "i2", "time", [row[1] for row in forecasts],
                   long_name="Download folder water year based on requested initialization date")
        coordinate("requested_forecast_hour", "i2", "time", [row[2] for row in forecasts],
                   long_name="Requested forecast lead", units="h")
        ref = nc.createVariable("forecast_reference_time", "i4", ("time",))
        ref.setncatts(dict(standard_name="forecast_reference_time", units=TIME_UNITS))
        lead = nc.createVariable("forecast_hour", "i2", ("time",))
        lead.setncatts(dict(standard_name="forecast_period", units="h"))

        metadata = {name: (description, units, grib)
                    for (grib, _), (name, description, units) in FIELDS.items()}
        metadata["wind"] = ("10 m wind speed", "m s-1", None)
        counts = dict.fromkeys(metadata, 0)
        for start in range(0, len(times), batch_size):
            stop = min(start + batch_size, len(times))
            section = slice(start, stop)
            fields, ref[section], lead[section] = decode(
                forecasts[section], Path(scratch), shape, checksum
            )
            if {"10u", "10v"} <= fields.keys():
                fields["wind"] = np.hypot(fields["10u"], fields["10v"])
            for name, array in fields.items():
                if name not in nc.variables:
                    description, units, grib = metadata[name]
                    var = nc.createVariable(name, "f4", ("time", "y", "x"),
                                            zlib=True, complevel=1, fill_value=np.float32(np.nan),
                                            chunksizes=(min(batch_size, len(times)), *shape))
                    var.setncatts(dict(long_name=description, units=units, grid_mapping="crs",
                                      coordinates="latitude longitude forecast_reference_time forecast_hour "
                                                  "requested_forecast_hour source_water_year"))
                    if grib:
                        var.GRIB_short_name = grib
                    if name == "wind":
                        var.standard_name = "wind_speed"
                nc[name][section] = array
                counts[name] += np.isfinite(array).any(axis=(1, 2)).sum().item()
            if start == 0 or start // batch_size % 20 == 0 or stop == len(times):
                print(f"Decoded {stop:,}/{len(times):,} forecasts", flush=True)
        print("Hours with data by field:", counts, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Output already exists: {output}")
    forecasts, times = inventory(args.source)
    print(f"Inventory: {len(times):,} forecasts, {np.maximum(np.diff(times) - 1, 0).sum()} missing hours "
          f"between {forecasts[0][0]} and {forecasts[-1][0]} UTC", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".canwell-", dir=output.parent) as staging:
        staged = Path(staging) / output.name
        write(staged, forecasts, times, args.batch_size)
        # Publish atomically, and fail if another run has already published.
        os.link(staged, output)
    print(output)


if __name__ == "__main__":
    main()
