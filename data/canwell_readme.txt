#############################################################
Source: Pascal Buri (pburi@alaska.edu)
Coordinate Reference System (CRS): EPSG:32606 - WGS 84 / UTM zone 6N

### Canwell Area of interest ###
Extent (xmin,ymin,xmax,ymax): 566640,7014060,586830,7029030

### Canwell South Moraine Station ###
Elev.: 982m
DD: 63.35652, -145.65991
UTM: 0567046E  7026013N

### Look Eyrie AWS ###
Elev.: 1588m
DD: 63.32000, -145.60000
UTM: 0570132E  7022009N

### GPS Station Lower Canwell ###
Elev.: 1039m
DD: 63.34132, -145.58132
UTM: 0571015E  7024405N

### GPS Station Middle Canwell ###
Elev.: 1266m
DD: 63.32174, -145.50278
UTM: 0574997E  7022314N

### GPS Station Upper Canwell & (planned) Accumulation Station ###
Elev.: 1564m
DD: 63.30667, -145.38934
UTM: 6V 0580720E  7020772N
#############################################################
Download configuration (2026-11-11)
-----------------------------------
Original EPSG:32606 extent: 566640,7014060,586830,7029030
Geographic extent (W,S,E,N): -145.672969,63.245029,-145.263039,63.383661
Buffer: 12000 m on each UTM side (four nominal 3-km HRRR cells).
Buffered UTM extent: 554640,7002060,598830,7041030
Buffered GRIB_AREA: -145.915909:-145.015718 63.134289:63.493377
Converted with pyproj transform_bounds, densify_pts=101; rounded outward.
GRIB subsetting preserves the native polar-stereographic grid; test: 17 x 15.

Dates refer to UTC model initialization dates, inclusive:
WY2020: 20190801-20200930 (includes August/September spin-up)
WY2021-WY2026: previous October 1 through September 30.
Forecasts: f05,f06,f07 from runs 00,03,...,21 UTC, as in existing f567 data.
Valid times extend 5-7 hours beyond initialization; consumers should select
valid times and distinguish hourly vs run-total APCP accumulations.
Archive: public NOAA AWS archive. Missing originals use next run f02/03/04
with matching valid time, including next UTC date when needed; logged as FILLED.
Unresolved files get .missing markers and entries in missing_forecasts_log.txt.
Completion of the campaign does not imply there are no missing forecasts.

Layout: canwell_domain/f567/WYyyyy/hrrr.YYYYMMDD/*.ak.grib2
Launch/resume: bash canwell_domain/run_canwell_downloads.sh
The runner uses six workers with two wgrib2 threads each, CPU affinity to
half the available logical CPUs (12 of 24 at launch), nice=10, ionice=2:7.
This caps CPU access, not network bandwidth; files are downloaded and
processed one forecast per worker, not whole years in memory.
Existing nonempty completed files are skipped; logs append on restart.
Original supplied script saved as download_hrrrak_canwell.sh.original.
Main log: canwell_domain/download_campaign.log
Process PID: canwell_domain/download_campaign.pid
Stop all campaign processes: kill -- -$(cat canwell_domain/download_campaign.pid)
