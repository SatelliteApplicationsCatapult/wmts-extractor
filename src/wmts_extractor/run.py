import argparse
from datetime import datetime
from pathlib import Path

import os
import yaml

from .utils import upload_to_s3
from .extractor import Extractor


def valid_date_time_argument(arg):
    """
    parse custom argparse *date* type
    """

    try:
        # attempt to parse arg string into datetime obj
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
    parser.add_argument('--options', help='output image creation options', default="-f COG")
    parser.add_argument('--prettify_table', help='Prints table nicely', default=None)

    parser.add_argument('--s3', action='store_true', help='Upload downloaded images to S3')
    parser.add_argument('-s3_endpoint', help='S3 Endpoint', default='https://s3-uk-1.sa-catapult.co.uk')
    parser.add_argument('-s3_bucket', help='S3 Bucket', default='public-eo-data')
    parser.add_argument('-s3_root_key', help='S3 root key', default=None)
    parser.add_argument('-s3_key_id', help='S3 key ID', default=None)
    parser.add_argument('-s3_access_key', help='S3 Access key', default=None)

    return parser.parse_args(args)


def cli():
    """
    main path of execution
    """

    # parse arguments
    args = parse_arguments()

    # load config parameters from file
    with open(args.config_file, 'r') as f:
        config = yaml.safe_load(f)

    try:
        # extract tiles coincident with point geometries
        obj = Extractor(config, args)
        tiles = obj.get_tiles()
        tiles = obj.filter_tiles(tiles)

        print(tiles.loc[:, tiles.columns != 'geometry'])

        if not args.info_only:
            print("Downloading tiles...")
            for file in obj.download_tiles(tiles):
                print(f"Downloaded completed for {file}")
                if args.s3:

                    if args.s3_root_key:
                        # Generate a key with (root_key)/(endpoint_name)/(AOI ID)/(platform)/(Datetime)/(Output Image)
                        key = f"{args.s3_root_key}/{Path(*Path(file).parts[-5:])}"
                    else:
                        # Generate a key with (endpoint_name)/(AOI ID)/(platform)/(Datetime)/(Output Image)
                        key = str(Path(*Path(file).parts[-5:]))

                    print(f"Uploading to file {args.s3_endpoint}/{args.s3_bucket}/{key}")
                    upload_to_s3(file, args.s3_endpoint, args.s3_bucket, args.s3_key_id, args.s3_access_key, key)

    except Exception as e:
        print(e)


# execute cli
if __name__ == '__main__':
    cli()
