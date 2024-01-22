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

class DensifyLinesWithNearestPointsByCondition(QgsProcessingAlgorithm):
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
                self.METHOD, self.tr('Method'), ['Use nearest Points as new Vertices (Modifies line paths)',
                                                 'Use interpolated Points on existing Line, closest to nearest Points, as new Vertices (Line paths remain unchanged)'
                                                ], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.AVOID_DUPLICATE_NODES, self.tr('Avoid duplicate Nodes'), defaultValue = 1))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.MAX_DIST, self.tr('Maximum distance (must evaluate to float; 0 or negative means unlimited)'), parentLayerParameterName = 'SOURCE_LYR', defaultValue = 0, optional = False))
        
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
                self.OUTPUT, self.tr('Densified Lines')))

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
        if source_layer_vl.crs().isGeographic():
            feedback.reportError('WARNING: Your Source-layer is in a geographic CRS. It must be in a projected CRS, otherwise you may encounter weird or incorrect results.')
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if points_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            points_layer_vl = points_layer_vl.materialize(QgsFeatureRequest(points_filter_expression))
        
        if source_layer.sourceCrs() != points_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Points Layer...')
            reproject_params = {'INPUT': points_layer_vl, 'TARGET_CRS': source_layer.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params, context=context, feedback=feedback)
            points_layer_vl = reproject_result['OUTPUT']
            
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
            
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        max_dist_expression_context = QgsExpressionContext()
        max_dist_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context = QgsExpressionContext()
        source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context2 = QgsExpressionContext()
        source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for line_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            current += 1
            line_geom = line_feat.geometry()
            new_geom = line_feat.geometry()
            vertices_dict = {}
            if comparisons:
                source_compare_expression_context.setFeature(line_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(line_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
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
                    
            vertices_dict = dict(sorted(vertices_dict.items()))
            for i, (k, v) in enumerate(vertices_dict.items()):
                if feedback.isCanceled():
                    break
                v[3] += i
                if method == 0:
                    new_geom.insertVertex(v[0].vertices().next(),v[3])
                else:
                    new_geom.insertVertex(v[1].vertices().next(),v[3])
            if avoid_duplicate_nodes:
                new_geom.removeDuplicateNodes(10,True)
            
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
        return DensifyLinesWithNearestPointsByCondition()

    def name(self):
        return 'DensifyLinesWithNearestPointsByCondition'

    def displayName(self):
        return self.tr('Densify Lines With Nearest Points By Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithm inserts new vertices to a given line layer. The new vertices are based on a given point layer. The point layer is casted to a singlepoint layer first, which means that the geometry of its nodes are used.'
        ' <b>Note that this algorithm may produce unexpected or weird results when input lines are not in a projected CRS!</b>'
        '\nYou can either choose to use the nearest points as new vertices, which will modify the lines path or use interpolated points on the existing line, which are closest to the nearest points as new vertices.'
        '\nIf two or more nearest points, when snapped on to the lines, are at the exact same distance along the line from its start, only one point is taken.'
        '\nYou can also choose an optional attribute condition to choose wheter a point shall be used or not.'
        '\nIf the algorithm does not find any matching points, the lines remain unchanged.'
        )