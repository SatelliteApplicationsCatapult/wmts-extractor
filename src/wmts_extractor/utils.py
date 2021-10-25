import pandas as pd


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
