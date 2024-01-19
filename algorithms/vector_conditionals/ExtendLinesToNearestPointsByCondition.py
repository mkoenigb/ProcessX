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

import operator, processing
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsPoint, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, 
                       QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingParameterBoolean)

class ExtendLinesToNearestPointsByCondition(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION2 = 'SOURCE_COMPARE_EXPRESSION2'
    POINTS_LYR = 'POINTS_LYR'
    POINTS_FILTER_EXPRESSION = 'POINTS_FILTER_EXPRESSION'
    POINTS_COMPARE_EXPRESSION = 'POINTS_COMPARE_EXPRESSION'
    POINTS_COMPARE_EXPRESSION2 = 'POINTS_COMPARE_EXPRESSION2'
    OPERATION = 'OPERATION'
    OPERATION2 = 'OPERATION2'
    CONCAT_OPERATION = 'CONCAT_OPERATION'
    EXTEND_METHOD = 'EXTEND_METHOD'
    EXTEND_MULTIPLE = 'EXTEND_MULTIPLE'
    EXTEND_DIST = 'EXTEND_DIST'
    MIN_DIST = 'MIN_DIST'
    ALLOW_SELF_CROSSING = 'ALLOW_SELF_CROSSING'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source-Layer (Lines to extend)'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.POINTS_LYR, self.tr('Points to extend lines to (MultiPoints will be casted to SinglePoints; If input is line or polygon their vertices will be used)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.POINTS_FILTER_EXPRESSION, self.tr('Filter-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.EXTEND_METHOD, self.tr('Extend ...'), ['Extend Start of Line',
                                                             'Extend End of Line',
                                                             'Extend Start of Parts (MultiLineStrings only)',
                                                             'Extend End of Parts (MultiLineStrings only)'
                                                            ], defaultValue = [], allowMultiple = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.EXTEND_MULTIPLE, self.tr('Extend to one and the same point more than once?'), ['Use a point as often as it is the nearest match',
                                                                                                'Use a point only once for the whole layer (ordered ascending by feature id or order-by-expression)',
                                                                                                'Use a point only once for the whole feature (ordered descending by vertex id)',
                                                                                                'Use a point only once for the whole part of a multiline feature (ordered descending by part id and vertex id)'
                                                                                               ], defaultValue = [0], allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.EXTEND_DIST, self.tr('Maximum extend distance / distance to nearest points (Must evaluate to float; 0 or negative means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MIN_DIST, self.tr('Extend only if distance to nearest point is greater than X (Must evaluate to float)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ALLOW_SELF_CROSSING, self.tr('Allow path-crossing of extended segments? '
                                                  '\nUnchecking this option can exponentially slow down the algorithm!'
                                                  '\nIf not allowed, it keeps searching for a nearest point until it finds one, where resulting segment will not cross initial path.'
                                                  '\nIf it cannot find such a point, the line/part will not be extended.'), defaultValue = True))
        
        ### Conditionals ###
        parameter_source_compare_expression = QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True)
        parameter_source_compare_expression.setFlags(parameter_source_compare_expression.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_source_compare_expression)
        
        parameter_operation = QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (points in source)'], defaultValue = 0, allowMultiple = False)
        parameter_operation.setFlags(parameter_operation.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_operation)
        
        parameter_points_compare_expression = QgsProcessingParameterExpression(
                self.POINTS_COMPARE_EXPRESSION, self.tr('Compare-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True)
        parameter_points_compare_expression.setFlags(parameter_points_compare_expression.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_points_compare_expression)
        
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
        
        parameter_points_compare_expression2 = QgsProcessingParameterExpression(
                self.POINTS_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True)
        parameter_points_compare_expression2.setFlags(parameter_points_compare_expression2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter_points_compare_expression2)
        
        ### Output ###
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Extended lines')))
        
        """
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (points in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.POINTS_COMPARE_EXPRESSION, self.tr('Compare-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONCAT_OPERATION, self.tr('And / Or a second condition. (To only use one condition, leave this to AND)'), ['AND','OR','XOR','iAND','iOR','iXOR','IS','IS NOT'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION2, self.tr('Second comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (points in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.POINTS_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True))
        """
        
    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        points_layer = self.parameterAsSource(parameters, self.POINTS_LYR, context)
        points_layer_vl = self.parameterAsLayer(parameters, self.POINTS_LYR, context)
        extend_method = self.parameterAsEnums(parameters, self.EXTEND_METHOD, context)
        extend_multiple = self.parameterAsInt(parameters, self.EXTEND_MULTIPLE, context)
        
        extend_dist_expression = self.parameterAsExpression(parameters, self.EXTEND_DIST, context)
        extend_dist_expression = QgsExpression(extend_dist_expression)
        min_dist_expression = self.parameterAsExpression(parameters, self.MIN_DIST, context)
        min_dist_expression = QgsExpression(min_dist_expression)
        allow_self_crossing = self.parameterAsBool(parameters, self.ALLOW_SELF_CROSSING, context)
        
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        points_filter_expression = self.parameterAsExpression(parameters, self.POINTS_FILTER_EXPRESSION, context)
        points_filter_expression = QgsExpression(points_filter_expression)
        
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        source_compare_expression2 = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION2, context)
        source_compare_expression2 = QgsExpression(source_compare_expression2)
        points_compare_expression = self.parameterAsExpression(parameters, self.POINTS_COMPARE_EXPRESSION, context)
        points_compare_expression = QgsExpression(points_compare_expression)
        points_compare_expression2 = self.parameterAsExpression(parameters, self.POINTS_COMPARE_EXPRESSION2, context)
        points_compare_expression2 = QgsExpression(points_compare_expression2)
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
        n_neighbors = 1
        if comparisons or not allow_self_crossing or extend_multiple != 0:
            n_neighbors = -1
        if op is not None and op2 is not None:
            comparisons = True
        elif op is None and op2 is None:
            comparisons = False
        elif op is None and op2 is not None:
            op = operator.eq # None is equal to ==: easier to implement, the second condtion then is just '' == '', so always true.
            points_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
        elif op2 is None and op is not None:
            op2 = operator.eq # None is equal to ==: easier to implement, the second condtion then is just '' == '', so always true.
            points_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
        
        
        output_layer_fields = source_layer.fields()
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer_vl.wkbType(),
                                               source_layer_vl.sourceCrs())
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if points_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            points_layer_vl = points_layer_vl.materialize(QgsFeatureRequest(points_filter_expression))
        
        if source_layer.sourceCrs() != points_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Points Layer...')
            reproject_params = {'INPUT': points_layer_vl, 'TARGET_CRS': source_layer.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params, context=context, feedback=feedback)
            points_layer_vl = reproject_result['OUTPUT']
        
        if points_layer_vl.geometryType() == QgsWkbTypes.PolygonGeometry or points_layer_vl.geometryType() == QgsWkbTypes.LineGeometry:
            feedback.setProgressText('Extracting Vertices...')
            extractvertices_result = processing.run("native:extractvertices",{'INPUT':points_layer_vl,'OUTPUT':'TEMPORARY_OUTPUT'}, context=context, feedback=feedback)
            points_layer_vl = extractvertices_result['OUTPUT']
        
        if QgsWkbTypes.isMultiType(points_layer_vl.wkbType()):
            feedback.setProgressText('Converting Multipoints to Singlepoints...')
            multitosinglepart_result = processing.run("native:multiparttosingleparts",{'INPUT':points_layer_vl,'OUTPUT':'TEMPORARY_OUTPUT'}, context=context, feedback=feedback)
            points_layer_vl = multitosinglepart_result['OUTPUT']
        else:
            points_layer_vl = points_layer_vl
            
        if comparisons:
            if source_layer_vl.featureCount() + points_layer_vl.featureCount() > 0:
                total = 100.0 / (source_layer_vl.featureCount() + points_layer_vl.featureCount())
            else:
                total = 0
        else:
            total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        current = 0
        
        feedback.setProgressText('Building spatial index...')
        points_layer_idx = QgsSpatialIndex(points_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        
        if comparisons: # dictonaries are a lot faster than featurerequests; https://gis.stackexchange.com/q/434768/107424
            feedback.setProgressText('Evaluating expressions...')
            points_layer_dict = {}
            points_layer_dict2 = {}
            points_compare_expression_context = QgsExpressionContext()
            points_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(points_layer_vl))
            points_compare_expression_context2 = QgsExpressionContext()
            points_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(points_layer_vl))
            for points_feat in points_layer_vl.getFeatures():
                current += 1
                if feedback.isCanceled():
                    break
                points_compare_expression_context.setFeature(points_feat)
                points_compare_expression_result = points_compare_expression.evaluate(points_compare_expression_context)
                points_layer_dict[points_feat.id()] = points_compare_expression_result 
                points_compare_expression_context2.setFeature(points_feat)
                points_compare_expression_result2 = points_compare_expression2.evaluate(points_compare_expression_context2)
                points_layer_dict2[points_feat.id()] = points_compare_expression_result2
                feedback.setProgress(int(current * total))
        if extend_multiple == 1: # clear skip list for layer
            points_skip = []
            
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        extend_dist_expression_context = QgsExpressionContext()
        extend_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        min_dist_expression_context = QgsExpressionContext()
        min_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context = QgsExpressionContext()
        source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context2 = QgsExpressionContext()
        source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for line_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            if extend_multiple == 2: # clear skip list for feature
                points_skip = []
            current += 1
            line_geom = line_feat.geometry()
            new_geom = QgsGeometry(line_geom.constGet().clone())
            extend_dist_expression_context.setFeature(line_feat)
            extend_dist_expression_result = extend_dist_expression.evaluate(extend_dist_expression_context)
            min_dist_expression_context.setFeature(line_feat)
            min_dist_expression_result = min_dist_expression.evaluate(min_dist_expression_context)
            if comparisons:
                source_compare_expression_context.setFeature(line_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(line_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
                
            n_vertices_line_geom = line_geom.constGet().nCoordinates()
            n_parts_line_geom = line_geom.constGet().partCount()
            line_geom_vertex_id = line_geom.constGet().nCoordinates()
            break_loop = False
            
            vertices_list_iterate = []
            vertices_list_start_geom = []
            vertices_list_start_part = []
            vertices_list_end_geom = []
            vertices_list_end_part = []
            if 0 in extend_method: # geom startpoint
                vertices_list_iterate.append(0)
                vertices_list_start_geom.append(0)
            if 1 in extend_method: # geom endpoint
                vertices_list_iterate.append(line_geom.constGet().nCoordinates() - 1)
                vertices_list_end_geom.append(line_geom.constGet().nCoordinates() - 1)
            vertex_id_counter = 0
            if 3 in extend_method or 2 in extend_method:
                for line_part_id, line_part in enumerate(line_geom.parts()):
                    if feedback.isCanceled():
                        break
                    for line_part_vertex_id, line_part_vertex in enumerate(line_part.vertices()):
                        if feedback.isCanceled():
                            break
                        if 2 in extend_method: # part startpoint
                            if line_part_vertex_id == 0:
                                vertices_list_iterate.append(vertex_id_counter)
                                vertices_list_start_part.append(vertex_id_counter)
                        if 3 in extend_method: # part endpoint
                            if line_part_vertex_id == line_geom.constGet().vertexCount(line_part_id,0) - 1:
                                vertices_list_iterate.append(vertex_id_counter)
                                vertices_list_end_part.append(vertex_id_counter)
                        vertex_id_counter += 1
            vertices_list_iterate = list(set(vertices_list_iterate))
            vertices_list_iterate.sort(reverse=True)
            try:
                vertices_list_start_part.remove(0)
            except:
                pass
            try:
                vertices_list_end_part.remove(line_geom.constGet().nCoordinates() - 1)
            except:
                pass
            
            for vertex_id in vertices_list_iterate:
                if feedback.isCanceled():
                    break
                vertex_point = line_geom.vertexAt(vertex_id)
                vertex_point_geom = QgsGeometry.fromWkt(vertex_point.asWkt())
                nearest_neighbors = points_layer_idx.nearestNeighbor(vertex_point_geom, neighbors=n_neighbors, maxDistance=extend_dist_expression_result)
                if not extend_multiple == 0:
                    nearest_neighbors = [x for x in nearest_neighbors if x not in points_skip]
                for nearest_neighbor_id in nearest_neighbors:
                    if feedback.isCanceled():
                        break
                    nearest_neighbor_geom = points_layer_idx.geometry(nearest_neighbor_id)
                    if comparisons:
                        points_compare_expression_result = points_layer_dict[nearest_neighbor_id]
                        points_compare_expression_result2 = points_layer_dict2[nearest_neighbor_id]
                        if concat_op(op(source_compare_expression_result, points_compare_expression_result),op2(source_compare_expression_result2, points_compare_expression_result2)):
                            if not extend_multiple == 0:
                                points_skip.append(nearest_neighbor_id)
                        else:
                            continue
                            
                    if not extend_multiple == 0:
                        points_skip.append(nearest_neighbor_id)
                    if vertex_point_geom.distance(nearest_neighbor_geom) <= min_dist_expression_result: # do not extend if vertex already is on a point
                        break
                        
                    if not allow_self_crossing:
                        old_geom = QgsGeometry(new_geom.constGet().clone())
                    if vertex_id in vertices_list_end_geom: # we cannot just add a vertex at -1 (end geom) because the api documentation is just wrong (does not add vertex, but recognizes as invalid and skips it)
                        new_geom.insertVertex(vertex_point,vertex_id) # duplicate last vertex
                        new_geom.moveVertex(nearest_neighbor_geom.vertices().next(),vertex_id+1) # move duplicated vertex to new position
                    elif vertex_id in vertices_list_end_part: # we can also not just add vertex to part, because it then would in fact be the first vertex of the next part
                        new_geom.insertVertex(vertex_point,vertex_id) # duplicate last vertex
                        new_geom.moveVertex(nearest_neighbor_geom.vertices().next(),vertex_id+1) # move duplicated vertex to new position
                    elif vertex_id in vertices_list_start_geom:
                        new_geom.insertVertex(nearest_neighbor_geom.vertices().next(),vertex_id)
                    elif vertex_id in vertices_list_start_part:
                        new_geom.insertVertex(nearest_neighbor_geom.vertices().next(),vertex_id)
                    if not allow_self_crossing:
                        test_geom = QgsGeometry.fromPolyline([new_geom.vertexAt(vertex_id),new_geom.vertexAt(vertex_id+1)])
                        if old_geom.crosses(test_geom):
                            if not extend_multiple == 0:
                                points_skip.remove(nearest_neighbor_id)
                            new_geom =  QgsGeometry(old_geom.constGet().clone()) # restore old geometry
                            continue
                    break # should actually be only one in list, but just to be sure :)
                    
            new_feat = QgsFeature(output_layer_fields)
            attridx = 0
            for attr in line_feat.attributes():
                new_feat[attridx] = attr
                attridx += 1
            new_feat.setGeometry(new_geom)
            
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))
            
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ExtendLinesToNearestPointsByCondition()

    def name(self):
        return 'ExtendLinesToNearestPointsByCondition'

    def displayName(self):
        return self.tr('Extend Lines to Nearest Points by Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithm extends lines and/or line parts to nearest points by using an optional attribute condition. The initial line/part will not be modified.'
        '\nYou can also set the maximum search distance for points or use an option to not extend a line/part if the start/end vertex already is on a nearest point respecitvely the points are closer than X.'
        '\nYou may also choose whether a point can be used unlimited as extend end/start-point or only once per layer/feature/part as well as whether the extended segment may cross the initial line or not.'
        )