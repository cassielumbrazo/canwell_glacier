# Canwell Glacier

Analysis of Canwell Glacier, Alaska.

Start with [`notebooks/01_canwell_sites_and_hrrr_grid.ipynb`](notebooks/01_canwell_sites_and_hrrr_grid.ipynb):

- Five site locations from Pascal Buri and the supplied UTM zone 6N domain.
- Buffered geographic window used by the HRRR-AK download.
- Satellite basemap of the sites and boundaries, without a temperature overlay.
- One downloaded HRRR-AK 2 m air-temperature field in °C, with native 3 km cell edges and centres.

The copied source text and download configuration are in [`data/canwell_readme.txt`](data/canwell_readme.txt).
Generated maps are saved locally in `figures/` (ignored by Git). Notebook outputs are cleared before committing; rerun the notebook to view its maps.

## Run

Create and activate the repository environment from its root.

```bash
mamba env create -f data/environment.yml
mamba activate canwell_glacier
```

Select the `canwell_glacier` Python environment in your notebook editor.

Run all notebook cells from the repo root or `notebooks/`. The first basemap request requires
internet access; imagery and its georeferencing are then cached locally (excluded from Git).
The Esri World Imagery attribution is included on the exported map; imagery is regional context
and does not represent the forecast timestamp.

The default GRIB is the Canwell subset at:

```
/hdd/snow_hydrology/hrrrak/canwell_domain/f567/WY2020/hrrr.20190801/hrrr.t00z.wrfsfcf05.ak.grib2
```

Set `CANWELL_GRIB` before starting the notebook kernel, or edit `GRIB` in its first cell,
to use another completed local forecast. GRIB data stay outside this repository.
The notebook invokes wgrib2 to decode just the 2 m temperature record; it does not require cfgrib.
Forecast times are UTC. The supplied UTM domain, geographic download window, and actual
whole-cell GRIB footprint are distinct boundaries and are labeled accordingly.

## Combined HRRR-AK NetCDF

Run the converter from the repository root with the `canwell_glacier`
environment active.

```bash
python scripts/process_hrrrak.py
```

The converter reads the Canwell `f567/WY2020` through `f567/WY2026` folders and
writes `data/hrrrak_canwell_f567_WY2020-WY2026.nc`. Use `--source` or `--output`
to override these locations. The output is ignored by Git. The converter decodes
and writes batches directly into one compressed NetCDF on the native 3 km
polar stereographic grid, with latitude and longitude at each grid cell center.
Publication occurs after decoding completes. An existing output causes the
converter to exit.

The time axis uses forecast valid times in UTC and includes the WY2020
August–September 2019 spin-up. `source_water_year` tracks the archive folder.
`forecast_reference_time` and `forecast_hour` use the actual GRIB initialization
and lead, while `requested_forecast_hour` tracks the original requested lead.
`precip_hourly` is the single-hour accumulation ending at valid time.
`precip_total` and `snowfall_total` accumulate from the actual initialization.
The 10 m wind components are relative to the HRRR grid axes.

Open [the HRRR-AK weather notebook](notebooks/02_canwell_hrrrak_weather.ipynb)
with a kernel that has xarray, netCDF4, pandas, and Matplotlib. It checks hourly
coverage, maps the stations and nearest grid cells, and plots a month of weather
at Look Eyrie AWS. Set `CANWELL_NETCDF` to inspect a file written elsewhere.

## Station comparisons

Open [the station comparison notebook](notebooks/03_compare_stations_and_hrrrak.ipynb)
with the `canwell_glacier` kernel. It uses the annual Look Eyrie CSVs in
`data/look_eyrie/`, the Canwell logger export and station README in
`data/canwell_weather_station_data/`, and the combined HRRR-AK NetCDF.
It shows station metadata, nearest cells, and daily and hourly time series for
the overlapping periods. The Canwell logger clock defaults to provisional UTC
and can be changed in the notebook's first code cell.

## Look Eyrie SNOWPACK forcing

With the `canwell_glacier` environment active, run:

```bash
python scripts/create_snowpack_forcing.py
```

This writes two hourly SMETs and a snow-depth evaluation CSV into
`data/snowpack_forcing/look_eyrie/`. Both forcings use the same UTC period
defined by the observed snow-depth and HRRR-AK overlap, from September 9, 2019
18:00 through September 8, 2026 19:00. The station metadata use the supplied
Look Eyrie SMET header (63.32000° N, 145.60000° W, 1,588 m). The nearest HRRR-AK
cell is 1.39 km away at 1,205 m. HRRR-AK temperature is used at its native
value, with no lapse-rate adjustment.

- `look_eyrie_hrrrak.smet` uses the nearest cell for every field. Grid-relative
  wind is rotated to true north and precipitation uses the single-hour accumulation.
- `look_eyrie_station_hrrrak.smet` uses measured air temperature, wind speed
  and direction as a pair, and precipitation where available. Precipitation is
  differenced from consecutive readings of each cumulative gauge, favoring
  gauge 2 when both are valid. Negative increments and jumps above 40 mm in
  one hour are excluded. Gauge undercatch and delayed melt can still affect
  the measured precipitation. HRRR-AK fills missing hours and supplies all
  humidity, radiation, and pressure.
- `look_eyrie_snow_depth.csv` provides hourly NRCS `SNWD.I-1` observations in
  meters, with blanks for gaps. It is kept separate for evaluating simulated
  depth independently. The provisional observations are screened for missing
  codes and negative depths and retain the original reported values otherwise.

The Canwell logger has `DT_Avg` and `TCDT_Avg` distance-like readings, but the
download does not document a calibrated snow-depth series or the snow-free
sensor height needed to derive one.
