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
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterBoolean, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString)

class JoinAttributesByNearestWithCondition(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION2 = 'SOURCE_COMPARE_EXPRESSION2'
    JOIN_LYR = 'JOIN_LYR'
    JOIN_FIELDS = 'JOIN_FIELDS'
    JOIN_FILTER_EXPRESSION = 'JOIN_FILTER_EXPRESSION'
    JOIN_COMPARE_EXPRESSION = 'JOIN_COMPARE_EXPRESSION'
    JOIN_COMPARE_EXPRESSION2 = 'JOIN_COMPARE_EXPRESSION2'
    OPERATION = 'OPERATION'
    OPERATION2 = 'OPERATION2'
    CONCAT_OPERATION = 'CONCAT_OPERATION'
    JOIN_N = 'JOIN_N'
    JOIN_DIST = 'JOIN_DIST'
    JOIN_PREFIX = 'JOIN_PREFIX'
    JOIN_MULTIPLE = 'JOIN_MULTIPLE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Choose method for calculation'), ['Source layer geometry to join layer geometry','Source layer centroid to join layer centroid'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.JOIN_LYR, self.tr('Join Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.JOIN_FILTER_EXPRESSION, self.tr('Filter-Expression for Join-Layer'), parentLayerParameterName = 'JOIN_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterField(
                self.JOIN_FIELDS, self.tr('Add the following fields of join layer to result (if none are chosen, all fields will be added)'),parentLayerParameterName='JOIN_LYR', allowMultiple = True, optional = True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.JOIN_N, self.tr('Join x nearest neighbors (0 means unlimited)'), type = 0, defaultValue = 3, minValue = 0, maxValue = 2147483647))
        self.addParameter(
            QgsProcessingParameterDistance(
                self.JOIN_DIST, self.tr('Maximum join distance (0 means unlimited)'), parentParameterName = 'SOURCE_LYR', defaultValue = 0, minValue = 0, maxValue = 2147483647))
        self.addParameter(
            QgsProcessingParameterString(
                self.JOIN_PREFIX, self.tr('Join Prefix'), defaultValue = 'join_', optional = True))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.JOIN_MULTIPLE, self.tr('Join Features more than once (if not checked, a feature is only joined to the first match, ordered by expression or feature id)'), optional = True, defaultValue = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (join in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.JOIN_COMPARE_EXPRESSION, self.tr('Compare-Expression for Join-Layer'), parentLayerParameterName = 'JOIN_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONCAT_OPERATION, self.tr('And / Or a second condition. (To only use one condition, leave this to AND)'), ['AND','OR','XOR','iAND','iOR','iXOR','IS','IS NOT'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION2, self.tr('Second comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (join in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.JOIN_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Join-Layer'), parentLayerParameterName = 'JOIN_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Joined Layer')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        method = self.parameterAsInt(parameters, self.METHOD, context)
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        source_compare_expression2 = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION2, context)
        source_compare_expression2 = QgsExpression(source_compare_expression2)
        join_layer_vl = self.parameterAsLayer(parameters, self.JOIN_LYR, context)
        join_compare_expression = self.parameterAsExpression(parameters, self.JOIN_COMPARE_EXPRESSION, context)
        join_compare_expression = QgsExpression(join_compare_expression)
        join_compare_expression2 = self.parameterAsExpression(parameters, self.JOIN_COMPARE_EXPRESSION2, context)
        join_compare_expression2 = QgsExpression(join_compare_expression2)
        join_fields = self.parameterAsFields(parameters, self.JOIN_FIELDS, context)
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
            join_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
        elif op2 is None and op is not None:
            op2 = operator.eq # None is equal to ==: easier to implement, the second condtion then is just '' == '', so always true.
            join_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            source_compare_expression2 = QgsExpression('') # Ignore eventually set fields/expressions!
            comparisons = True
        
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        join_filter_expression = self.parameterAsExpression(parameters, self.JOIN_FILTER_EXPRESSION, context)
        join_filter_expression = QgsExpression(join_filter_expression)
        join_n = self.parameterAsInt(parameters, self.JOIN_N, context)
        join_dist = self.parameterAsDouble(parameters, self.JOIN_DIST, context)
        join_prefix = self.parameterAsString(parameters, self.JOIN_PREFIX, context)
        join_multiple = self.parameterAsBool(parameters, self.JOIN_MULTIPLE, context)
        
        sourcejoinlayerequal = False
        if join_n == 0:
            join_n =  2147483647 # float('inf') produces OverflowError: argument 'neighbors' overflowed: value must be in the range -2147483648 to 2147483647
        if source_layer_vl == join_layer_vl:
            sourcejoinlayerequal = True
            if join_n < 2147483647:
                join_n += 1
        
        source_layer_fields = source_layer.fields()
        if join_fields:
            join_layer_vl = join_layer_vl.materialize(QgsFeatureRequest().setSubsetOfAttributes(join_fields, join_layer_vl.fields()))
        join_layer_vl_fields = join_layer_vl.fields()
        output_layer_fields = source_layer_fields
        for join_layer_vl_field in join_layer_vl.fields():
            join_layer_vl_field_copy = join_layer_vl_field
            if join_prefix:
                join_layer_vl_field_copy.setName(join_prefix + join_layer_vl_field_copy.name())
            if join_layer_vl_field_copy.name() in source_layer_fields.names():
                join_layer_vl_field_copy.setName(join_layer_vl_field_copy.name() + '_2')
            output_layer_fields.append(join_layer_vl_field_copy)
        join_dist_field_name = 'shortestdistance'
        source_join_line_field_name = 'shortestline'
        if join_prefix:
            join_dist_field_name = join_prefix + join_dist_field_name
            source_join_line_field_name = join_prefix + source_join_line_field_name
        whilecounter = 0
        while join_dist_field_name in output_layer_fields.names():
            whilecounter += 1
            join_dist_field_name = join_dist_field_name + '_2'
            if whilecounter > 9:
                feedback.setProgressText('You should clean up your fieldnames!')
                break
        whilecounter = 0
        while source_join_line_field_name in output_layer_fields.names():
            whilecounter += 1
            source_join_line_field_name = source_join_line_field_name + '_2'
            if whilecounter > 9:
                feedback.setProgressText('You should clean up your fieldnames!')
                break
                
        output_layer_fields.append(QgsField(join_dist_field_name, QVariant.Double, len=20, prec=5))
        output_layer_fields.append(QgsField(source_join_line_field_name, QVariant.String))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer.wkbType(),
                                               source_layer.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer = source_layer.materialize(QgsFeatureRequest(source_filter_expression))
        if join_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            join_layer_vl = join_layer_vl.materialize(QgsFeatureRequest(join_filter_expression))
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        
        if source_layer.sourceCrs() != join_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Join Layer...')
            reproject_params = {'INPUT': join_layer_vl, 'TARGET_CRS': source_layer.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            join_layer_vl = reproject_result['OUTPUT']
        if method == 1:
            feedback.setProgressText('Creating centroids for Join Layer...')
            centroid_params = { 'ALL_PARTS' : False, 'INPUT' : join_layer_vl, 'OUTPUT' : 'memory:Centroids' }
            centroid_result = processing.run("native:centroids", centroid_params)
            join_layer_vl = centroid_result['OUTPUT']
        
        feedback.setProgressText('Building spatial index...')
        join_layer_idx = QgsSpatialIndex(join_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
            
        feedback.setProgressText('Start processing...')
        for current, source_feat in enumerate(source_layer.getFeatures(source_orderby_request)):
            if feedback.isCanceled():
                break
            matches_found_counter = 0
            
            if method == 0:
                source_feat_geom = source_feat.geometry()
            elif method == 1:
                source_feat_geom = source_feat.geometry().centroid()
                
            if not comparisons:
                nearest_neighbors = join_layer_idx.nearestNeighbor(source_feat_geom, neighbors = join_n, maxDistance = join_dist)
            else:
                nearest_neighbors = join_layer_idx.nearestNeighbor(source_feat_geom, neighbors = -1, maxDistance = join_dist)
                source_compare_expression_context = QgsExpressionContext()
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2 = QgsExpressionContext()
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
            if sourcejoinlayerequal is True:
                nearest_neighbors.remove(source_feat.id())
            
            for join_feat_id in nearest_neighbors:
                if feedback.isCanceled():
                    break
                if matches_found_counter >= join_n:
                    break
                    
                join_feat = join_layer_vl.getFeature(join_feat_id)
                
                if not comparisons:
                    matches_found_counter += 1
                    new_feat = QgsFeature(output_layer_fields)
                    new_feat.setGeometry(source_feat.geometry())
                    attridx = 0
                    for attr in source_feat.attributes():
                        new_feat[attridx] = attr
                        attridx += 1
                    for attr in join_feat.attributes():
                        new_feat[attridx] = attr
                        attridx += 1
                    new_feat[join_dist_field_name] = source_feat_geom.distance(join_feat.geometry())
                    new_feat[source_join_line_field_name] = str(source_feat_geom.shortestLine(join_feat.geometry()).asWkt())
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                    if join_multiple is False:
                        join_layer_idx.deleteFeature(join_feat)
                else:
                    join_compare_expression_context = QgsExpressionContext()
                    join_compare_expression_context.setFeature(join_feat)
                    join_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(join_layer_vl))
                    join_compare_expression_result = join_compare_expression.evaluate(join_compare_expression_context)
                    join_compare_expression_context2 = QgsExpressionContext()
                    join_compare_expression_context2.setFeature(join_feat)
                    join_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(join_layer_vl))
                    join_compare_expression_result2 = join_compare_expression2.evaluate(join_compare_expression_context2)
                    
                    if concat_op(op(source_compare_expression_result, join_compare_expression_result),op2(source_compare_expression_result2, join_compare_expression_result2)):
                        matches_found_counter += 1
                        new_feat = QgsFeature(output_layer_fields)
                        new_feat.setGeometry(source_feat.geometry())
                        attridx = 0
                        for attr in source_feat.attributes():
                            new_feat[attridx] = attr
                            attridx += 1
                        for attr in join_feat.attributes():
                            new_feat[attridx] = attr
                            attridx += 1
                        new_feat[join_dist_field_name] = source_feat_geom.distance(join_feat.geometry())
                        new_feat[source_join_line_field_name] = str(source_feat_geom.shortestLine(join_feat.geometry()).asWkt())
                        sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                        if join_multiple is False:
                            join_layer_idx.deleteFeature(join_feat)
                
            if matches_found_counter == 0:
                new_feat = QgsFeature(output_layer_fields)
                new_feat.setGeometry(source_feat.geometry())
                attridx = 0
                for attr in source_feat.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                    
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return JoinAttributesByNearestWithCondition()

    def name(self):
        return 'JoinAttributesByNearestWithCondition'

    def displayName(self):
        return self.tr('Join attributes by nearest with condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr('This Algorithm creates a copy of the source layer, finds the x nearest neighbors by a given condition and joins them.')