import argparse
from datetime import datetime

import yaml
from .extractor import Extractor
from munch import munchify


def valid_date_time_argument(arg):
    """
    parse custom argparse *date* type 
    """

    try:
        # attempt to parse arg string into datetime obj
        print(arg)
        return datetime.strptime(arg, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        msg = "Argument ({0}) not valid! Expected format, DD/MM/YYYY HH:MM:SS!".format(arg)
        raise argparse.ArgumentTypeError(msg)


def parse_arguments(args=None):
    """
    parse arguments
    """

    # parse command line arguments
    parser = argparse.ArgumentParser(description='wmts ingestion')

    # mandatory args
    parser.add_argument('config_file', action='store', help='yaml configuration file')
    parser.add_argument('zoom', type=int, action='store', help='zoom level: 1 -> 20')
    parser.add_argument('out_path', action='store', help='root directory for output files')

    # filter options
    parser.add_argument('-s', '--start_datetime', type=valid_date_time_argument, help='start acquisition datetime',
                        default=None)
    parser.add_argument('-e', '--end_datetime', type=valid_date_time_argument, help='end  acquisition datetime',
                        default=None)
    parser.add_argument('-c', '--max_cloud', type=float, help='max cloud cover', default=None)
    parser.add_argument('-f', '--features', nargs='+', help='feature id list', default=None)
    parser.add_argument('-o', '--overlap', type=int, help='minimum percentage overlap ', default=None)
    parser.add_argument('-a', '--aois', nargs='+', help='aoi list', default=None)
    parser.add_argument('-p', '--platforms', nargs='+', help='platforms list', default=None)
    parser.add_argument('-r', '--max_resolution', type=float, help='Max resolution in meters', default=None)
    parser.add_argument('-pr', '--period_resolution', help='weight assigned to a pair time period/resolution by YML')

    parser.add_argument('--overwrite', action='store_true', help='overwrite existing files')
    parser.add_argument('--info_only', action='store_true', help='print available features only')
    parser.add_argument('--max_downloads', type=int, help='max compliant downloads for aoi', default=None)
    parser.add_argument('--dirs', help='path structure', action='store_true', default=None)
    parser.add_argument('--format', help='output image format', default='GTIFF')
    parser.add_argument('--options', help='output image creation options', default="TILED=YES COMPRESS=LZW")
    parser.add_argument('--prettify_table', help='Prints table nicely', default=None)

    return parser.parse_args(args)


def cli():
    """
    main path of execution
    """

    # parse arguments
    args = parse_arguments()

    # load config parameters from file
    with open(args.config_file, 'r') as f:
        config = munchify(yaml.safe_load(f))

    # extract tiles coincident with point geometries
    obj = Extractor(config, args)
    tiles = obj.get_tiles(config, args)

    if args.info_only:
        print(tiles.loc[:, tiles.columns != 'geometry'])
    else:
        obj.download_tiles(tiles, config, args)


# execute cli
if __name__ == '__main__':
    cli()
