### Specifications for the WetlandElevationChangeTable.csv ###

Name
####
Type - Text
Nullable - False, cannot contain null values
Desc - Name of feature class or shapefile, without file extension or alias. Example: DN1_LT11, MA_LT12

Date
####
Type - Text
Nullable - False, cannot contain null values
Desc - Year, date sting, or any arbitrary time period. No spaces or special characters allowed. (ex. 2002, 1/22/2012, May_1980, Spring, etc.)

ElevationField
##############
Type - Text
Nullable - False, cannot contain null values
Desc - The name of the field containing elevations in meters to be used in the analysis. Field name must match exactly. Aliases cannot be used. Elevations not in meters will cause incorrect results. 

StudyAreaFieldName
##################
Type - Text
Nullable - False, cannot contain null values
Desc - Field name in the dataset indicating the top level group for analysis, such as watershed (Dennis), stream (Christinia), or region (Delmarva Peninsula). Can be further refined by the Sub-Study Area (see below). If only one study area exists, a new data column must be created and populated with a common value.

SubStudyAreaFieldName
#####################
Type - Text
Null - True, optional field 
Desc - Field name in the dataset containing additional information for how to sub-divide the study area, such as SET number, tributary, sub-region, etc. Non-spatially contiguous groups will not be evaluated, so make sure that contents of sub-groups overlap each other in space.