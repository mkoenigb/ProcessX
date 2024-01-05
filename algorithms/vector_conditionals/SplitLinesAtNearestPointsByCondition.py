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
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsPointXY, QgsWkbTypes, 
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingParameterBoolean)

class SplitLinesAtNearestPointsByCondition(QgsProcessingAlgorithm):
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
    METHOD = 'METHOD'
    MAX_DIST = 'MAX_DIST'
    AVOID_DUPLICATE_NODES = 'AVOID_DUPLICATE_NODES'
    DROP_LENGTH = 'DROP_LENGTH'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Lines'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Lines-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Lines-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.POINTS_LYR, self.tr('Points'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.POINTS_FILTER_EXPRESSION, self.tr('Filter-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Method'), ['Modifiy line paths by using the nearest points themselves as split points and new vertices',
                                                 'Use interpolated points on existing line, closest to nearest points, as split points and new vertices (line paths remain unchanged)'
                                                ], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.AVOID_DUPLICATE_NODES, self.tr('Avoid duplicate nodes, empty, null or invalid geometries'), defaultValue = 1))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.DROP_LENGTH, self.tr('Drop lines or line parts equal or shorter than X (must evaluate to float; neagtive means keep all)'), defaultValue = 0.0, parentLayerParameterName = 'SOURCE_LYR', optional = False))
                
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_DIST, self.tr('Maximum distance to split points (must evaluate to float; 0 or negative means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0, optional = False))
        
        
        #parameter_source_compare_expression = QgsProcessingParameterExpression(
        #        self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True)
        #parameter_source_compare_expression.setFlags(parameter_source_compare_expression.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        #self.addParameter(parameter_source_compare_expression)
        
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
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Splitted Lines')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        points_layer = self.parameterAsSource(parameters, self.POINTS_LYR, context)
        points_layer_vl = self.parameterAsLayer(parameters, self.POINTS_LYR, context)
        
        method = self.parameterAsInt(parameters, self.METHOD, context)
        max_dist_expression = self.parameterAsExpression(parameters, self.MAX_DIST, context)
        max_dist_expression = QgsExpression(max_dist_expression)
        avoid_duplicate_nodes = self.parameterAsBool(parameters, self.AVOID_DUPLICATE_NODES, context)
        drop_length_expression = self.parameterAsExpression(parameters, self.DROP_LENGTH, context)
        drop_length_expression = QgsExpression(drop_length_expression)
        
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
        if comparisons:
            n_neighbors = -1
        
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
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            points_layer_vl = reproject_result['OUTPUT']
            
        if QgsWkbTypes.isMultiType(points_layer_vl.wkbType()):
            feedback.setProgressText('Converting Multipoints to Singlepoints...')
            multitosinglepart_result = processing.run("native:multiparttosingleparts",{'INPUT':points_layer_vl,'OUTPUT':'TEMPORARY_OUTPUT'})
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
        points_layer_idx = QgsSpatialIndex(points_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
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
            
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        max_dist_expression_context = QgsExpressionContext()
        max_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        drop_length_expression_context = QgsExpressionContext()
        drop_length_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context = QgsExpressionContext()
        source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context2 = QgsExpressionContext()
        source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for line_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            current += 1
            line_geom = line_feat.geometry()
            vertices_dict = {}
            if comparisons:
                source_compare_expression_context.setFeature(line_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(line_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
            drop_length_expression_context.setFeature(line_feat)
            drop_length_expression_result = drop_length_expression.evaluate(drop_length_expression_context)
            max_dist_expression_context.setFeature(line_feat)
            max_dist_expression_result = max_dist_expression.evaluate(max_dist_expression_context)
            nearest_point_ids = points_layer_idx.nearestNeighbor(line_geom,-1,max_dist_expression_result)
            for nearest_point_id in nearest_point_ids:
                if feedback.isCanceled():
                    break
                if comparisons:
                    points_compare_expression_result = points_layer_dict[nearest_point_id]
                    points_compare_expression_result2 = points_layer_dict2[nearest_point_id]
                    if concat_op(op(source_compare_expression_result, points_compare_expression_result),op2(source_compare_expression_result2, points_compare_expression_result2)):
                        pass
                    else:
                        continue
                nearest_point_geom = points_layer_idx.geometry(nearest_point_id)
                dist_along_line = line_geom.lineLocatePoint(nearest_point_geom)
                point_on_line = line_geom.interpolate(dist_along_line)
                vertex_after_id = line_geom.constGet().closestSegment(point_on_line.vertices().next(),10)[2]
                vertex_after_nr_old = line_geom.vertexNrFromVertexId(vertex_after_id)
                vertex_after_nr_new = line_geom.vertexNrFromVertexId(vertex_after_id)
                try:
                    vertices_dict[dist_along_line] = [nearest_point_geom,point_on_line,vertex_after_nr_old,vertex_after_nr_new]
                except:
                    pass
            
            # densify the geometry with the nearest points, sorted by distance from start
            vertices_dict = dict(sorted(vertices_dict.items()))
            from_to_list = []
            densified_geom = line_feat.geometry()
            for i, (k, v) in enumerate(vertices_dict.items()):
                if feedback.isCanceled():
                    break
                v[3] += i
                if method == 0:
                    densified_geom.insertVertex(v[0].vertices().next(),v[3])
                else:
                    densified_geom.insertVertex(v[1].vertices().next(),v[3])
                from_to_list.append(v[3])
                
            max_vert = densified_geom.constGet().nCoordinates() - 1
            from_to_list.append(0)
            from_to_list.append(max_vert)
            from_to_list.sort()
            
            # create the new lines from start vertices to their end vertices
            for from_to_index, from_to_value in enumerate(from_to_list):
                if feedback.isCanceled():
                    break
                if from_to_value == max_vert:
                    break
                from_vert = from_to_value
                try:
                    to_vert = from_to_list[from_to_index+1]
                except IndexError:
                    to_vert = densified_geom.constGet().nCoordinates() - 1
                # create a deep copy so we can safely modify the geometry
                new_geom = QgsGeometry(densified_geom.constGet().clone())
                keep_vert_index = list(range(from_vert,to_vert+1))
                vertices_deleted = 0
                del_vert = 0
                for vert_index in range(0,densified_geom.constGet().nCoordinates()):
                    if feedback.isCanceled():
                        break
                    if vert_index in keep_vert_index:
                        del_vert += 1
                        continue
                    # if the second last vertex of a part gets deleted, two vertices are deleted at the same time
                    # because there is no response about this, we need to somehow figure out when that happened
                    del_diff = densified_geom.constGet().nCoordinates() - (new_geom.constGet().nCoordinates() + vertices_deleted)
                    if del_diff > 0:
                        vertices_deleted += 1
                        continue
                    new_geom.deleteVertex(del_vert)
                    vertices_deleted += 1
                    
                if drop_length_expression_result < 0:
                    pass
                else:
                    for k, part in enumerate(new_geom.parts()):
                        if part is None:
                            break # otherwise this loop will run infinite
                        if feedback.isCanceled():
                            break
                        if part.length() <= drop_length_expression_result:
                            new_geom.deletePart(k)
                            #feedback.reportError('Deleting Part {} between Vertices {} and {} of Feature {}.'.format(k, from_to_index, from_to_value, line_feat.id()), fatalError = False)
                    if new_geom.length() <= drop_length_expression_result:
                        #feedback.reportError('Dropping line between Vertices {} and {} of Feature {} due to its length.'.format(k, from_to_index, from_to_value, line_feat.id()), fatalError = False)
                        continue
                    
                if avoid_duplicate_nodes:
                    new_geom.removeDuplicateNodes(10,True)
                    if not new_geom.isGeosValid():
                        try:
                            new_geom = new_geom.makeValid()
                        except:
                            #feedback.reportError('Could not make LinePart between Vertices {} and {} of Feature {} valid; Skipping.'.format(from_to_index, from_to_value, line_feat.id()), fatalError = False)
                            continue
                        if not new_geom.isGeosValid():
                            #feedback.reportError('LinePart between Vertices {} and {} of Feature {} is not valid; Skipping.'.format(from_to_index, from_to_value, line_feat.id()), fatalError = False)
                            continue
                    if new_geom.isNull() or new_geom.isEmpty():
                        #feedback.reportError('LinePart between Vertices {} and {} of Feature {} is empty or null; Skipping.'.format(from_to_index, from_to_value, line_feat.id()), fatalError = False)
                        continue

                
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
        return SplitLinesAtNearestPointsByCondition()

    def name(self):
        return 'SplitLinesAtNearestPointsByCondition'

    def displayName(self):
        return self.tr('Split Lines At Nearest Points By Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithm splits lines by nearest points if an optional attribute condition is met. It takes linestrings, multilinestrings as well as z and m values into account. '
        '<b>Note that this algorithm may produce unexpected or weird results when input lines are not in a projected CRS!</b> '
        'Also this algorithm may produce lines of length 0 (or rather 0.0000...1), if the only remaining start-vertex and end-vertex are at the same position. You can drop these by using the corresponding option or keep them by setting this option to -1.'
        '\nYou can either choose to modify the lines path by moving the vertices to their split-points or use interpolated points on the existing line, which are closest to the nearest points, as split points.'
        '\nIf two or more nearest points, when snapped on to the lines, are at the exact same distance along the line from its start, only one point is taken as split-point.'
        '\nIf the algorithm does not find any matching points, the lines remain unchanged.'
        )