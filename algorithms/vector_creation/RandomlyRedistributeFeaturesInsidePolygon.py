# -*- coding: utf-8 -*-
"""
Author: Mario Königbauer (mkoenigb@gmx.de)
(C) 2023 - today by Mario Koenigbauer
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

import processing, random, math
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsPoint, QgsPointXY, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterEnum, QgsProcessingParameterBoolean)

class RandomlyRedistributeFeaturesInsidePolygon(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    ROTATE = 'ROTATE'
    MAX_TRY = 'MAX_TRY'
    HANDLE_MULTIPLE_OVERLAYS = 'HANDLE_MULTIPLE_OVERLAYS'
    OUTPUT = 'OUTPUT'
    OUTPUT_POLYGONS = 'OUTPUT_POLYGONS'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.OVERLAY_LYR, self.tr('Overlay Polygon Layer'), [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ROTATE, self.tr('Also rotate features randomly'), defaultValue = True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_TRY, self.tr('Maximum tries to randomly translate source geometry inside overlay polygon (0 means infinite)'), defaultValue = 0, minValue = 0, type = 0)) # type 0 = Int
        self.addParameter(
            QgsProcessingParameterEnum(
                self.HANDLE_MULTIPLE_OVERLAYS, self.tr('Handle multiple overlays'), ['Take the first overlay polygon only',
                                                                                     'Take a random polygon out of the overlays',
                                                                                     'Build a uniary union polygon of all overlays',
                                                                                     'Build an intersection polygon of all overlays that intersect with the centroid'
                                                                                     ], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Redistributed')))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_POLYGONS, self.tr('Redistribution-Polygons'), createByDefault = False, optional = True))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        overlay_layer = self.parameterAsSource(parameters, self.OVERLAY_LYR, context)
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
        rotate = self.parameterAsBool(parameters, self.ROTATE, context)
        max_try = self.parameterAsInt(parameters, self.MAX_TRY, context)
        handle_multiple_overlays = self.parameterAsInt(parameters, self.HANDLE_MULTIPLE_OVERLAYS, context)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               source_layer.fields(), source_layer.wkbType(),
                                               source_layer.sourceCrs())
        
        (sink2, dest_id2) = self.parameterAsSink(parameters, self.OUTPUT_POLYGONS, context,
                                               source_layer.fields(), QgsWkbTypes.multiType(overlay_layer.wkbType()),
                                               overlay_layer.sourceCrs())
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer = source_layer.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer = overlay_layer.materialize(QgsFeatureRequest(overlay_filter_expression))
                
        source_layer_feature_count = source_layer.featureCount()
        total = 100.0 / source_layer_feature_count if source_layer_feature_count else 0
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        
        feedback.setProgressText('Start processing...')
        for current, source_feat in enumerate(source_layer.getFeatures()):
            if feedback.isCanceled():
                break
                
            new_feat = source_feat
            new_geom = source_feat.geometry()
            overlays = overlay_layer_idx.intersects(source_feat.geometry().boundingBox())
            intersecting_geoms = []
            aborted = False
            overlay_geom = QgsGeometry()
            
            if overlays:
                for overlay_id in overlays:
                    if feedback.isCanceled():
                        break
                    current_overlay_geom = overlay_layer_idx.geometry(overlay_id)
                    if not source_feat.geometry().within(current_overlay_geom):
                        continue
                        
                    if handle_multiple_overlays == 0:
                        overlay_geom = current_overlay_geom
                        break
                    elif handle_multiple_overlays == 3:
                        if current_overlay_geom.intersects(source_feat.geometry().centroid()):
                            intersecting_geoms.append(current_overlay_geom)
                    else:
                        intersecting_geoms.append(current_overlay_geom)
                    
                if handle_multiple_overlays != 0 and intersecting_geoms:
                    if handle_multiple_overlays == 1:
                        overlay_geom = random.choice(intersecting_geoms)
                    if handle_multiple_overlays == 2:
                        overlay_geom = QgsGeometry().unaryUnion(intersecting_geoms)
                    if handle_multiple_overlays == 3:
                        if len(intersecting_geoms) == 1:
                            overlay_geom = intersecting_geoms[0]
                        else:
                            for i, intersecting_geom in enumerate(intersecting_geoms):
                                if i == 0:
                                    overlay_geom = intersecting_geoms[0]
                                else:
                                    overlay_geom = overlay_geom.intersection(intersecting_geom)
                        
                if (not overlay_geom.isNull() or not overlay_geom.isEmpty()) and overlay_geom.isGeosValid():
                    overlay_geom_bbox = overlay_geom.boundingBox()
                    overlay_width = overlay_geom_bbox.width()
                    overlay_height = overlay_geom_bbox.height()
                    overlay_max = math.sqrt((overlay_width**2) + (overlay_height**2))
                    overlay_geometryengine = QgsGeometry.createGeometryEngine(overlay_geom.constGet())
                    overlay_geometryengine.prepareGeometry()
                    inside = False
                    whilecount = 0
                    while inside is False:
                        if feedback.isCanceled():
                            break
                        if whilecount > max_try and max_try > 0:
                            aborted = True
                            break
                        whilecount += 1
                        if whilecount % 10000 == 0:
                            feedback.pushWarning('Trying to redistribute feature ' + str(source_feat.id()) + ' in attempt #' + str(whilecount) + ' now with still no match. Consider cancelling the process or keep waiting.')
                        new_geom = source_feat.geometry()
                        new_geom.translate(dx=random.uniform(overlay_max*-1,overlay_max),dy=random.uniform(overlay_max*-1,overlay_max))
                        if rotate:
                            new_geom.rotate(rotation=random.uniform(0,360),center=QgsPointXY(source_feat.geometry().centroid().asPoint()))
                        if overlay_geometryengine.contains(new_geom.constGet()):
                            inside = True
                            
            if aborted:
                new_geom = source_feat.geometry()
            new_feat.setGeometry(new_geom)
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            
            new_polygon_feat = source_feat
            overlay_geom.convertToMultiType()
            new_polygon_feat.setGeometry(overlay_geom)
            try: # There is no documentation on how to check if an output is optional, so we just use try except to prevent errors if its set to skip
                sink2.addFeature(new_polygon_feat, QgsFeatureSink.FastInsert)
            except:
                pass
            
            feedback.setProgress(int(current * total))
            
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RandomlyRedistributeFeaturesInsidePolygon()

    def name(self):
        return 'RandomlyRedistributeFeaturesInsidePolygon'

    def displayName(self):
        return self.tr('Randomly Redistribute Features inside Polygon')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
        'This algorithm redistributes features randomly inside a given polygon by using translate in x and y direction. You can also choose to rotate the features randomly. '
        'z and m values are not considered. The source layer can be of multi- or singletype and contain points, lines or polygons.\n'
        'You can choose between different methods on how to handle the overlay / polygon features, if the source feature is within multiple overlay polygons.\n'
        'You can also add these polygons used for redistributing the source features as an optional output. This output is set to skip by default.\n'
        'If a feature is not within at least one polygon, its geometry will not be modified.\n'
        'You can also set a limit for the maximum tries of randomly translating the source feature. If no match is found before this limit is exceeded, the source features geometry remain unchanged.\n'
        )