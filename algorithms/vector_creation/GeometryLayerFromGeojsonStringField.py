# -*- coding: utf-8 -*-
"""
Author: Mario Königbauer (mkoenigb@gmx.de)
(C) 2022 - today by Mario Koenigbauer
License: GNU General Public License v3.0

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsJsonUtils, QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsGeometry, QgsPoint, QgsFields, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterGeometry, QgsProcessingParameterCrs, QgsProcessingParameterField, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterString, QgsProcessingParameterNumber)

class GeometryLayerFromGeojsonStringField(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    GEOJSON_FIELD = 'GEOJSON_FIELD'
    GEOMETRYTYPE_ENUM = 'GEOMETRYTYPE_ENUM'
    CRS = 'CRS'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):  
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source')))
        self.addParameter(
            QgsProcessingParameterField(
                self.GEOJSON_FIELD, self.tr('Field containing the GeoJSON as string'),'GeoJSON','SOURCE_LYR', QgsProcessingParameterField.String))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.GEOMETRYTYPE_ENUM, self.tr('Geometry type of the target layer / of the GeoJSON content'),
                ['Unknown','Point','LineString','Polygon','MultiPoint','MultiLineString','MultiPolygon','GeometryCollection','CircularString','CompoundCurve','CurvePolygon'],defaultValue=5)) # Only Works because these are ascending numerated in QGIS... NOT A GOOD SOLUTION!! But better than typing in a number by hand... see https://qgis.org/api/classQgsWkbTypes.html
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS, self.tr('CRS of the target layer / of the GeoJSON content'),'EPSG:4326'))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('new_geojson_layer')))

    def processAlgorithm(self, parameters, context, feedback):
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_geojsonfield = self.parameterAsString(parameters, self.GEOJSON_FIELD, context)
        wkbgeometrytype_fromenum = self.parameterAsInt(parameters, self.GEOMETRYTYPE_ENUM, context)
        wkbgeometrytype = wkbgeometrytype_fromenum
        crsgeometry = self.parameterAsCrs(parameters, self.CRS, context)
        
        total = 100.0 / source_layer.featureCount() if source_layer.featureCount() else 0
        
        source_fields = source_layer.fields()
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, source_fields, wkbgeometrytype, crsgeometry)
                                               
        for current, feature in enumerate(source_layer.getFeatures()):
            if feedback.isCanceled():
                break
            # Thanks to https://gis.stackexchange.com/a/382615/107424
            geoj = feature.attributes()[source_fields.indexFromName(source_geojsonfield)]
            geojfeats = QgsJsonUtils.stringToFeatureList(geoj, QgsFields(), None)
            if len(geojfeats) > 0:
                new_geom = geojfeats[0].geometry()
                new_feat = QgsFeature(feature)
                new_feat.setGeometry(new_geom)
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}



    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GeometryLayerFromGeojsonStringField()

    def name(self):
        return 'GeometryLayerFromGeojsonStringField'

    def displayName(self):
        return self.tr('New Layer from GeoJSON String')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr('This Algorithm takes a source layer containing a GeoJSON as a String in a field and creates a copy of this layer with the geometry of this GeoJSON field')