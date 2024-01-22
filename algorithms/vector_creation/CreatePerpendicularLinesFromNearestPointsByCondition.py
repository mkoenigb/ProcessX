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

import processing, math, operator
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsPoint, QgsPointXY, QgsWkbTypes, QgsCoordinateReferenceSystem,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition, QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, QgsProcessingParameterExpression, QgsProcessingParameterEnum, QgsProcessingParameterBoolean)

class CreatePerpendicularLinesFromNearestPointsByCondition(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    MAX_DIST = 'MAX_DIST'
    MAX_NEIGHBORS = 'MAX_NEIGHBORS'
    LINE_LENGTH = 'LINE_LENGTH'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    FIRST_MATCH_ONLY = 'FIRST_MATCH_ONLY'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION2 = 'SOURCE_COMPARE_EXPRESSION2'
    OVERLAY_COMPARE_EXPRESSION = 'OVERLAY_COMPARE_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION2 = 'OVERLAY_COMPARE_EXPRESSION2'
    OPERATION = 'OPERATION'
    OPERATION2 = 'OPERATION2'
    CONCAT_OPERATION = 'CONCAT_OPERATION'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Points'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FIRST_MATCH_ONLY, self.tr('Create perpendicular lines only for first match'), defaultValue = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.OVERLAY_LYR, self.tr('Lines'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_DIST, self.tr('Maximum distance between points and line \n(must evaluate to float or int; 0 or negative number means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_NEIGHBORS, self.tr('Maximum number of neighboring lines \n(must evaluate to int; -1 means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 1))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.LINE_LENGTH, self.tr('Length of perpendicular line \n(must evaluate to float or int; must be greater 0)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 1))
        
        ### Conditionals ###
        parameter_source_compare_expression = QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True)
        parameter_source_compare_expression.setFlags(parameter_source_compare_expression.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_source_compare_expression)
        
        parameter_operation = QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (points in source)'], defaultValue = 0, allowMultiple = False)
        parameter_operation.setFlags(parameter_operation.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_operation)
        
        parameter_overlay_compare_expression = QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION, self.tr('Compare-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True)
        parameter_overlay_compare_expression.setFlags(parameter_overlay_compare_expression.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_overlay_compare_expression)
        
        parameter_concat_operation = QgsProcessingParameterEnum(
                self.CONCAT_OPERATION, self.tr('And / Or a second condition. (To only use one condition, leave this to AND)'), ['AND','OR','XOR','iAND','iOR','iXOR','IS','IS NOT'], defaultValue = 0, allowMultiple = False)
        parameter_concat_operation.setFlags(parameter_concat_operation.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_concat_operation)
        
        parameter_source_compare_expression2 = QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True)
        parameter_source_compare_expression2.setFlags(parameter_source_compare_expression2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_source_compare_expression2)
                
        parameter_operation2 = QgsProcessingParameterEnum(
                self.OPERATION2, self.tr('Second comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (points in source)'], defaultValue = 0, allowMultiple = False)
        parameter_operation2.setFlags(parameter_operation2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_operation2)
        
        parameter_overlay_compare_expression2 = QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True)
        parameter_overlay_compare_expression2.setFlags(parameter_overlay_compare_expression2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_overlay_compare_expression2)
        
        ### Output ###
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Perpendicular Lines')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        #source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context) # Cant use Feature Source due to a bug when reprojecting; see: https://gis.stackexchange.com/questions/450122/qgscoordinatetransform-causes-crash-in-processing-script
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        #overlay_layer = self.parameterAsSource(parameters, self.OVERLAY_LYR, context)
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        max_dist = self.parameterAsExpression(parameters, self.MAX_DIST, context)
        max_dist_expression = QgsExpression(max_dist)
        max_neighbors = self.parameterAsExpression(parameters, self.MAX_NEIGHBORS, context)
        max_neighbors_expression = QgsExpression(max_neighbors)
        line_length = self.parameterAsExpression(parameters, self.LINE_LENGTH, context)
        line_length_expression = QgsExpression(line_length)
        
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        first_match_only = self.parameterAsBool(parameters, self.FIRST_MATCH_ONLY, context)
        
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
        
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        source_compare_expression2 = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION2, context)
        source_compare_expression2 = QgsExpression(source_compare_expression2)
        overlay_compare_expression = self.parameterAsExpression(parameters, self.OVERLAY_COMPARE_EXPRESSION, context)
        overlay_compare_expression = QgsExpression(overlay_compare_expression)
        overlay_compare_expression2 = self.parameterAsExpression(parameters, self.OVERLAY_COMPARE_EXPRESSION2, context)
        overlay_compare_expression2 = QgsExpression(overlay_compare_expression2)
        operation = self.parameterAsInt(parameters, self.OPERATION, context)
        operation2 = self.parameterAsInt(parameters, self.OPERATION2, context)
        concat_operation = self.parameterAsInt(parameters, self.CONCAT_OPERATION, context)
        ops = {
            0: None,
            1: operator.ne,
            2: operator.eq,
            3: operator.lt,
            4: operator.gt,
            5: operator.le,
            6: operator.ge,
            7: operator.is_,
            8: operator.is_not,
            9: operator.contains
            }
        op = ops[operation]
        op2 = ops[operation2]
        cops = {
            0: operator.and_, # None is equal to AND: easier to implement, the second condition then is just '' == '', so always true.
            1: operator.or_,
            2: operator.xor,
            3: operator.iand,
            4: operator.ior,
            5: operator.ixor,
            6: operator.is_,
            7: operator.is_not
            }
        concat_op = cops[concat_operation]
        
        comparisons = False
        if op is not None and op2 is not None:
            comparisons = True
        elif op is None and op2 is None:
            comparisons = False
        elif op is None and op2 is not None:
            op = operator.eq # None is equal to ==: easier to implement, the second condtion then is just '' == '', so always true.
            overlay_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
        elif op2 is None and op is not None:
            op2 = operator.eq # None is equal to ==: easier to implement, the second condtion then is just '' == '', so always true.
            overlay_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
            
        # QgsGeometry.nearestPoint() does return incorrect results when not using a projected CRS.
        if source_layer_vl.crs().isGeographic():
            feedback.reportError('WARNING: Your Pointlayer is in a geographic CRS. It must be in a projected CRS, otherwise the result will be incorrect! Reproject your input and try again.')
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        
        field_name_dict = {
                'cross_line_feature_id_fieldname': 'cross_line_feature_id',
                'cross_line_segment_wkt_fieldname': 'cross_line_segment_wkt',
                'cross_line_segment_angle_fieldname': 'cross_line_segment_angle_degree',
                'intersection_point_wkt_fieldname': 'intersection_point_wkt',
                'distance_point_to_nearest_line_fieldname': 'distance_point_to_nearest_line'
            }
        
        output_layer_fields = source_layer_vl.fields()
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
                                               output_layer_fields, QgsWkbTypes.LineString, # LineString = 2
                                               source_layer_vl.sourceCrs())
        
        if comparisons:
            if source_layer_vl.featureCount() + overlay_layer_vl.featureCount() > 0:
                total = 100.0 / (source_layer_vl.featureCount() + overlay_layer_vl.featureCount())
            else:
                total = 0
        else:
            total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        current = 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Overlay Layer...')
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params, context=context, feedback=feedback)
            overlay_layer_vl = reproject_result['OUTPUT']
            
        if comparisons: # dictonaries are a lot faster than featurerequests; https://gis.stackexchange.com/q/434768/107424
            feedback.setProgressText('Evaluating expressions...')
            overlay_layer_dict = {}
            overlay_layer_dict2 = {}
            overlay_compare_expression_context = QgsExpressionContext()
            overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
            overlay_compare_expression_context2 = QgsExpressionContext()
            overlay_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
            for overlay_feat in overlay_layer_vl.getFeatures():
                current += 1
                if feedback.isCanceled():
                    break
                overlay_compare_expression_context.setFeature(overlay_feat)
                overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                overlay_layer_dict[overlay_feat.id()] = overlay_compare_expression_result 
                overlay_compare_expression_context2.setFeature(overlay_feat)
                overlay_compare_expression_result2 = overlay_compare_expression2.evaluate(overlay_compare_expression_context2)
                overlay_layer_dict2[overlay_feat.id()] = overlay_compare_expression_result2
                feedback.setProgress(int(current * total))
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        overlay_skip = []
        max_dist_expression_context = QgsExpressionContext()
        max_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        max_neighbors_expression_context = QgsExpressionContext()
        max_neighbors_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        line_length_expression_context = QgsExpressionContext()
        line_length_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        if comparisons:
            source_compare_expression_context = QgsExpressionContext()
            source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_compare_expression_context2 = QgsExpressionContext()
            source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for source_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            current += 1
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
                
            if comparisons:
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
            if comparisons:
                doit_counter = 0
                nearest_lines = overlay_layer_idx.nearestNeighbor(source_feat.geometry().centroid().asPoint(), neighbors = -1, maxDistance = max_dist_expression_result)
            else:
                nearest_lines = overlay_layer_idx.nearestNeighbor(source_feat.geometry().centroid().asPoint(), neighbors = max_neighbors_expression_result, maxDistance = max_dist_expression_result)
            
            for nearest_line_id in nearest_lines:
                if feedback.isCanceled():
                    break
                if nearest_line_id in overlay_skip:
                    continue
                
                doit = True
                if comparisons:
                    if doit_counter >= max_neighbors_expression_result:
                        continue
                    doit = False
                    overlay_compare_expression_result = overlay_layer_dict[nearest_line_id]
                    overlay_compare_expression_result2 = overlay_layer_dict2[nearest_line_id]
                    if concat_op(op(source_compare_expression_result, overlay_compare_expression_result),op2(source_compare_expression_result2, overlay_compare_expression_result2)):
                        doit = True
                        doit_counter += 1
                        
                if not doit:
                    continue
                
                if first_match_only:
                    overlay_skip.append(nearest_line_id)
                    
                nearest_line_geom = overlay_layer_idx.geometry(nearest_line_id)
                point_on_nearest_line = nearest_line_geom.nearestPoint(source_feat.geometry().centroid())
                
                sqrDist, minDistPoint, afterVertex, leftOf = nearest_line_geom.closestSegmentWithContext(point_on_nearest_line.asPoint())
                vertexOnSegment2 = nearest_line_geom.vertexAt(afterVertex)
                vertexOnSegment1 = nearest_line_geom.vertexAt(afterVertex - 1)
                segmentAngle = math.atan2(vertexOnSegment2.x() - vertexOnSegment1.x(), vertexOnSegment2.y() - vertexOnSegment1.y())
                segmentAngleDegree = math.degrees(segmentAngle) if segmentAngle > 0 else math.degrees(segmentAngle) + 180
                segmentgeom = QgsGeometry.fromPolyline([vertexOnSegment1,vertexOnSegment2])
                perpendicularLinePoint1 = QgsPoint(point_on_nearest_line.asPoint().project(line_length_expression_result,segmentAngleDegree+90))
                perpendicularLinePoint2 = QgsPoint(point_on_nearest_line.asPoint().project(line_length_expression_result,segmentAngleDegree-90))
                perpendicularLineGeom = QgsGeometry.fromPolyline([perpendicularLinePoint1,perpendicularLinePoint2])
                
                new_feat = QgsFeature(output_layer_fields)
                attridx = 0
                for attr in source_feat.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
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
        return CreatePerpendicularLinesFromNearestPointsByCondition()

    def name(self):
        return 'CreatePerpendicularLinesFromNearestPointsByCondition'

    def displayName(self):
        return self.tr('Create Perpendicular Lines from Nearest Points')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
        'This algorithm takes points as source input and creates perpendicular lines on the nearest line by an optional attribute condition. The perpendicular line will be located on the nearest segment and intersect the line layer on the nearest point to the input points.\n '
        'If the input point layer is of type multipoint, the centroids are taken. <b>The point layer must be in a projected CRS, otherwise the result will be incorrect!</b> See PyQGIS documentation for more informations.\n'
        'You can also choose the iteration order of the points and set whether a perpendicular line shall only be created on the first match.\n'
        'As maximum distance, maximum neighbors and line length you may choose an expression or field based on the points layer, so you can set these individually for each point. '
        'If the expression evaluates to an invalid result, the feature will be skipped and no perpendicular line is created.\n'
        'Attribute informations containing the feature id of the nearest line, wkt of the crossed segment, the angle of this segment, the intersection point and the distance from point to nearest line are added to the result.\n'
        'Intentionally this algorithm was designed to create split lines to use in <i>Split with Lines</i> algorithm. For this purpose you may choose a very low line length like 0.000001. But of course there are many other usecases.'
        )