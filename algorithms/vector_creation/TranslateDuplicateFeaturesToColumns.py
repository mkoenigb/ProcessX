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

import processing, random
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, 
                       QgsProcessingParameterEnum, QgsProcessingParameterField, QgsProcessingParameterExpression, QgsProcessingParameterBoolean)

class TranslateDuplicateFeaturesToColumns(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    DUPLICATE_EXPRESSION = 'DUPLICATE_EXPRESSION'
    DUPLICATE_METHOD = 'DUPLICATE_METHOD'
    PRESERVE_GEOMETRY = 'PRESERVE GEOMETRY'
    OUTPUT_STRUCTURE = 'OUTPUT_STRUCTURE'
    FIELDS_TO_TRANSLATE = 'FIELDS_TO_TRANSLATE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer (if left empty the FIDs are used)'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.DUPLICATE_EXPRESSION, self.tr('Expression or Field to identify duplicate Features'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DUPLICATE_METHOD, self.tr('Duplicate Identifier'), ['Use only an expression or field',
                                                                         'Use only geometry',
                                                                         'Use expression/field or geometry',
                                                                         'Use expression/field and geometry'],
                                                                        defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PRESERVE_GEOMETRY, self.tr('Preserve Geometry'), ['Keep first geometry of order-by expression',
                                                                       'Keep one random geometry of all duplicates',
                                                                       'Create one unary union multipart geometry of all duplicates'],
                                                                       defaultValue = 2, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_STRUCTURE, self.tr('Choose the desired structure for the output'), ['Create new field for each duplicate feature field',
                                                                                                'Create one dictionary string-field for each duplicate feature'], 
                                                                                                defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELDS_TO_TRANSLATE, self.tr('Fields to translate and duplicate \n(the fields containing the unique values; fields not chosen here, will only be added once for the first feature)\n(if none are chosen, all fields will be translated)'),parentLayerParameterName='SOURCE_LYR', allowMultiple = True, optional = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Translated')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        
        duplicate_expression = self.parameterAsExpression(parameters, self.DUPLICATE_EXPRESSION, context)
        duplicate_expression = QgsExpression(duplicate_expression)
        duplicate_method = self.parameterAsInt(parameters, self.DUPLICATE_METHOD, context)
        
        preserve_geometry = self.parameterAsInt(parameters, self.PRESERVE_GEOMETRY, context)
        output_structure = self.parameterAsInt(parameters, self.OUTPUT_STRUCTURE, context)
        fields_to_translate = self.parameterAsFields(parameters, self.FIELDS_TO_TRANSLATE, context)
        
        if duplicate_method in (0,2,3):
            if duplicate_expression in (QgsExpression(''),QgsExpression(None)):
                feedback.pushWarning('You chose to use an expression/field but did not enter a value for this!')
        
        total = 100.0 / (source_layer.featureCount()*2) if source_layer.featureCount() else 0
        current = 0
        
        if not fields_to_translate:
            fields_to_translate = source_layer.fields().names()
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
                
        source_layer_attr_dict = {}
        source_layer_expression_context = QgsExpressionContext()
        source_layer_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        duplicate_geom_dict = {}
        if duplicate_method in (1,2,3):
            feedback.setProgressText('Building spatial index...')
            source_layer_idx = QgsSpatialIndex(source_layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        feedback.setProgressText('Evaluating geometries/expressions...')
        for source_feat in source_layer.getFeatures(source_orderby_request):
            current += 1
            if feedback.isCanceled():
                break
            if duplicate_method in (0,2,3):
                source_layer_expression_context.setFeature(source_feat)
                source_layer_expression_result = duplicate_expression.evaluate(source_layer_expression_context)
                source_layer_attr_dict[source_feat.id()] = source_layer_expression_result 
            if duplicate_method in (1,2,3):
                duplicate_geom_dict[source_feat.id()] = []
                bbox_intersecting = source_layer_idx.intersects(source_feat.geometry().boundingBox())
                try:
                    bbox_intersecting.remove(source_feat.id())
                except:
                    pass
                source_feat_geometryengine = QgsGeometry.createGeometryEngine(source_feat.geometry().constGet())
                source_feat_geometryengine.prepareGeometry()
                for overlay_feat_id in bbox_intersecting:
                    overlay_feat_geom = source_layer_idx.geometry(overlay_feat_id).constGet()
                    if source_feat_geometryengine.isEqual(overlay_feat_geom):
                        duplicate_geom_dict[source_feat.id()].append(overlay_feat_id)
            feedback.setProgress(int(current * total))
                
        feedback.setProgressText('Setting up output structure...')
        duplicate_attr_dict = {}
        if duplicate_method in (0,2,3):
            for source_feat_id, value in source_layer_attr_dict.items():
                duplicate_attr_dict[source_feat_id] = [id for id, val in source_layer_attr_dict.items() if val == value]
                try:
                    duplicate_attr_dict[source_feat_id].remove(source_feat_id)
                except:
                    pass
        
        duplicate_dict = {}
        if duplicate_method in (2,3):
            # merge attr and geom dict: https://stackoverflow.com/a/59279514/8947209
            duplicate_dict = {k: list(d[k] for d in (duplicate_attr_dict, duplicate_geom_dict) if k in d) for k in set(duplicate_attr_dict.keys()) | set(duplicate_geom_dict.keys())}
            if duplicate_method == 2: # attr or geom duplicate
                # combine lists to one list and remove duplicates
                for k, v in duplicate_dict.items():
                    duplicate_dict[k] = list(set([item for sublist in v for item in sublist]))
            elif duplicate_method == 3: # attr and geom duplicate
                # combine lists to one list only if fid is in all sublists and remove duplicates
                for k, v in duplicate_dict.items():
                    duplicate_dict[k] = list(set.intersection(*[set(sublist) for sublist in v]))
        elif duplicate_method == 0:
            duplicate_dict = duplicate_attr_dict
        elif duplicate_method == 1:
            duplicate_dict = duplicate_geom_dict
        else:
            feedback.reportError('Undefined duplicate method!', fatalError = True)
        
        try:
            max_duplicate_fields = len(max(duplicate_dict.values(), key=len)) +1
        except:
            max_duplicate_fields = 0
        
        if max_duplicate_fields == 0:
            feedback.pushWarning('Could not find any duplicates!')
            
        output_layer_fields = QgsFields()
        for source_layer_field in source_layer.fields():
            if source_layer_field.name() not in fields_to_translate: # append the fields not to translate in front
                output_layer_fields.append(source_layer_field)
        
        if output_structure == 0: # Create a field
            for i in range(0,max_duplicate_fields):
                for field_name in fields_to_translate:
                    field_type = source_layer.fields().field(source_layer.fields().indexFromName(field_name)).type()
                    field_name = field_name + '_' + str(i)
                    output_layer_fields.append(QgsField(field_name,field_type))
            
        elif output_structure == 1: # Create one dictionary
            dict_fieldname = 'feature_dictionary'
            for i in range(0,max_duplicate_fields):
                output_layer_fields.append(QgsField(dict_fieldname + '_' + str(i), QVariant.String))
                
        cl = output_layer_fields.count()
        if cl > 250:
            feedback.pushWarning('WARNING: Output layer will have more than ' + str(cl) + ' fields. Expect QGIS to crash when you open the attribute table of the result!')
        else:
            feedback.setProgressText('Creating ' + str(cl) + ' fields for output layer...')
        maxstrlengthexceeded = False
        
        output_layer_wkbtype = source_layer.wkbType()
        if preserve_geometry == 2:
            output_layer_wkbtype = QgsWkbTypes.multiType(output_layer_wkbtype)
            
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, output_layer_wkbtype,
                                               source_layer.sourceCrs())
        
        feedback.setProgressText('Start processing...')
        duplicate_expression_context = QgsExpressionContext()
        duplicate_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
        skip_feats = []
        for source_feat in source_layer.getFeatures(source_orderby_request):
            current += 1
            feedback.setProgress(int(current * total))
            if feedback.isCanceled():
                break
            if source_feat.id() in skip_feats:
                continue
            
            new_feat = QgsFeature(output_layer_fields)
            new_feat_geom = QgsGeometry()
            duplicate_geoms = [source_feat.geometry()]
            duplicate_attrs = {}
            
            for source_feat_field in source_feat.fields():
                if source_feat_field.name() not in fields_to_translate:
                    new_feat[source_feat_field.name()] = source_feat.attribute(source_feat_field.name())
            
            if output_structure == 0: # Create a field
                for field_name in fields_to_translate:
                    new_feat[field_name + '_' + str(0)] = source_feat.attribute(field_name)
            if output_structure == 1: # Create one dictionary
                for field_name in fields_to_translate:
                    duplicate_attrs[field_name] = source_feat.attribute(field_name)
                new_feat[dict_fieldname + '_' + str(0)] = str(duplicate_attrs)
            
            duplicate_feature_ids = duplicate_dict[source_feat.id()]
            duplicate_cnt = 0
            for duplicate_feat_id in duplicate_feature_ids:
                if feedback.isCanceled():
                    break
                if duplicate_feat_id == source_feat.id():
                    continue
                if duplicate_feat_id in skip_feats:
                    continue
                duplicate_cnt += 1 # 0 is the source feat
                
                duplicate_request = QgsFeatureRequest()
                duplicate_request.setSubsetOfAttributes(fields_to_translate, source_layer.fields())
                duplicate_request.setFilterFid(duplicate_feat_id)
                duplicate_feat = next(source_layer.getFeatures(duplicate_request))
                
                duplicate_attrs = {}
                if output_structure == 0: # Create a field
                    for field_name in fields_to_translate:
                        new_feat[field_name + '_' + str(duplicate_cnt)] = duplicate_feat.attribute(field_name)
                if output_structure == 1: # Create one dictionary
                    for field_name in fields_to_translate:
                        duplicate_attrs[field_name] = duplicate_feat.attribute(field_name)
                    new_feat[dict_fieldname + '_' + str(duplicate_cnt)] = str(duplicate_attrs)
                duplicate_geoms.append(duplicate_feat.geometry())
                
                if len(str(duplicate_attrs)) > 1000:
                    maxstrlengthexceeded = True
                    
                skip_feats.append(duplicate_feat_id)
            skip_feats.append(source_feat.id())
            
            if preserve_geometry == 0: # Keep first geometry of order-by expression
                new_feat_geom = duplicate_geoms[0]
            elif preserve_geometry == 1: # Keep one random geometry of all duplicates
                new_feat_geom = random.choice(duplicate_geoms)
            elif preserve_geometry == 2: # Merge geometries of all duplicates to one multipart geometry
                new_feat_geom = QgsGeometry().unaryUnion(duplicate_geoms)
            new_feat.setGeometry(new_feat_geom)
            
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
        
        if output_structure == 1:
            if maxstrlengthexceeded:
                feedback.pushWarning('WARNING: At least one output attribute will have more than ' + str(1000) + ' characters. Open the attribute table of the result carefully and expect QGIS to crash!')
        
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TranslateDuplicateFeaturesToColumns()

    def name(self):
        return 'TranslateDuplicateFeaturesToColumns'

    def displayName(self):
        return self.tr('Translate Duplicate Features to Columns')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
            'This algorithm translates features (rows) to columns by an duplicate-identifier, which can be an expression, a field or geometry. \n'
            'You can choose which geometry of these duplicates you want to keep; either the first one in order-by expression or feature id, a random one or a unary union multipart geometry.\n'
            'You may also set up the output structure yourself. Duplicated fields ending with a 0 as postfix (original_fieldname_0) contain the information of the first feature. '
            '<b>Create new field for each duplicate feature field</b> creates a copy for each field per duplicate with a number as postfix in its name (original_fieldname_n) containing the attributes of the duplicate. '
            '<b>Warning:</b> If the number of fields exceed the limit of maximum fields possible, this can crash QGIS, especially when you open the attribute table of the result! '
            '<b>Create one dictionary string-field for each duplicate feature</b> creates one new string field with a number as postfix in its name (feature_dictionary_n) for each duplicate feature. '
            'This field contains a Python dictionary as string with the fieldnames as keys and its attributes as values. For example: <i>{\'field_one\':1,\'field_two\':\'some_attribute\',\'field_three\':42}</i>. '
            '<b>Warning:</b> If the number of fields exceed the limit of maximum fields possible, or the string length of its attributes exceeds the maximum string length possible, this can lead to an overflow and cause QGIS to crash, especially when opening the attribute table!\n'
            'In fields to translate you can choose the fields you want to translate. These will be copied as <i>original_fieldname_n</i> as explained above. '
            'The fields you do not choose here, will not be translated and kept as they are: <i>original_fieldname</i> having only the attribute information of the first feature in iteration order (you can set up individually in order-by expression).'
            )