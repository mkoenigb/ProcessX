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

import processing, operator
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsWkbTypes, QgsVectorLayer, 
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterVectorLayer, QgsProcessingParameterEnum, QgsProcessingParameterExpression)

class RemoveSelfOverlappingPortionsByCondition(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    ORDERBY_ASC = 'ORDERBY_ASC'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
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
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer (if unused, the feature id\'s are taken'), parentLayerParameterName = 'SOURCE_LYR', optional = True, defaultValue = '$area'))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ORDERBY_ASC, self.tr('OrderBy Method'), ['Order Ascending (Features with larger values will keep the overlapping portions)',
                                                              'Order Descending (Features with smaller values will keep the overlapping portions)']
                                                              , defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (join in source)'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_COMPARE_EXPRESSION, self.tr('Compare-Expression for Overlay-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
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
                self.OVERLAY_COMPARE_EXPRESSION2, self.tr('Second compare-Expression for Overlay-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Source Layer without Self-Intersections')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        #source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        orderby_asc = self.parameterAsEnum(parameters, self.ORDERBY_ASC, context)
        if orderby_asc == 0:
            orderby_asc = True
        elif orderby_asc == 1:
            orderby_asc = False
            
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        
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
            
        output_layer_fields = source_layer_vl.fields()
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, QgsWkbTypes.multiType(source_layer_vl.wkbType()),
                                               source_layer_vl.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest().setFilterFids(source_layer_vl.allFeatureIds()))
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        current = 0
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(source_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression, orderby_asc)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        source_compare_expression_context = QgsExpressionContext()
        source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context2 = QgsExpressionContext()
        source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        overlay_compare_expression_context = QgsExpressionContext()
        overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        overlay_compare_expression_context2 = QgsExpressionContext()
        overlay_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        for source_feat in source_layer_vl.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            current += 1
            
            if comparisons:
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
                
            source_feat_geom = source_feat.geometry()
            source_feat_geometryengine = QgsGeometry.createGeometryEngine(source_feat_geom.constGet())
            source_feat_geometryengine.prepareGeometry()
            
            overlay_features = overlay_layer_idx.intersects(source_feat_geom.boundingBox())
            try:
                overlay_features.remove(source_feat.id())
            except:
                pass
            
            for overlay_feat_id in overlay_features:
                if feedback.isCanceled():
                    break
                overlay_feat = source_layer_vl.getFeature(overlay_feat_id) # need to get it from the edited layer because the index is based on the original input
                overlay_feat_geom = overlay_feat.geometry()
                if source_feat_geometryengine.overlaps(overlay_feat_geom.constGet()):
                    doit = False
                    if comparisons:
                        overlay_compare_expression_context.setFeature(overlay_feat)
                        overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                        overlay_compare_expression_context2.setFeature(overlay_feat)
                        overlay_compare_expression_result2 = overlay_compare_expression2.evaluate(overlay_compare_expression_context2)
                        if concat_op(op(source_compare_expression_result, overlay_compare_expression_result),op2(source_compare_expression_result2, overlay_compare_expression_result2)):
                            doit = True
                    else:
                        doit = True
                    if doit:
                        source_layer_vl.startEditing()
                        source_feat.geometry().convertToMultiType()
                        source_feat.setGeometry(source_feat.geometry().difference(overlay_feat.geometry()))
                        source_layer_vl.updateFeature(source_feat)
                        source_layer_vl.commitChanges()
            #if not source_feat.geometry().isGeosValid():
            #    feedback.pushWarning('Invalid geometry for feature ' + str(source_feat.id()) + '. Skipping feature...')
            #    continue
            sink.addFeature(source_feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))
            
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveSelfOverlappingPortionsByCondition()

    def name(self):
        return 'RemoveSelfOverlappingPortionsByCondition'

    def displayName(self):
        return self.tr('Remove Self-Overlapping Portions by Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithm removes self overlapping portions within a layer by an optional condition.'
        )