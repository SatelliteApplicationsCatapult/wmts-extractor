import boto3
from botocore.exceptions import ClientError


class S3:
    """Class to handle S3 operations."""

    def __init__(self, key, secret, s3_endpoint, region_name):
        """
        Initialize s3 class.
        Params:
            key           (str): AWS_ACCESS_KEY_ID
            secret        (str): AWS_SECRET_ACCESS_KEY
            s3_endpoint   (str): S3 endpoint URL
            region_name   (str): Region Name
        """
        self.s3_resource = boto3.resource(
            "s3",
            endpoint_url=s3_endpoint,
            verify=False,
            region_name=region_name,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
        )
        self.buckets_exist = []

    def list_objects(self, bucket_name, *, prefix=None, suffix=None, limit=None):
        """
        List objects stored in a bucket.
        Params:
            bucket_name      (str): Bucket name
        Keyword arguments (opt):
            prefix           (str): Filter only objects with specific prefix
                                    default None
            suffix           (str): Filter only objects with specific suffix
                                    default None
            limit            (int): Limit the number of objects returned
                                    default None
        Returns:
            An iterable of ObjectSummary resources
        """
        if prefix:
            objects = list(self.s3_resource.Bucket(bucket_name).objects.filter(Prefix=prefix).limit(limit))
        else:
            objects = list(self.s3_resource.Bucket(bucket_name).objects.all().limit(limit))

        if not objects:
            raise NoObjectError(f'Nothing found with {prefix}*{suffix} in {bucket_name} bucket')

        if suffix:
            return [obj for obj in objects if obj.key.endswith(suffix)]
        else:
            return objects

    def get_object_body(self, bucket_name, object_name):
        """
        Download an object from S3 and return its body.
        Params:
            bucket_name            (str): Bucket name
            object_name            (str): Object name
        """
        try:
            obj = self.s3_resource.Object(bucket_name=bucket_name, key=object_name).get()
            return obj.get('Body').read()
        except ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchKey':
                raise NoObjectError(f'Nothing found with {object_name} in {bucket_name} bucket')

    def put_object(self, bucket_name, key, body):
        try:
            response = self.s3_resource.Object(bucket_name=bucket_name, key=key).put(Body=body)
            return response
        except ClientError as ex:
            return None

    def list_common_prefixes(self, bucket_name, prefix):
        """
        List all common prefixes with the given prefix delimited by '/'.
        Params:
            bucket_name            (str): Bucket name
            prefix                 (str): Prefix
        """
        common_prefixes = []
        paginator = self.s3_resource.meta.client.get_paginator('list_objects')

        for result in paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/'):
            if result.get('CommonPrefixes'):
                common_prefixes = [p.get('Prefix') for p in result.get('CommonPrefixes')]

        return common_prefixes


class NoObjectError(Exception):
    pass

