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
import math
from PyQt5.QtCore import QCoreApplication, QVariant, QDateTime
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils, QgsGeometry, QgsPointXY,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, QgsProcessingParameterExpression)

class InterpolateDateTimeAlongLine(QgsProcessingAlgorithm):
    METHOD = 'METHOD'
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_START_TIME_EXPR = 'SOURCE_START_TIME_EXPR'
    SOURCE_END_TIME_EXPR = 'SOURCE_END_TIME_EXPR'
    SOURCE_INTERPOLATION_DENSITY_EXPR = 'SOURCE_INTERPOLATION_DENSITY_EXPR'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Source Layer (must be in metric CRS!)'),[QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_START_TIME_EXPR, self.tr('Expression, field or datetime representing start-datetime of features (must be in datetime format!)'), parentLayerParameterName = 'SOURCE_LYR', optional = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_END_TIME_EXPR, self.tr('Expression, field or datetime representing end-datetime of features (must be in datetime format!)'), parentLayerParameterName = 'SOURCE_LYR', optional = False))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SOURCE_INTERPOLATION_DENSITY_EXPR, self.tr('Expression, field or number representing maximum length of segments (integer or double; must be in meters!)'), parentLayerParameterName = 'SOURCE_LYR', optional = False, defaultValue = 'length($geometry) / 10'))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Interpolated DateTime Along Line')))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.setProgressText('Prepare processing...')
        source_layer = self.parameterAsSource(parameters, self.SOURCE_LYR, context)
        source_layer_vl = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        source_start_time_expr = self.parameterAsExpression(parameters, self.SOURCE_START_TIME_EXPR, context)
        source_start_time_expr = QgsExpression(source_start_time_expr)
        source_end_time_expr = self.parameterAsExpression(parameters, self.SOURCE_END_TIME_EXPR, context)
        source_end_time_expr = QgsExpression(source_end_time_expr)
        source_interpolation_density_expr = self.parameterAsExpression(parameters, self.SOURCE_INTERPOLATION_DENSITY_EXPR, context)
        source_interpolation_density_expr = QgsExpression(source_interpolation_density_expr)
        
        if source_layer_vl.crs().mapUnits() != 0:
            #feedback.pushWarning('Layer is not in a metric CRS! Calculations will be incorrect! Reproject your layer to a metric CRS and retry!')
            feedback.reportError('Layer is not in a metric CRS! Calculations will be incorrect! Reproject your layer to a metric CRS and retry!', fatalError=True)
            
        source_layer_fields = source_layer.fields()
        output_layer_fields = source_layer_fields
        field_name_dict = {
            'line_id_field_name' : 'line_id',
            'part_id_field_name' : 'part_id',
            'segment_id_field_name' : 'segment_id',
            'interpolated_starttime_field_name' : 'interpolated_start_datetime',
            'interpolated_endtime_field_name' : 'interpolated_end_datetime',
            'interpolated_speed_field_name' : 'interpolated_speed_meters_per_second',
            'seconds_from_linestart_field_name' : 'seconds_from_line_start',
            'distance_from_partstart_field_name' : 'distance_meters_from_part_start',
            'distance_from_linestart_field_name' : 'distance_meters_from_line_start',
            'segment_length_field_name' : 'segment_length_meters'
            }
        whilecounter = 0
        while any(elem in field_name_dict.values() for elem in output_layer_fields.names()):
            whilecounter += 1
            for var,name in field_name_dict.items():
                field_name_dict[var] = name + '_2'
            if whilecounter > 9:
                break
        
        output_layer_fields.append(QgsField(field_name_dict['line_id_field_name'], QVariant.Int))
        output_layer_fields.append(QgsField(field_name_dict['part_id_field_name'], QVariant.Int))
        output_layer_fields.append(QgsField(field_name_dict['segment_id_field_name'], QVariant.Int))
        output_layer_fields.append(QgsField(field_name_dict['interpolated_starttime_field_name'], QVariant.DateTime))
        output_layer_fields.append(QgsField(field_name_dict['interpolated_endtime_field_name'], QVariant.DateTime))
        output_layer_fields.append(QgsField(field_name_dict['interpolated_speed_field_name'], QVariant.Double, len = 20, prec = 8))
        output_layer_fields.append(QgsField(field_name_dict['seconds_from_linestart_field_name'], QVariant.Double, len = 20, prec = 8))
        output_layer_fields.append(QgsField(field_name_dict['distance_from_partstart_field_name'], QVariant.Double, len = 20, prec = 8))
        output_layer_fields.append(QgsField(field_name_dict['distance_from_linestart_field_name'], QVariant.Double, len = 20, prec = 8))
        output_layer_fields.append(QgsField(field_name_dict['segment_length_field_name'], QVariant.Double, len = 20, prec = 8))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_layer_fields, source_layer.wkbType(),
                                               source_layer.sourceCrs())
        
        total = 100.0 / source_layer_vl.featureCount() if source_layer_vl.featureCount() else 0
        
        feedback.setProgressText('Start processing...')
        for current, source_feat in enumerate(source_layer.getFeatures()):
            if feedback.isCanceled():
                break
            segment_id = 0
            part_id = 0
            source_geom = source_feat.geometry()
            source_length = source_geom.length()
            
            source_start_time_expr_context = QgsExpressionContext()
            source_start_time_expr_context.setFeature(source_feat)
            source_start_time_expr_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_start_time_expr_result = source_start_time_expr.evaluate(source_start_time_expr_context)
            
            source_end_time_expr_context = QgsExpressionContext()
            source_end_time_expr_context.setFeature(source_feat)
            source_end_time_expr_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_end_time_expr_result = source_end_time_expr.evaluate(source_end_time_expr_context)
            
            if not 'QDateTime' in str(type(source_start_time_expr_result)) or not 'QDateTime' in str(type(source_end_time_expr_result)):
                feedback.pushWarning('Given start-datetime or end-datetime of Feature ' + str(source_feat.id()) + ' is not in QDateTime format! Skipping feature...')
                continue
            if not source_start_time_expr_result.isValid() or not source_end_time_expr_result.isValid():
                feedback.pushWarning('Feature ' + str(source_feat.id()) + ' does not have a valid QDateTime! Skipping feature...')
                continue
            
            source_interpolation_density_expr_context = QgsExpressionContext()
            source_interpolation_density_expr_context.setFeature(source_feat)
            source_interpolation_density_expr_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(source_layer_vl))
            source_interpolation_density_expr_result = source_interpolation_density_expr.evaluate(source_interpolation_density_expr_context)
            
            seconds_needed = source_start_time_expr_result.secsTo(source_end_time_expr_result)
            speed_m_per_s = source_length / seconds_needed
            #speed_km_per_h = speed_m_per_s * 3.6
            
            for source_part in source_geom.parts():
                if feedback.isCanceled():
                    break
                part_id += 1
                source_part_geom = QgsGeometry.fromPolyline(source_part)
                source_part_length = source_part_geom.length()
                nsegments = math.ceil(source_part_length / source_interpolation_density_expr_result)
                segment_startdistance = 0
                segment_enddistance = source_interpolation_density_expr_result
                for segment in range(0,nsegments):
                    if feedback.isCanceled():
                        break
                    segment_id += 1
                    segment_linestring = source_part.curveSubstring(segment_startdistance,segment_enddistance)
                    segment_geom = QgsGeometry.fromPolyline(segment_linestring)
                    
                    segment_startpoint = QgsGeometry.fromPointXY(QgsPointXY(segment_linestring[0]))
                    segment_endpoint = QgsGeometry.fromPointXY(QgsPointXY(segment_linestring[-1]))
                    segment_start_distance_from_line_start = source_geom.lineLocatePoint(segment_startpoint)
                    segment_end_distance_from_line_start = source_geom.lineLocatePoint(segment_endpoint)
                    interpolated_starttime = source_start_time_expr_result.addSecs(segment_start_distance_from_line_start / speed_m_per_s)
                    interpolated_endtime = source_start_time_expr_result.addSecs(segment_end_distance_from_line_start / speed_m_per_s)

                    new_feat = QgsFeature(output_layer_fields)
                    new_feat.setGeometry(segment_geom)
                    attridx = 0
                    for attr in source_feat.attributes():
                        new_feat[attridx] = attr
                        attridx += 1
                    new_feat[field_name_dict['line_id_field_name']] = source_feat.id()
                    new_feat[field_name_dict['part_id_field_name']] = part_id
                    new_feat[field_name_dict['segment_id_field_name']] = segment_id
                    new_feat[field_name_dict['interpolated_starttime_field_name']] = interpolated_starttime
                    new_feat[field_name_dict['interpolated_endtime_field_name']] = interpolated_endtime
                    new_feat[field_name_dict['interpolated_speed_field_name']] = speed_m_per_s
                    new_feat[field_name_dict['seconds_from_linestart_field_name']] = segment_start_distance_from_line_start / speed_m_per_s
                    new_feat[field_name_dict['distance_from_partstart_field_name']] = segment_startdistance
                    new_feat[field_name_dict['distance_from_linestart_field_name']] = segment_start_distance_from_line_start
                    new_feat[field_name_dict['segment_length_field_name']] = segment_geom.length()
                    
                    segment_startdistance += source_interpolation_density_expr_result
                    segment_enddistance += source_interpolation_density_expr_result
                    
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                    
            feedback.setProgress(int(current * total))
            

        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return InterpolateDateTimeAlongLine()

    def name(self):
        return 'InterpolateDateTimeAlongLine'

    def displayName(self):
        return self.tr('Interpolate DateTime Along Line')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Interpolation'

    def shortHelpString(self):
        return self.tr('This Algorithm segmentizes a given linelayer into pieces by a given maximum distance and interpolates the start-datetime and end-datetime on these segments linear. \n'
                       'The layer <b>must be in a metric CRS</b> and needs attributes for start-datetime and end-datetime in QDateTime format where both datetime attributes must be in the same timezone. \n'
                       'You can use <i>to_datetime()</i>, <i>datetime_from_epoch()</i> or <i>make_datetime()</i> expressions to use datetimes stored e.g. as string or unixtime for usage in this algorithm. \n'
                       'This algorithm is designed for animating lines with Temporal Controller. \n'
                       )