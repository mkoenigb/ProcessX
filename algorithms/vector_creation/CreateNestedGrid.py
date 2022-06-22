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

import operator, processing, math
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFields, QgsFeature, QgsProcessing, QgsExpression, QgsSpatialIndex, QgsGeometryEngine, QgsGeometry, QgsPointXY, QgsPoint, QgsWkbTypes, 
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm, QgsExpressionContext, QgsExpressionContextUtils,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterExtent, QgsProcessingParameterDistance, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterExpression, QgsProcessingParameterNumber, QgsProcessingParameterString)

class CreateNestedGrid(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    GRIDTYPE = 'GRIDTYPE'
    XSPACING = 'XSPACING'
    YSPACING = 'YSPACING'
    SUBGRIDS = 'SUBGRIDS'
    LETTERS = 'LETTERS'
    OUTPUT = 'OUTPUT'
    
    # Source: https://stackoverflow.com/a/12334507 (modified)
    def linspace(self, a, b, n, endpoint):
        if endpoint is False:
            n += 1
        if n < 2:
            return b
        diff = (float(b) - a)/(n - 1)
        result = [diff * i + a for i in range(n)]
        if endpoint is False:
            del result[-1]
        return result
    
    # Source: https://stackoverflow.com/a/42176641/8947209
    def num_to_char(self, n):
        if n < 1:
            raise ValueError("Number must be positive")
        result = ""
        while True:
            if n > 26:
                n, r = divmod(n - 1, 26)
                result = chr(r + ord('A')) + result
            else:
                return chr(n + ord('A') - 1) + result
        
        
    def initAlgorithm(self, config=None):
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.GRIDTYPE, self.tr('Gridtype'), ['Rectangle'], defaultValue = 0, allowMultiple = False))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.LETTERS, self.tr('Use Latin Grid-Letters instead of Grid-Numbers on Axis'), ['X','Y'], defaultValue = None, allowMultiple = True, optional = True))
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT, self.tr('Extent')))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.XSPACING, self.tr('X-Spacing of Parent-Grid in Extent-CRS-Units'), minValue = 0.000001, defaultValue = 1000, type = 1))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.YSPACING, self.tr('Y-Spacing of Parent-Grid in Extent-CRS-Units'), minValue = 0.000001, defaultValue = 1000, type = 1))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUBGRIDS, self.tr('Number of Subgrids incl. Parentgrid (1 means only Parent-Grid)'), minValue = 1, maxValue = 9999, defaultValue = 3, type = 0))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('Grid')))

    def processAlgorithm(self, parameters, context, feedback):
        gridtype = self.parameterAsInt(parameters, self.GRIDTYPE, context)
        extent_rect = self.parameterAsExtent(parameters, self.EXTENT, context)
        extent_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        extent_geom = self.parameterAsExtentGeometry(parameters, self.EXTENT, context)
        xspacing = self.parameterAsDouble(parameters, self.XSPACING, context)
        yspacing = self.parameterAsDouble(parameters, self.YSPACING, context)
        subgrids = self.parameterAsInt(parameters, self.SUBGRIDS, context)
        polygonsides = {
            0: 4, # Rectangle
            1: 6 # Hexagon
        }
        letters = self.parameterAsEnums(parameters, self.LETTERS, context)
        polygonsides = polygonsides[gridtype]
        feedback.setProgressText('Prepare processing...')
        
        if not extent_rect.isFinite():
            feedback.reportError('The chosen extent is not finite!', fatalError = True)
        
        output_layer_fields = QgsFields()
        output_layer_fields.append(QgsField('fid', QVariant.Int))
        output_layer_fields.append(QgsField('uid', QVariant.String))
        output_layer_fields.append(QgsField('s_id', QVariant.Int))
        if 0 in letters:
            output_layer_fields.append(QgsField('p_x_id', QVariant.String))
        else:
            output_layer_fields.append(QgsField('p_x_id', QVariant.Int))
        if 1 in letters:
            output_layer_fields.append(QgsField('p_y_id', QVariant.String))
        else:
            output_layer_fields.append(QgsField('p_y_id', QVariant.Int))
        if 0 in letters:
            output_layer_fields.append(QgsField('c_x_id', QVariant.String))
        else:
            output_layer_fields.append(QgsField('c_x_id', QVariant.Int))
        if 1 in letters:
            output_layer_fields.append(QgsField('c_y_id', QVariant.String))
        else:
            output_layer_fields.append(QgsField('c_y_id', QVariant.Int))
        output_layer_fields.append(QgsField('x_cent', QVariant.Double))
        output_layer_fields.append(QgsField('y_cent', QVariant.Double))
        output_layer_fields.append(QgsField('v_coords', QVariant.String))
        output_layer_fields.append(QgsField('x_space', QVariant.Double))
        output_layer_fields.append(QgsField('y_space', QVariant.Double))
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, output_layer_fields, QgsWkbTypes.Polygon, extent_crs)
        
        n_parentgrids_x = int(math.ceil(extent_rect.width() / xspacing))
        n_parentgrids_y = int(math.ceil(extent_rect.height() / yspacing))
        n_parentgrids_t = n_parentgrids_x * n_parentgrids_y
        
        total = 100.0 / (n_parentgrids_t * subgrids) if n_parentgrids_t > 0 else 0
        current = 0
        
        feedback.setProgressText('Start processing...')
        start_pointxy = QgsPointXY(extent_rect.xMinimum(),extent_rect.yMaximum())
        
        if gridtype == 0:
            step_x = 2**((subgrids-1)*-1)*xspacing
            step_y = 2**((subgrids-1)*-1)*yspacing
            fid = 1
            for subgrid in range(subgrids, 0, -1):
                if feedback.isCanceled():
                    break
                feedback.setProgressText('Creating Subgrid #' + str(subgrid) + '...')
                p_x_id = 1
                p_y_id = 1
                c_x_id = 1
                c_y_id = 1
                parentcellindicator_x = 1
                parentcellindicator_y = 1
                current += 1
                point_topleft_pxy = start_pointxy
                point_topleft_geom = QgsGeometry.fromPointXY(point_topleft_pxy)
                
                while ((point_topleft_pxy.x() <= extent_rect.xMaximum()) and (point_topleft_pxy.y() >= extent_rect.yMinimum())):
                    if feedback.isCanceled():
                        break
                    
                    #point_topright_pxy = point_topleft_pxy.project(step_x,90)
                    #point_lowerright_pxy = point_topleft_pxy.project(math.sqrt((step_x**2)+(step_y**2)),90+math.degrees(math.atan(step_x/step_y)))
                    #point_lowerleft_pxy = point_topleft_pxy.project(step_y,180)
                    point_topright_pxy = point_topleft_pxy.project(step_x,90)
                    point_lowerright_pxy = point_topright_pxy.project(step_y,180)
                    point_lowerleft_pxy = point_lowerright_pxy.project(step_x,270)
                    grid_geom = [point_topleft_pxy,
                                 point_topright_pxy,
                                 point_lowerright_pxy,
                                 point_lowerleft_pxy,
                                 point_topleft_pxy]
                    grid_geom = QgsGeometry.fromPolygonXY([grid_geom])
                    new_feat = QgsFeature(output_layer_fields)
                    new_feat.setGeometry(grid_geom)
                    new_feat['x_cent'] = grid_geom.centroid().asPoint().x()
                    new_feat['y_cent'] = grid_geom.centroid().asPoint().y()
                    new_feat['v_coords'] = ';'.join([str(vert.x())+','+str(vert.y()) for vert in grid_geom.vertices()])
                    new_feat['x_space'] = step_x
                    new_feat['y_space'] = step_y
                    new_feat['fid'] = fid
                    uid = str(subgrid).zfill(len(str(subgrids)))
                    if 0 in letters:
                        new_feat['p_x_id'] = self.num_to_char(p_x_id)
                        new_feat['c_x_id'] = self.num_to_char(c_x_id)
                        uid = uid + '_' + self.num_to_char(p_x_id) + '_' + self.num_to_char(c_x_id)
                    else:
                        new_feat['p_x_id'] = p_x_id
                        new_feat['c_x_id'] = c_x_id
                        uid = uid + '_' + str(p_x_id) + '_' + str(c_x_id)
                    if 1 in letters:
                        new_feat['p_y_id'] = self.num_to_char(p_y_id)
                        new_feat['c_y_id'] = self.num_to_char(c_y_id)
                        uid = uid + '_' + self.num_to_char(p_y_id) + '_' + self.num_to_char(c_y_id)
                    else:
                        new_feat['p_y_id'] = p_y_id
                        new_feat['c_y_id'] = c_y_id
                        uid = uid + '_' + str(p_y_id) + '_' + str(c_y_id)
                    new_feat['s_id'] = subgrid
                    new_feat['uid'] = uid
                    
                    sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                    fid += 1
                    
                    #next x:
                    point_topleft_pxy = QgsPointXY(point_topleft_pxy.x()+step_x,point_topleft_pxy.y())
                    point_topleft_geom = QgsGeometry.fromPointXY(point_topleft_pxy)
                    if 2**(subgrid-1) == parentcellindicator_x:
                        p_x_id += 1
                        parentcellindicator_x = 0
                        current += 1
                    parentcellindicator_x += 1
                    c_x_id += 1
                    
                    #next y (reset x):
                    if point_topleft_pxy.x() > extent_rect.xMaximum() and point_topleft_pxy.y() > extent_rect.yMinimum():
                        point_topleft_pxy = QgsPointXY(start_pointxy.x(),point_topleft_pxy.y() - step_y)
                        point_topleft_geom = QgsGeometry.fromPointXY(point_topleft_pxy)
                        parentcellindicator_x = 1
                        p_x_id = 1
                        c_x_id = 1
                        if 2**(subgrid-1) == parentcellindicator_y:
                            p_y_id += 1
                            parentcellindicator_y = 0
                            current += 1
                        parentcellindicator_y += 1
                        c_y_id += 1
                        
                    feedback.setProgress(int(current * total))
                        
                #next subgrid:
                step_x = step_x * 2
                step_y = step_y * 2
                
                
        
        """
        elif gridtype == 1:
            grid_geom = [QgsPointXY(parent_x_coord+math.sin(angle)*(xspacing), parent_y_coord+math.cos(angle)*(yspacing)) for angle in self.linspace(0,(2*math.pi),polygonsides,False)]
            grid_geom = QgsGeometry.fromPolygonXY([parent_geom])
        """
            
        return {self.OUTPUT: dest_id}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateNestedGrid()

    def name(self):
        return 'CreateNestedGrid'

    def displayName(self):
        return self.tr('Create Nested Grid')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Creation'

    def shortHelpString(self):
        return self.tr('This Algorithm creates a nested grid, where the gridsize is specified for the parentgrid. Each childgrid has half the x- and y-spacing of its parent.'
                       '\nNote that the parentgrid is created at last, so it lies on top of its childgrids. Change your symbology to make the childgrids visible.'
                       '\n You can also choose giving one or both axis letters as ids instead of numbers. These letters follow the Excel-Style-Column-Naming.'
                       '\n Each childgrid also has the id of its parent it lies within assigned.'
                       '\n Note that the progress indicator is not 100% accurate.'
                       '\n Meaning of the attributes:'
                       '\n - fid: unique feature id'
                       '\n - uid: unique id of a cell: s_id + _ + p_x_id + _ + c_x_id + _ + p_y_id + _ + c_y_id'
                       '\n - s_id: id of the subgrid; 1 is always the parentgrid'
                       '\n - p_x_id: id of the parentgrid in x-axis'
                       '\n - p_y_id: id of the parentgrid in y-axis'
                       '\n - c_x_id: id of the childgrid in x-axis'
                       '\n - c_y_id: id of the childgrid in y-axis'
                       '\n - x_cent: x-coordinate of the centroid of this gridcell'
                       '\n - y_cent: y-coordinate of the centroid of this gridcell'
                       '\n - v_coords: coordinates of all vertices of this gridcell as string array. Coordinatepairs are separated by comma and vertices separated by semicolon, e.g.: [v1.x,v1.y;v2.x,v2.y;v3.x,v3.y;v1.x,v1.y]'
                       '\n - x_space: width of the gridcell in x-axis'
                       '\n - y_space: height of the gridcell in y-axis'
                       )