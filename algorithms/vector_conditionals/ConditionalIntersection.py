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
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometryEngine, QgsGeometry,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterBoolean, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString)

class ConditionalIntersection(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION = 'SOURCE_COMPARE_EXPRESSION'
    SOURCE_COMPARE_EXPRESSION2 = 'SOURCE_COMPARE_EXPRESSION2'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FIELDS = 'OVERLAY_FIELDS'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION = 'OVERLAY_COMPARE_EXPRESSION'
    OVERLAY_COMPARE_EXPRESSION2 = 'OVERLAY_COMPARE_EXPRESSION2'
    OVERLAY_PREFIX = 'OVERLAY_PREFIX'
    OPERATION = 'OPERATION'
    OPERATION2 = 'OPERATION2'
    CONCAT_OPERATION = 'CONCAT_OPERATION'
    INTERSECT_MULTIPLE = 'INTERSECT_MULTIPLE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.OVERLAY_LYR, self.tr('Overlay Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.OVERLAY_FILTER_EXPRESSION, self.tr('Filter-Expression for Overlay-Layer'), parentLayerParameterName = 'OVERLAY_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterField(
                self.OVERLAY_FIELDS, self.tr('Add the following fields of overlay layer to result (if none are chosen, all fields will be added)'),parentLayerParameterName='OVERLAY_LYR', allowMultiple = True, optional = True))
        self.addParameter(
            QgsProcessingParameterString(
                self.OVERLAY_PREFIX, self.tr('Overlay Field-Prefix'), defaultValue = 'overlay_', optional = True))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.INTERSECT_MULTIPLE, self.tr('Intersect features more than once (if not checked, an intersection is only built with the first match, ordered by expression or feature id)'), optional = True, defaultValue = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_COMPARE_EXPRESSION, self.tr('Compare-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPERATION, self.tr('Comparison operator (if no operator is set, the comparison expressions/fields remain unused) [optional]'), [None,'!=','=','<','>','<=','>=','is','is not','contains (join in source)'], defaultValue = 0, allowMultiple = False))
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
                self.OUTPUT, self.tr('Intersection')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
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
        overlay_fields = self.parameterAsFields(parameters, self.OVERLAY_FIELDS, context)
        
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
        overlay_prefix = self.parameterAsString(parameters, self.OVERLAY_PREFIX, context)
        intersect_multiple = self.parameterAsBool(parameters, self.INTERSECT_MULTIPLE, context)
        
        
        sourceoverlayequal = False
        if source_layer_vl == overlay_layer_vl:
            sourceoverlayequal = True
        
        source_layer_fields = source_layer_vl.fields()
        if overlay_fields:
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest().setSubsetOfAttributes(overlay_fields, overlay_layer_vl.fields()))
        overlay_layer_fields = overlay_layer_vl.fields()
        output_layer_fields = source_layer_fields
        for overlay_layer_field in overlay_layer_fields:
            overlay_layer_field_copy = overlay_layer_field
            if overlay_prefix:
                overlay_layer_field_copy.setName(overlay_prefix + overlay_layer_field_copy.name())
            if overlay_layer_field_copy.name() in source_layer_fields.names():
                overlay_layer_field_copy.setName(overlay_layer_field_copy.name() + '_2')
            output_layer_fields.append(overlay_layer_field_copy)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer_vl.wkbType(),
                                               source_layer_vl.sourceCrs())
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Overlay Layer...')
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params)
            overlay_layer_vl = reproject_result['OUTPUT']
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        source_compare_expression_context = QgsExpressionContext()
        source_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        source_compare_expression_context2 = QgsExpressionContext()
        source_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        overlay_compare_expression_context = QgsExpressionContext()
        overlay_compare_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
        overlay_compare_expression_context2 = QgsExpressionContext()
        overlay_compare_expression_context2.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
        for current, source_feat in enumerate(source_layer_vl.getFeatures(source_orderby_request)):
            if feedback.isCanceled():
                break
            
            source_feat_geom = source_feat.geometry().constGet()
            # Speeding up processing by using QgsGeometryEngine, see https://api.qgis.org/api/classQgsGeometryEngine.html
            source_feat_geometryengine = QgsGeometry.createGeometryEngine(source_feat_geom)
            source_feat_geometryengine.prepareGeometry()
            
            bbox_intersecting = overlay_layer_idx.intersects(source_feat_geom.boundingBox())
            if sourceoverlayequal is True:
                bbox_intersecting.remove(source_feat.id())
            
            if comparisons:
                source_compare_expression_context.setFeature(source_feat)
                source_compare_expression_result = source_compare_expression.evaluate(source_compare_expression_context)
                source_compare_expression_context2.setFeature(source_feat)
                source_compare_expression_result2 = source_compare_expression2.evaluate(source_compare_expression_context2)
            
            for overlay_feat_id in bbox_intersecting:
                if feedback.isCanceled():
                    break
                    
                overlay_feat_geom = overlay_layer_idx.geometry(overlay_feat_id).constGet()
                
                if source_feat_geometryengine.intersects(overlay_feat_geom):
                    overlay_feat = overlay_layer_vl.getFeature(overlay_feat_id)
                    
                    if not comparisons:
                        new_feat = QgsFeature(output_layer_fields)
                        new_feat.setGeometry(source_feat_geometryengine.intersection(overlay_feat_geom))
                        attridx = 0
                        for attr in source_feat.attributes():
                            new_feat[attridx] = attr
                            attridx += 1
                        for attr in overlay_feat.attributes():
                            new_feat[attridx] = attr
                            attridx += 1
                        sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                        if intersect_multiple is False:
                            overlay_layer_idx.deleteFeature(overlay_feat)
                    else:
                        overlay_compare_expression_context.setFeature(overlay_feat)
                        overlay_compare_expression_result = overlay_compare_expression.evaluate(overlay_compare_expression_context)
                        overlay_compare_expression_context2.setFeature(overlay_feat)
                        overlay_compare_expression_result2 = overlay_compare_expression2.evaluate(overlay_compare_expression_context2)
                        if concat_op(op(source_compare_expression_result, overlay_compare_expression_result),op2(source_compare_expression_result2, overlay_compare_expression_result2)):
                            new_feat = QgsFeature(output_layer_fields)
                            new_feat.setGeometry(source_feat_geometryengine.intersection(overlay_feat_geom))
                            attridx = 0
                            for attr in source_feat.attributes():
                                new_feat[attridx] = attr
                                attridx += 1
                            for attr in overlay_feat.attributes():
                                new_feat[attridx] = attr
                                attridx += 1
                            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                            if intersect_multiple is False:
                                overlay_layer_idx.deleteFeature(overlay_feat)
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ConditionalIntersection()

    def name(self):
        return 'ConditionalIntersection'

    def displayName(self):
        return self.tr('Conditional Intersection')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr('This Algorithm builds an intersection if a given condition is fullfilled. It can also be used as polygon-self-intersection.')