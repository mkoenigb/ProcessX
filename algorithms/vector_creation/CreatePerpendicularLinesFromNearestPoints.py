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

import processing, math
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProject, QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsPoint, QgsPointXY, QgsWkbTypes, QgsCoordinateReferenceSystem,  QgsCoordinateTransform,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, QgsProcessingParameterExpression)

class CreatePerpendicularLinesFromNearestPoints(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    OVERLAY_LYR = 'OVERLAY_LYR'
    MAX_DIST = 'MAX_DIST'
    MAX_NEIGHBORS = 'MAX_NEIGHBORS'
    LINE_LENGTH = 'LINE_LENGTH'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Points'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.OVERLAY_LYR, self.tr('Lines'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_DIST, self.tr('Maximum distance between points and line \n(must evaluate to float or int; 0 or negative number means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_NEIGHBORS, self.tr('Maximum number of neighboring lines \n(must evaluate to int; must be greater 0)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 1))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.LINE_LENGTH, self.tr('Length of perpendicular line \n(must evaluate to float or int; must be greater 0)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0.00001))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Perpendicular Lines')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        overlay_layer = self.parameterAsSource(parameters, self.OVERLAY_LYR, context)
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        max_dist = self.parameterAsExpression(parameters, self.MAX_DIST, context)
        max_dist_expression = QgsExpression(max_dist)
        max_neighbors = self.parameterAsExpression(parameters, self.MAX_NEIGHBORS, context)
        max_neighbors_expression = QgsExpression(max_neighbors)
        line_length = self.parameterAsExpression(parameters, self.LINE_LENGTH, context)
        line_length_expression = QgsExpression(line_length)
        
        field_name_dict = {
                'cross_line_feature_id_fieldname': 'cross_line_feature_id',
                'cross_line_segment_wkt_fieldname': 'cross_line_segment_wkt',
                'cross_line_segment_angle_fieldname': 'cross_line_segment_angle_degree',
                'intersection_point_wkt_fieldname': 'intersection_point_wkt',
                'distance_point_to_nearest_line_fieldname': 'distance_point_to_nearest_line'
            }
        
        output_layer_fields = source_layer.fields()
        whilecounter = 0
        while any(elem in field_name_dict.values() for elem in output_layer_fields.names()):
            whilecounter += 1
            for var,name in field_name_dict.items():
                field_name_dict[var] = name + '_2'
            if whilecounter > 9:
                feedback.setProgressText('You should clean up your fieldnames!')
                break
        output_layer_fields.append(QgsField(field_name_dict['cross_line_feature_id_fieldname'], QVariant.Int))
        output_layer_fields.append(QgsField(field_name_dict['cross_line_segment_wkt_fieldname'], QVariant.String))
        output_layer_fields.append(QgsField(field_name_dict['cross_line_segment_angle_fieldname'], QVariant.Double))
        output_layer_fields.append(QgsField(field_name_dict['intersection_point_wkt_fieldname'], QVariant.String))
        output_layer_fields.append(QgsField(field_name_dict['distance_point_to_nearest_line_fieldname'], QVariant.Double))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, 2, # LineString = 2
                                               source_layer.sourceCrs())
                
        source_layer_feature_count = source_layer.featureCount()
        total = 100.0 / source_layer_feature_count if source_layer_feature_count else 0
        
        source_layer_crs = QgsCoordinateReferenceSystem(source_layer_vl.crs().authid())
        overlay_layer_crs = QgsCoordinateReferenceSystem(overlay_layer_vl.crs().authid())
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        feedback.setProgressText('Start processing...')
        max_dist_expression_context = QgsExpressionContext()
        max_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        max_neighbors_expression_context = QgsExpressionContext()
        max_neighbors_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        line_length_expression_context = QgsExpressionContext()
        line_length_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for current, source_feat in enumerate(source_layer.getFeatures()):
            if feedback.isCanceled():
                break
                
            max_dist_expression_context.setFeature(source_feat)
            max_dist_expression_result = max_dist_expression.evaluate(max_dist_expression_context)
            max_neighbors_expression_context.setFeature(source_feat)
            max_neighbors_expression_result = max_neighbors_expression.evaluate(max_neighbors_expression_context)
            line_length_expression_context.setFeature(source_feat)
            line_length_expression_result = line_length_expression.evaluate(line_length_expression_context)
            
            expression_errors = []
            try:
                max_dist_expression_result = float(max_dist_expression_result)
            except:
                expression_errors.append(' an invalid maximum distance expression')
            try:
                max_neighbors_expression_result = int(max_neighbors_expression_result)
                if not max_neighbors_expression_result > 0:
                    expression_errors.append(' an invalid maximum neighbors expression')
            except:
                expression_errors.append(' an invalid maximum neighbors expression')
            try:
                line_length_expression_result = float(line_length_expression_result)
                if not line_length_expression_result > 0:
                    expression_errors.append(' an invalid line length expression')
            except:
                expression_errors.append(' an invalid line length expression')
            
            if expression_errors:
                expression_errors = list(dict.fromkeys(expression_errors))
                feedback.pushWarning('Feature ' + str(source_feat.id()) + ' evaluates to ' + ','.join(expression_errors) + '. Skipping feature.')
                continue
            nearest_lines = overlay_layer_idx.nearestNeighbor(source_feat.geometry().centroid().asPoint(), neighbors = max_neighbors_expression_result, maxDistance = max_dist_expression_result)
            
            for nearest_line_id in nearest_lines:
                
                new_feat = QgsFeature(output_layer_fields)
                attridx = 0
                for attr in source_feat.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
                    
                nearest_line_geom = overlay_layer_idx.geometry(nearest_line_id)
                if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
                    nearest_line_geom.transform(QgsCoordinateTransform(source_layer_crs, overlay_layer_crs, context.transformContext()))
                    
                # WARNING: THIS WILL CRASH QGIS IF A TRANSFORMATION TO EPSG:4326 WAS DONE BEFORE! see: https://gis.stackexchange.com/questions/450122/qgscoordinatetransform-causes-crash-in-processing-script
                point_on_nearest_line = nearest_line_geom.nearestPoint(source_feat.geometry().centroid())
        
                sqrDist, minDistPoint, afterVertex, leftOf = nearest_line_geom.closestSegmentWithContext(point_on_nearest_line.asPoint(),1)
                vertexOnSegment2 = nearest_line_geom.vertexAt(afterVertex)
                vertexOnSegment1 = nearest_line_geom.vertexAt(afterVertex - 1)
                segmentAngle = math.atan2(vertexOnSegment2.x() - vertexOnSegment1.x(), vertexOnSegment2.y() - vertexOnSegment1.y())
                segmentAngleDegree = math.degrees(segmentAngle) if segmentAngle > 0 else math.degrees(segmentAngle) + 180
                segmentgeom = QgsGeometry.fromPolyline([vertexOnSegment1,vertexOnSegment2])
                perpendicularLinePoint1 = point_on_nearest_line.asPoint().project(line_length_expression_result,segmentAngleDegree+90)
                perpendicularLinePoint2 = point_on_nearest_line.asPoint().project(line_length_expression_result,segmentAngleDegree-90)
                perpendicularLineGeom = QgsGeometry.fromPolylineXY([perpendicularLinePoint1,perpendicularLinePoint2])
                
                new_feat.setGeometry(perpendicularLineGeom)
                new_feat[field_name_dict['cross_line_feature_id_fieldname']] = nearest_line_id
                new_feat[field_name_dict['cross_line_segment_wkt_fieldname']] = str(segmentgeom.asWkt())
                new_feat[field_name_dict['cross_line_segment_angle_fieldname']] = segmentAngleDegree
                new_feat[field_name_dict['intersection_point_wkt_fieldname']] = str(point_on_nearest_line.asWkt())
                new_feat[field_name_dict['distance_point_to_nearest_line_fieldname']] = nearest_line_geom.distance(source_feat.geometry().centroid())
                
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

            feedback.setProgress(int(current * total))
        
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreatePerpendicularLinesFromNearestPoints()

    def name(self):
        return 'CreatePerpendicularLinesFromNearestPoints'

    def displayName(self):
        return self.tr('Create Perpendicular Lines from Nearest Points')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
        'This algorithm takes points as source input and creates perpendicular lines on the nearest line. The perpendicular line will be located on the nearest segment and intersect the line layer on the nearest point to the input points.\n '
        'If the input point layer is of type multipoint, the centroids are taken.\n'
        'As maximum distance, maximum neighbors and line length you may choose an expression or field based on the points layer, so you can set these individually for each point. '
        'If the expression evaluates to an invalid result, the feature will be skipped and no perpendicular line is created.\n'
        'Attribute informations containing the feature id of the nearest line, wkt of the crossed segment, the angle of this segment, the intersection point and the distance from point to nearest line are added to the result.\n'
        'Intentionally this algorithm was designed to create split lines to use in <i>Split with Lines</i> algorithm. For this purpose you may choose a very low line length like 0.000001. But of course there are many other usecases.'
        )