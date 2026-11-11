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

Use an environment with the dependencies in `environment.yml` and `wgrib2` on PATH.
On this workstation `/opt/anaconda3/envs/envdata/bin/python` already provides the Python dependencies,
and `/usr/local/bin/wgrib2` is available. Select the envdata kernel in your notebook editor.
Alternatively, create the provided environment with `conda env create -f environment.yml`.

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
