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

import processing
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsSpatialIndexKDBush, QgsGeometry, QgsPoint, QgsPointXY, QgsWkbTypes,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingParameterBoolean)

class NearestPointsToPath(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_LYR_ORDERBY = 'SOURCE_LYR_ORDERBY'
    SOURCE_FILTER_EXPRESSION = 'SOURCE_FILTER_EXPRESSION'
    SOURCE_GROUPBY_EXPRESSION = 'SOURCE_GROUPBY_EXPRESSION'
    SOURCE_CUSTOM_ID = 'SOURCE_CUSTOM_ID'
    MAX_DIST = 'MAX_DIST'
    MAX_POINTS = 'MAX_POINTS'
    HANDLE_INVALID = 'HANDLE_INVALID'
    ADD_PATH_FIDS = 'ADD_PATH_FIDS'
    ADD_PATH_DISTS = 'ADD_PATH_DISTS'
    ALLOW_SELF_CROSSING = 'ALLOW_SELF_CROSSING'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Point-Layer (Z- and M-Values as well as MultiPoints are not supported)'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_LYR_ORDERBY, self.tr('OrderBy-Expression for Source-Layer \n(used to determine the points to start from, if unused the feature ids are taken)'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_FILTER_EXPRESSION, self.tr('Filter-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_GROUPBY_EXPRESSION, self.tr('GroupBy-Expression for Source-Layer'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_CUSTOM_ID, self.tr('Add a custom field or expression value to result layer (will show up as string value within cid fields in result)'), parentLayerParameterName = 'SOURCE_LYR', optional = True))
        self.addParameter(
            QgsProcessingParameterDistance(
                self.MAX_DIST, self.tr('Maximum distance between points of a group (0 means unlimited)'), parentParameterName = 'SOURCE_LYR', defaultValue = 0, minValue = 0, maxValue = 2147483647))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_POINTS, self.tr('Maximum number of points in a group (0 means unlimited)'), defaultValue = 0, minValue = 0, maxValue = 2147483647))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.HANDLE_INVALID, self.tr('How to handle result paths with identical start- and endpoint and no midpoints?'), ['Add them to result anyway','Skip these and do not add them to result'], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_PATH_FIDS, self.tr('Add a semicolon-separated field with all feature ids the path passes '
                                            '\n(better do not use it, if you expect very large groups for a path because it can crash QGIS)'), defaultValue = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_PATH_DISTS, self.tr('Add a semicolon-separated field with all lengths the path has '
                                             '\n(better do not use it, if you expect very large groups for a path because it can crash QGIS; '
                                             'or if you want to speed up the algorithm a little)'), defaultValue = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ALLOW_SELF_CROSSING, self.tr('Allow self-crossing of a result path? '
                                                  '\nUnchecking this option can exponentially slow down the algorithm!'
                                                  '\nIf not allowed, a new feature is created when there is no self-cross-avoiding-point available'), defaultValue = True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Path')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_orderby_expression = self.parameterAsExpression(parameters, self.SOURCE_LYR_ORDERBY, context)
        source_orderby_expression = QgsExpression(source_orderby_expression)
        source_filter_expression = self.parameterAsExpression(parameters, self.SOURCE_FILTER_EXPRESSION, context)
        source_filter_expression = QgsExpression(source_filter_expression)
        source_groupby_expression = self.parameterAsExpression(parameters, self.SOURCE_GROUPBY_EXPRESSION, context)
        source_groupby_expression = QgsExpression(source_groupby_expression)
        source_custom_id = self.parameterAsExpression(parameters, self.SOURCE_CUSTOM_ID, context)
        source_custom_id = QgsExpression(source_custom_id)
        max_dist = self.parameterAsDouble(parameters, self.MAX_DIST, context)
        max_points = self.parameterAsInt(parameters, self.MAX_POINTS, context)
        if max_points == 0:
            max_points = 2147483647
        handle_invalid = self.parameterAsInt(parameters, self.HANDLE_INVALID, context)
        add_path_fids = self.parameterAsBool(parameters, self.ADD_PATH_FIDS, context)
        add_path_dists = self.parameterAsBool(parameters, self.ADD_PATH_DISTS, context)
        allow_self_crossing = self.parameterAsBool(parameters, self.ALLOW_SELF_CROSSING, context)
        
        output_layer_fields = QgsFields()
        output_layer_fields.append(QgsField('path_group_id', QVariant.Int))
        output_layer_fields.append(QgsField('path_group_name', QVariant.String))
        output_layer_fields.append(QgsField('path_n_vertices', QVariant.Int))
        output_layer_fields.append(QgsField('path_length', QVariant.Double))
        output_layer_fields.append(QgsField('path_begin_fid', QVariant.Int))
        output_layer_fields.append(QgsField('path_begin_cid', QVariant.String))
        output_layer_fields.append(QgsField('path_end_fid', QVariant.Int))
        output_layer_fields.append(QgsField('path_end_cid', QVariant.String))
        if add_path_fids:
            output_layer_fields.append(QgsField('path_fids', QVariant.String))
            output_layer_fields.append(QgsField('path_cids', QVariant.String))
        if add_path_dists:
            output_layer_fields.append(QgsField('path_dists', QVariant.String))
            
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, 2, # LineString = 2
                                               source_layer.sourceCrs())
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer = source_layer.materialize(QgsFeatureRequest(source_filter_expression))
            
        groupby_expr = False
        if source_groupby_expression not in (QgsExpression(''),QgsExpression(None)):
            groupby_expr = True
        add_custom_ids = False
        if source_custom_id not in (QgsExpression(''),QgsExpression(None)):
            add_custom_ids = True
        invalid_paths = 0
                
        source_layer_feature_count = source_layer.featureCount()
        total = 100.0 / source_layer_feature_count if source_layer_feature_count else 0
        if groupby_expr:
            if source_layer_feature_count * 2 > 0:
                total = 100.0 / (source_layer_feature_count* 2)
            else:
                total = 0
        else:
            total = 100.0 / source_layer_feature_count if source_layer_feature_count else 0
        current = 0
        
        feedback.setProgressText('Building spatial index...')
        source_layer_idx = QgsSpatialIndex(source_layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        
        if groupby_expr or add_custom_ids:
            feedback.setProgressText('Evaluating Group-By Expression...')
            source_layer_dict = {}
            source_layer_custom_ids = {}
            for source_feat in source_layer.getFeatures():
                current += 1
                if feedback.isCanceled():
                    break
                source_groupby_expression_context = QgsExpressionContext()
                source_groupby_expression_context.setFeature(source_feat)
                source_groupby_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_groupby_expression_result = source_groupby_expression.evaluate(source_groupby_expression_context)
                source_layer_dict[source_feat.id()] = source_groupby_expression_result 
                source_custom_id_context = QgsExpressionContext()
                source_custom_id_context.setFeature(source_feat)
                source_custom_id_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_custom_id_result = source_custom_id.evaluate(source_custom_id_context)
                source_layer_custom_ids[source_feat.id()] = str(source_custom_id_result)
                feedback.setProgress(int(current * total))
        points_skip = []
        path_group_id = 1
        
        source_orderby_request = QgsFeatureRequest()
        if source_orderby_expression not in (QgsExpression(''),QgsExpression(None)):
            order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(source_orderby_expression)])
            source_orderby_request.setOrderBy(order_by)
        
        feedback.setProgressText('Start processing...')
        for source_feat in source_layer.getFeatures(source_orderby_request):
            if feedback.isCanceled():
                break
            if source_feat.id() in points_skip:
                continue
            
            new_geom = [source_feat.geometry().centroid().asPoint()]
            new_begin = source_feat.id()
            new_end = source_feat.id()
            if add_path_fids:
                new_path = [str(source_feat.id())]
                if add_custom_ids:
                    new_path_cids = [source_layer_custom_ids[source_feat.id()]]
            if add_path_dists:
                new_dists = []
            if add_custom_ids:
                new_begin_cid = source_layer_custom_ids[source_feat.id()]
                new_end_cid = source_layer_custom_ids[source_feat.id()]
            if groupby_expr:
                group = source_layer_dict[source_feat.id()]
            else:
                group = source_feat.id()
            search_from_point_geom = source_feat.geometry().centroid()
            search_from_point_id = source_feat.id()
            no_further_matches = False
            points_skip.append(source_feat.id())
            
            for i in range(0,source_layer_feature_count + 1):
                if feedback.isCanceled():
                    break
                if no_further_matches:
                    break
                if len(new_geom) >= max_points:
                    break
                nearest_neighbors = source_layer_idx.nearestNeighbor(search_from_point_geom.asPoint(), neighbors = -1, maxDistance = max_dist)
                nearest_neighbors.remove(search_from_point_id)
                for j, neighbor_id in enumerate(nearest_neighbors):
                    if feedback.isCanceled():
                        break
                    if neighbor_id in points_skip:
                        continue
                    if groupby_expr:
                        if not group == source_layer_dict[neighbor_id]:
                            continue
                    neighbor_geom = source_layer_idx.geometry(neighbor_id)
                    neighbor_geom = neighbor_geom.centroid()
                    if not allow_self_crossing:
                        current_geom = QgsGeometry.fromPolylineXY(new_geom)
                        planned_geom = QgsGeometry.fromPolylineXY([new_geom[-1],neighbor_geom.asPoint()])
                        if current_geom.crosses(planned_geom):
                            continue
                    if add_path_dists:
                        new_dists.append(str(round(neighbor_geom.distance(QgsGeometry.fromPointXY(new_geom[-1])),6)))
                    if add_path_fids:
                        new_path.append(str(neighbor_id))
                        if add_custom_ids:
                            new_path_cids.append(source_layer_custom_ids[neighbor_id])
                    new_end = neighbor_id
                    if add_custom_ids:
                        new_end_cid = source_layer_custom_ids[neighbor_id]
                    new_geom.append(neighbor_geom.asPoint())
                    search_from_point_geom = neighbor_geom
                    search_from_point_id = neighbor_id
                    points_skip.append(neighbor_id)
                    current += 1
                    feedback.setProgress(int(current * total))
                    break
                else:
                    no_further_matches = True
            
            if len(new_geom) < 2:
                invalid_paths += 1
                if handle_invalid == 0:
                    new_geom.append(source_feat.geometry().centroid().asPoint()) # will likely create invalid geometry, but should the feature be skipped instead?
                elif handle_invalid == 1:
                    continue
            new_feat = QgsFeature(output_layer_fields)
            new_feat.setGeometry(QgsGeometry.fromPolylineXY(new_geom))
            new_feat['path_group_id'] = path_group_id
            new_feat['path_group_name'] = str(group)
            new_feat['path_n_vertices'] = len(new_geom)
            new_feat['path_length'] = QgsGeometry.fromPolylineXY(new_geom).length()
            new_feat['path_begin_fid'] = new_begin
            new_feat['path_end_fid'] = new_end
            if add_custom_ids:
                new_feat['path_begin_cid'] = new_begin_cid
                new_feat['path_end_cid'] = new_end_cid
            if add_path_fids:
                new_feat['path_fids'] = ';'.join(new_path)
                if add_custom_ids:
                    new_feat['path_cids'] = ';'.join(new_path_cids)
            if add_path_dists:
                new_feat['path_dists'] = ';'.join(new_dists)
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            path_group_id += 1
            
        if handle_invalid == 0 and invalid_paths > 0:
            feedback.pushWarning('Added ' + str(invalid_paths) + ' paths with 2 vertices (identical start- and endvertices) to resultlayer')
        elif handle_invalid == 1 and invalid_paths > 0:
            feedback.pushWarning('Skipped ' + str(invalid_paths) + ' paths with 2 vertices (identical start- and endvertices) to resultlayer')
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return NearestPointsToPath()

    def name(self):
        return 'NearestPointsToPath'

    def displayName(self):
        return self.tr('Nearest Points To Path')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr(
        'This algorithm connects points to a path based on their distance to each other. A point is only used once.'
        '\nThis algorithm does not support Z- and M-Values. It will simply ignore these. If the inputlayer is of type MultiPoint, it will take the centroids of these points.'
        '\nIt basically does the same as the native "Points to Path" algorithm, but instead of an order field it takes the distance between points as condition.'
        '\nYou can group the points/paths by an optional maximum distance and/or an expression and/or a maximum number of points per group.'
        '\nThe algorithm adds a field with the feature id (fid) of the startpoint and a field with the feature id of the endpoint to each path.'
        ' Additionally you can also enter an expression or field you want to add to the result. These will be called cid (custom id) and converted to datatype string.'
        ' Also, fields with the number of vertices and the total length are added.'
        ' Additionally you may choose whether array-like-string fields of the vertices feature ids and the distances between them shall be added.'
        ' Be aware that these array-like fields may cause an overflow, if you expect large groups or the inputlayer is pretty big. USE THIS WITH CAUTION, since it can cause QGIS to crash, especiall when you open the attribute table of the resultlayer.'
        '\nThe setting to avoid self-crossing of paths is extremely computationally expensive.'
        ' It avoids self-crossing of a single feature/path in the result, but it does not prevent different result-features/paths from crossing each other.'
        ' If the algorithm cannot find a nearby point where creating a path would cross the already existing path, it will close the current feature/path and start with the next one.'
        )