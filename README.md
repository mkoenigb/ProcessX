# ProcessX
Repository for QGIS ProcessX Plug-In

This Plug-In adds a new processing provider to QGIS. It contains a variety of processing algorithms.

The algorithms are:
### Vector - Conditional:
- ***Join Attributes By Nearest With Condition***: Joins the attributes of the x nearest features if an expression condition returns true
- ***Count Features In Features With Condition***: Counts features in another layers features (can be lines and polygons as well as points) if an expression condition returns true
- ***Select Duplicates By Similarity***: Provides the possibility to select possible duplicates in a layer by distance and either exact attribute match, soundex, hamming distance, levensthein distance
- ***Conditional Intersection***: Creates an intersection geometry between the features of two layers only if an expression condition returns true
### Vector - Creation
- ***Create Timepolygons With Pointcount***: Creates x duplicates of given polygons in a given timerange with from- and to-timestamp and the pointcount falling inbetween this timerange and geometry
- ***Geometry Layer From Geojson String Field***: Creates a duplicated layer of the input with modified geometry, taken from a field with a valid GeoJSON-String
### OpenTripPlanner
- ***OtpRoutes***: Requests routes from an OpenTripPlanner instance and creates a linelayer from the returned geometry and attributes
- ***OtpTraveltime***: Adds some attributes to a given layer based on OpenTripPlanner routing results