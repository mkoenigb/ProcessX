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

import processing
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsGeometry, QgsRectangle, QgsWkbTypes, 
                       QgsFeatureSink, QgsProcessingAlgorithm, QgsCoordinateTransform, QgsProject, QgsUnitTypes,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterExtent, QgsProcessingParameterCrs)

class CreatePolygonFromExtent(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    CRS = 'CRS'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT, self.tr('Extent')))
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS, self.tr('Reproject Extent to the following CRS (if unused, the extents origin CRS will be used)'), optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Extent-Polygon')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        extent_rect = self.parameterAsExtent(parameters, self.EXTENT, context)
        extent_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        extent_geom = self.parameterAsExtentGeometry(parameters, self.EXTENT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        
        if not extent_rect.isFinite():
            feedback.reportError('The chosen extent is not finite!', fatalError = True)
        if not extent_crs.isValid():
            feedback.pushWarning('The extent crs is not valid!')
        
        output_layer_fields = QgsFields()
        output_layer_fields.append(QgsField('id', QVariant.Int))
        output_layer_fields.append(QgsField('wkt', QVariant.String))
        output_layer_fields.append(QgsField('centroid', QVariant.String))
        output_layer_fields.append(QgsField('xmin', QVariant.Double))
        output_layer_fields.append(QgsField('xmax', QVariant.Double))
        output_layer_fields.append(QgsField('ymin', QVariant.Double))
        output_layer_fields.append(QgsField('ymax', QVariant.Double))
        output_layer_fields.append(QgsField('crs_authid', QVariant.String))
        #output_layer_fields.append(QgsField('crs_friendlyid', QVariant.String))
        output_layer_fields.append(QgsField('crs_description', QVariant.String))
        output_layer_fields.append(QgsField('crs_units', QVariant.String))
        output_layer_fields.append(QgsField('width', QVariant.Double))
        output_layer_fields.append(QgsField('height', QVariant.Double))
        output_layer_fields.append(QgsField('area', QVariant.Double))
        output_layer_fields.append(QgsField('perimeter', QVariant.Double))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, output_layer_fields, QgsWkbTypes.Polygon, extent_crs)
        feedback.setProgress(0)
        feedback.setProgressText('Start processing...')
        target_crs = extent_crs
        if crs.isValid():
            source_crs = extent_crs
            target_crs = crs
            extent_geom.transform(QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance()))
        
        new_feat = QgsFeature(output_layer_fields)
        new_feat.setGeometry(extent_geom)
        new_feat['id'] = 1
        new_feat['wkt'] = str(extent_geom.asWkt())
        new_feat['centroid'] = extent_geom.centroid().asWkt()
        new_feat['xmin'] = extent_geom.boundingBox().xMinimum()
        new_feat['xmax'] = extent_geom.boundingBox().xMaximum()
        new_feat['ymin'] = extent_geom.boundingBox().yMinimum()
        new_feat['ymax'] = extent_geom.boundingBox().yMaximum()
        new_feat['crs_authid'] = str(target_crs.authid())
        #new_feat['crs_friendlyid'] = str(target_crs.userFriendlyIdentifier())
        new_feat['crs_description'] = str(target_crs.description())
        new_feat['crs_units'] = str(QgsUnitTypes.encodeUnit(target_crs.mapUnits()))
        new_feat['width'] = extent_geom.boundingBox().width()
        new_feat['height'] = extent_geom.boundingBox().height()
        new_feat['area'] = extent_geom.area()
        new_feat['perimeter'] = extent_geom.length()
            
        sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
        feedback.setProgress(1)

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreatePolygonFromExtent()

    def name(self):
        return 'CreatePolygonFromExtent'

    def displayName(self):
        return self.tr('Create Polygon From Extent')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
        'This algorithm takes an extent as input and creates a polygon out of it. You can choose an optional CRS to reproject the extent to.'
        )