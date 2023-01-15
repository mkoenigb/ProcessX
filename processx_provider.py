# -*- coding: utf-8 -*-

"""
/***************************************************************************
 ProcessX
                                 A QGIS plugin
 This plugin provides diverse processing tools
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-06-05
        copyright            : (C) 2022 by Mario Koenigbauer
        email                : mkoenigb@gmx.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Mario Koenigbauer'
__date__ = '2022-06-05'
__copyright__ = '(C) 2022 by Mario Koenigbauer'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

# Vecotr - Conditional
from .algorithms.vector_conditionals.JoinAttributesByNearestWithCondition import *
from .algorithms.vector_conditionals.CountFeaturesInFeaturesWithCondition import *
from .algorithms.vector_conditionals.SelectDuplicatesBySimilarity import *
from .algorithms.vector_conditionals.ConditionalIntersection import *
from .algorithms.vector_conditionals.CountPointsInPolygonsWithCondition import * 
from .algorithms.vector_conditionals.SnapVerticesToNearestPointsByCondition import *
from .algorithms.vector_conditionals.CountNearestFeaturesByCondition import *
from .algorithms.vector_conditionals.CountFeaturesInFeaturesByCategory import *
# Vector - Creation
from .algorithms.vector_creation.CreateTimepolygonsWithPointcount import *
from .algorithms.vector_creation.GeometryLayerFromGeojsonStringField import *
from .algorithms.vector_creation.CreateNestedGrid import *
from .algorithms.vector_creation.NearestPointsToPath import *
from .algorithms.vector_creation.CreatePolygonFromExtent import *
from .algorithms.vector_creation.RandomlyRedistributeFeaturesInsidePolygon import *
from .algorithms.vector_creation.TranslateDuplicateFeaturesToColumns import *
# Vector - Interpolation
from .algorithms.vector_interpolation.InterpolateDateTimeAlongLine import *
# OpenTripPlanner
from .algorithms.opentripplanner.OtpRoutes import *
from .algorithms.opentripplanner.OtpTraveltime import *

pluginPath = os.path.split(os.path.dirname(__file__))[0]

class ProcessXProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        # Vecotr - Conditional
        self.addAlgorithm(JoinAttributesByNearestWithCondition())
        self.addAlgorithm(CountFeaturesInFeaturesWithCondition())
        self.addAlgorithm(SelectDuplicatesBySimilarity())
        self.addAlgorithm(ConditionalIntersection())
        self.addAlgorithm(CountPointsInPolygonsWithCondition())
        self.addAlgorithm(SnapVerticesToNearestPointsByCondition())
        self.addAlgorithm(CountNearestFeaturesByCondition())
        self.addAlgorithm(CountFeaturesInFeaturesByCategory())
        # Vector - Creation
        self.addAlgorithm(CreateTimepolygonsWithPointcount())
        self.addAlgorithm(GeometryLayerFromGeojsonStringField())
        self.addAlgorithm(CreateNestedGrid())
        self.addAlgorithm(NearestPointsToPath())
        self.addAlgorithm(CreatePolygonFromExtent())
        self.addAlgorithm(RandomlyRedistributeFeaturesInsidePolygon())
        self.addAlgorithm(TranslateDuplicateFeaturesToColumns())
        # Vector - Interpolation
        self.addAlgorithm(InterpolateDateTimeAlongLine())
        # OpenTripPlanner
        self.addAlgorithm(OtpRoutes())
        self.addAlgorithm(OtpTraveltime())

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'ProcessX'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('ProcessX')

    def icon(self):
        """
        Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        #return QgsProcessingProvider.icon(self)
        return QIcon(os.path.join(pluginPath, 'processx', 'icon.png'))
        
    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
