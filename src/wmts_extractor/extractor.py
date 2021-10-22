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

endpoint_class = {
    "mapserver": MapServer,
    "sentinelhub": SentinelHub,
    "securewatch": SecureWatch
}


class Extractor:

    def __init__(self, config, args):

        """
        constructor
        """

        # create endpoint
        _class = endpoint_class[config.endpoint.name]

        self._endpoint = _class(config.endpoint, args)
        self._downloader = Downloader(config.endpoint)

    def get_tiles(self, config, args):

        """
        search and download wmts tiles collocated with spatiotemporal constraints
        """
        aois = self.get_aois(config.aoi)
        inventory = None

        # check valid aois
        if aois is not None:
            # for each aoi
            for aoi in aois.itertuples():
                # get image inventory collocated with aoi
                inventory = self._endpoint.get_inventory(aoi.geometry)
                if inventory is not None:
                    # apply filter constraints
                    inventory = self.filter_inventory(inventory, args)

        return inventory

    def download_tiles(self, inventory, config, args):
        root_path = os.path.join(args.out_path, config.endpoint.name)
        aois = self.get_aois(config.aoi)
        downloads = 0
        # check valid aois
        if aois is not None:
            # for each aoi
            for aoi in aois.itertuples():
                for record in inventory.itertuples():
                    # construct out pathname
                    out_pathname = os.path.join(root_path, self._endpoint.get_pathname(record, aoi))

                    # check pathname exists or overwrite
                    if not os.path.exists(out_pathname) or args.overwrite:

                        if not os.path.exists(os.path.dirname(out_pathname)):
                            os.makedirs(os.path.dirname(out_pathname))

                        # retrieve images aligned with constraints
                        print(f'downloading : {out_pathname}')
                        self._downloader.process(self._endpoint.get_uri(record),
                                                 aoi,
                                                 args,
                                                 out_pathname)
                        print('... OK!')

                    else:

                        # output file already exists - ignore
                        print(f'output file already exists: {out_pathname}')

                    # check downloads vs max downloads
                    downloads += 1
                    if args.max_downloads is not None and downloads >= args.max_downloads:
                        print(f'... exiting after {downloads} downloads')
                        break

    @staticmethod
    def get_aois(config):

        """
        load aois from file into geodataframe
        """

        # error handling
        aois = []
        try:

            # open geometries pathname
            ds = ogr.Open(config.pathname)
            if ds is not None:

                # convert ogr feature to shapely object
                layer = ds.GetLayer(0)
                for idx, feature in enumerate(layer):
                    # create aoi object
                    config.name = f'aoi-{idx}'
                    aois.append(Aoi.from_ogr_feature(feature, config))
            else:
                # file not found
                raise Exception('pathname not found')

        # error processing aoi feature
        except Exception as e:
            print('AoI Exception {}: -> {}'.format(str(e), config.pathname))
            aois.clear()

        return gpd.GeoDataFrame(aois, crs='EPSG:4326', geometry='geometry') if len(aois) > 0 else None

    def filter_inventory(self, inventory, args):

        """
        filter image inventory on user-defined conditions passed via command line
        """

        if args.period_resolution:

            if not isinstance(args.period_resolution, dict):
                # load config parameters from file
                with open(args.period_resolution, 'r') as f:
                    tr_file = munchify(yaml.safe_load(f))
            else:
                tr_file = args.period_resolution

            number_images = tr_file.get('number_images')
            periods = tr_file.get('periods')
            resolution_indexes = [str(r) for r in tr_file.get('resolutions')]

            start_period = periods[0].get('date_range')[0]
            end_first_period = periods[0].get("date_range")[-1]
            nweights_first_period = len(periods[0].get('weights'))
            end_period = periods[-1].get('date_range')[-1]
            weights = []

            # filter inventory by initial and end date
            inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                  (inventory['acq_datetime'] >= start_period)]

            inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                  (inventory['acq_datetime'] <= end_period)]

            date_index = pd.date_range(start=start_period, end=end_first_period, periods=nweights_first_period)

            weights += periods[0].get('weights')

            for p in periods[1:]:
                date_index = date_index.union(pd.date_range(start=p.get("date_range")[0],
                                                            end=p.get("date_range")[1],
                                                            periods=len(p.get('weights'))))
                weights += p.get('weights')

            period_names = [p.get('name') for p in periods for w in p.get('weights')]

            tr_values = pd.DataFrame([[period_names[i]]+w for i, w in enumerate(weights)], index=date_index,
                                     columns=['Period Name'] + resolution_indexes)

            print("\n\t\tDecision Table")
            print(tr_values)
            print()

            pr_weights = [tr_values.loc[tr_values.truncate(after=dt).index[-1], str(resolution)]
                          if str(resolution) in resolution_indexes else 0
                          for idx, dt, resolution in inventory[['acq_datetime', 'resolution']].itertuples()]

            p_names = [tr_values.loc[tr_values.truncate(after=dt).index[-1], 'Period Name']
                       if str(resolution) in resolution_indexes else 0
                       for idx, dt, resolution in inventory[['acq_datetime', 'resolution']].itertuples()]

            inventory['Weights'] = pr_weights
            inventory['Period Name'] = p_names

            inventory = inventory.sort_values(by='Weights', ascending=False).head(number_images)

        else:

            # apply start datetime condition
            if args.start_datetime is not None:
                inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                      (inventory['acq_datetime'] >= args.start_datetime)]

            # apply end datetime condition
            if args.end_datetime is not None:
                inventory = inventory[(pd.isnull(inventory['acq_datetime'])) |
                                      (inventory['acq_datetime'] <= args.end_datetime)]

            if args.max_resolution is not None:
                inventory = inventory[(pd.isnull(inventory['resolution'])) |
                                      (inventory['resolution'] <= args.max_resolution)]

        # apply max cloud coverage condition
        if args.max_cloud is not None:
            inventory = inventory[(pd.isnull(inventory['cloud_cover'])) |
                                  (inventory['cloud_cover'] <= args.max_cloud)]

        # apply platform condition
        if args.platforms is not None:
            inventory = inventory[(pd.isnull(inventory['platform'])) |
                                  (inventory['platform'].isin(args.platforms))]

        # apply min overlap condition
        if args.overlap is not None:
            inventory = inventory[(pd.isnull(inventory['overlap'])) |
                                  (inventory['overlap'] >= args.overlap)]

        # endpoint specific filtering
        return self._endpoint.filter_inventory(inventory)
