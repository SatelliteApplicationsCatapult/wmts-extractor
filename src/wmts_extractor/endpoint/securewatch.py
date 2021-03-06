import os
import tempfile
from datetime import datetime

import geopandas as gpd
import pandas as pd
import xmltodict
from .base import Endpoint
from .wfs import WfsCatalog
from shapely.geometry import Polygon


class SecureWatch(Endpoint):

    def __init__(self, config, args):

        """
        constructor
        """

        # initialise base object
        super().__init__(config, args)
        self._prefix = '?SERVICE=WMTS&VERSION=1.0.0&STYLE=&REQUEST=GetTile'

        # get uri info and credentials
        self._credentials = config.credentials if 'credentials' in config else None
        self._catalog = Catalog(config)

        # platform info lut
        self._platform = {'WV01': 'WorldView-01',
                          'GE01': 'GeoEye-01',
                          'WV02': 'WorldView-02',
                          'WV03_VNIR': 'WorldView-03',
                          'WV03_SWIR': 'WorldView-03',
                          'QB02': 'Quickbird',
                          'WV04': 'WorldView-04'}

        return

    def get_inventory(self, aoi):

        """
        get catalog entries collocated with area of interest
        """

        # get metadata of features (rasters) intersecting aoi
        with tempfile.TemporaryDirectory() as tmp_path:
            features = self._catalog.get_features(aoi.bounds, tmp_path)

        # for each meta record
        records = []
        for feature in features:
            # create and append feature record
            footprint = self.get_footprint(feature)
            records.append({'platform': self._platform.get(feature['DigitalGlobe:source'], 'Unknown'),
                            'uid': feature['DigitalGlobe:featureId'],
                            'product': feature['DigitalGlobe:productType'],
                            'acq_datetime': datetime.strptime(feature['DigitalGlobe:acquisitionDate'],
                                                              '%Y-%m-%d %H:%M:%S'),
                            'cloud_cover': float(
                                feature['DigitalGlobe:cloudCover']) if 'DigitalGlobe:cloudCover' in feature else None,
                            'resolution': float(feature['DigitalGlobe:groundSampleDistance']),
                            'geometry': footprint,
                            'overlap': (aoi.intersection(footprint).area / aoi.area) * 100})

        return gpd.GeoDataFrame(records, crs='EPSG:4326') if len(records) > 0 else None

    def filter_inventory(self, inventory):

        """
        endpoint specific filtering options
        """

        # apply optional feature id condition
        if self._args.features is not None:
            inventory = inventory[(pd.isnull(inventory['uid'])) |
                                  (inventory['uid'] in self._args.features)]

        return inventory.reset_index(drop=True)

    def get_uri(self, record):

        """
        get template uri for inventory record
        """

        # generate template uri including record feature id
        return "{root}{prefix}&CONNECTID={id}&LAYER={layer}&STYLE=_null&FORMAT=image/{img_format}&TileRow={{" \
               "y}}&TileCol={{x}}&TileMatrixSet={tilematrixset}&TileMatrix={tilematrixset}:{{" \
               "z}}&CQL_FILTER=featureId='{feature_id}'" \
            .format(root=self._config.uri,
                    prefix=self._prefix,
                    img_format=self._config.format,
                    id=self._config.id,
                    layer=self._config.layer,
                    tilematrixset=self._config.tilematrixset,
                    feature_id=record.uid)

    def get_pathname(self, record, aoi):

        """
        get pathname 
        """

        # first section - check null platform
        out_path = aoi.name
        if pd.notnull(record.platform):
            out_path = os.path.join(record.platform, aoi.name) if self._args.dirs == 'platform' else os.path.join(
                aoi.name, record.platform)

        # append acquisition datetime if available
        if pd.notnull(record.acq_datetime):
            out_path = os.path.join(out_path, record.acq_datetime.strftime('%Y%m%d_%H%M%S'))

        # construct unique filename
        filename = '{name}_{date}_{zoom}_{distance}_{uid}.tif'.format(name=aoi.name,
                                                                      date=record.acq_datetime.strftime('%Y%m%d%H%M%S'),
                                                                      zoom=self._args.zoom,
                                                                      distance=aoi.distance,
                                                                      uid=record.uid)

        return os.path.join(out_path, filename)

    @staticmethod
    def get_footprint(feature):

        """
        get footprint polygon of gml raster perimeter
        """

        # initialise to null
        polygon = None
        try:

            # convert string to points list
            coords = [float(x) for x in
                      feature['DigitalGlobe:geometry']['gml:Polygon']['gml:exterior']['gml:LinearRing'][
                          'gml:posList'].split()]
            it = iter(coords)

            points = list(zip(it, it))
            points = [(point[1], point[0]) for point in points]

            # create shapely polygon
            polygon = Polygon(points)

        except Exception as e:
            print('getFootprint Exception: {}'.format(str(e)))

        return polygon


class Catalog(WfsCatalog):

    def __init__(self, config):

        """
        constructor
        """

        # root url of wfs server
        super().__init__(config)
        self._root = 'https://securewatch.digitalglobe.com/catalogservice/wfsaccess?SERVICE=WFS&VERSION=1.1.0' \
                     '&REQUEST=GetFeature&maxFeatures={max_features}&typeName=DigitalGlobe:FinishedFeature&connectid' \
                     '={id}&BBOX={{bbox}}'.format(max_features=config.get('max_features', 500), id=config.id)

        # blacklisted dataset types
        self._blacklist = {'unit': ['DEM'],
                           'source': ['RS2']}

        return

    def get_features(self, bbox, out_path):

        """
        retrieve features (rasters) coincident with bbox
        """

        features = []

        # append comma separated bbox coords and download file from uri
        bbox = (bbox[1], bbox[0], bbox[3], bbox[2])
        uri = self._root.format(bbox=','.join(str(x) for x in bbox))
        try:

            # download feature meta data file 
            self.download_features(uri, os.path.join(out_path, 'features.xml'))
            with open(os.path.join(out_path, 'features.xml')) as fd:
                doc = xmltodict.parse(fd.read())

                # extract and record feature schemas 
                schemas = self.find_items(doc, 'DigitalGlobe:FinishedFeature')
                for schema in schemas[0]:
                    # filter out non-EO datasets / SAR datasets
                    if schema['DigitalGlobe:sourceUnit'] not in self._blacklist['unit'] and \
                            schema['DigitalGlobe:source'] not in self._blacklist['source']:
                        features.append(schema)

        except Exception as e:
            raise RuntimeError('Invalid credentials') from e

        return features
