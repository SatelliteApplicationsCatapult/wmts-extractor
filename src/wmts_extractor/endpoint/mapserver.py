import os

import geopandas as gpd
import pandas as pd
from .base import Endpoint


class MapServer(Endpoint):

    def __init__(self, config, args):
        """
        constructor
        """

        # initialise base object
        super().__init__(config, args)
        self._prefix = 'tile/1.0.0/World_Imagery/default'

        return

    def get_inventory(self, aoi):
        """
        get catalog entries collocated with area of interest
        """

        # create and append feature record
        records = [{'platform': 'misc',
                    'product': 'default',
                    'acq_datetime': pd.NaT,
                    'cloud_cover': 0.0,
                    'geometry': aoi}]

        return gpd.GeoDataFrame(records, crs='EPSG:4326')

    def get_uri(self, record):
        """
        get template uri for inventory record
        """

        # generate template uri including record feature id
        return "{root}/{prefix}/{tilematrixset}/{{z}}/{{y}}/{{x}}.jpeg".format(root=self._config.uri,
                                                                               prefix=self._prefix,
                                                                               tilematrixset=self._config.tilematrixset)

    def get_pathname(self, record, aoi):
        """
        get pathname 
        """

        # construct pathname
        filename = '{name}_{zoom}_{distance}.tif'.format(name=aoi.name,
                                                         zoom=self._args.zoom,
                                                         distance=aoi.distance)

        return os.path.join(aoi.name, filename)

    def filter_inventory(self, inventory):
        raise NotImplementedError
