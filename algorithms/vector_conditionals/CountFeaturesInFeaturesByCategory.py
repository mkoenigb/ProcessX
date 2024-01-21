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

import processing
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometry, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, 
                       QgsProcessingParameterString, QgsProcessingParameterBoolean)

class CountFeaturesInFeaturesByCategory(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    CONCAT_METHOD = 'CONCAT_METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    OVERLAY_LYR = 'OVERLAY_LYR'
    OVERLAY_FILTER_EXPRESSION = 'OVERLAY_FILTER_EXPRESSION'
    OVERLAY_CATEGORY_EXPRESSION = 'OVERLAY_CATEGORY_EXPRESSION'
    COUNT_FIELDNAME = 'COUNT_FIELDNAME'
    CATEGORY_FIELDNAME = 'CATEGORY_FIELDNAME'
    COUNT_MULTIPLE = 'COUNT_MULTIPLE'
    OUTPUT_STRUCTURE = 'OUTPUT_STRUCTURE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer (Features to add count to)')))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
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
            QgsProcessingParameterExpression(
                self.OVERLAY_CATEGORY_EXPRESSION, self.tr('Category-Expression or Field for Overlay-Layer containing the different Categories'), parentLayerParameterName = 'OVERLAY_LYR', optional = False))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_STRUCTURE, self.tr('Choose the desired structure for the output'), ['Create a feature for each category','Create a field for each category','Create one dictionary/map for all categories'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, self.tr('Choose geometric predicate(s). (Overlay *predicate* Source; e.g. Overlay within Source)'), ['within','intersects','overlaps','contains','equals','crosses','touches','disjoint'], defaultValue = 1, allowMultiple = True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONCAT_METHOD, self.tr('Choose how to handle several geometric predicates'), ['All geometric predicates must be true (AND)','At least one geometric predicate must be true (OR)'], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.COUNT_MULTIPLE, self.tr('Count Features more than once (if not checked, a feature is only counted for the first match, ordered by expression or feature id)'), optional = True, defaultValue = True))
        self.addParameter(
            QgsProcessingParameterString(
                self.CATEGORY_FIELDNAME, self.tr('Category Fieldname'), defaultValue = 'category_count_ind', optional = False))
        self.addParameter(
            QgsProcessingParameterString(
                self.COUNT_FIELDNAME, self.tr('Count Fieldname or Count Prefix'), defaultValue = 'category_count_n', optional = False))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('CategoryCount')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        
        #source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        
        overlay_layer_vl = self.parameterAsLayer(parameters, self.OVERLAY_LYR, context)
        overlay_category_expression = self.parameterAsExpression(parameters, self.OVERLAY_CATEGORY_EXPRESSION, context)
        overlay_category_expression = QgsExpression(overlay_category_expression)
        
        output_structure = self.parameterAsInt(parameters, self.OUTPUT_STRUCTURE, context)
        method = self.parameterAsEnums(parameters, self.METHOD, context)
        concat_method = self.parameterAsInt(parameters, self.CONCAT_METHOD, context)
        
        category_fieldname = self.parameterAsString(parameters, self.CATEGORY_FIELDNAME, context)
        count_fieldname = self.parameterAsString(parameters, self.COUNT_FIELDNAME, context)
        count_multiple = self.parameterAsBool(parameters, self.COUNT_MULTIPLE, context)
        
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        overlay_filter_expression = self.parameterAsExpression(parameters, self.OVERLAY_FILTER_EXPRESSION, context)
        overlay_filter_expression = QgsExpression(overlay_filter_expression)
        
        
        sourceoverlayequal = False
        if source_layer_vl == overlay_layer_vl:
            sourceoverlayequal = True
        
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer_vl = source_layer_vl.materialize(QgsFeatureRequest(source_filter_expression))
        if overlay_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            overlay_layer_vl = overlay_layer_vl.materialize(QgsFeatureRequest(overlay_filter_expression))
        
        if source_layer_vl.featureCount() + overlay_layer_vl.featureCount() > 0:
            total = 100.0 / (source_layer_vl.featureCount() + overlay_layer_vl.featureCount())
        else:
            total = 0
        current = 0
        
        if source_layer_vl.sourceCrs() != overlay_layer_vl.sourceCrs():
            feedback.setProgressText('Reprojecting Overlay Layer...')
            reproject_params = {'INPUT': overlay_layer_vl, 'TARGET_CRS': source_layer_vl.sourceCrs(), 'OUTPUT': 'memory:Reprojected'}
            reproject_result = processing.run('native:reprojectlayer', reproject_params, context=context, feedback=feedback)
            overlay_layer_vl = reproject_result['OUTPUT']
        
        feedback.setProgressText('Building spatial index...')
        overlay_layer_idx = QgsSpatialIndex(overlay_layer_vl.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries, feedback=feedback)
        if 7 in method:
            all_overlay_feature_ids = [feat.id() for feat in overlay_layer_vl.getFeatures()]
            
        feedback.setProgressText('Evaluating expressions...')
        overlay_layer_dict = {}
        overlay_category_expression_context = QgsExpressionContext()
        overlay_category_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(overlay_layer_vl))
        for overlay_feat in overlay_layer_vl.getFeatures(): # setting subset to nogeometry would speed up things but would make expressions using geometry not possible..
            current += 1
            if feedback.isCanceled():
                break
            overlay_category_expression_context.setFeature(overlay_feat)
            overlay_category_expression_result = overlay_category_expression.evaluate(overlay_category_expression_context)
            overlay_layer_dict[overlay_feat.id()] = overlay_category_expression_result 
            feedback.setProgress(int(current * total))
        overlay_layer_skip = []
        
        categories = list(set(overlay_layer_dict.values()))
        categories.sort()
        
        cl = len(categories)
        feedback.setProgressText('Creating counts for ' + str(cl) + ' different categories...')
        
        if output_structure == 1:
            if cl > 250:
                feedback.pushWarning('WARNING: Output layer will have more than ' + str(cl) + ' category fields. Expect QGIS to crash when you open the attribute table of the result!')
        if output_structure == 2:
            cl = sum(len(str(s)) for s in categories)
            if cl > 1000:
                feedback.pushWarning('WARNING: Output attributes will have more than ' + str(cl) + ' characters. Expect QGIS to crash when you open the attribute table of the result!')
        
        feedback.setProgressText('Setting up output structure...')
        field_name_dict = {
                'category_fieldname' : category_fieldname,
                'count_fieldname' : count_fieldname,
            }
        source_layer_fields = source_layer_vl.fields()
        output_layer_fields = source_layer_fields
        
        if output_structure == 0: # Create a feature for each category
            whilecounter = 0
            while any(elem in field_name_dict.values() for elem in output_layer_fields.names()):
                whilecounter += 1
                for var,name in field_name_dict.items():
                    field_name_dict[var] = name + '_2'
                if whilecounter > 9:
                    feedback.setProgressText('You should clean up your fieldnames!')
                    break
            output_layer_fields.append(QgsField(field_name_dict['category_fieldname'], QVariant.String))
            output_layer_fields.append(QgsField(field_name_dict['count_fieldname'], QVariant.Int))
            
        elif output_structure == 1: # Create a field for each category
            whilecounter = 0
            while count_fieldname in output_layer_fields.names():
                whilecounter += 1
                field_name_dict['count_fieldname'] = count_fieldname + '_2'
                if whilecounter > 9:
                    feedback.setProgressText('You should clean up your fieldnames!')
                    break
            #output_layer_fields.append(QgsField(field_name_dict['category_fieldname'], QVariant.String))
            for category in categories:
                output_layer_fields.append(QgsField(field_name_dict['count_fieldname'] + '_' + str(category), QVariant.Int))
            
        elif output_structure == 2: # Create one dictionary/map for all categories
            output_layer_fields.append(QgsField(field_name_dict['category_fieldname'], QVariant.String))
            #output_layer_fields.append(QgsField(field_name_dict['count_fieldname'], QVariant.Int))
        
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer_vl.wkbType(),
                                               source_layer_vl.sourceCrs())
        
        
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
            
            #methods: ['within','intersects','overlaps','contains','equals','crosses','touches','disjoint']
            if 7 in method:
                overlay_feature_ids = all_overlay_feature_ids
            else:
                overlay_feature_ids = overlay_layer_idx.intersects(source_feat_geom.boundingBox())
            if sourceoverlayequal is True:
                overlay_feature_ids.remove(source_feat.id())
            matching_counter = 0
            
            source_feat_results = dict.fromkeys(categories, 0)
            
            for overlay_feat_id in overlay_feature_ids:
                if feedback.isCanceled():
                    break
                if overlay_feat_id in overlay_layer_skip:
                    continue
                    
                overlay_feat_geom = overlay_layer_idx.geometry(overlay_feat_id)
                
                geometrictest = []
                if 0 in method:
                    if overlay_feat_geom.within(source_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 1 in method:
                    if source_feat_geometryengine.intersects(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 2 in method:
                    if overlay_feat_geom.overlaps(source_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 3 in method:
                    if overlay_feat_geom.contains(source_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 4 in method:
                    if source_feat_geom.equals(overlay_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 5 in method:
                    if overlay_feat_geom.crosses(source_feat_geom):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 6 in method:
                    if source_feat_geometryengine.touches(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                if 7 in method:
                    if source_feat_geometryengine.disjoint(overlay_feat_geom.constGet()):
                        geometrictest.append(True)
                    else:
                        geometrictest.append(False)
                        
                doit = False
                if concat_method == 0: # and
                    if not False in geometrictest:
                        doit = True
                elif concat_method == 1: # or
                    if True in geometrictest:
                        doit = True
                        
                if doit:
                    source_feat_results[overlay_layer_dict[overlay_feat_id]] += 1
                    matching_counter += 1
                    if count_multiple is False:
                        overlay_layer_skip.append(overlay_feat_id)
                        
            
            if output_structure == 0: # Create a feature for each category
                for category, count in source_feat_results.items():
                    if feedback.isCanceled():
                        break
                    new_feat = QgsFeature(output_layer_fields)
                    new_feat.setGeometry(source_feat_geom)
                    attridx = 0
                    for attr in source_feat.attributes():
                        new_feat[attridx] = attr
                        attridx += 1
                    new_feat[field_name_dict['category_fieldname']] = category
                    new_feat[field_name_dict['count_fieldname']] = count
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                    
            elif output_structure == 1: # Create a field for each category
                new_feat = QgsFeature(output_layer_fields)
                new_feat.setGeometry(source_feat_geom)
                attridx = 0
                for attr in source_feat.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
                for category, count in source_feat_results.items():
                    #new_feat[field_name_dict['category_fieldname']] = None
                    new_feat[field_name_dict['count_fieldname'] + '_' + str(category)] = count
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                
            elif output_structure == 2: # Create one dictionary/map for all categories
                new_feat = QgsFeature(output_layer_fields)
                new_feat.setGeometry(source_feat_geom)
                attridx = 0
                for attr in source_feat.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
                new_feat[field_name_dict['category_fieldname']] = str(source_feat_results)
                #new_feat[field_name_dict['count_fieldname']] = None
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CountFeaturesInFeaturesByCategory()

    def name(self):
        return 'CountFeaturesInFeaturesByCategory'

    def displayName(self):
        return self.tr('Count Features in Features by Category')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
            'This Algorithm counts features in features (both can be Points, Lines or Polygons of any type) by a given category, evaluated either via an expression or a field. '
            'If it does not find a match, it adds a 0 as count.\n'
            'You can also choose one or multiple geometric predicate(s) on which features you want to count and set whether only at least one predicate must match or all of them. '
            'Additionally you may choose whether a feature should be counted only once or multiple times.\n'
            'You can set up the structure of the output layer yourself, the options are:\n'
            '\n<b>Create a feature for each category</b>: This creates a new feature for every source feature and every possible category. You will get n_source_features * n_categories = n_output_features with two fields; '
                                                        'One indicating the name of the category and one having the count of this category. '
            
            '\n<b>Create a field for each category</b>: This creates one single feature for every source feature with one field for each category containing the count of this category for this feature. '
                                                       '<b>Warning: </b>If the number of different categories exceed the limit of maximum fields possible, this option can crash QGIS (especially when opening the attribute table). '
            
            '\n<b>Create a dictionary/map for all categories</b>: This creates one single feature for every source feature with one field containing the results for this feature. '
                                                                 'The result will be a string in form of a Python dictionary with the category names as keys and the category counts as values, like <i>{\'cat_a\':0,\'cat_b\':13,\'cat_c\':7}</i>. '
                                                                 '<b>Warning: </b>If the length of the sum of all different category names exceeds the maximum string length, this option can crash QGIS (especially when opening the attribute table). '
            
            '\nWith both options you are save if you do not have weird characters in the category names, a lot of different categories and the category names are quite short. If you are unsure, just use <i>Create a feature for each category</i>.'
            )