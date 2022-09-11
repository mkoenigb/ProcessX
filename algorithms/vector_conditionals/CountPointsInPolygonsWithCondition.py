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
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingParameterBoolean)

class CountPointsInPolygonsWithCondition(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
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
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Choose geometric predicate'), ['within','intersects'], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer (Polygons to add count to)'), [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.OVERLAY_LYR, self.tr('Overlay Layer (2D-Single-Points to count)'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.COUNT_MULTIPLE, self.tr('Count Points more than once (if not checked, a feature is only counted for the first match, ordered by expression or feature id)'), optional = True, defaultValue = True))
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
        method = self.parameterAsInt(parameters, self.METHOD, context)
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
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
            if source_layer_vl.featureCount() + overlay_layer_vl.featureCount() > 0:
                total = 100.0 / (source_layer_vl.featureCount() + overlay_layer_vl.featureCount())
            else:
                total = 0
        else:
            total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        current = 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Overlay Layer...')
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            overlay_layer_vl = reproject_result['OUTPUT']
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndexKDBush(overlay_layer_vl.getFeatures())
        if overlay_layer_idx.size() == 0:
            feedback.pushWarning('Spatial Index is empty! Check if your input point layer is of type Single-Point 2D. This algorithm does not support 2.5D, 3D or MultiPoints!')
            
        if comparisons: # dictonaries are a lot faster than featurerequests; https://gis.stackexchange.com/q/434768/107424
            feedback.setProgressText('Evaluating expressions...')
            #overlay_layer_dict = {feat.id():feat for feat in overlay_layer_vl.getFeatures()}
            overlay_layer_dict = {}
            overlay_layer_dict2 = {}
            #request_nogeom = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry) # Can speed up the request, but makes expressions involving geometry (e.g. $area or others) impossible
            for overlay_feat in overlay_layer_vl.getFeatures():
                current += 1
                if feedback.isCanceled():
                    break
                overlay_compare_expression_context = QgsExpressionContext()
                overlay_compare_expression_context.setFeature(overlay_feat)
                overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                overlay_layer_dict[overlay_feat.id()] = overlay_compare_expression_result 
                overlay_compare_expression_context2 = QgsExpressionContext()
                overlay_compare_expression_context2.setFeature(overlay_feat)
                overlay_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                overlay_compare_expression_result2 = overlay_compare_expression2.evaluate(overlay_compare_expression_context2)
                overlay_layer_dict2[overlay_feat.id()] = overlay_compare_expression_result2
                feedback.setProgress(int(current * total))
        overlay_layer_skip = []
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        for source_feat in source_layer_vl.getFeatures(source_orderby_request):
            current += 1
            if feedback.isCanceled():
                break
            source_feat_geom = source_feat.geometry()
            source_feat_geometryengine = QgsGeometry.createGeometryEngine(source_feat_geom.constGet())
            source_feat_geometryengine.prepareGeometry()
            
            overlay_features = overlay_layer_idx.intersects(source_feat_geom.boundingBox())
            matching_counter = 0
            
            if comparisons:
                source_compare_expression_context = QgsExpressionContext()
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2 = QgsExpressionContext()
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
            for overlay_feat in overlay_features:
                if feedback.isCanceled():
                    break
                
                if overlay_feat.id in overlay_layer_skip:
                    continue
                
                overlay_feat_geom = QgsGeometry.fromPointXY(overlay_feat.point()).constGet()
                
                geometrictest = False
                if method == 0:
                    if source_feat_geometryengine.contains(overlay_feat_geom):
                        geometrictest = True
                if method == 1:
                    if source_feat_geometryengine.intersects(overlay_feat_geom):
                        geometrictest = True
                        
                if geometrictest:
                    if not comparisons:
                        matching_counter += 1
                        if count_multiple is False:
                            overlay_layer_skip.append(overlay_feat.id)
                    else:
                        #overlay_real_feat = overlay_layer_dict[overlay_feat.id]
                        #overlay_real_feat = overlay_layer_vl.getFeature(overlay_feat.id)
                        overlay_compare_expression_result = overlay_layer_dict[overlay_feat.id]
                        overlay_compare_expression_result2 = overlay_layer_dict2[overlay_feat.id]
                        #overlay_compare_expression_context = QgsExpressionContext()
                        #overlay_compare_expression_context.setFeature(overlay_real_feat)
                        #overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
                        #overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                        if concat_op(op(source_compare_expression_result, overlay_compare_expression_result),op2(source_compare_expression_result2, overlay_compare_expression_result2)):
                            matching_counter += 1
                            if count_multiple is False:
                                overlay_layer_skip.append(overlay_feat.id)
                        
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
        return CountPointsInPolygonsWithCondition()

    def name(self):
        return 'CountPointsInPolygonsWithCondition'

    def displayName(self):
        return self.tr('Count Points In Polygons With Condition')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr('This algorithm counts points in polygons with given condition(s). '
                       'This algorithm does only work with 2D-Single-Points, Multi-Points or 3D-Points are not supported; '
                       'it is much faster than "Count Features in Features with Condition" if you want to count points in polygons')