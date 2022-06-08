# Author: Mario Königbauer
# License: GNU General Public License v3.0

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsJsonUtils, QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsGeometry, QgsPoint, QgsFields, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterGeometry, QgsProcessingParameterCrs, QgsProcessingParameterField, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterString, QgsProcessingParameterNumber)

class GeometryLayerFromGeojsonStringField(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    GEOJSON_FIELD = 'GEOJSON_FIELD'
    #GEOMETRYTYPE_STRING = 'GEOMETRYTYPE_STRING'
    GEOMETRYTYPE_ENUM = 'GEOMETRYTYPE_ENUM'
    CRS = 'CRS'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):  
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source'), [QgsProcessing.TypeMapLayer])) # Take any source layer, unfortunately no-geometry layers will not be available...
        self.addParameter(
            QgsProcessingParameterField(
                self.GEOJSON_FIELD, self.tr('Field containing the GeoJSON as string'),'GeoJSON','SOURCE_LYR', 1)) # Choose the field containing the GeoJSON as string
        #self.addParameter(
        #    QgsProcessingParameterNumber(
        #        self.GEOMETRYTYPE_STRING, self.tr('Geometry type of the target layer / of the GeoJSON content as number (lookup at https://qgis.org/pyqgis/3.0/core/Wkb/QgsWkbTypes.html)'),0,5)) # Unfortunately there is no WKB-Type-Input available...
        self.addParameter(
            QgsProcessingParameterEnum(
                self.GEOMETRYTYPE_ENUM, self.tr('Geometry type of the target layer / of the GeoJSON content'),
                ['Unknown','Point','LineString','Polygon','MultiPoint','MultiLineString','MultiPolygon','GeometryCollection','CircularString','CompoundCurve','CurvePolygon'],defaultValue=5)) # Only Works because these are ascending numerated in QGIS... NOT A GOOD SOLUTION!! But better than typing in a number by hand... see https://qgis.org/api/classQgsWkbTypes.html
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS, self.tr('CRS of the target layer / of the GeoJSON content'),'EPSG:4326')) # CRS of the targetlayer
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('new_geojson_layer'))) # Output

    def processAlgorithm(self, parameters, context, feedback):
        # Get Parameters and assign to variable to work with
        source_layer = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_geojsonfield = self.parameterAsString(parameters, self.GEOJSON_FIELD, context)
        #wkbgeometrytype = self.parameterAsInt(parameters, self.GEOMETRYTYPE_STRING, context)
        wkbgeometrytype_fromenum = self.parameterAsInt(parameters, self.GEOMETRYTYPE_ENUM, context)
        wkbgeometrytype = wkbgeometrytype_fromenum # testing assignment        
        crsgeometry = self.parameterAsCrs(parameters, self.CRS, context)
        
        total = 100.0 / source_layer.featureCount() if source_layer.featureCount() else 0 # Initialize progress for progressbar
        
        source_fields = source_layer.fields() # get all fields of the sourcelayer
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, source_fields, wkbgeometrytype, crsgeometry)
                                               
        for current, feature in enumerate(source_layer.getFeatures()): # iterate over source 
            # geoj is the string object that contains the GeoJSON
            geoj = feature.attributes()[source_fields.indexFromName(source_geojsonfield)]
            # PyQGIS has a parser class for JSON and GeoJSON
            geojfeats = QgsJsonUtils.stringToFeatureList(geoj, QgsFields(), None)
            # if there are features in the list
            if len(geojfeats) > 0:
                new_geom = geojfeats[0].geometry()
                new_feat = QgsFeature(feature)
                new_feat.setGeometry(new_geom)
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert) # add feature to the output
            
            if feedback.isCanceled(): # Cancel algorithm if button is pressed
                break
            
            feedback.setProgress(int(current * total)) # Set Progress in Progressbar

        return {self.OUTPUT: dest_id} # Return result of algorithm



    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GeometryLayerFromGeojsonStringField()

    def name(self):
        return 'GeometryLayerFromGeojsonStringField'

    def displayName(self):
        return self.tr('New Layer from GeoJSON String')

    def group(self):
        return self.tr('FROM GISSE')

    def groupId(self):
        return 'from_gisse'

    def shortHelpString(self):
        return self.tr('This Algorithm takes a source layer containing a GeoJSON as a String in a field and creates a copy of this layer with the geometry of this GeoJSON field')