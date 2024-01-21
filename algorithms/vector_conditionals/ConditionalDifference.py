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

class ConditionalDifference(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    CONCAT_METHOD = 'CONCAT_METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    ORDERBY_ASC = 'ORDERBY_ASC'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
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
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Choose geometric predicate(s). (Source *predicate* Overlay; e.g. Source within Overlay)'), ['within','intersects','overlaps','contains','equals','crosses','touches'], defaultValue = 2, allowMultiple = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONCAT_METHOD, self.tr('Choose how to handle several geometric predicates'), ['All geometric predicates must be true (AND)','At least one geometric predicate must be true (OR)'], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer (if unused, the feature id\'s are taken'), parentLayerParameterName = 'SOURCE_LYR', optional = True, defaultValue = 'coalesce($area,coalesce($length,coalesce($id)))'))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ORDERBY_ASC, self.tr('OrderBy Method'), ['Order Ascending (Features with larger values will keep the overlapping portions)',
                                                              'Order Descending (Features with smaller values will keep the overlapping portions)'],
                                                              defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.OVERLAY_LYR, self.tr('Overlay Layer (Features to count)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        
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
                self.OUTPUT, self.tr('Difference')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        method = self.parameterAsEnums(parameters, self.METHOD, context)
        concat_method = self.parameterAsInt(parameters, self.CONCAT_METHOD, context)
        #source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        orderby_asc = self.parameterAsEnum(parameters, self.ORDERBY_ASC, context)
        if orderby_asc == 0:
            orderby_asc = True
        elif orderby_asc == 1:
            orderby_asc = False
        
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
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
        
        sourceoverlayequal = False
        if source_layer_vl == overlay_layer_vl:
            sourceoverlayequal = True
            
        output_layer_fields = source_layer_vl.fields()
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, QgsWkbTypes.multiType(source_layer_vl.wkbType()),
                                               source_layer_vl.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest().setFilterFids(source_layer_vl.allFeatureIds()))
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        current = 0
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression, orderby_asc)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        if comparisons:
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
            if sourceoverlayequal:
                try:
                    overlay_features.remove(source_feat.id())
                except:
                    pass
            
            for overlay_feat_id in overlay_features:
                if feedback.isCanceled():
                    break
                    
                if sourceoverlayequal:
                    overlay_feat = source_layer_vl.getFeature(overlay_feat_id) # need to get it from the edited layer because the index is based on the original input
                else:
                    overlay_feat = overlay_layer_vl.getFeature(overlay_feat_id) # if source and overlay are different layers, one could implement this way more efficient. But since it is not guaranteed, its a lot easier to implement this way
                    
                overlay_feat_geom = overlay_feat.geometry()
                
                geometrictest = []
                if 0 in method:
                    if source_feat_geometryengine.within(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 1 in method:
                    if source_feat_geometryengine.intersects(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 2 in method:
                    if source_feat_geometryengine.overlaps(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 3 in method:
                    if source_feat_geometryengine.contains(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 4 in method:
                    if source_feat_geom.equals(overlay_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 5 in method:
                    if source_feat_geometryengine.crosses(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 6 in method:
                    if source_feat_geometryengine.touches(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                        
                geodoit = False
                if concat_method == 0: # and
                    if not False in geometrictest:
                        geodoit = True
                elif concat_method == 1: # or
                    if True in geometrictest:
                        geodoit = True
                
                if geodoit:
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
            if source_feat.geometry().isNull():
                feedback.pushWarning('No geometry remaining for feature ' + str(source_feat.id()) + '. Skipping feature...')
                continue
            sink.addFeature(source_feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))
            
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ConditionalDifference()

    def name(self):
        return 'ConditionalDifference'

    def displayName(self):
        return self.tr('Conditional Difference')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This algorithms builds a difference between two layers by an optional attribute condition. Both layers can basically be of any type, but of course not all constellation make sense and not all constellations will return a valid output. '
        'The output is an edited copy of the source layer (no, it does not do inplace edits).\n'
        'This algorithm is based on <i>"Remove Self-Overlapping Poritions by Condition"</i> algorithm, and therefore acts the same way if source and overlay layer are identical. '
        'The difference in that case is build on the already during processing modified source layer. '
        'But other than <i>Remove Self-Overlapping Portions by Condition</i> it also allows to remove overlapping/intersecting/... portions between two different layers. '
        'Overall you are free to choose which geometric predicate must be fullfilled, but expect some weird results if you do not choose wisely.\n'
        'If you use the optional attribute condition, the difference is only done if the condition between the <i>intersecting</i> features is met.\n'
        'You can choose the iteration order and therefore which feature should keep the <i>intersecting</i> parts. This is especially (or maybe only?) useful if source and overlay input are the same layer.\n'
        )