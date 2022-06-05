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
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString)

class JoinAttributesByNearestWithCondition(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    #SOURCE_FIELD = 'SOURCE_FIELD'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    JOIN_LYR = 'JOIN_LYR'
    JOIN_FIELDS = 'JOIN_FIELDS'
    #JOIN_FIELD = 'JOIN_FIELD'
    JOIN_FILTER_EXPRESSION = 'JOIN_FILTER_EXPRESSION'
    JOIN_COMPARE_EXPRESSION = 'JOIN_COMPARE_EXPRESSION'
    OPERATION = 'OPERATION'
    JOIN_N = 'JOIN_N'
    JOIN_DIST = 'JOIN_DIST'
    JOIN_PREFIX = 'JOIN_PREFIX'
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
        #self.addParameter(
        #    QgsProcessingParameterField(
        #        self.SOURCE_FIELD, self.tr('Source Layer compare Field'),parentLayerParameterName='SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','not','is not','contains (join in source)'], defaultValue = 0, allowMultiple = False))
        #self.addParameter(
        #    QgsProcessingParameterField(
        #        self.JOIN_FIELD, self.tr('Join Layer compare Field'),parentLayerParameterName='JOIN_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.JOIN_COMPARE_EXPRESSION, self.tr('Compare-Expression for Join-Layer'), parentLayerParameterName = 'JOIN_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Joined Layer')))

    def processAlgorithm(self, parameters, context, feedback):
        method = self.parameterAsInt(parameters, self.METHOD, context)
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        #source_field = self.parameterAsFields(parameters, self.SOURCE_FIELD, context)
        #if source_field:
        #    source_field = source_field[0]
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        join_layer = self.parameterAsLayer(parameters, self.JOIN_LYR, context)
        #join_field = self.parameterAsFields(parameters, self.SOURCE_FIELD, context)
        #if join_field:
        #    join_field = join_field[0]
        join_compare_expression = self.parameterAsExpression(parameters, self.JOIN_COMPARE_EXPRESSION, context)
        join_compare_expression = QgsExpression(join_compare_expression)
        join_fields = self.parameterAsFields(parameters, self.JOIN_FIELDS, context)
        operation = self.parameterAsInt(parameters, self.OPERATION, context)
        ops = { # get the operator by this index
            0: None,
            1: operator.ne,
            2: operator.eq,
            3: operator.lt,
            4: operator.gt,
            5: operator.le,
            6: operator.ge,
            7: operator.is_,
            8: operator.not_,
            9: operator.is_not,
            10: operator.contains,
            
            }
        op = ops[operation]
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        join_filter_expression = self.parameterAsExpression(parameters, self.JOIN_FILTER_EXPRESSION, context)
        join_filter_expression = QgsExpression(join_filter_expression)
        join_n = self.parameterAsInt(parameters, self.JOIN_N, context)
        join_dist = self.parameterAsDouble(parameters, self.JOIN_DIST, context)
        join_prefix = self.parameterAsString(parameters, self.JOIN_PREFIX, context)
        
        sourcejoinlayerequal = False
        if join_n == 0:
            join_n =  2147483647 # float('inf') produces OverflowError: argument 'neighbors' overflowed: value must be in the range -2147483648 to 2147483647
        if source_layer_vl == join_layer:
            sourcejoinlayerequal = True
            if join_n < 2147483647:
                join_n += 1
        
        source_layer_fields = source_layer.fields()
        if join_fields:
            join_layer = join_layer.materialize(QgsFeatureRequest().setSubsetOfAttributes(join_fields, join_layer.fields()))
        join_layer_fields = join_layer.fields()
        output_layer_fields = source_layer_fields
        for join_layer_field in join_layer.fields():
            join_layer_field_copy = join_layer_field
            if join_prefix:
                join_layer_field_copy.setName(join_prefix + join_layer_field_copy.name())
            if join_layer_field_copy.name() in source_layer_fields.names():
                join_layer_field_copy.setName(join_layer_field_copy.name() + '_2')
            output_layer_fields.append(join_layer_field_copy)
        join_dist_field_name = 'dist'
        if join_prefix:
            join_dist_field_name = join_prefix + join_dist_field_name
        if join_dist_field_name in output_layer_fields.names():
            join_dist_field_name = join_dist_field_name + '_2'
        output_layer_fields.append(QgsField(join_dist_field_name, QVariant.Double, len=20, prec=5))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer.wkbType(),
                                               source_layer.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer = source_layer.materialize(QgsFeatureRequest(source_filter_expression))
        if join_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            join_layer = join_layer.materialize(QgsFeatureRequest(join_filter_expression))
        
        total = 100.0 / source_layer.featureCount() if source_layer.featureCount() else 0
        
        if source_layer.sourceCrs() != join_layer.sourceCrs():
            reproject_params = {'INPUT': join_layer, 'TARGET_CRS': source_layer.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            join_layer = reproject_result['OUTPUT']
        if method == 1:
            centroid_params = { 'ALL_PARTS' : False, 'INPUT' : join_layer, 'OUTPUT' : 'memory:Centroids' }
            centroid_result = processing.run("native:centroids", centroid_params)
            join_layer = centroid_result['OUTPUT']
        
        join_layer_idx = QgsSpatialIndex(join_layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        for current, source_feat in enumerate(source_layer.getFeatures()):
            if feedback.isCanceled():
                break
            matches_found_counter = 0
            
            if method == 0:
                source_feat_geom = source_feat.geometry()
            elif method == 1:
                source_feat_geom = source_feat.geometry().centroid()
                
            if op is None:
                nearest_neighbors = join_layer_idx.nearestNeighbor(source_feat_geom, neighbors = join_n, maxDistance = join_dist)
            else:
                nearest_neighbors = join_layer_idx.nearestNeighbor(source_feat_geom, neighbors = -1, maxDistance = join_dist)
            if sourcejoinlayerequal is True:
                nearest_neighbors.remove(source_feat.id())
            
            source_compare_expression_context = QgsExpressionContext()
            source_compare_expression_context.setFeature(source_feat)
            source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
            
            for join_feat_id in nearest_neighbors:
                if feedback.isCanceled():
                    break
                if matches_found_counter >= join_n:
                    break
                    
                join_feat = join_layer.getFeature(join_feat_id)
                join_compare_expression_context = QgsExpressionContext()
                join_compare_expression_context.setFeature(join_feat)
                join_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(join_layer))
                join_compare_expression_result = join_compare_expression.evaluate(join_compare_expression_context)
                if op is None:
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
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                #elif op(source_feat[source_field], join_feat[join_field]):
                elif op(source_compare_expression_result, join_compare_expression_result):
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
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                
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
        return self.tr('This Algorithm finds the x nearest neighbors by a given condition and joins them.')