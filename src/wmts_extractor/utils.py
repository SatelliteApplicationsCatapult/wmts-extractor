import pandas as pd
import urllib3
from .s3 import S3

urllib3.disable_warnings()


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
