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
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsSpatialIndexKDBush, QgsGeometry, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, 
                       QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, 
                       QgsProcessingParameterString, QgsProcessingParameterBoolean)

class CountNearestFeaturesByCondition(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION2 = 'SOURCE_COMPARE_EXPRESSION2'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION = 'OVERLAY_COMPARE_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION2 = 'OVERLAY_COMPARE_EXPRESSION2'
    COUNT_FIELDNAME = 'COUNT_FIELDNAME'
    OPERATION = 'OPERATION'
    OPERATION2 = 'OPERATION2'
    CONCAT_OPERATION = 'CONCAT_OPERATION'
    COUNT_MULTIPLE = 'COUNT_MULTIPLE'
    MAX_DIST = 'MAX_DIST'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer (Features to add count to)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.OVERLAY_LYR, self.tr('Overlay Layer (Features to count)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterDistance(
                self.MAX_DIST, self.tr('Maximum search distance (0 means unlimited)'), parentParameterName = 'SOURCE_LYR', optional = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.COUNT_MULTIPLE, self.tr('Count Features more than once\n(if not checked, a feature is only counted for the nearest feature.\nIn case more than one feature has the same minimum distance, it takes the first one)'), optional = True, defaultValue = True))
        self.addParameter(
            QgsProcessingParameterString(
                self.COUNT_FIELDNAME, self.tr('Count Fieldname'), defaultValue = 'count_n', optional = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (overlay in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION, self.tr('Compare-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONCAT_OPERATION, self.tr('And / Or a second condition. (To only use one condition, leave this to AND)'), ['AND','OR','XOR','iAND','iOR','iXOR','IS','IS NOT'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION2, self.tr('Second comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (overlay in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Count')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        source_compare_expression2 = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION2, context)
        source_compare_expression2 = QgsExpression(source_compare_expression2)
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
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
        
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
        count_fieldname = self.parameterAsString(parameters, self.COUNT_FIELDNAME, context)
        count_multiple = self.parameterAsBool(parameters, self.COUNT_MULTIPLE, context)
        max_dist = self.parameterAsDouble(parameters, self.MAX_DIST, context)
        
        sourceoverlayequal = False
        if source_layer_vl == overlay_layer_vl:
            sourceoverlayequal = True
        
        source_layer_fields = source_layer_vl.fields()
        output_layer_fields = source_layer_fields
        whilecounter = 0
        while count_fieldname in output_layer_fields.names():
            whilecounter += 1
            count_fieldname = count_fieldname + '_2'
            if whilecounter > 9:
                feedback.setProgressText('You should clean up your fieldnames!')
                break
        
        output_layer_fields.append(QgsField(count_fieldname, QVariant.Int))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer_vl.wkbType(),
                                               source_layer_vl.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        
        if comparisons:
            if source_layer_vl.featureCount() * 2 + overlay_layer_vl.featureCount() > 0:
                total = 100.0 / (source_layer_vl.featureCount() * 2 + overlay_layer_vl.featureCount())
            else:
                total = 0
        else:
            total = 100.0 / (source_layer_vl.featureCount() + overlay_layer_vl.featureCount()) if (source_layer_vl.featureCount() + overlay_layer_vl.featureCount()) > 0 else 0
        current = 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Overlay Layer...')
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            overlay_layer_vl = reproject_result['OUTPUT']
        
        feedback.setProgressText('Building spatial index...')
        source_layer_idx = QgsSpatialIndex(source_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
            
        if comparisons: # dictonaries are a lot faster than featurerequests; https://gis.stackexchange.com/q/434768/107424
            feedback.setProgressText('Evaluating expressions...')
            source_layer_dict = {}
            source_layer_dict2 = {}
            for source_feat in source_layer_vl.getFeatures():
                current += 1
                source_compare_expression_context = QgsExpressionContext()
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_layer_dict[source_feat.id()] = source_compare_expression_result 
                source_compare_expression_context2 = QgsExpressionContext()
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
                source_layer_dict2[source_feat.id()] = source_compare_expression_result2
                feedback.setProgress(int(current * total))
        result_dict = {}
        
        feedback.setProgressText('Start processing...')
        for overlay_feat in overlay_layer_vl.getFeatures():
            current += 1
            if feedback.isCanceled():
                break
            
            nearest_source_features = source_layer_idx.nearestNeighbor(overlay_feat.geometry(), neighbors = -1, maxDistance = max_dist)
            if sourceoverlayequal:
                nearest_source_features.remove(overlay_feat.id())
            
            if comparisons:
                overlay_compare_expression_context = QgsExpressionContext()
                overlay_compare_expression_context.setFeature(overlay_feat)
                overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                overlay_compare_expression_context2 = QgsExpressionContext()
                overlay_compare_expression_context2.setFeature(overlay_feat)
                overlay_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                overlay_compare_expression_result2 = overlay_compare_expression2.evaluate(overlay_compare_expression_context2)
                        
            for source_feat_id in nearest_source_features:
                if feedback.isCanceled():
                    break
                
                doit = False
                if comparisons:
                    source_compare_expression_result = source_layer_dict[source_feat_id]
                    source_compare_expression_result2 = source_layer_dict2[source_feat_id]
                    if concat_op(op(source_compare_expression_result, overlay_compare_expression_result),op2(source_compare_expression_result2, overlay_compare_expression_result2)):
                        doit = True
                else:
                    doit = True
                    
                if doit:
                    if source_feat_id not in result_dict:
                        result_dict[source_feat_id] = 0
                    result_dict[source_feat_id] += 1
                    if not count_multiple:
                        break
            feedback.setProgress(int(current * total))
            
        feedback.setProgressText('Creating result layer...')
        for source_feat in source_layer_vl.getFeatures():
            new_feat = QgsFeature(output_layer_fields)
            new_feat.setGeometry(source_feat.geometry())
            attridx = 0
            for attr in source_feat.attributes():
                new_feat[attridx] = attr
                attridx += 1
            if source_feat.id() not in result_dict:
                new_feat[count_fieldname] = 0
            else:
                new_feat[count_fieldname] = result_dict[source_feat.id()]
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CountNearestFeaturesByCondition()

    def name(self):
        return 'CountNearestFeaturesByCondition'

    def displayName(self):
        return self.tr('Count Nearest Features by Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr('This algorithm counts nearest features by a maximum search distance and optional attribute condition(s).\nYou may choose whether a feature should be counted more than once, if you deny, that feature is only counted to the nearest match.')