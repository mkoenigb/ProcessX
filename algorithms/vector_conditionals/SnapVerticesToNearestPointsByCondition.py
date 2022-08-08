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

class SnapVerticesToNearestPointsByCondition(QgsProcessingAlgorithm):
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
    SNAP_METHOD = 'SNAP_METHOD'
    SNAP_MULTIPLE = 'SNAP_MULTIPLE'
    SNAP_DIST = 'SNAP_DIST'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer (Containing the vertices that shall be snapped)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.POINTS_LYR, self.tr('Points Layer to snap line vertices to (MultiPoints will be casted to SinglePoints)'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.POINTS_FILTER_EXPRESSION, self.tr('Filter-Expression for Points-Layer'), parentLayerParameterName = 'POINTS_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SNAP_METHOD, self.tr('Snap Vertices'), ['Snap Startvertices of Geometry',
                                                             'Snap Endvertices of Geometry',
                                                             'Snap Startvertices of Parts (MultiLineStrings only)',
                                                             'Snap Endvertices of Parts (MultiLineStrings only)',
                                                             'Snap all Midvertices (all Vertices between Start- and Endvertices)'
                                                            ], defaultValue = [], allowMultiple = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SNAP_MULTIPLE, self.tr('Snap to one and the same point more than once?'), ['Use a point as often as it is the nearest match',
                                                                                                'Use a point only once for the whole layer (ordered ascending by feature id or order-by-expression)',
                                                                                                'Use a point only once for the whole feature (ordered ascending by vertex id)',
                                                                                                'Use a point only once for the whole part of a multiline feature (ordered ascending by part id and vertex id)'
                                                                                               ], defaultValue = [0], allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterDistance(
                self.SNAP_DIST, self.tr('Maximum snapping distance (0 means unlimited)'), parentParameterName = 'SOURCE_LYR', defaultValue = 0, minValue = 0, maxValue = 2147483647))
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
                self.OUTPUT, self.tr('Snapped lines')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        points_layer = self.parameterAsSource(parameters, self.POINTS_LYR, context)
        points_layer_vl = self.parameterAsLayer(parameters, self.POINTS_LYR, context)
        snap_method = self.parameterAsEnums(parameters, self.SNAP_METHOD, context)
        snap_multiple = self.parameterAsInt(parameters, self.SNAP_MULTIPLE, context)
        snap_dist = self.parameterAsDouble(parameters, self.SNAP_DIST, context)
        
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
            for points_feat in points_layer_vl.getFeatures():
                current += 1
                points_compare_expression_context = QgsExpressionContext()
                points_compare_expression_context.setFeature(points_feat)
                points_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(points_layer_vl))
                points_compare_expression_result = points_compare_expression.evaluate(points_compare_expression_context)
                points_layer_dict[points_feat.id()] = points_compare_expression_result 
                points_compare_expression_context2 = QgsExpressionContext()
                points_compare_expression_context2.setFeature(points_feat)
                points_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(points_layer_vl))
                points_compare_expression_result2 = points_compare_expression2.evaluate(points_compare_expression_context2)
                points_layer_dict2[points_feat.id()] = points_compare_expression_result2
                feedback.setProgress(int(current * total))
        if snap_multiple == 1: # clear skip list for layer
            points_skip = []
            
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        # https://gis.stackexchange.com/questions/411126/modifying-specific-vertices-of-multilinestring-using-pyqgis
        # https://gis.stackexchange.com/a/411157/107424
        for line_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            if snap_multiple == 2: # clear skip list for feature
                points_skip = []    
            current += 1
            line_geom = line_feat.geometry()
            new_geom = line_geom # to be modified
            line_vertex_id = 0
            n_vertices_line_geom = len([v for i, v in enumerate(line_geom.vertices())]) # does not support len(), count() or whatever, so lets just do it complicated...
            if comparisons:
                source_compare_expression_context = QgsExpressionContext()
                source_compare_expression_context.setFeature(line_feat)
                source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2 = QgsExpressionContext()
                source_compare_expression_context2.setFeature(line_feat)
                source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            for line_part_id, line_part in enumerate(line_geom.parts()):
                if feedback.isCanceled():
                    break
                if snap_multiple == 3: # clear skip list for part
                    points_skip = []
                n_vertices_line_part = len([v for i, v in enumerate(line_part.vertices())])
                for line_part_vertex_id, line_vertex in enumerate(line_part.vertices()):
                    if feedback.isCanceled():
                        break
                    vertex_is_midpoint = True # easier than rewriting all conditions...
                    doit = False # my lazy ass does not want to write that stuff 5 times...
                    if line_vertex_id == 0:
                        vertex_is_midpoint = False
                        if 0 in snap_method:
                            doit = True
                    if line_vertex_id == (n_vertices_line_geom - 1):
                        vertex_is_midpoint = False
                        if 1 in snap_method:
                            doit = True
                    if line_part_vertex_id == 0:
                        vertex_is_midpoint = False
                        if 2 in snap_method:
                            doit = True
                    if line_part_vertex_id == (n_vertices_line_part - 1):
                        vertex_is_midpoint = False
                        if 3 in snap_method:
                            doit = True
                    if vertex_is_midpoint is True:
                        if 4 in snap_method:
                            doit = True
                    
                    if doit:
                        nearest_neighbors = points_layer_idx.nearestNeighbor(QgsPointXY(line_vertex), neighbors=n_neighbors, maxDistance=snap_dist)
                        if not snap_multiple == 0:
                            nearest_neighbors = [x for x in nearest_neighbors if x not in points_skip]
                        for nearest_neighbor_id in nearest_neighbors:
                            if feedback.isCanceled():
                                break
                            if comparisons:
                                points_compare_expression_result = points_layer_dict[nearest_neighbor_id]
                                points_compare_expression_result2 = points_layer_dict2[nearest_neighbor_id]
                                if concat_op(op(source_compare_expression_result, points_compare_expression_result),op2(source_compare_expression_result2, points_compare_expression_result2)):
                                    nearest_neighbor_geom = points_layer_idx.geometry(nearest_neighbor_id)
                                    new_geom.moveVertex(nearest_neighbor_geom.asPoint().x(),nearest_neighbor_geom.asPoint().y(), line_vertex_id)
                                    if not snap_multiple == 0:
                                        points_skip.append(nearest_neighbor_id)
                                    break # stop testing after first match
                                else:
                                    continue
                            else:
                                nearest_neighbor_geom = points_layer_idx.geometry(nearest_neighbor_id)
                                new_geom.moveVertex(nearest_neighbor_geom.asPoint().x(),nearest_neighbor_geom.asPoint().y(), line_vertex_id)
                                if not snap_multiple == 0:
                                    points_skip.append(nearest_neighbor_id)
                                break # should actually be only one in list, but just to be sure :)
                    line_vertex_id += 1 # line_part_vertex_id is not the same!
                    
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
        return SnapVerticesToNearestPointsByCondition()

    def name(self):
        return 'SnapVerticesToNearestPointsByCondition'

    def displayName(self):
        return self.tr('Snap Vertices to Nearest Points by Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithm snaps the vertices of a given layer to the nearest point of a given point layer by optional attribute and distance conditions. The point layer is casted to a singlepoint layer first, which means that the geometry of its nodes are used.'
        '\nWhile this algorithm was intentionally developed for line layers (singlelines or multilines) it does also work with polygons or points as input.'
        '\nYou may also choose which kind of vertices (Start- or Endvertices of a geometry, Start- or Endvertices of a MultiLinePart, or all Middlevertices) should be moved.'
        '\nYou can also decide whether a point should be used more than once as a possible snapping option or not. When using this option, the nearest match is always taken for the first matching vertex by iteration order.'
        '\nIf the algorithm does not find any matches, the vertices remain on their original location.'
        )