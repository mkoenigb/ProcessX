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
# Version 1.0.1
# Date: 2021-03-05
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

class OtpRoutes(QgsProcessingAlgorithm):
    
    # Source: https://stackoverflow.com/a/33557535/8947209 (slightly modified)
    def decode_polyline(self, polyline_str):
        index, lat, lng = 0, 0, 0
        #coordinates = []
        pointlist = []
        changes = {'latitude': 0, 'longitude': 0}
    
        # Coordinates have variable length when encoded, so just keep
        # track of whether we've hit the end of the string. In each
        # while loop iteration, a single coordinate is decoded.
        while index < len(polyline_str):
            # Gather lat/lon changes, store them in a dictionary to apply them later
            for unit in ['latitude', 'longitude']: 
                shift, result = 0, 0

                while True:
                    byte = ord(polyline_str[index]) - 63
                    index+=1
                    result |= (byte & 0x1f) << shift
                    shift += 5
                    if not byte >= 0x20:
                        break

                if (result & 1):
                    changes[unit] = ~(result >> 1)
                else:
                    changes[unit] = (result >> 1)

            lat += changes['latitude']
            lng += changes['longitude']
            
            qgspointgeom = QgsPoint(float(lng / 100000.0),float(lat / 100000.0))
            pointlist.append(qgspointgeom)

            #coordinates.append((lat / 100000.0, lng / 100000.0)) # original code, but we dont need a tuple of coords, only the qgspoints
        return pointlist    
    
    SERVER_URL = 'SERVER_URL'
    SOURCE_LYR = 'SOURCE_LYR'
    STARTLAT_FIELD = 'STARTLAT_FIELD'
    STARTLON_FIELD = 'STARTLON_FIELD'
    ENDLAT_FIELD = 'ENDLAT_FIELD'
    ENDLON_FIELD = 'ENDLON_FIELD'
    DATE_FIELD = 'DATE_FIELD'
    TIME_FIELD = 'TIME_FIELD'
    MODE = 'MODE'
    OPTIMIZE = 'OPTIMIZE'
    ADDITIONAL_PARAMS = 'ADDITIONAL_PARAMS'
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
                self.MODE, self.tr('Travelmode for Routes'),
                ['WALK','CAR','BICYCLE','TRANSIT','WALK,TRANSIT','WALK,BICYCLE'],defaultValue=5))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPTIMIZE, self.tr('Preferred Route Optimization'),
                ['QUICK','TRANSFERS','SAFE','FLAT','GREENWAYS','TRIANGLE'],defaultValue=5))
        self.addParameter(
            QgsProcessingParameterString(
                self.ADDITIONAL_PARAMS, self.tr('Additional Parameters as String, beginning with an & Sign'),'&triangleTimeFactor=0.34&triangleSlopeFactor=0.32&triangleSafetyFactor=0.34',optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ITERINARIES, self.tr('Number of Iterinaries'),type=0,defaultValue=1,minValue=1))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('OTP Routes'))) # Output
                

        
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
        travelmode = self.parameterAsString(parameters, self.MODE, context)
        modelist = ['WALK','CAR','BICYCLE','TRANSIT','WALK,TRANSIT','WALK,BICYCLE']
        travelmode = str(modelist[int(travelmode[0])])
        traveloptimize = self.parameterAsString(parameters, self.OPTIMIZE, context)
        optimizelist = ['QUICK','TRANSFERS','SAFE','FLAT','GREENWAYS','TRIANGLE']
        traveloptimize = str(optimizelist[int(traveloptimize[0])])
        
        additional_params = self.parameterAsString(parameters, self.ADDITIONAL_PARAMS, context)
        iterinaries = self.parameterAsInt(parameters, self.ITERINARIES, context)
        
        total = 100.0 / source_layer.featureCount() if source_layer.featureCount() else 0 # Initialize progress for progressbar
        
        fields = source_layer.fields() # get all fields of the sourcelayer
        n_source_fields = source_layer.fields().count()
        
        fieldlist = [ # Master for attributes and varnames
            QgsField("Route_LegID",QVariant.Int),
            QgsField("Route_RouteID", QVariant.Int),
            QgsField("Route_RelationID", QVariant.Int),
            QgsField("Route_From", QVariant.String), # !
            QgsField("Route_To", QVariant.String), # !
            QgsField("Route_Error", QVariant.String),
            QgsField("Route_ErrorID", QVariant.Int),
            QgsField("Route_ErrorDescription", QVariant.String),
            QgsField("Route_URL", QVariant.String),
            QgsField("Route_From_Lat", QVariant.Double, len=4, prec=8),
            QgsField("Route_From_Lon", QVariant.Double, len=4, prec=8),
            QgsField("Route_From_StopId", QVariant.String),
            QgsField("Route_From_StopCode", QVariant.String),
            QgsField("Route_From_Name", QVariant.String),
            QgsField("Route_From_StartTime", QVariant.DateTime),
            QgsField("Route_To_Lat", QVariant.Double, len=4, prec=8),
            QgsField("Route_To_Lon", QVariant.Double, len=4, prec=8),
            QgsField("Route_To_StopId", QVariant.String),
            QgsField("Route_To_StopCode", QVariant.String),
            QgsField("Route_To_Name", QVariant.String),
            QgsField("Route_To_EndTime", QVariant.DateTime),
            QgsField("Route_Total_Mode", QVariant.String),
            QgsField("Route_Total_Duration", QVariant.Int),
            QgsField("Route_Total_Distance", QVariant.Double),
            QgsField("Route_Total_TransitTime", QVariant.Int),
            QgsField("Route_Total_WaitingTime", QVariant.Int),
            QgsField("Route_Total_WalkTime", QVariant.Int),
            QgsField("Route_Total_WalkDistance", QVariant.Double),
            QgsField("Route_Total_Transfers", QVariant.Int),
            QgsField("Route_Leg_StartTime", QVariant.DateTime),
            QgsField("Route_Leg_DepartureDelay", QVariant.Int),
            QgsField("Route_Leg_EndTime", QVariant.DateTime),
            QgsField("Route_Leg_ArrivalDelay", QVariant.Int),
            QgsField("Route_Leg_Duration", QVariant.Int),
            QgsField("Route_Leg_Distance", QVariant.Double),
            QgsField("Route_Leg_Mode", QVariant.String),
            QgsField("Route_Leg_From_Lat", QVariant.Double, len=4, prec=8),
            QgsField("Route_Leg_From_Lon", QVariant.Double, len=4, prec=8),
            QgsField("Route_Leg_From_StopId", QVariant.String),
            QgsField("Route_Leg_From_StopCode", QVariant.String),
            QgsField("Route_Leg_From_Name", QVariant.String),
            QgsField("Route_Leg_From_Departure", QVariant.DateTime),
            QgsField("Route_Leg_To_Lat", QVariant.Double, len=4, prec=8),
            QgsField("Route_Leg_To_Lon", QVariant.Double, len=4, prec=8),
            QgsField("Route_Leg_To_StopId", QVariant.String),
            QgsField("Route_Leg_To_StopCode", QVariant.String),
            QgsField("Route_Leg_To_Name", QVariant.String),
            QgsField("Route_Leg_To_Arrival", QVariant.DateTime)
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
            if 'route_total_distance' in x:
                fieldindex_position_of_routetotaldistance = fieldindexcounter
            fieldindexcounter += 1
        len_fieldindexdict = len(fieldindexdict)
        
        
        # Counter
        route_legid = 0
        route_routeid = 0
        route_relationid = 0
        route_from = ''
        route_to = ''
        notavailablestring = None #'not available'
        notavailableint = None #0
        notavailableothers = None
        
        # Pseudopointlist for errors in decode polyline
        errorlinegeom = []
        errorlinegeomp1 = QgsPoint(float(-0.1),float(0.0))
        errorlinegeom.append(errorlinegeomp1)
        errorlinegeomp2 = QgsPoint(float(0.1),float(0.0))
        errorlinegeom.append(errorlinegeomp2)
        
        # some general settings
        route_headers = {"accept":"application/json"} # this plugin only works for json responses
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fields, 2, # 2 = wkbType LineString
                                               QgsCoordinateReferenceSystem('EPSG:4326'))
                                               
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
            route_url = (str(server_url) + "plan?" + # Add Plan request to server url
                "fromPlace=" + str(source_feature[startlat_field]) + "," + str(source_feature[startlon_field]) +
                "&toPlace=" + str(source_feature[endlat_field]) + "," + str(source_feature[endlon_field]) +
                "&mode=" + travelmode +
                "&date=" + use_date +
                "&time=" + use_time +
                "&numItineraries=" + str(iterinaries) +
                "&optimize=" + traveloptimize +
                additional_params # Additional Parameters entered as OTP-Readable string -> User responsibility
            )
            
            #print(route_url)
            
            # Reset Error Indicators
            route_error = 'Success'
            route_error_bool = False
            route_errorid = None
            route_errordescription = None
            route_errormessage = None
            route_errornopath = None

            try: # Try to request route
                route_request = urllib.request.Request(route_url, headers=route_headers)
                try: # Try to receive response
                    route_response = urllib.request.urlopen(route_request)
                    try: # Try to read response data
                        response_data = route_response.read()
                        encoding = route_response.info().get_content_charset('utf-8')
                        route_data = json.loads(response_data.decode(encoding))
                        try: # Check if response says Error
                            route_error = 'Error: No Route'
                            route_error_bool = True
                            route_errorid = route_data['error']['id']
                            route_errordescription = route_data['error']['msg']
                            try: # not every error delivers this
                                route_errormessage = route_data['error']['message']
                            except:
                                pass
                            try: # not every error delivers this
                                route_errornopath = route_data['error']['noPath']
                            except:
                                pass
                        except:
                            route_error = 'Success'
                            route_error_bool = False
                    except:
                        route_error = 'Error: Cannot read response data'
                        route_error_bool = True
                except:
                    route_error = 'Error: No response received'
                    route_error_bool = True
            except:
                route_error = 'Error: Requesting the route failed'
                route_error_bool = True
            
            #print(route_error)
            try:
                if not route_data['plan']['itineraries']: # check if response is empty
                    route_error = 'Error: Empty response route'
                    route_error_bool = True
            except:
                pass
                
            #print(route_data)
            # Reading response
            if route_error_bool == False:
                # Get general informations. Note that not all are available in all responses: use try/except
                try:
                    route_from_lat = route_data['plan']['from']['lat']
                    route_from_lon = route_data['plan']['from']['lon']
                except:
                    route_from_lat = notavailableint
                    route_from_lon = notavailableint
                try:
                    route_from_stopid = route_data['plan']['from']['stopId']
                except:
                    route_from_stopid = notavailablestring
                try:
                    route_from_stopcode = route_data['plan']['from']['stopCode']
                except:
                    route_from_stopcode = notavailablestring
                try:
                    route_from_name = route_data['plan']['from']['name']
                except:
                    route_from_name = notavailablestring
                try:
                    route_to_lat = route_data['plan']['to']['lat']
                    route_to_lon = route_data['plan']['to']['lon']
                except:
                    route_to_lat = notavailableint
                    route_to_lon = notavailableint
                try:
                    route_to_stopid = route_data['plan']['to']['stopId']
                except:
                    route_to_stopid = notavailablestring
                try:
                    route_to_stopcode = route_data['plan']['to']['stopCode']
                except:
                    route_to_stopcode = notavailablestring
                try:
                    route_to_name = route_data['plan']['to']['name']
                except:
                    route_to_name = notavailablestring
                
                # loop through iterinaries    
                for iter in route_data['plan']['itineraries']: 
                    route_routeid += 1
                    try:
                        route_from_starttime = iter['startTime']
                        route_from_starttime = datetime.fromtimestamp(int(route_from_starttime)/1000)
                        route_from_starttime = QDateTime.fromString(str(route_from_starttime),'yyyy-MM-dd hh:mm:ss')
                    except:
                        route_from_starttime = notavailableothers
                    try:
                        route_to_endtime = iter['endTime']
                        route_to_endtime = datetime.fromtimestamp(int(route_to_endtime)/1000)
                        route_to_endtime = QDateTime.fromString(str(route_to_endtime),'yyyy-MM-dd hh:mm:ss')
                    except:
                        route_to_endtime = notavailableothers
                    try:
                        route_total_duration = iter['duration']
                    except:
                        route_total_duration = notavailableint
                    route_total_distance = 0 # set to 0 on start of each new route, well take the sum of all legs of a route
                    route_total_mode = travelmode
                    try:
                        route_total_transittime = iter['transitTime']
                    except:
                        route_total_transittime = notavailableint
                    try:
                        route_total_waitingtime = iter['waitingTime']
                    except:
                        route_total_waitingtime = notavailableint
                    try:
                        route_total_walktime = iter['walkTime']
                    except:
                        route_total_walktime = notavailableint
                    try:
                        route_total_walkdistance = iter['walkDistance']
                    except:
                        route_total_walkdistance = notavailableint
                    try:
                        route_total_transfers = iter['transfers']
                    except:
                        route_total_transfers = notavailableint
                    #print('From lat: ' + str(route_total_duration))
                    
                    # loop through legs --> they will become the features of our layer
                    route_leg_totaldistcounter = 0 # set to 0 on start of each new route
                    for leg in iter['legs']: 
                        route_legid += 1
                        new_feature = QgsFeature(fields)
                        
                        try:
                            route_leg_starttime = leg['startTime']
                            route_leg_starttime = datetime.fromtimestamp(int(route_leg_starttime)/1000)
                            route_leg_starttime = QDateTime.fromString(str(route_leg_starttime),'yyyy-MM-dd hh:mm:ss')
                        except:
                            route_leg_starttime = notavailableothers
                        try:
                            route_leg_departuredelay = leg['departureDelay']
                        except:
                            route_leg_departuredelay = notavailableint
                        try:
                            route_leg_endtime = leg['endTime']
                            route_leg_endtime = datetime.fromtimestamp(int(route_leg_endtime)/1000)
                            route_leg_endtime = QDateTime.fromString(str(route_leg_endtime),'yyyy-MM-dd hh:mm:ss')
                        except:
                            route_leg_endtime = notavailableothers
                        try:
                            route_leg_arrivaldelay = leg['arrivalDelay']
                        except:
                            route_leg_arrivaldelay = notavailableint
                        try:
                            route_leg_duration = leg['duration']
                        except:
                            route_leg_duration = notavailableint
                        try:
                            route_leg_distance = leg['distance']
                            #route_total_distance += route_leg_distance # Field does not exist in response. Build sum of all legs
                            route_total_distance = None
                        except:
                            route_leg_distance = notavailableint
                            #route_total_distance += 0 # Field does not exist in response.....
                        try:
                            route_leg_mode = leg['mode']
                        except:
                            route_leg_mode = notavailablestring
                        try:
                            route_leg_from_lat = leg['from']['lat']
                            route_leg_from_lon = leg['from']['lon']
                        except:
                            route_leg_from_lat = notavailableint
                            route_leg_from_lon = notavailableint
                        try:
                            route_leg_from_stopid = leg['from']['stopId']
                        except:
                            route_leg_from_stopid = notavailablestring
                        try:
                            route_leg_from_stopcode = leg['from']['stopCode']
                        except:
                            route_leg_from_stopcode = notavailablestring
                        try:
                            route_leg_from_name = leg['from']['name']
                        except:
                            route_leg_from_name = notavailablestring
                        try:
                            route_leg_from_departure = leg['from']['departure']
                            route_leg_from_departure = datetime.fromtimestamp(int(route_leg_from_departure)/1000)
                            route_leg_from_departure = QDateTime.fromString(str(route_leg_from_departure),'yyyy-MM-dd hh:mm:ss')
                        except:
                            route_leg_from_departure = notavailableothers
                        try:
                            route_leg_to_lat = leg['to']['lat']
                            route_leg_to_lon = leg['to']['lon']
                        except:
                            route_leg_to_lat = notavailableint
                            route_leg_to_lon = notavailableint
                        try:
                            route_leg_to_stopid = leg['to']['stopId']
                        except:
                            route_leg_to_stopid = notavailablestring
                        try:
                            route_leg_to_stopcode = leg['to']['stopCode']
                        except:
                            route_leg_to_stopcode = notavailablestring
                        try:
                            route_leg_to_name = leg['to']['name']
                        except:
                            route_leg_to_name = notavailablestring
                        try:
                            route_leg_to_arrival = leg['to']['arrival']
                            route_leg_to_arrival = datetime.fromtimestamp(int(route_leg_to_arrival)/1000)
                            route_leg_to_arrival = QDateTime.fromString(str(route_leg_to_arrival),'yyyy-MM-dd hh:mm:ss')
                        except:
                            route_leg_to_arrival = notavailableothers
                        
                        try:
                            route_leg_encodedpolylinestring = leg['legGeometry']['points']
                            route_leg_decodedpolylinestring_aspointlist = self.decode_polyline(route_leg_encodedpolylinestring)
                            new_feature.setGeometry(QgsGeometry.fromPolyline(route_leg_decodedpolylinestring_aspointlist))
                        except:
                            new_feature.setGeometry(QgsGeometry.fromPolyline(errorlinegeom))
                            route_error = 'Error: Decoding route geometry failed'
                        
                        # Adding the attributes to resultlayer
                        for key, value in fieldindexdict.items(): # keys contain the fieldindex, values the variablename which is the same as the fieldname, just in lowercase
                            fieldindex = key
                            if key < n_source_fields: # Copy source attributes from source layer
                                fieldvalue = source_feature[fieldindex] # source_feature = sourcelayer-feature, new_feature = new feature
                            else: # Get the leg attributes from variables
                                fieldvalue = locals()[value] # variables are named exactly as the fieldnames, just lowercase, we adjusted that before
                            new_feature.setAttribute(fieldindex,fieldvalue)
                        sink.addFeature(new_feature, QgsFeatureSink.FastInsert) # add feature to the output
                        route_leg_totaldistcounter += 1 # counting the number of legs of a route
                        # END OF LOOP legs
                        
                    # Update total distance here since it is the sum of all legs and not available in response jsons
                    #attr_totaldistance = { fieldindex_position_of_routetotaldistance : route_total_distance } # only change totaldistance field, we get its position while building the dict
                    #last_featureid_totaldistance = new_feature.id() # the last featureid of a route = current feature
                    #first_featureid_totaldistance = last_featureid_totaldistance - route_leg_totaldistcounter + 1 # the first featureid of a route
                    #print('last: ' + str(last_featureid_totaldistance))
                    #print('first: ' + str(first_featureid_totaldistance))
                    #for features_before in range(first_featureid_totaldistance,last_featureid_totaldistance): # loop through all legs of the current route
                        #new_feature.setAttribute(fieldindex_position_of_routetotaldistance,route_total_distance)
                        #dings = new_feature.id(features_before)
                        #dings.setAttribute(fieldindex_position_of_routetotaldistance,route_total_distance)
                        #new_feature.id(features_before)[fieldindex_position_of_routetotaldistance] = route_total_distance
                        #print(new_feature.id(features_before))
                        #routes_memorylayer_pr.changeAttributeValues({ features_before : attr_totaldistance }) # add the leg-sum of all legs of a route as totaldistance
                    # END OF LOOP iterinaries
                    
                # END OF if route_error_bool == False
            else: # Create error-dummyfeature if no route has been returned
                route_routeid += 1
                route_legid += 1
                new_feature = QgsFeature(fields)
                try:
                    route_errorid = route_data['error']['id']
                except:
                    route_errorid = notavailableint
                try:
                    route_errordescription = route_data['error']['msg']
                except:
                    route_errordescription = notavailablestring
                try:
                    route_errormessage = route_data['error']['message']
                except:
                    route_errormessage = notavailablestring
                try:
                    route_errornopath = route_data['error']['noPath']
                except:
                    route_errornopath = notavailablestring
                
                # Create dummy-geometry
                new_feature.setGeometry(QgsGeometry.fromPolyline(errorlinegeom))
                # Adding the attributes to resultlayer
                for key, value in fieldindexdict.items(): # keys contain the fieldindex, values the variablename which is the same as the fieldname, just in lowercase
                    fieldindex = key
                    if fieldindex < n_source_fields: # copy attributes from source layer
                        fieldvalue = source_feature[fieldindex]
                        new_feature[fieldindex] = fieldvalue
                    elif fieldindex <= fieldindex_position_of_last_alwaysneededfield: # Only fill the first fields on error
                        fieldvalue = locals()[value]
                        new_feature[fieldindex] = fieldvalue
                    else: # Leave the others empty as there is no data available
                        fieldvalue = None
                        new_feature[fieldindex] = fieldvalue
                        
                sink.addFeature(new_feature, QgsFeatureSink.FastInsert) # add feature to the output
                # END OF errorroutecreation
                
            
            if feedback.isCanceled(): # Cancel algorithm if button is pressed
                break
            
            feedback.setProgress(int(current * total)) # Set Progress in Progressbar

        return {self.OUTPUT: dest_id} # Return result of algorithm



    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return OtpRoutes()

    def name(self):
        return 'OtpRoutes'

    def displayName(self):
        return self.tr('OpenTripPlanner Routes')

    def group(self):
        return self.tr('OpenTripPlanner')

    def groupId(self):
        return 'otp'

    def shortHelpString(self):
        return self.tr('This Tool requests routes from an OTP instance based on a layer and returns its geometry and attributes')