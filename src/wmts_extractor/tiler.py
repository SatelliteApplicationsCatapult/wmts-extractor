import math


class MercatorTiler(object):
    """
    TMS Global Mercator Profile
    ---------------------------

    Functions necessary for generation of tiles in Spherical Mercator projection,
    EPSG:900913 (EPSG:gOOglE, Google Maps Global Mercator), EPSG:3785, OSGEO:41001.

    Such tiles are compatible with Google Maps, Microsoft Virtual Earth, Yahoo Maps,
    UK Ordnance Survey OpenSpace API, ...
    and you can overlay them on top of base maps of those web mapping applications.
    
    Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

    What coordinate conversions do we need for TMS Global Mercator tiles::

         LatLon      <->       Meters      <->     Pixels    <->       Tile     

     WGS84 coordinates   Spherical Mercator  Pixels in pyramid  Tiles in pyramid
         lat/lon            XY in metres     XY pixels Z zoom      XYZ from TMS 
        EPSG:4326           EPSG:900913                                         
         .----.              ---------               --                TMS      
        /      \     <->     |       |     <->     /----/    <->      Google    
        \      /             |       |           /--------/          QuadTree   
         -----               ---------         /------------/                   
       KML, public         WebMapService         Web Clients      TileMapService

    What is the coordinate extent of Earth in EPSG:900913?

      [-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244]
      Constant 20037508.342789244 comes from the circumference of the Earth in meters,
      which is 40 thousand kilometers, the coordinate origin is in the middle of extent.
      In fact you can calculate the constant as: 2 * math.pi * 6378137 / 2.0
      $ echo 180 85 | gdaltransform -s_srs EPSG:4326 -t_srs EPSG:900913
      Polar areas with abs(latitude) bigger then 85.05112878 are clipped off.

    What are zoom level constants (pixels/meter) for pyramid with EPSG:900913?

      whole region is on top of pyramid (zoom=0) covered by 256x256 pixels tile,
      every lower zoom level resolution is always divided by two
      initialResolution = 20037508.342789244 * 2 / 256 = 156543.03392804062

    What is the difference between TMS and Google Maps/QuadTree tile name convention?

      The tile raster itself is the same (equal extent, projection, pixel size),
      there is just different identification of the same raster tile.
      Tiles in TMS are counted from [0,0] in the bottom-left corner, id is XYZ.
      Google placed the origin [0,0] to the top-left corner, reference is XYZ.
      Microsoft is referencing tiles by a QuadTree name, defined on the website:
      http://msdn2.microsoft.com/en-us/library/bb259689.aspx

    The lat/lon coordinates are using WGS84 datum, yeh?

      Yes, all lat/lon we are mentioning should use WGS84 Geodetic Datum.
      Well, the web clients like Google Maps are projecting those coordinates by
      Spherical Mercator, so in fact lat/lon coordinates on sphere are treated as if
      the were on the WGS84 ellipsoid.
     
      From MSDN documentation:
      To simplify the calculations, we use the spherical form of projection, not
      the ellipsoidal form. Since the projection is used only for map display,
      and not for displaying numeric coordinates, we don't need the extra precision
      of an ellipsoidal projection. The spherical projection causes approximately
      0.33 percent scale distortion in the Y direction, which is not visually noticable.

    How do I create a raster in EPSG:900913 and convert coordinates with PROJ.4?

      You can use standard GIS tools like gdalwarp, cs2cs or gdaltransform.
      All of the tools supports -t_srs 'epsg:900913'.

      For other GIS programs check the exact definition of the projection:
      More info at http://spatialreference.org/ref/user/google-projection/
      The same projection is degined as EPSG:3785. WKT definition is in the official
      EPSG database.

      Proj4 Text:
        +proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0
        +k=1.0 +units=m +nadgrids=@null +no_defs

      Human readable WKT format of EPGS:900913:
         PROJCS["Google Maps Global Mercator",
             GEOGCS["WGS 84",
                 DATUM["WGS_1984",
                     SPHEROID["WGS 84",6378137,298.2572235630016,
                         AUTHORITY["EPSG","7030"]],
                     AUTHORITY["EPSG","6326"]],
                 PRIMEM["Greenwich",0],
                 UNIT["degree",0.0174532925199433],
                 AUTHORITY["EPSG","4326"]],
             PROJECTION["Mercator_1SP"],
             PARAMETER["central_meridian",0],
             PARAMETER["scale_factor",1],
             PARAMETER["false_easting",0],
             PARAMETER["false_northing",0],
             UNIT["metre",1,
                 AUTHORITY["EPSG","9001"]]]
    """

    def __init__(self, tileSize=256):
        """Initialize the TMS Global Mercator pyramid"""
        self._tileSize = tileSize
        self._initialResolution = 2 * math.pi * 6378137 / self._tileSize
        # 156543.03392804062 for tileSize 256 pixels
        self._originShift = 2 * math.pi * 6378137 / 2.0
        # 20037508.342789244

        self._proj = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
        return

    def lat_lon_to_meters(self, lat, lon):
        """Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"""

        mx = lon * self._originShift / 180.0
        my = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)

        my = my * self._originShift / 180.0
        return mx, my

    def meters_to_lat_lon(self, mx, my):
        """Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"""

        lon = (mx / self._originShift) * 180.0
        lat = (my / self._originShift) * 180.0

        lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return lat, lon

    def pixels_to_meters(self, px, py, zoom):
        """Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"""

        res = self.Resolution(zoom)
        mx = px * res - self._originShift
        my = py * res - self._originShift
        return mx, my

    def meters_to_pixels(self, mx, my, zoom):
        """Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"""

        res = self.Resolution(zoom)
        px = (mx + self._originShift) / res
        py = (my + self._originShift) / res
        return px, py

    def pixels_to_tile(self, px, py):
        """Returns a tile covering region in given pixel coordinates"""

        tx = int(math.ceil(px / float(self._tileSize)) - 1)
        ty = int(math.ceil(py / float(self._tileSize)) - 1)
        return tx, ty

    def pixels_to_raster(self, px, py, zoom):
        """Move the origin of pixel coordinates to top-left corner"""

        map_size = self._tileSize << zoom
        return px, map_size - py

    def meters_to_tile(self, mx, my, zoom):
        """Returns tile for given mercator coordinates"""

        px, py = self.meters_to_pixels(mx, my, zoom)
        return self.pixels_to_tile(px, py)

    def tile_bounds(self, tx, ty, zoom):
        """Returns bounds of the given tile in EPSG:900913 coordinates"""

        min_x, min_y = self.pixels_to_meters(tx * self._tileSize, ty * self._tileSize, zoom)
        max_x, max_y = self.pixels_to_meters((tx + 1) * self._tileSize, (ty + 1) * self._tileSize, zoom)
        return min_y, min_x, max_y, max_x

    def tile_lat_lon_bounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in latutude/longitude using WGS84 datum"

        bounds = self.tile_bounds(tx, ty, zoom)
        minLat, minLon = self.meters_to_lat_lon(bounds[0], bounds[1])
        maxLat, maxLon = self.meters_to_lat_lon(bounds[2], bounds[3])

        return (minLat, minLon, maxLat, maxLon)

    def Resolution(self, zoom):
        "Resolution (meters/pixel) for given zoom level (measured at Equator)"

        # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
        return self._initialResolution / (2 ** zoom)

    def ZoomForPixelSize(self, pixelSize):
        """Maximal scaledown zoom of the pyramid closest to the pixelSize."""

        for i in range(30):
            if pixelSize > self.Resolution(i):
                return i - 1 if i != 0 else 0  # We don't want to scale up

    def google_tile(self, tx, ty, zoom):
        """Converts TMS tile coordinates to Google Tile coordinates"""

        # coordinate origin is moved from bottom-left to top-left corner of the extent
        return tx, (2 ** zoom - 1) - ty

    def quad_tree(self, tx, ty, zoom):
        """Converts TMS tile coordinates to Microsoft QuadTree"""

        quad_key = ""
        ty = (2 ** zoom - 1) - ty
        for i in range(zoom, 0, -1):
            digit = 0
            mask = 1 << (i - 1)
            if (tx & mask) != 0:
                digit += 1
            if (ty & mask) != 0:
                digit += 2
            quad_key += str(digit)

        return quad_key

    def lat_lon_to_tile(self, lat, lon, z):
        """Converts latlon to mercator tile coordinates"""

        mx, my = self.lat_lon_to_meters(lat, lon)
        return self.meters_to_tile(mx, my, z)

    # -------------------------------------------------------


# Translates between lat/long and the slippy-map tile
# numbering scheme
# 
# http://wiki.openstreetmap.org/index.php/Slippy_map_tilenames
# 
# Written by Oliver White, 2007
# This file is public-domain
# -------------------------------------------------------
class SlippyTiler:

    def __init__(self, tile_size=256):
        self._tileSize = tile_size
        self._proj = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
        return

    def num_tiles(self, z):
        return math.pow(2, z)

    def sec(self, x):
        return 1.0 / math.cos(x)

    def lat_lon_to_relative_xy(self, lat, lon):
        x = (lon + 180.0) / 360.0
        y = (1.0 - math.log(math.tan(math.radians(lat)) + self.sec(math.radians(lat))) / math.pi) / 2.0
        return x, y

    def lat_lon_to_xy(self, lat, lon, z):
        n = self.num_tiles(z)
        x, y = self.lat_lon_to_relative_xy(lat, lon)
        return n * x, n * y

    def lat_lon_to_tile(self, lat, lon, z):
        x, y = self.lat_lon_to_xy(lat, lon, z)
        return int(x), int(y)

    def xy_to_lat_lon(self, x, y, z):
        n = self.num_tiles(z)
        rel_y = y / n
        lat = self.mercator_to_lat(math.pi * (1 - 2 * rel_y))
        lon = -180.0 + 360.0 * x / n
        return lat, lon

    def lat_bounds(self, y, z):
        n = self.num_tiles(z)
        unit = 1 / n
        rel_y1 = y * unit
        rel_y2 = rel_y1 + unit
        lat1 = self.mercator_to_lat(math.pi * (1 - 2 * rel_y1))
        lat2 = self.mercator_to_lat(math.pi * (1 - 2 * rel_y2))
        return lat1, lat2

    def lon_bounds(self, x, z):
        n = self.num_tiles(z)
        unit = 360 / n
        lon1 = -180 + x * unit
        lon2 = lon1 + unit
        return lon1, lon2

    def tile_bounds(self, x, y, z):
        lat1, lat2 = self.lat_bounds(y, z)
        lon1, lon2 = self.lon_bounds(x, z)
        return lat2, lon1, lat1, lon2  # S,W,N,E

    def mercator_to_lat(self, mercatorY):
        return math.degrees(math.atan(math.sinh(mercatorY)))


if __name__ == "__main__":
    obj = SlippyTiler()
    for z in range(0, 22):
        # x,y = obj.LatLonToTile(51.50610, -0.119888, z)
        x, y = obj.lat_lon_to_tile(15.5527, 48.5164, z)
        x, y = obj.lat_lon_to_tile(12.75108333, 44.89085, z)

        x, y = obj.lat_lon_to_tile(12.749273988762466, 44.88900829538637, z)
        x, y = obj.lat_lon_to_tile(12.76757362, 44.8908577, z)

        s, w, n, e = obj.tile_bounds(x, y, z)
        print("%d: %d,%d --> %1.3f :: %1.3f, %1.3f :: %1.3f" % (z, x, y, s, n, w, e))
