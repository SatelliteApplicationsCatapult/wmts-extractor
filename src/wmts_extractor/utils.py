import pandas as pd
import geopandas as gpd
import urllib3
from .s3 import S3
import folium

urllib3.disable_warnings()


class OpenStreetMap:
    def __init__(self, df: gpd.GeoDataFrame, popup_column: str, epsg: int, aoi_file: str):
        self.df = df
        self.map = folium.Map(location=[df.envelope.centroid[0].y, df.envelope.centroid[0].x], zoom_start=10,
                              tiles='CartoDB positron')
        self.popup_column = popup_column
        self.df.to_crs(epsg=epsg)
        self.shp_file = gpd.read_file(aoi_file)

    def show(self):
        tiles_group = folium.FeatureGroup(name="Tiles")
        for _, r in self.df.iterrows():
            # Without simplifying the representation of each borough,
            # the map might not be displayed
            sim_geo = gpd.GeoSeries(r['geometry']).simplify(tolerance=0.001)
            geo_j = sim_geo.to_json()
            geo_j = folium.GeoJson(data=geo_j,
                                   style_function=lambda x: {'weight': 0.5, 'color': 'blue', 'fillColor': 'blue'})
            folium.Popup(r[self.popup_column]).add_to(geo_j)
            geo_j.add_to(tiles_group)

        aoi_group = folium.FeatureGroup(name="AOIs")
        for _, r in self.df.iterrows():
            for idx, feature in self.shp_file.iterrows():
                if r['aoi_name'] == feature['name']:
                    aoi_geo_j = folium.GeoJson(data=feature['geometry'],
                                               style_function=lambda x: {'weight': 1, 'color': 'red',
                                                                         'fillColor': 'red'})
                    folium.Popup(feature['name']).add_to(aoi_geo_j)
                    aoi_geo_j.add_to(aoi_group)

        tiles_group.add_to(self.map)
        aoi_group.add_to(self.map)
        folium.LayerControl().add_to(self.map)

        return self.map


def obtain_decision_table(period_resolution: dict) -> pd.DataFrame:
    """ Return a pandas dataframe table containing the weights relationship between the resolutions and periods of time
    given in the `period_resolution` dictionary.
    """
    periods = period_resolution.get('periods')
    resolution_indexes = [str(r) for r in period_resolution.get('resolutions')]

    start_period = periods[0].get('date_range')[0]
    end_first_period = periods[0].get("date_range")[-1]
    nweights_first_period = len(periods[0].get('weights'))
    weights = []

    date_index = pd.date_range(start=start_period, end=end_first_period, periods=nweights_first_period)

    weights += periods[0].get('weights')

    for p in periods[1:]:
        date_index = date_index.union(pd.date_range(start=p.get("date_range")[0],
                                                    end=p.get("date_range")[1],
                                                    periods=len(p.get('weights'))))
        weights += p.get('weights')

    period_names = [p.get('name') for p in periods for w in p.get('weights')]

    decision_table = pd.DataFrame([[period_names[i]] + w for i, w in enumerate(weights)], index=date_index,
                                  columns=['Period Name'] + resolution_indexes)

    return decision_table


def upload_to_s3(file: str, endpoint: str, bucket: str, key_id: str, access_key: str, key: str) -> int:
    """ Upload the given file to s3 bucket given: endpoint, bucket, key_id, access_key and key
     Return HTTP Status Code
    """
    s3 = S3(key=key_id, secret=access_key, s3_endpoint=endpoint, region_name=None)

    with open(file, 'rb') as f:
        response = s3.put_object(
            bucket_name=bucket,
            key=key,
            body=f
        )

    return response.get('ResponseMetadata').get('HTTPStatusCode')


def filter_tiles_by_pr_table(tiles, pr_table, number_images_per_period):
    """
    It will compare each element in the tiles table and assign a weight based on the resolution and time period.
    After that, it will filter for each period in each AOI and select the best `number_images_per_period` images for
    each of them.
    """
    filtered_pr_tiles = []

    resolution_indexes = list(pr_table.columns[1:].values)

    pr_weights = [pr_table.loc[pr_table.truncate(after=dt).index[-1], str(resolution)]
                  if str(resolution) in resolution_indexes else None
                  for idx, dt, resolution in tiles[['acq_datetime', 'resolution']].itertuples()]

    p_names = [pr_table.loc[pr_table.truncate(after=dt).index[-1], 'Period Name']
               if str(resolution) in resolution_indexes else None
               for idx, dt, resolution in tiles[['acq_datetime', 'resolution']].itertuples()]

    tiles['weights'] = pr_weights
    tiles['period'] = p_names

    for aoi_name in tiles.aoi_name.unique():
        for period in tiles.period.unique():
            filtered_pr_tiles.append(
                tiles.loc[(tiles.period == period) &
                          (tiles.aoi_name == aoi_name)].sort_values(by='weights',
                                                                    ascending=False).head(number_images_per_period))

    return gpd.GeoDataFrame(pd.concat(filtered_pr_tiles, ignore_index=True))
