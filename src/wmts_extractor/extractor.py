import os
import yaml

import geopandas as gpd
import pandas as pd
from .aoi import Aoi
from .downloader import Downloader
from osgeo import ogr
from munch import munchify

from .endpoint.mapserver import MapServer
from .endpoint.sentinelhub import SentinelHub
from .endpoint.securewatch import SecureWatch
from .utils import obtain_decision_table

endpoint_class = {
    "mapserver": MapServer,
    "sentinelhub": SentinelHub,
    "securewatch": SecureWatch
}


class Extractor:

    def __init__(self, config: dict, args):

        """
        constructor
        """

        # create endpoint
        _class = endpoint_class[config.get('endpoint').get('name')]

        self._endpoint = _class(munchify(config.get('endpoint')), munchify(args))
        self._downloader = Downloader(munchify(config.get('endpoint')))

        self._config = munchify(config)
        self._args = munchify(args)

        self._aoi = munchify(config.get('aoi'))

    def get_tiles(self):

        """
        search and download wmts tiles collocated with spatiotemporal constraints
        """
        try:
            aois = self.get_aois()
            inventory = None
            # check valid aois
            if aois is not None:
                # for each aoi
                for aoi in aois.itertuples():
                    # get image inventory collocated with aoi
                    inventory = self._endpoint.get_inventory(aoi.geometry)
                    if inventory is not None:
                        # apply filter constraints
                        inventory = self.filter_inventory(inventory)

        except Exception as e:
            raise e

        return inventory

    def download_tiles(self, inventory):
        root_path = os.path.join(self._args.out_path, self._config.endpoint.name)
        aois = self.get_aois()
        downloads = 0
        # check valid aois
        if aois is not None:
            # for each aoi
            for aoi in aois.itertuples():
                for record in inventory.itertuples():
                    # construct out pathname
                    out_pathname = os.path.join(root_path, self._endpoint.get_pathname(record, aoi))

                    # check pathname exists or overwrite
                    if not os.path.exists(out_pathname) or self._args.overwrite:

                        if not os.path.exists(os.path.dirname(out_pathname)):
                            os.makedirs(os.path.dirname(out_pathname))

                        # retrieve images aligned with constraints
                        print(f'downloading : {out_pathname}')
                        self._downloader.process(self._endpoint.get_uri(record),
                                                 aoi,
                                                 self._args,
                                                 out_pathname)
                        print('... OK!')

                    else:

                        # output file already exists - ignore
                        print(f'output file already exists: {out_pathname}')

                    # check downloads vs max downloads
                    downloads += 1
                    if self._args.max_downloads is not None and downloads >= self._args.max_downloads:
                        print(f'... exiting after {downloads} downloads')
                        break

    def get_aois(self):

        """
        load aois from file into geodataframe
        """

        # error handling
        aois = []
        try:

            # open geometries pathname
            ds = ogr.Open(self._aoi.pathname)
            if ds is not None:

                # convert ogr feature to shapely object
                layer = ds.GetLayer(0)
                for idx, feature in enumerate(layer):
                    # create aoi object
                    self._aoi.name = f'aoi-{idx}'
                    aois.append(Aoi.from_ogr_feature(feature, self._aoi))
            else:
                # file not found
                raise Exception('pathname not found')

        # error processing aoi feature
        except Exception as e:
            print('AoI Exception {}: -> {}'.format(str(e), self._aoi.pathname))
            aois.clear()

        return gpd.GeoDataFrame(aois, crs='EPSG:4326', geometry='geometry') if len(aois) > 0 else None

    def filter_inventory(self, inventory):

        """
        filter image inventory on user-defined conditions passed via command line
        """

        if self._args.period_resolution:

            if not isinstance(self._args.period_resolution, dict):
                # load config parameters from file
                with open(self._args.period_resolution, 'r') as f:
                    period_resolution = munchify(yaml.safe_load(f))
            else:
                period_resolution = self._args.period_resolution

            # filter inventory by initial and end date
            start_period = period_resolution.get('periods')[0].get('date_range')[0]
            end_period = period_resolution.get('periods')[-1].get('date_range')[-1]

            inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                  (inventory['acq_datetime'] >= start_period)]

            inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                  (inventory['acq_datetime'] <= end_period)]

            decision_table = obtain_decision_table(period_resolution)
            resolution_indexes = [str(r) for r in period_resolution.get('resolutions')]
            number_images = period_resolution.get('number_images')

            pr_weights = [decision_table.loc[decision_table.truncate(after=dt).index[-1], str(resolution)]
                          if str(resolution) in resolution_indexes else 0
                          for idx, dt, resolution in inventory[['acq_datetime', 'resolution']].itertuples()]

            p_names = [decision_table.loc[decision_table.truncate(after=dt).index[-1], 'Period Name']
                       if str(resolution) in resolution_indexes else 0
                       for idx, dt, resolution in inventory[['acq_datetime', 'resolution']].itertuples()]

            inventory['Weights'] = pr_weights
            inventory['Period Name'] = p_names

            inventory = inventory.sort_values(by='Weights', ascending=False).head(number_images)

        else:

            # apply start datetime condition
            if self._args.start_datetime is not None:
                inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                      (inventory['acq_datetime'] >= self._args.start_datetime)]

            # apply end datetime condition
            if self._args.end_datetime is not None:
                inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                      (inventory['acq_datetime'] <= self._args.end_datetime)]

            if self._args.max_resolution is not None:
                inventory = inventory[(pd.isnull(inventory['resolution'])) |
                                      (inventory['resolution'] <= self._args.max_resolution)]

        # apply max cloud coverage condition
        if self._args.max_cloud is not None:
            inventory = inventory[(pd.isnull(inventory['cloud_cover'])) |
                                  (inventory['cloud_cover'] <= self._args.max_cloud)]

        # apply platform condition
        if self._args.platforms is not None:
            inventory = inventory[(pd.isnull(inventory['platform'])) |
                                  (inventory['platform'].isin(self._args.platforms))]

        # apply min overlap condition
        if self._args.overlap is not None:
            inventory = inventory[(pd.isnull(inventory['overlap'])) |
                                  (inventory['overlap'] >= self._args.overlap)]

        # endpoint specific filtering
        return self._endpoint.filter_inventory(inventory)
