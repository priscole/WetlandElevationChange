### Specifications for the WetlandElevationChangeTable.csv ###

FileName
########
Type - Text
Null - False, cannot contain null values
Desc - Field contains the names of each input point feature
		class or shapefile. Names must exactly match the file
		name, and will fail if aliases are supplied. Do not supply the file extension. One row represents one input file. 


Watershed
#########
Type - Text
Null - False, cannot contain null values
Desc - Name of the watershed. Watersheds are one part of 
		organizing the analysis groups, so that locations can be evaluated over a period of years.

Year
####
Type - Date/year
Null - False, cannot contain null values
Desc - 4-digit year (ex. 2002, 1909, 2016)

ElevationField
##############
Type - Text
Null - False, cannot contain null values
Desc - The name of the field containing elevations in meters to 
		be used in the analysis. Field name must match exactly. Aliases cannot be used. Elevations not in meters will cause incorrect results. 

SetField
########
Type - Numeric
Null - True, optional field
Desc - Sediment elevation number (SET). Use this field if SETs 			were used in the sampling methodology. Leave black if 			SETs were not used. The SET number helps to organize 			data into analysis groups, if these sub-divisions exist.

OtherGroup
##########
Type - Numeric
Null - True, optional field
Desc - Optional number by which to group data for analysis, 			which is not already apparent according to the 					watershed/SET/date combination. Specifying a group 				overrides other derived grouping configurations.
		
		WARNING: the interpolation tools used in this analysis
		assume spatial continuity, or that points are nearby each other. If large gaps occur between data points 
		the interpolators can produce strange results. Forcing data into groups without spatial continuity will not produce the desired results. 