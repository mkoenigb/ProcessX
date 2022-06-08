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

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsGeometry, QgsPoint, QgsFields, QgsWkbTypes, QgsStringUtils,
                       QgsProcessingAlgorithm, QgsProcessingParameterField, QgsProcessingParameterVectorLayer, QgsProcessingOutputVectorLayer, QgsProcessingParameterEnum, QgsProcessingParameterString, QgsProcessingParameterNumber)

class SelectDuplicatesBySimilarity(QgsProcessingAlgorithm):
    SOURCE_LYR = 'SOURCE_LYR'
    SOURCE_FIELD = 'SOURCE_FIELD'
    MAX_DISTANCE = 'MAX_DISTANCE'
    ALGORITHM = 'ALGORITHM'
    ANDORALG = 'ANDORALG'
    THRESHOLD_LEVENSHTEIN = 'THRESHOLD_LEVENSHTEIN'
    THRESHOLD_SUBSTRING = 'THRESHOLD_SUBSTRING'
    THRESHOLD_HAMMING = 'THRESHOLD_HAMMING'
    OPERATOR = 'OPERATOR'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SOURCE_LYR, self.tr('Source Layer'))) # Take any source layer
        self.addParameter(
            QgsProcessingParameterField(
                self.SOURCE_FIELD, self.tr('Attribute Field to search for similarity'),'Name','SOURCE_LYR')) # Choose the Trigger field of the source layer, default if exists is 'Trigger'
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_DISTANCE, self.tr('Maximum Search Distance for Duplicates in Layer CRS units'),1,10000))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ALGORITHM, self.tr('Select the Algorithms you want to use to identify similar attributes.'),
                    ['Exact Duplicates',
                    'Soundex',
                    'Levenshtein Distance',
                    'Longest Common Substring',
                    'Hamming Distance'],
                    allowMultiple=True,defaultValue=[1]))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ANDORALG, self.tr('Choose if all selected algorithms need to fulfill criteria or only at least one'),['All','Only at least one'],defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD_LEVENSHTEIN, self.tr('Choose a Threshold for Levenshtein < Threshold'),0,None,True,0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD_SUBSTRING, self.tr('Choose a Threshold for Longest Common Substring > (Length of Attributevalue - Threshold)'),0,None,True,0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD_HAMMING, self.tr('Choose a Threshold for Hamming Distance > (Length of Attributevalue - Threshold)'),0,None,True,0))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT, self.tr('Possible Duplicates')))

    def processAlgorithm(self, parameters, context, feedback):
        # Get Parameters and assign to variable to work with
        layer = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        field = self.parameterAsString(parameters, self.SOURCE_FIELD, context)
        maxdist = self.parameterAsDouble(parameters, self.MAX_DISTANCE, context)
        th_levenshtein = self.parameterAsInt(parameters, self.THRESHOLD_LEVENSHTEIN, context)
        th_substring = self.parameterAsInt(parameters, self.THRESHOLD_SUBSTRING, context)
        th_hamming = self.parameterAsInt(parameters, self.THRESHOLD_HAMMING, context)
        alg = self.parameterAsEnums(parameters, self.ALGORITHM, context)
        ao = self.parameterAsInt(parameters, self.ANDORALG, context)
        op = self.parameterAsString(parameters, self.OPERATOR, context)
        feedback.setProgressText('Prepare processing...')
        
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0 # Initialize progress for progressbar
        
        layer.removeSelection() # clear selection before every run
        #totalfeatcount = layer.featureCount()
        
        feedback.setProgressText('Start processing...')
        for current, feat in enumerate(layer.getFeatures()): # iterate over source 
            s = None # reset selection indicator
            s0 = None
            s1 = None
            s2 = None
            s3 = None
            s4 = None
            th_levenshtein_new = th_levenshtein
            th_substring_new  = th_substring
            th_hamming_new = th_hamming
            if feat[field] is not None and len(str(feat[field])) > 0: # only compare if field is not empty
                # recalc thresholds based on current attribute values
                th_levenshtein_new = th_levenshtein_new
                if th_levenshtein_new < 0: # set to 0 if it would be negative
                    th_levenshtein_new = 0
                th_substring_new = len(str(feat[field])) - th_substring
                if th_substring_new < 0: # set to 0 if it would be negative
                    th_substring_new = 0
                th_hamming_new = len(str(feat[field])) - th_hamming
                if th_hamming_new < 0: # set to 0 if it would be negative
                    th_hamming_new = 0            
                for lookupnr in range(1,feat.id(),1): # only compare to previous features, because we do not want to select the first feature of each duplicate group
                    lookup = layer.getFeature(lookupnr) # get the lookup-feature
                    if lookup[field] is not None and len(str(lookup[field])) > 0: # only compare if field is not empty
                        if feat.geometry().centroid().distance(lookup.geometry().centroid()) <= maxdist: # only select if within given maxdistance
                            if 0 in alg: # Exact Duplicates
                                if feat[field] == lookup[field]:
                                    s0 = 1
                                else: s0 = 0
                            if 1 in alg: # Soundex
                                if QgsStringUtils.soundex(str(feat[field])) == QgsStringUtils.soundex(str(lookup[field])):
                                    s1 = 1
                                else: s1 = 0
                            if 2 in alg: # Levenshtein
                                if QgsStringUtils.levenshteinDistance(str(feat[field]),str(lookup[field])) < th_levenshtein_new:
                                    s2 = 1
                                else: s2 = 0
                            if 3 in alg: # Longest Common Substring
                                if len(QgsStringUtils.longestCommonSubstring(str(feat[field]),str(lookup[field]))) > th_substring_new:
                                    s3 = 1
                                else: s3 = 0
                            if 4 in alg: # Hamming Distance:
                                if QgsStringUtils.hammingDistance(str(feat[field]),str(lookup[field])) > th_hamming_new:
                                    s4 = 1  
                                else: s4 = 0
                                
                            if ao == 0: # All chosen algorithms need to match
                                if 0 in (s0, s1, s2, s3, s4): # Dont select current feature if at least one used algorithm returned 0
                                    s = 0
                                else: # Select current feature if all algorithms returned 1 or None
                                    s = 1
                            elif ao == 1: # Only at least one algorithm needs to match
                                if 1 in (s0, s1, s2, s3, s4): # Select current feature if at least one used algorithm returned 1
                                    s = 1
                                else: # Dont select current feature if no used algorithm returned 1
                                    s = 0
                                    
                            if s == 1: # select the current feature if indicator is true
                                layer.select(feat.id())
                            
                if feedback.isCanceled(): # Cancel algorithm if button is pressed
                    break
            feedback.setProgress(int(current * total)) # Set Progress in Progressbar

        return {self.OUTPUT: parameters[self.SOURCE_LYR]} # Return result of algorithm

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return SelectDuplicatesBySimilarity()

    def name(self):
        return 'SelectDuplicatesBySimilarity'

    def displayName(self):
        return self.tr('Select possible duplicate features by similarity (attribute and distance)')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Vector - Conditional'

    def shortHelpString(self):
        return self.tr(
        'This Algorithm selects possible duplicate features by their similarity. The first feature (ordered by feature id) in each group will NOT get selected. The algorithm always creates a new selection when running it.'
        'You can choose between the following algorithms, and can also combine them: \n'
        '- Exact Match: Matches if the attribue values are exactly the same \n'
        '- Soundex: Matches by sound, as pronounced in English if both results are equal \n '
        '- Levenshtein Distance: Matches if by measuring the difference between two sequences is lower than the threshold\n '
        '- Longest Common Substring: Matches if the longest string that is a substring of compared value and greater than the threshold \n'
        '- Hamming Distance: Matches if between two strings of equal length the number of positions at which the corresponding symbols are greater than the threshold \n '
        'You can also choose a maximum search distance in CRS units. If the layer is not a single-point layer, the centroids are taken for distance calculation.'
        )