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

from PyQt5.QtCore import QCoreApplication, QVariant, QDateTime
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsGeometry, QgsPoint, QgsFields, QgsWkbTypes, QgsDateTimeFieldFormatter, QgsApplication, QgsProcessingParameterBoolean,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsSpatialIndex, QgsProcessingParameterExpression, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterDateTime, QgsProcessingParameterField, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterString, QgsProcessingParameterNumber)
import processing
from datetime import *
import math


class CreateTimepolygonsWithPointcount(QgsProcessingAlgorithm):
    POLYGON_LYR = 'POLYGON_LYR'
    POINT_LYR = 'POINT_LYR'
    DATETIME_FIELD = 'DATETIME_FIELD'
    START_DATETIME = 'START_DATETIME'
    END_DATETIME = 'END_DATETIME'
    INTERVALSEC = 'INTERVALSEC'
    COUNT_POINT_MULTIPLE_TIMES = 'COUNT_POINT_MULTIPLE_TIMES'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.POLYGON_LYR, self.tr('Polygon'), [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.POINT_LYR, self.tr('Point'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.DATETIME_FIELD, self.tr('Datetime-Expression of Points (Expects a valid Datetime, either via a Field or as evaluated Expression)'), parentLayerParameterName = 'POINT_LYR', optional = False))
        self.addParameter(
            QgsProcessingParameterDateTime(
                self.START_DATETIME, self.tr('Start Datetime'), type = QgsProcessingParameterDateTime.DateTime, defaultValue = QDateTime.currentDateTime().addDays(-31)))
        self.addParameter(
            QgsProcessingParameterDateTime(
                self.END_DATETIME, self.tr('End Datetime'), type = QgsProcessingParameterDateTime.DateTime, defaultValue = QDateTime.currentDateTime().addDays(-1)))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.INTERVALSEC, self.tr('Interval in Seconds (Expects a valid Integer)'), optional = False, defaultValue = 86400))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.COUNT_POINT_MULTIPLE_TIMES, self.tr('Check if a point may be counted more than once (slowing down processing around 25%)')))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('TimePolygons with Pointcount')))

    def processAlgorithm(self, parameters, context, feedback):
        lyr_polygons = self.parameterAsLayer(parameters, self.POLYGON_LYR, context)
        lyr_points = self.parameterAsLayer(parameters, self.POINT_LYR, context)
        point_time_expression = self.parameterAsExpression(parameters, self.DATETIME_FIELD, context)
        point_time_expression = QgsExpression(point_time_expression)
        start_date = self.parameterAsDateTime(parameters, self.START_DATETIME, context)
        end_date = self.parameterAsDateTime(parameters, self.END_DATETIME, context)
        intervalsec = self.parameterAsInt(parameters, self.INTERVALSEC, context)
        count_point_multiple_times = self.parameterAsBool(parameters, self.COUNT_POINT_MULTIPLE_TIMES, context)
        feedback.setProgressText('Prepare processing...')
        
        if lyr_polygons.sourceCrs() != lyr_points.sourceCrs():
            feedback.setProgressText('Reprojecting Point Layer...')
            reproj = processing.run('native:reprojectlayer', {'INPUT': lyr_points, 'TARGET_CRS': lyr_polygons.sourceCrs(), 'OUTPUT': 'memory:Reprojected'})
            lyr_points = reproj['OUTPUT']
        
        fields = lyr_polygons.fields()
        fields.append(QgsField('from_datetime', QVariant.DateTime))
        fields.append(QgsField('to_datetime', QVariant.DateTime))
        fields.append(QgsField('pointcount', QVariant.Int, len=0))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fields, lyr_polygons.wkbType(),
                                               lyr_polygons.sourceCrs())
        
        start_date = QDateTime.toPyDateTime(start_date)
        end_date = QDateTime.toPyDateTime(end_date)
        total_seconds = int((end_date - start_date).total_seconds())
        
        feedback.setProgressText('Building spatial index...')
        idx_points = QgsSpatialIndex(lyr_points.getFeatures())
        
        required_iterations = math.ceil(total_seconds / intervalsec) 
        total = 100.0 / (lyr_polygons.featureCount() * required_iterations) if lyr_polygons.featureCount() else 0
        current = 0
        
        feedback.setProgressText('Start processing...')
        for current_interval in range(0,total_seconds,intervalsec): 
            if feedback.isCanceled():
                break
            current_start_datetime = start_date + timedelta(seconds = current_interval)
            current_end_datetime = (start_date + timedelta(seconds = current_interval+intervalsec) - timedelta(seconds = 1))
            for polygon in lyr_polygons.getFeatures():
                current += 1
                if feedback.isCanceled():
                    break
                new_feat = QgsFeature(fields)
                new_feat.setGeometry(polygon.geometry())
                attridx = 0
                for attr in polygon.attributes():
                    new_feat[attridx] = attr
                    attridx += 1
                new_feat['from_datetime'] = current_start_datetime.strftime('%Y-%m-%d %H:%M:%S')
                new_feat['to_datetime'] = current_end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                new_feat['pointcount'] = 0
                for pointid in idx_points.intersects(polygon.geometry().boundingBox()):
                    point = lyr_points.getFeature(pointid)
                    if feedback.isCanceled():
                        break
                    point_time_expression_context = QgsExpressionContext()
                    point_time_expression_context.setFeature(point)
                    point_time_expression_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(lyr_points))
                    point_time_expression_result = point_time_expression.evaluate(point_time_expression_context)
                    if point_time_expression_result > current_start_datetime and point_time_expression_result <= current_end_datetime:
                        if point.geometry().intersects(polygon.geometry()):
                            new_feat['pointcount'] += 1
                            if not count_point_multiple_times:
                                idx_points.deleteFeature(point) # dont count a point twice, removing it from the index speeds up the code around 25%
                        
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                feedback.setProgress(int(current * total))
                
        return {self.OUTPUT: dest_id} # Return result of algorithm
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateTimepolygonsWithPointcount()

    def name(self):
        return 'CreateTimepolygonsWithPointcount'

    def displayName(self):
        return self.tr('Create Timepolygons with Pointcount')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr('This Algorithm duplicates the polygons by the given interval input, '
                       'adds a from_datetime and to_datetime field to them '
                       'and counts the points intersecting with the polygon as '
                       'if they are inbetween the timerange (greater than starttime and smaller or equal endtime)'
                       )