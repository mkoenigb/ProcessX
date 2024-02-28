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
# Author: Mario Königbauer
# License: GNU General Public License v3.0
# Version 0.1
# Date: 2021-03-04
# Tested with: QGIS 3.4.15 and QGIS 3.18.0 (recommend 3.18, as at least 3.4 crashes sometimes without any reason or error message, but works on the same data and same settings perfectly when trying another time)

from PyQt5.QtCore import QCoreApplication, QVariant, QDate, QTime, QDateTime, Qt
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsExpression, QgsGeometry, QgsPoint, QgsFields, QgsWkbTypes, QgsCoordinateReferenceSystem, QgsDateTimeFieldFormatter,
                       QgsFeatureSink, QgsFeatureRequest, QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterField, QgsProcessingParameterFeatureSource, QgsProcessingParameterEnum, QgsProcessingParameterString, QgsProcessingParameterNumber)
from osgeo import ogr
from datetime import *
import os.path
import os
import urllib.request
import urllib
import json

class OtpTraveltimeComparison(QgsProcessingAlgorithm):
    
    SERVER_URL = 'SERVER_URL'
    SOURCE_LYR = 'SOURCE_LYR'
    STARTLAT_FIELD = 'STARTLAT_FIELD'
    STARTLON_FIELD = 'STARTLON_FIELD'
    ENDLAT_FIELD = 'ENDLAT_FIELD'
    ENDLON_FIELD = 'ENDLON_FIELD'
    DATE_FIELD = 'DATE_FIELD'
    TIME_FIELD = 'TIME_FIELD'
    MODE_A = 'MODE_A'
    OPTIMIZE_A = 'OPTIMIZE_A'
    ADDITIONAL_PARAMS_A = 'ADDITIONAL_PARAMS_A'
    MODE_B = 'MODE_B'
    OPTIMIZE_B = 'OPTIMIZE_B'
    ADDITIONAL_PARAMS_B = 'ADDITIONAL_PARAMS_B'
    ITERINARIES = 'ITERINARIES'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterString(
                self.SERVER_URL, self.tr('URL to OTP-Server including port and path to router ending with an /'),'http://localhost:8080/otp/routers/default/'))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE_LYR, self.tr('Sourcelayer')))
        self.addParameter(
            QgsProcessingParameterField(
                self.STARTLAT_FIELD, self.tr('Field containing Latitude of Startpoint'),'Start_Lat','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterField(
                self.STARTLON_FIELD, self.tr('Field containing Longitude of Startpoint'),'Start_Lon','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterField(
                self.ENDLAT_FIELD, self.tr('Field containing Latitude of Endpoint'),'End_Lat','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterField(
                self.ENDLON_FIELD, self.tr('Field containing Longitude of Endpoint'),'End_Lon','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterField(
                self.DATE_FIELD, self.tr('Field containing Date of Tripstart (or Tripend)'),'Start_date','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterField(
                self.TIME_FIELD, self.tr('Field containing Time of Tripstart (or Tripend)'),'Start_time','SOURCE_LYR'))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE_A, self.tr('Travelmode A for Routes'),
                ['WALK','CAR','BICYCLE','TRANSIT','WALK,TRANSIT','WALK,BICYCLE'],defaultValue=5))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPTIMIZE_A, self.tr('Preferred Route Optimization for Mode A'),
                ['QUICK','TRANSFERS','SAFE','FLAT','GREENWAYS','TRIANGLE'],defaultValue=5))
        self.addParameter(
            QgsProcessingParameterString(
                self.ADDITIONAL_PARAMS_A, self.tr('Additional Parameters as String for Mode A, beginning with an & Sign'),'&triangleTimeFactor=0.34&triangleSlopeFactor=0.32&triangleSafetyFactor=0.34&maxWalkDistance=500&maxOffroadDistance=500',optional=True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE_B, self.tr('Travelmode B for Routes'),
                ['WALK','CAR','BICYCLE','TRANSIT','WALK,TRANSIT','WALK,BICYCLE'],defaultValue=4))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPTIMIZE_B, self.tr('Preferred Route Optimization for Mode B'),
                ['QUICK','TRANSFERS','SAFE','FLAT','GREENWAYS','TRIANGLE'],defaultValue=0))
        self.addParameter(
            QgsProcessingParameterString(
                self.ADDITIONAL_PARAMS_B, self.tr('Additional Parameters as String for Mode B, beginning with an & Sign'),'&maxWalkDistance=500&maxOffroadDistance=500',optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ITERINARIES, self.tr('Number of Iterinaries (currently only possible with 1)'),type=QgsProcessingParameterNumber.Integer,defaultValue=1,minValue=1,maxValue=1))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('OTP TraveltimeComparison'))) # Output
                

        
    def processAlgorithm(self, parameters, context, feedback):
        # Get Parameters and assign to variable to work with
        server_url = self.parameterAsString(parameters, self.SERVER_URL, context)
        source_layer = self.parameterAsLayer(parameters, self.SOURCE_LYR, context)
        startlat_field = self.parameterAsString(parameters, self.STARTLAT_FIELD, context)
        startlon_field = self.parameterAsString(parameters, self.STARTLON_FIELD, context)
        endlat_field = self.parameterAsString(parameters, self.ENDLAT_FIELD, context)
        endlon_field = self.parameterAsString(parameters, self.ENDLON_FIELD, context)
        date_field = self.parameterAsString(parameters, self.DATE_FIELD, context)
        time_field = self.parameterAsString(parameters, self.TIME_FIELD, context)
        travelmode_a = self.parameterAsString(parameters, self.MODE_A, context)
        travelmode_b = self.parameterAsString(parameters, self.MODE_B, context)
        modelist = ['WALK','CAR','BICYCLE','TRANSIT','WALK,TRANSIT','WALK,BICYCLE']
        travelmode_a = str(modelist[int(travelmode_a[0])])
        travelmode_b = str(modelist[int(travelmode_b[0])])
        traveloptimize_a = self.parameterAsString(parameters, self.OPTIMIZE_A, context)
        traveloptimize_b = self.parameterAsString(parameters, self.OPTIMIZE_B, context)
        optimizelist = ['QUICK','TRANSFERS','SAFE','FLAT','GREENWAYS','TRIANGLE']
        traveloptimize_a = str(optimizelist[int(traveloptimize_a[0])])
        traveloptimize_b = str(optimizelist[int(traveloptimize_b[0])])        
        additional_params_a = self.parameterAsString(parameters, self.ADDITIONAL_PARAMS_A, context)
        additional_params_b = self.parameterAsString(parameters, self.ADDITIONAL_PARAMS_B, context)
        iterinaries = self.parameterAsInt(parameters, self.ITERINARIES, context)
        
        total = 100.0 / source_layer.featureCount() if source_layer.featureCount() else 0 # Initialize progress for progressbar
        
        fields = source_layer.fields() # get all fields of the sourcelayer
        n_source_fields = source_layer.fields().count()
        
        fieldlist = [ # Master for attributes and varnames
            QgsField("Route_RelationID", QVariant.Int),
            QgsField("Route_A_RouteID", QVariant.Int),
            QgsField("Route_B_RouteID", QVariant.Int),
            QgsField("Route_A_Error", QVariant.String),
            QgsField("Route_A_ErrorID", QVariant.Int),
            QgsField("Route_A_ErrorDescription", QVariant.String),
            QgsField("Route_A_URL", QVariant.String),
            QgsField("Route_A_Total_Mode", QVariant.String),
            QgsField("Route_A_Total_Duration", QVariant.Int),
            QgsField("Route_A_Total_Transfers", QVariant.Int),
            QgsField("Route_B_Error", QVariant.String),
            QgsField("Route_B_ErrorID", QVariant.Int),
            QgsField("Route_B_ErrorDescription", QVariant.String),
            QgsField("Route_B_URL", QVariant.String),
            QgsField("Route_B_Total_Mode", QVariant.String),
            QgsField("Route_B_Total_Duration", QVariant.Int),
            QgsField("Route_B_Total_Transfers", QVariant.Int),
            QgsField("Route_Faster_ModeWinner", QVariant.String),
            QgsField("Route_Faster_TimeGain", QVariant.Int),
            QgsField("Route_Faster_SavedTransfers", QVariant.Int)
            ]
        for field in fieldlist:
            fields.append(field) # add fields from the list
        # Fieldindex as dictionary to avoid a mess
        fieldindexcounter = 0 # start with index 0
        fieldindexdict = {} # empty dictionary
        for field in fields: # iterate through field list we just created above
            x = str(field.name()).lower() # convert to lowercase, string
            fieldindexdict[fieldindexcounter] = x # assign index as key and fieldname as value
            if '_url' in x:
                fieldindex_position_of_last_alwaysneededfield = fieldindexcounter
            fieldindexcounter += 1
        len_fieldindexdict = len(fieldindexdict)
        
        
        # Counter
        route_relationid = 0
        route_a_routeid = 0
        route_b_routeid = 0
        
        notavailablestring = None #'not available'
        notavailableint = None #0
        notavailableothers = None
        
        # some general settings
        route_headers = {"accept":"application/json"} # this plugin only works for json responses
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fields, source_layer.wkbType(),
                                               source_layer.sourceCrs())
                                               
        for current, source_feature in enumerate(source_layer.getFeatures()): # iterate over source
        
            route_relationid += 1
            
            # Making Script compatible with earlier versions than QGIS 3.18: If date or time field is a string, do not convert it to a string...
            use_date = ''
            use_time = ''
            try:
                use_date = str(source_feature[date_field].toString('yyyy-MM-dd'))
            except:
                use_date = str(source_feature[date_field])
            try:
                use_time = str(source_feature[time_field].toString('HH:mm:ss'))
            except:
                use_time = str(source_feature[time_field])
            
            # Create URL for current feature
            route_a_url = (str(server_url) + "plan?" + # Add Plan request to server url
                "fromPlace=" + str(source_feature[startlat_field]) + "," + str(source_feature[startlon_field]) +
                "&toPlace=" + str(source_feature[endlat_field]) + "," + str(source_feature[endlon_field]) +
                "&mode=" + travelmode_a +
                "&date=" + use_date +
                "&time=" + use_time +
                "&numItineraries=" + str(iterinaries) +
                "&optimize=" + traveloptimize_a +
                additional_params_a # Additional Parameters entered as OTP-Readable string -> User responsibility
            )
            
            route_b_url = (str(server_url) + "plan?" + # Add Plan request to server url
                "fromPlace=" + str(source_feature[startlat_field]) + "," + str(source_feature[startlon_field]) +
                "&toPlace=" + str(source_feature[endlat_field]) + "," + str(source_feature[endlon_field]) +
                "&mode=" + travelmode_b +
                "&date=" + use_date +
                "&time=" + use_time +
                "&numItineraries=" + str(iterinaries) +
                "&optimize=" + traveloptimize_b +
                additional_params_b # Additional Parameters entered as OTP-Readable string -> User responsibility
            )
            
            # Reset Error Indicators
            route_a_error = 'Success'
            route_a_error_bool = False
            route_a_errorid = None
            route_a_errordescription = None
            route_a_errormessage = None
            route_a_errornopath = None
            route_b_error = 'Success'
            route_b_error_bool = False
            route_b_errorid = None
            route_b_errordescription = None
            route_b_errormessage = None
            route_b_errornopath = None
            
            try: # Try to request route a
                route_a_request = urllib.request.Request(route_a_url, headers=route_headers)
                try: # Try to receive response
                    route_a_response = urllib.request.urlopen(route_a_request)
                    try: # Try to read response data
                        response_a_data = route_a_response.read()
                        encoding_a = route_a_response.info().get_content_charset('utf-8')
                        route_a_data = json.loads(response_a_data.decode(encoding_a))
                        try: # Check if response says Error
                            route_a_error = 'Error: No Route'
                            route_a_error_bool = True
                            route_a_errorid = route_a_data['error']['id']
                            route_a_errordescription = route_a_data['error']['msg']
                            try: # not every error delivers this
                                route_a_errormessage = route_a_data['error']['message']
                            except:
                                pass
                            try: # not every error delivers this
                                route_a_errornopath = route_a_data['error']['noPath']
                            except:
                                pass
                        except:
                            route_a_error = 'Success'
                            route_a_error_bool = False
                    except:
                        route_a_error = 'Error: Cannot read response data'
                        route_a_error_bool = True
                except:
                    route_a_error = 'Error: No response received'
                    route_a_error_bool = True
            except:
                route_a_error = 'Error: Requesting the route failed'
                route_a_error_bool = True
            
            try:
                if not route_a_data['plan']['itineraries']: # check if response is empty
                    route_a_error = 'Error: Empty response route'
                    route_a_error_bool = True
            except:
                pass
            
            
            try: # Try to request route b
                route_b_request = urllib.request.Request(route_b_url, headers=route_headers)
                try: # Try to receive response
                    route_b_response = urllib.request.urlopen(route_b_request)
                    try: # Try to read response data
                        response_b_data = route_b_response.read()
                        encoding_b = route_b_response.info().get_content_charset('utf-8')
                        route_b_data = json.loads(response_b_data.decode(encoding_b))
                        try: # Check if response says Error
                            route_b_error = 'Error: No Route'
                            route_b_error_bool = True
                            route_b_errorid = route_b_data['error']['id']
                            route_b_errordescription = route_b_data['error']['msg']
                            try: # not every error delivers this
                                route_b_errormessage = route_b_data['error']['message']
                            except:
                                pass
                            try: # not every error delivers this
                                route_b_errornopath = route_b_data['error']['noPath']
                            except:
                                pass
                        except:
                            route_b_error = 'Success'
                            route_b_error_bool = False
                    except:
                        route_b_error = 'Error: Cannot read response data'
                        route_b_error_bool = True
                except:
                    route_b_error = 'Error: No response received'
                    route_b_error_bool = True
            except:
                route_b_error = 'Error: Requesting the route failed'
                route_b_error_bool = True
            
            try:
                if not route_b_data['plan']['itineraries']: # check if response is empty
                    route_b_error = 'Error: Empty response route'
                    route_b_error_bool = True
            except:
                pass
                
                
                
            
            # Reading a response
            if route_a_error_bool == False:
                # loop through iterinaries
                for iter in route_a_data['plan']['itineraries']: 
                    route_a_routeid += 1
                    route_a_total_mode = travelmode_a
                    try:
                        route_a_total_duration = iter['duration']
                    except:
                        route_a_total_duration = notavailableint
                    try:
                        route_a_total_transfers = iter['transfers']
                    except:
                        route_a_total_transfers = notavailableint
            else:
                route_a_routeid += 1
                route_a_total_mode = travelmode_a
                try:
                    route_a_errorid = route_a_data['error']['id']
                except:
                    route_a_errorid = notavailableint
                try:
                    route_a_errordescription = route_a_data['error']['msg']
                except:
                    route_a_errordescription = notavailablestring
                try:
                    route_a_errormessage = route_a_data['error']['message']
                except:
                    route_a_errormessage = notavailablestring
                try:
                    route_a_errornopath = route_a_data['error']['noPath']
                except:
                    route_a_errornopath = notavailablestring
                    
            # Reading b response
            if route_b_error_bool == False:
                # loop through iterinaries
                for iter in route_b_data['plan']['itineraries']: 
                    route_b_routeid += 1
                    route_b_total_mode = travelmode_b
                    try:
                        route_b_total_duration = iter['duration']
                    except:
                        route_b_total_duration = notavailableint
                    try:
                        route_b_total_transfers = iter['transfers']
                    except:
                        route_b_total_transfers = notavailableint
            else:
                route_b_routeid += 1
                route_b_total_mode = travelmode_b
                try:
                    route_b_errorid = route_b_data['error']['id']
                except:
                    route_b_errorid = notavailableint
                try:
                    route_b_errordescription = route_b_data['error']['msg']
                except:
                    route_b_errordescription = notavailablestring
                try:
                    route_b_errormessage = route_b_data['error']['message']
                except:
                    route_b_errormessage = notavailablestring
                try:
                    route_b_errornopath = route_b_data['error']['noPath']
                except:
                    route_b_errornopath = notavailablestring


            new_feature = QgsFeature(fields)
            new_feature.setGeometry(source_feature.geometry())
            
            # Comparison
            if route_a_error_bool == True or route_b_error_bool == True:
                #print('Error')
                route_faster_modewinner = 'No comparison possible'
                route_faster_timegain = None
                route_faster_savedtransfers = None
                route_a_total_duration = None
                route_a_total_transfers = None
                route_b_total_duration = None
                route_b_total_transfers = None
                # Adding the attributes to resultlayer
                for key, value in fieldindexdict.items(): # keys contain the fieldindex, values the variablename which is the same as the fieldname, just in lowercase
                    fieldindex = key
                    if fieldindex < n_source_fields: # copy attributes from source layer
                        fieldvalue = source_feature[fieldindex]
                        new_feature[fieldindex] = fieldvalue
                    else: # Leave the others empty as there is no data available
                        fieldvalue = locals()[value]
                        new_feature[fieldindex] = fieldvalue
                    new_feature['Route_A_URL'] = route_a_url
                    new_feature['Route_B_URL'] = route_b_url
                    new_feature.setAttribute(fieldindex,fieldvalue)
            else: # if no error on both modes
                #print('NoError')
                if route_a_total_duration < route_b_total_duration:
                    route_faster_modewinner = 'A: ' + travelmode_a
                    route_faster_timegain = route_b_total_duration - route_a_total_duration
                    route_faster_savedtransfers = route_b_total_transfers - route_a_total_transfers
                elif route_b_total_duration == route_b_total_duration:
                    route_faster_modewinner = 'EQUAL'
                    route_faster_timegain = 0
                    if (route_a_total_transfers - route_b_total_transfers) < 0:
                        route_faster_savedtransfers = route_b_total_transfers - route_a_total_transfers
                    else:
                        route_faster_savedtransfers = route_a_total_transfers - route_b_total_transfers
                elif route_b_total_duration < route_a_total_duration:
                    route_faster_modewinner = 'B: ' + travelmode_b
                    route_faster_timegain = route_a_total_duration - route_b_total_duration
                    route_faster_savedtransfers = route_a_total_transfers - route_b_total_transfers
                else:
                    route_faster_modewinner = 'No comparison possible'
                    route_faster_timegain = None
                    route_faster_savedtransfers = None
                # Adding the attributes to resultlayer
                for key, value in fieldindexdict.items(): # keys contain the fieldindex, values the variablename which is the same as the fieldname, just in lowercase
                    fieldindex = key
                    if key < n_source_fields: # Copy source attributes from source layer
                        fieldvalue = source_feature[fieldindex] # source_feature = sourcelayer-feature, new_feature = new feature
                    else: # Get the leg attributes from variables
                        fieldvalue = locals()[value] # variables are named exactly as the fieldnames, just lowercase, we adjusted that before
                    new_feature.setAttribute(fieldindex,fieldvalue)
            
            sink.addFeature(new_feature, QgsFeatureSink.FastInsert) # add feature to the output
            
            
            if feedback.isCanceled(): # Cancel algorithm if button is pressed
                break
            
            feedback.setProgress(int(current * total)) # Set Progress in Progressbar

        return {self.OUTPUT: dest_id} # Return result of algorithm



    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return OtpTraveltimeComparison()

    def name(self):
        return 'OtpTraveltimeComparison'

    def displayName(self):
        return self.tr('OpenTripPlanner Traveltime Comparison')

    def group(self):
        return self.tr('OpenTripPlanner')

    def groupId(self):
        return 'otp'

    def shortHelpString(self):
        return self.tr('This Tool requests routes from an OTP instance based on a layer and creates a new layer, duplicated from the source (geometry and attributes), and adds a few attributes like total duration and transfers')