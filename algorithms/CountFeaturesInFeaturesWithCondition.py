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

class CountFeaturesInFeaturesWithCondition(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION = 'OVERLAY_COMPARE_EXPRESSION'
    COUNT_FIELDNAME = 'COUNT_FIELDNAME'
    OPERATION = 'OPERATION'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Choose geometric predicate(s). If several are chosen it acts like an OR operator. (Overlay *predicate* Source; e.g. Overlay within Source)'), ['within','intersects','overlaps','contains','equals','crosses','touches','disjoint'], defaultValue = 1, allowMultiple = True))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer (Features to add count to)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.OVERLAY_LYR, self.tr('Overlay Layer (Features to count)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterString(
                self.COUNT_FIELDNAME, self.tr('Count Fieldname'), defaultValue = 'count_n', optional = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','not','is not','contains (overlay in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION, self.tr('Compare-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Count')))

    def processAlgorithm(self, parameters, context, feedback):
        method = self.parameterAsEnums(parameters, self.METHOD, context)
        print(method)
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_compare_expression = self.parameterAsExpression(parameters, self.SOURCE_COMPARE_EXPRESSION, context)
        source_compare_expression = QgsExpression(source_compare_expression)
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        overlay_compare_expression = self.parameterAsExpression(parameters, self.OVERLAY_COMPARE_EXPRESSION, context)
        overlay_compare_expression = QgsExpression(overlay_compare_expression)
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
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
        count_fieldname = self.parameterAsString(parameters, self.COUNT_FIELDNAME, context)
        
        sourceoverlayequal = False
        if source_layer_vl == overlay_layer_vl:
            sourceoverlayequal = True
        
        source_layer_fields = source_layer_vl.fields()
        output_layer_fields = source_layer_fields
        if count_fieldname in output_layer_fields.names():
            count_fieldname = count_fieldname + '_2'
        output_layer_fields.append(QgsField(count_fieldname, QVariant.Int, len=20))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer_vl.wkbType(),
                                               source_layer_vl.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            overlay_layer_vl = reproject_result['OUTPUT']
        
        overlay_layer_idx = QgsSpatialIndex(overlay_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        for current, source_feat in enumerate(source_layer_vl.getFeatures()):
            if feedback.isCanceled():
                break
            source_feat_geom = source_feat.geometry()
            
            #methods: ['within','intersects','overlaps','contains','equals','crosses','touches','disjoint']
            if 7 in method:
                overlay_feature_ids = [feat.id() for feat in overlay_layer_vl.getFeatures()]
            else:
                overlay_feature_ids = overlay_layer_idx.intersects(source_feat_geom.boundingBox())
            if sourceoverlayequal is True:
                overlay_feature_ids.remove(source_feat.id())
            matching_counter = 0
            
            source_compare_expression_context = QgsExpressionContext()
            source_compare_expression_context.setFeature(source_feat)
            source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
            
            for overlay_feat_id in overlay_feature_ids:
                if feedback.isCanceled():
                    break
                
                overlay_feat = overlay_layer_vl.getFeature(overlay_feat_id)
                geometrictest = False
                if 0 in method:
                    if overlay_feat.geometry().within(source_feat_geom):
                        geometrictest = True
                if 1 in method:
                    if overlay_feat.geometry().intersects(source_feat_geom):
                        geometrictest = True
                if 2 in method:
                    if overlay_feat.geometry().overlaps(source_feat_geom):
                        geometrictest = True
                if 3 in method:
                    if overlay_feat.geometry().contains(source_feat_geom):
                        geometrictest = True
                if 4 in method:
                    if overlay_feat.geometry().equals(source_feat_geom):
                        geometrictest = True
                if 5 in method:
                    if overlay_feat.geometry().crosses(source_feat_geom):
                        geometrictest = True
                if 6 in method:
                    if overlay_feat.geometry().touches(source_feat_geom):
                        geometrictest = True
                if 7 in method:
                    if overlay_feat.geometry().disjoint(source_feat_geom):
                        geometrictest = True
                        
                if geometrictest is True:
                    overlay_compare_expression_context = QgsExpressionContext()
                    overlay_compare_expression_context.setFeature(overlay_feat)
                    overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                    overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                    if op is None:
                        matching_counter += 1
                    elif op(source_compare_expression_result, overlay_compare_expression_result):
                        matching_counter += 1
                        
            new_feat = QgsFeature(output_layer_fields)
            new_feat.setGeometry(source_feat_geom)
            attridx = 0
            for attr in source_feat.attributes():
                new_feat[attridx] = attr
                attridx += 1
            new_feat[count_fieldname] = matching_counter
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CountFeaturesInFeaturesWithCondition()

    def name(self):
        return 'CountFeaturesInFeaturesWithCondition'

    def displayName(self):
        return self.tr('Count Features in Features with Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr('This Algorithm counts features in features with a given condition')