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
    #USE_MULTIPLE = 'USE_MULTIPLE' # Does not make any sense: never use it
    MAX_DIST = 'MAX_DIST'
    MAX_POINTS = 'MAX_POINTS'
    HANDLE_INVALID = 'HANDLE_INVALID'
    ADD_PATH_FIDS = 'ADD_PATH_FIDS'
    ADD_PATH_DISTS = 'ADD_PATH_DISTS'
    #ALLOW_SELF_CROSSING = 'ALLOW_SELF_CROSSING'
    OUTPUT = 'OUTPUT'
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer (Z- and M-Values are not supported)'), [QgsProcessing.TypeVectorPoint]))
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
            QgsProcessingParameterDistance(
                self.MAX_DIST, self.tr('Maximum distance between points of a group (0 means unlimited)'), parentParameterName = 'SOURCE_LYR', defaultValue = 0, minValue = 0, maxValue = 2147483647))
        #self.addParameter(
        #    QgsProcessingParameterBoolean(
        #        self.USE_MULTIPLE, self.tr('Use points more than once to build the path')))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_POINTS, self.tr('Maximum number of points in a group (0 means unlimited)'), defaultValue = 0, minValue = 0, maxValue = 2147483647))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.HANDLE_INVALID, self.tr('How to handle result paths with identical start- and endpoint and no midpoints?'), ['Add them to result anyway','Skip these and do not add them to result'], defaultValue = 1, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_PATH_FIDS, self.tr('Add a semicolon-separated field with all feature ids the path passes \n(better do not use it, if you expect very large groups for a path because it can crash QGIS)'), defaultValue = False))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_PATH_DISTS, self.tr('Add a semicolon-separated field with all lengths the path has \n(better do not use it, if you expect very large groups for a path because it can crash QGIS; or if you want to speed up the algorithm a little)'), defaultValue = False))
        #self.addParameter(
        #    QgsProcessingParameterBoolean(
        #        self.ALLOW_SELF_CROSSING, self.tr('Allow self-crossing of the result path? \n(Unchecking this option can exponentially slow down the algorithm!)'), defaultValue = True))
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
        #use_multiple = self.parameterAsBool(parameters, self.USE_MULTIPLE, context)
        max_dist = self.parameterAsDouble(parameters, self.MAX_DIST, context)
        max_points = self.parameterAsInt(parameters, self.MAX_POINTS, context)
        if max_points == 0:
            max_points = 2147483647
        handle_invalid = self.parameterAsInt(parameters, self.HANDLE_INVALID, context)
        add_path_fids = self.parameterAsBool(parameters, self.ADD_PATH_FIDS, context)
        add_path_dists = self.parameterAsBool(parameters, self.ADD_PATH_DISTS, context)
        #allow_self_crossing = self.parameterAsBool(parameters, self.ALLOW_SELF_CROSSING, context)
        allow_self_crossing = True
        
        output_layer_fields = QgsFields()
        output_layer_fields.append(QgsField('path_group', QVariant.String))
        output_layer_fields.append(QgsField('begin_fid', QVariant.Int))
        if add_path_fids:
            output_layer_fields.append(QgsField('path_fids', QVariant.String))
        output_layer_fields.append(QgsField('path_n_vertices', QVariant.Int))
        if add_path_dists:
            output_layer_fields.append(QgsField('path_dists', QVariant.String))
        output_layer_fields.append(QgsField('path_length', QVariant.Double))
        output_layer_fields.append(QgsField('end_fid', QVariant.Int))
        
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, 2, # LineString = 2
                                               source_layer.sourceCrs())
            
        if source_filter_expression not in (QgsExpression(''),QgsExpression(None)):
            source_layer = source_layer.materialize(QgsFeatureRequest(source_filter_expression))
            
        groupby_expr = False
        n_neighbors = 2
        if source_groupby_expression not in (QgsExpression(''),QgsExpression(None)):
            groupby_expr = True
            n_neighbors = -1
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
        #if source_layer_idx.size() == 0:
        #    feedback.pushWarning('Spatial Index is empty! Check if your input point layer is of type Single-Point 2D. This algorithm does not support 2.5D, 3D or MultiPoints!')
        
        if groupby_expr:
            feedback.setProgressText('Evaluating Group-By Expression...')
            source_layer_dict = {}
            for source_feat in source_layer.getFeatures():
                current += 1
                source_groupby_expression_context = QgsExpressionContext()
                source_groupby_expression_context.setFeature(source_feat)
                source_groupby_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
                source_groupby_expression_result = source_groupby_expression.evaluate(source_groupby_expression_context)
                source_layer_dict[source_feat.id()] = source_groupby_expression_result 
                feedback.setProgress(int(current * total))
        points_skip = []
        
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
            
            new_geom = [source_feat.geometry().asPoint()]
            new_begin = source_feat.id()
            if add_path_fids:
                new_path = [str(source_feat.id())]
            if add_path_dists:
                new_dists = []
            new_end = source_feat.id()
            if groupby_expr:
                group = source_layer_dict[source_feat.id()]
            else:
                group = source_feat.id()
            search_from_point_geom = source_feat.geometry()
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
                for neighbor_id in nearest_neighbors:
                    if feedback.isCanceled():
                        break
                    if neighbor_id in points_skip:
                        continue
                    if groupby_expr:
                        if not group == source_layer_dict[neighbor_id]:
                            continue
                    neighbor_geom = source_layer_idx.geometry(neighbor_id)
                    if not allow_self_crossing:
                        current_geom = QgsGeometry.fromPolylineXY(new_geom)
                        future_geoml = new_geom
                        future_geoml.append(neighbor_geom.asPoint())
                        future_geom = QgsGeometry.fromPolylineXY(future_geoml)
                        if future_geom.overlaps(current_geom):
                            feedback.pushWarning('to ' + str(neighbor_id) + ' intersects')
                            continue
                    if add_path_dists:
                        new_dists.append(str(round(neighbor_geom.distance(QgsGeometry.fromPointXY(new_geom[-1])),6)))
                    if add_path_fids:
                        new_path.append(str(neighbor_id))
                    new_end = neighbor_id
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
                    new_geom.append(source_feat.geometry().asPoint()) # will likely create invalid geometry, but should the feature be skipped instead?
                elif handle_invalid == 1:
                    continue
            new_feat = QgsFeature(output_layer_fields)
            new_feat.setGeometry(QgsGeometry.fromPolylineXY(new_geom))
            new_feat['begin_fid'] = new_begin
            if add_path_fids:
                new_feat['path_fids'] = ';'.join(new_path)
            new_feat['path_n_vertices'] = len(new_geom)
            if add_path_dists:
                new_feat['path_dists'] = ';'.join(new_dists)
            new_feat['path_length'] = QgsGeometry.fromPolylineXY(new_geom).length()
            new_feat['path_group'] = str(group)
            new_feat['end_fid'] = new_end
            
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
            
        if handle_invalid == 0 and invalid_paths > 0:
            feedback.pushWarning('Added ' + str(invalid_paths) + ' paths with less than 2 vertices to resultlayer')
        elif handle_invalid == 1 and invalid_paths > 0:
            feedback.pushWarning('Skipped ' + str(invalid_paths) + ' paths with less than 2 vertices')
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
        'This algorithm connects points to a path based on their distance. A point is only used once.'
        '\nIt basically does the same as the native "Points to Path" algorithm, but instead of an order field it takes the distance between points as condition.'
        '\nYou can group the points/paths by an optional maximum distance and/or an expression and/or a maximum number of points per group.'
        '\nThe algorithm adds a field with the feature id of the startpoint and a field with the feature id of the endpoint to each path.'
        ' Also fields with the number of vertices and the total length are added.'
        ' Additionally you may choose whether array-like-string fields of the vertices feature ids and the distances between them shall be added.'
        )