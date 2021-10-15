# wmts-extractor

## Overview

This software implements functionality to query MAXAR SecureWatch catalogue and facilitate download of Maxar satellite 
imagery satisfying user-defined spatial and temporal constraints via cost and bandwidth-efficient WMTS end point.

The software utilises a series of standard OGC WFS requests to retrieve metadata of imagery aligned with area of 
interest – point, line and polygon geometries are supported – in any OGR supported file format – 
see: <https://gdal.org/drivers/vector/index.html>. Additional filter parameters may also be specified by the end user 
based on acquisition date, product type, cloud cover, etc. Response from MAXAR SecureWatch WFS end point is subsequently 
parsed to retrieve unique feature identifier of images satisfying user-defined constraints.

For each image identified for download, the software subsequently forwards a series of WMTS requests – with unique 
feature identifier appended to URI – to download each PNG / JPG 256x256 tile aligned with nominated area of interest. 
Having completed downloads, individual tiles are assimilated into a single georeferenced image and copied into datetime 
indexed directory on local file system.

Additionally, this software tool also provides integrated support for sourcing and downloading imagery via additional 
WMTS end points – currently, time series Sentinel-1/2 imagery via Sentinel-Hub and selected base map layers via ESRI 
MapServer services.

## Usage

The software has been deployed using Docker. If you don't have docker installed follow 
[this link](https://docs.docker.com/desktop/windows/install/).

Once installed and running, all you have to do is running the container in interactive mode as 
indicated below:

```powershell
docker run -it -- satapps/wmts-extractor
```

This will download the latest version of `satapps/wmts-extractor` docker image from dockerhub and open a bash session
on your CLI, from which you can start invoking the tool by:

``` bash
wmts-extractor <pathname-to-config-file> <zoom-level> <output-path> [options]
```

The commands described above are the minimum you need to run the tool, but you might need mounting a directory on your
container in order to store the downloaded images from your local filesystem or simply modifying the configuration. For 
more information about bind-mount in docker, visit [this link](https://docs.docker.com/storage/bind-mounts/).

```powershell
docker run -it \
    -v /c/Users/username/wmts-extractor/images:/images \
    -v /c/Users/username/wmts-extractor/cfg:/cfg \
    satapps/wmts-extractor
```

With this command we are mapping our local directory to a docker directory, in this case the folder 
`/c/Users/username/wmts-extractor/images` from your laptop is going to be the same as `/images` in your container, and 
we can see or modify any content of it without having to stop the container.

### Configuration file

The ``pathname-to-config-file`` argument is full pathname of a YAML configuration file specific to this software 
application. The YAML configuration file specifies identity of Digital Globe WMTS end point along with necessary login 
credentials. It also defines full pathname to OGR-supported file defining one or more area of interest geometries. The 
format of template configuration file is shown in the table below:

``` yaml
credentials:
    username: < Catapult email address >
    password: < Password for SecureWatch web portal >
uri:
    service: securewatch
    root: https://securewatch.digitalglobe.com/earthservice/wmtsaccess
    id: < unique 32-character id assigned by Maxar to access services >
    layer: DigitalGlobe:ImageryTileService
    format: png
    tilematrix: EPSG:3857
    profile: Currency_RGB_Profile
aoi:
    pathname: < full pathname to OGR supported file encoding one or more Point, Line or Polygon geometries >
    field: < [optional] data attribute uniquely identifying each geometry feature in nominated AOI file – for example osm_id. Attribute value is appended to output filename / output directory structure – defaults to {GeometryType} {Index} >
    buffer: < Buffering distance in metres added to AOI geometry – for point geometries, buffer distance is utilised to create bounding box centred on nominated point location >
```

### Zoom Level

The ``zoom-level`` argument stipulates an integer value between 1 and maximum zoom level supported by WMTS end point. 
For SecureWatch WMTS end point, maximum zoom level is generally 20. Compromise exists between spatial resolution of 
output imagery and bandwidth / cost overhead of streaming data from denser WMTS tile pyramids.

### Output Path

The ``output-path`` specifies root directory to copy output images – software application creates the following 
sub-directory hierarchy to store output images:

``` text
Output Root Directory
|__AOI Geometry Unique ID
   |__ Datetime
      |__Output Image
```

### Options

List of current command line options supported by the software application:

- **-s, --start_datetime**: Ignore imagery acquired before start datetime – `format DD/MM/YYYY HH:MM:SS`
- **-e, --end_datetime**: Ignore imagery acquired after end datetime – `format DD/MM/YYYY HH:MM:SS`
- **-c, --max_cloud**: Max cloud cover in percentage - `example: 0.5`
- **-f, --features**: Identify imagery for download by specifying list of space-separated, unique feature identifiers 
defined in metadata
- **-o, --overlap**: Minimum percentage overlap - `example: 80`
- **-p, --platforms**: List of space-separated platforms - `example: WorldView-01 GeoEye-01`
- **-r, --max_resolution**: Max resolution in meters - `example: 0.4`
- **-pr, --period_resolution**: File location to [YML file](cfg/period_resolution_filter.yml) containing weights 
assigned to a pair time period/resolution - `example: /cfg/period_resolution_filter.yml` 
More info in the [Appendix](#appendix) section.
- **--overwrite**: Overwrite existing output files – otherwise skip download
- **--info_only**: Print table of metadata field values for imagery satisfying user-defined spatial and temporal 
constraints
- **--max_downloads**: Max compliant downloads for aoi
- **--dirs**: Path structure
- **--format**: Output image format, by default `GTIFF`
- **--options**: Output image creation options, by default `TILED=YES COMPRESS=LZW`

### Typical Usage

Download all available imagery from zoom level 19 tile pyramid hosted by Digital Globe WMTS end point and copy output 
imagery into sub-directories below `/images`

``` bash
# wmts-extractor /cfg/securewatch.yml 19 /images
```

Download all available zoom level 18 imagery for 2018 from Digital Globe WMTS end point and copy output imagery into 
sub-directories below `/images`

``` bash
# wmts-extractor /cfg/securewatch.yml 18 /images -s "01/01/2018 00:00:00" -e "31/12/2018 23:59:59"
```

Retrieve metadata of available zoom level 17 imagery for 2019 and display on command line:

``` bash
# wmts-extractor /cfg/securewatch.yml 17 /images -s "01/01/2019 00:00:00" -e "31/12/2019 23:59:59" --info_only
```

## Appendix

### Period Resolution filter (-pr)

This filter has been added to fill a recurrent use case where the user needs a filtered list of products under a complex
criteria based on periods of time and resolution.

To do this, we have to design a bi-dimensional table that relates a pair of `time periods` and `resolution` values by 
what we call `weights`. An example of this table can be seen below:

```
            Period Name  0.3  0.4  0.5
2011-01-01    Period 1    11   12   13
2012-12-31    Period 1    21   22   23
2014-12-31    Period 1    31   32   33
2015-01-31    Period 2    41   42   43
2016-01-25    Period 2    51   52   53
2017-01-18    Period 2    61   62   63
2018-01-12    Period 2    71   72   73
```

If we pay attention to the first row, we can deduce that for a time period between `2011-01-01` and `2011-01-01` for the
given resolution values (0.3, 0.4 and 0.5) there are some weights assigned with values 11, 12 and 13.

This table as well as the maximum number of images we want to obtain is given by a YML file that can be checked 
[here](cfg/period_resolution_filter.yml).

The result of this filter using the [example config file for securewatch](cfg/securewatch.yml):

```bash
# wmts-extractor /cfg/securewatch.yml 18 /images/ -pr /cfg/period_resolution_filter.yml --info_only

                Decision Table
           Period Name  0.3  0.4  0.5
2011-01-01    Period 1   11   12   12
2012-12-31    Period 1   21   22   23
2014-12-31    Period 1   31   32   33
2015-01-31    Period 2   41   42   43
2016-01-25    Period 2   51   52   53
2017-01-18    Period 2   61   62   63
2018-01-12    Period 2   71   72   73

Datasets collocated with AoI: aoi-0
       platform                               uid                      product        acq_datetime  cloud_cover  resolution     overlap  Weights Period Name
0  WorldView-03  708f35be5cdb8810eff1a91f48420951  Pan Sharpened Natural Color 2017-08-28 07:50:19  0.000000     0.3         100.000000  61       Period 2
1  WorldView-02  4e1a9ad33e8e8867f3198b6cbb1906cf  Pan Sharpened Natural Color 2014-03-10 07:41:54  0.038534     0.5         100.000000  23       Period 1
2  WorldView-03  66c9145994bd1dae337d05708f3c2c8c  Pan Sharpened Natural Color 2014-11-04 07:36:45  0.000000     0.3         50.113704   21       Period 1
3  WorldView-03  9a93bbeb4991fa865fb083809cbf0e63  Pan Sharpened Natural Color 2014-10-21 07:16:16  0.011507     0.3         100.000000  21       Period 1
4  GeoEye-01     f0a5b45e09f868a70e004337488674c7  Pan Sharpened Natural Color 2011-10-23 07:22:39  0.007486     0.4         100.000000  12       Period 1
5  WorldView-02  1ffcacf3ebb20241b067a14b4ffd2786  Pan Sharpened Natural Color 2011-03-10 07:58:48  0.029268     0.4         100.000000  12       Period 1
6  GeoEye-01     95603441945ef85d77d7075e6c806eed  Pan Sharpened Natural Color 2011-03-01 07:26:02  0.498521     0.4         100.000000  12       Period 1
```

**NOTE**: This filter can be used in addition to other filters such as minimum number for overlap (-o) and maximum
number of cloud cover (-c), but will ignore any other related to time periods (-s, -e) or resolution (-r).

```bash
# wmts-extractor /cfg/securewatch.yml 18 /images/ -pr /cfg/period_resolution_filter.yml -o 90 -c 0.1 --info_only

                Decision Table
           Period Name  0.3  0.4  0.5
2011-01-01    Period 1   11   12   12
2012-12-31    Period 1   21   22   23
2014-12-31    Period 1   31   32   33
2015-01-31    Period 2   41   42   43
2016-01-25    Period 2   51   52   53
2017-01-18    Period 2   61   62   63
2018-01-12    Period 2   71   72   73

Datasets collocated with AoI: aoi-0
       platform                               uid                      product        acq_datetime  cloud_cover  resolution  overlap  Weights Period Name
0  WorldView-03  708f35be5cdb8810eff1a91f48420951  Pan Sharpened Natural Color 2017-08-28 07:50:19  0.000000     0.3         100.0    61       Period 2
1  WorldView-02  4e1a9ad33e8e8867f3198b6cbb1906cf  Pan Sharpened Natural Color 2014-03-10 07:41:54  0.038534     0.5         100.0    23       Period 1
2  WorldView-03  9a93bbeb4991fa865fb083809cbf0e63  Pan Sharpened Natural Color 2014-10-21 07:16:16  0.011507     0.3         100.0    21       Period 1
3  GeoEye-01     f0a5b45e09f868a70e004337488674c7  Pan Sharpened Natural Color 2011-10-23 07:22:39  0.007486     0.4         100.0    12       Period 1
4  WorldView-02  1ffcacf3ebb20241b067a14b4ffd2786  Pan Sharpened Natural Color 2011-03-10 07:58:48  0.029268     0.4         100.0    12       Period 1
```