import os
import tempfile
from datetime import datetime

import geopandas as gpd
import pyproj
import xmltodict
from base import Endpoint
from wfs import WfsCatalog
from shapely.geometry import Polygon


class SentinelHub(Endpoint):

    def __init__(self, config, args):

        """
        constructor
        """

        # initialise base object
        super().__init__(config, args)
        self._catalog = Catalog(config, args)

        # create transformations
        self._proj = {'geo': pyproj.Proj('epsg:4326', ellps='WGS84'), 'web': pyproj.Proj('epsg:3857', ellps='WGS84')}
        self._proj['geo2web'] = pyproj.Transformer.from_proj(self._proj['geo'], self._proj['web'])
        self._proj['web2geo'] = pyproj.Transformer.from_proj(self._proj['web'], self._proj['geo'])

        return

    def get_inventory(self, aoi):

        """
        get catalog entries collocated with area of interest
        """

        # get metadata of features (rasters) intersecting aoi
        with tempfile.TemporaryDirectory() as tmp_path:
            # transform latlon to web mercator
            bbox = list(self._proj['geo2web'].transform(aoi.bounds[1], aoi.bounds[0]))
            bbox.extend(list(self._proj['geo2web'].transform(aoi.bounds[3], aoi.bounds[2])))

            features = self._catalog.getFeatures(bbox, tmp_path)

        # for each meta record
        records = []
        for feature in features:
            acq_datetime = datetime.strptime(feature['date'] + ' ' + feature['time'], '%Y-%m-%d %H:%M:%S')
            footprint = self.getFootprint(feature)

            records.append({'platform': feature['id'].split('_')[0],
                            'uid': feature['id'],
                            'cell': feature['id'].split('_')[-2],
                            'product': self._config.layer,
                            'acq_datetime': acq_datetime,
                            'cloud_cover': float(feature['cloudCoverPercentage']),
                            'geometry': footprint,
                            'overlap': (aoi.intersection(footprint).area / aoi.area) * 100})

        return gpd.GeoDataFrame(records, crs='EPSG:4326')

    def get_uri(self, record):

        """
        get template uri for inventory record
        """

        # generate template uri including record feature id
        return '{uri}/{id}?REQUEST=GetTile&TILEMATRIXSET={tilematrixset}' \
               '&LAYER={layer}' \
               '&MAXCC={max_cloud}' \
               '&FORMAT=image/{format}' \
               '&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}' \
               '&TIME={date}/{date}'.format(uri=self._config.uri,
                                            id=self._config.id,
                                            tilematrixset=self._config.tilematrixset,
                                            layer=self._config.layer,
                                            max_cloud=self._args.max_cloud,
                                            format=self._config.get('format', 'png'),
                                            date=record.acq_datetime.strftime('%Y-%m-%d'))

    def get_pathname(self, record, aoi):

        """
        get pathname 
        """

        # construct unique filename
        out_path = os.path.join(aoi.name, record.acq_datetime.strftime('%Y%m%d_%H%M%S'))
        filename = '{name}_{date}_{zoom}_{distance}_{layer}_{cell}.TIF'.format(name=aoi.name,
                                                                               date=record.acq_datetime.strftime(
                                                                                   '%Y%m%d%H%M%S'),
                                                                               zoom=self._args.zoom,
                                                                               distance=aoi.distance,
                                                                               layer=self._config.layer,
                                                                               cell=record.cell)

        return os.path.join(out_path, filename)

    def get_footprint(self, feature):

        """
        get footprint polygon of gml raster perimeter
        """

        # initialise to null
        polygon = None
        try:

            # convert string to points list
            coords = feature['geometryProperty']['gml:MultiPolygon']['gml:polygonMember']['gml:Polygon'][
                    'gml:outerBoundaryIs']['gml:LinearRing']['gml:coordinates'].replace(',', ' ')

            coords = [float(x) for x in coords.split()]
            it = iter(coords)

            # transform to geographic
            points = list(zip(it, it))
            points = [self._proj['web2geo'].transform(point[0], point[1]) for point in points]
            points = [(point[1], point[0]) for point in points]

            # create shapely polygon
            polygon = Polygon(points)

        except Exception as e:
            print('getFootprint Exception: {}'.format(str(e)))

        return polygon

    def filter_inventory(self, inventory):
        raise NotImplementedError


class Catalog(WfsCatalog):

    def __init__(self, config, args):

        """
        constructor
        """

        # root url of wfs server
        super().__init__(config)
        self._root = 'https://services.sentinel-hub.com/ogc/wfs/{id}?' \
                     'REQUEST=GetFeature&srsName=EPSG:3857&TYPENAMES=DSS2' \
                     '&TIME={start_datetime}/{end_datetime}' \
                     '&MAXCC={max_cloud}' \
                     '&BBOX={{bbox}}'.format(id=config.id,
                                             start_datetime=args.start_datetime.strftime('%Y-%m-%d'),
                                             end_datetime=args.end_datetime.strftime('%Y-%m-%d'),
                                             max_cloud=args.max_cloud)
        return

    def get_features(self, bbox, out_path):

        """
        retrieve features (rasters) coincident with bbox
        """

        features = []

        # append comma separated bbox coords
        uri = self._root.format(bbox=','.join(str(x) for x in bbox))
        try:

            # download feature meta data file 
            self.downloadFeatures(uri, os.path.join(out_path, 'features.xml'))
            with open(os.path.join(out_path, 'features.xml')) as fd:
                doc = xmltodict.parse(fd.read())

                # extract and record feature schemas 
                schemas = self.findItems(doc, 'DSS2')
                for schema in schemas:
                    features.append(schema)

        except Exception as e:
            print('Meta Exception: {}'.format(str(e)))

        return features
