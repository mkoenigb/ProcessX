# ProcessX
Repository for QGIS ProcessX Plug-In

This Plug-In adds a new processing provider to QGIS. It contains a variety of processing algorithms.

Please report bugs or issues you encounter with these algorithms on https://github.com/mkoenigb/processx/issues/

The algorithms are:

### Vector - Conditional
- (New in v1.0) **Join Attributes By Nearest With Condition**: Joins the attributes of the x nearest features if an expression condition returns true.
- (New in v1.0) **Count Features In Features With Condition**: Counts features in another layers features (can be lines and polygons as well as points and different geometric predicates like intersects, within, disjoint, equals...) if an expression condition returns true.
- (New in v1.0) **Select Duplicates By Similarity**: Selects possible duplicates in a layer by distance and attribute like exact attribute match, soundex, hamming distance, levenshtein distance or longest common substring.
- (New in v1.0) **Conditional Intersection**: Creates an intersection geometry between the features of two layers only if an expression condition returns true. This algorithm can also be used as polygon-self-intersection.
- (New in v1.1) **Count Points in Polygons With Condition**: Counts points in polygons (intersects or within) if an expression condition returns true (This algorithm is a lot faster than "Count Features In Features With Condition" when counting 2D-Single-Points in Polygons).
- (New in v1.2) **Snap Vertices to nearest Points by Condition**: Snaps the vertices of a given layer (singleline, multiline, polygon or point) to the nearest point of a given point layer by optional attribute and distance conditions.
- (New in v1.3) **Count Nearest Features by Condition**: Counts the number of nearby features by a given maximum distance and optional attribute condition(s). You can also set whether a feature should be counted only once, if so, it will only be counted to the nearest feature.
- (New in v1.4) **Count Features in Features by Category**: Counts features in features (both can be Points, Lines or Polygons of any type) per a given category, evaluated either via an expression or a field.
- (New in v1.5) **Count Nearest Features by Category**: Counts nearest features per a given category, evaluated either via an expression or a field.
- (New in v1.5) **Remove Self-Overlapping Portions by Condition**: Removes self overlapping portions within a layer by an optional attribute condition. You can choose the iteration order and which feature should keep overlapping parts.
- (New in v1.5) **Conditional Difference**: Builds a difference between two features of different or the same layer if an optional attribute condition is met. This algorithm is based on *Remove Self-Overlapping Portions by Condition* and enhances its possibilities.

### Vector - Creation
- (New in v1.0) **Create Timepolygons With Pointcount**: Creates x duplicates of given polygons in a given timerange with from- and to-timestamp and the pointcount falling inbetween this timerange and geometry.
- (New in v1.0) **Geometry Layer From Geojson String Field**: Creates a duplicated layer of the input with modified geometry, taken from a field with a valid GeoJSON-String.
- (New in v1.1) **Create Nested Grid**: Creates a parent grid and x child grids. You can choose how many childcells a parent shall have in x and y direction.
- (New in v1.2) **Nearest Points to Path**: Connects points to paths based on their distance.
- (New in v1.4) **Create Polygon From Extent**: Takes an extent as input and an optional CRS and creates a new polygon layer from it with some basic attributes.
- (New in v1.4) **Randomly Redistribute Features Inside Polygon**: Takes a point, line or polygon layer as input and redistributes its features randomly, by using translate and rotate, inside a polygon the feature is within.
- (New in v1.5) **Translate Duplicate Features to Columns**: Translates features (rows) to columns by an duplicate-identifier, which can be an expression, geometry or a field.

### Vector - Interpolation
- (New in v1.3) **Interpolate DateTime Along Line**: Segmentizes a line by a given distance and interpolates Start- and End-DateTime for these segments. This algorithm is designed for animating lines with Temporal Controller.

### OpenTripPlanner
- (New in v1.0) **OTP Routes**: Requests routes from an OpenTripPlanner instance and creates a linelayer from the returned geometry and attributes.
- (New in v1.0) **OTP Traveltime**: Adds some attributes to a given layer based on OpenTripPlanner routing results.