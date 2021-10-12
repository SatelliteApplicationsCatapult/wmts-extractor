import abc


class Endpoint:

    def __init__(self, config, args):
        """
        base class constructor
        """

        # copy args
        self._config = config
        self._args = args

    @abc.abstractmethod
    def get_inventory(self, aoi):
        raise NotImplementedError

    @abc.abstractmethod
    def get_uri(self, record):
        raise NotImplementedError

    @abc.abstractmethod
    def get_pathname(self, record, aoi):
        raise NotImplementedError

    @abc.abstractmethod
    def filter_inventory(self, inventory):
        raise NotImplementedError
