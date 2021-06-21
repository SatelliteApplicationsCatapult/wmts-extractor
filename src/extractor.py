import os
import ogr
import json
import pandas as pd
import geopandas as gpd

from aoi import Aoi
from downloader import Downloader
from shapely.geometry import shape

from endpoint.mapserver import Mapserver
from endpoint.sentinelhub import Sentinelhub
from endpoint.securewatch import Securewatch

class Extractor:

    def __init__( self, config, args ):

        """
        constructor
        """

        # create endpoint 
        _class = globals()[ str( config.endpoint.name ).capitalize() ]  
        
        self._endpoint = _class ( config.endpoint, args )        
        self._downloader = Downloader( config.endpoint )

        return

    
    def process( self, config, args ):

        """
        search and download wmts tiles collocated with spatiotemporal constraints
        """

        # process each feature (raster)
        root_path = os.path.join( args.out_path, config.endpoint.name )
        aois = self.getAoIs( config.aoi )

        # check valid aois
        if aois is not None:
            
            # for each aoi
            for aoi in aois.itertuples():

                # get image inventory collocated with aoi
                inventory = self._endpoint.getInventory( aoi.geometry )
                if inventory is not None:
                
                    self.printInventory( f'Datasets collocated with AoI: {aoi.name}', inventory )

                    # apply filter constraints
                    inventory = self.filterInventory( inventory, args )
                    for record in inventory.itertuples():

                        # construct out pathname
                        out_pathname = os.path.join( root_path, self._endpoint.getPathname( record, aoi ) )
                        
                        # check pathname exists or overwrite 
                        if not os.path.exists( out_pathname ) or args.overwrite:
                    
                            if not os.path.exists( os.path.dirname ( out_pathname ) ):
                                os.makedirs( os.path.dirname ( out_pathname ) )

                            # retrieve images aligned with constraints            
                            print ( f'downloading : {out_pathname}' )
                            self._downloader.process(   self._endpoint.getUri( record ),
                                                        aoi, 
                                                        args, 
                                                        out_pathname )
                            print ( '... OK!' )

                        else:

                            # output file already exists - ignore
                            print ( f'output file already exists: {out_pathname}' )

        return


    def getAoIs( self, config ):

        """
        load aois from file into geodataframe
        """

        # error handling
        aois = []
        try:

            # open geometries pathname
            ds = ogr.Open( config.pathname )
            if ds is not None:

                # convert ogr feature to shapely object
                layer = ds.GetLayer( 0 )
                for idx, feature in enumerate( layer ):
                    
                    # create aoi object
                    config.name = f'aoi-{idx}'
                    aois.append( Aoi.fromOgrFeature( feature, config ) )
            else:
                # file not found
                raise Exception ( 'pathname not found' )

        # error processing aoi feature
        except Exception as e:
            print ( 'AoI Exception {}: -> {}'.format( str( e ), config.pathname ) )
            aois.clear()

        return gpd.GeoDataFrame( aois, crs='EPSG:4326', geometry='geometry' ) if len( aois ) > 0 else None


    def printInventory( self, title, inventory ):

        """
        print inventory of images collocated with aoi
        """

        # set options
        print ( title )
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.expand_frame_repr', False, 'max_colwidth', -1 ):  

            # print all columns apart from geoemetry 
            columns = inventory.columns.to_list()
            columns.remove( 'geometry' )

            print( inventory[ columns ] )

        return


    def filterInventory( self, inventory, args ):

        """
        filter image inventory on user-defined conditions passed via command line
        """

        # apply start datetime condition
        if args.start_datetime is not None:
            inventory = inventory [ ( pd.isnull( inventory[ 'acq_datetime' ] ) ) | 
                                    ( inventory[ 'acq_datetime' ] >= args.start_datetime ) ]

        # apply end datetime condition
        if args.end_datetime is not None:
            inventory = inventory [ ( pd.isnull( inventory[ 'acq_datetime' ] ) ) | 
                                    ( inventory[ 'acq_datetime' ] <= args.end_datetime ) ]

        # apply max cloud coverage condition
        if args.max_cloud is not None:
            inventory = inventory [ ( pd.isnull( inventory[ 'cloud_cover' ] ) ) | 
                                    ( inventory[ 'cloud_cover' ] <= args.max_cloud ) ]

        # apply platform condition
        if args.platforms is not None:
            inventory = inventory [ ( pd.isnull( inventory[ 'platform' ] ) ) | 
                                    ( inventory[ 'platform' ].isin ( args.platforms ) ) ]

        # endpoint specific filtering
        return self._endpoint.filterInventory( inventory )
