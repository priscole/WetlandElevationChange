#-------------------------------------------------------------
# Authored by Priscole
# 5/1/16
# Software: ArcMap 10.3 with GeoStatistical Analyst extension
# Description: Tool takes many elevation point files
# and exports a single csv file to compare elevation 
# changes over time. Interpolation method default is EBK, 
# with optional Spline with barriers if provided.
#-------------------------------------------------------------

import arcpy, csv, os

metadataTable = arcpy.GetParameterAsText(0) #type file
inWorkspace = arcpy.GetParameterAsText(1) #type folder
outFolder = arcpy.GetParameterAsText(2) #type folder
outCSV = arcpy.GetParameterAsText(3) #type string
outGDB = arcpy.GetParameterAsText(4) #type data element - optional or in_memory?
projection = arcpy.GetParameterAsText(5) #type int (optional) - default Delaware SP (m)

arcpy.env.workspace = inWorkspace

isNull = ["null", "NULL", "NA", "na", "N/A", "n/a", "", " "]
requiredFields = ["Name", "Date", "ElevationField", "StudyAreaFieldName"]
optionalField = "SubStudyAreaFieldName"

def makeFullPath(Path, Name):
	return Path + "\\" + Name

#############################################################################
#Handle Projections

def setSR(projection):
	if projection == "":
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)
	else: 
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(projection)

#############################################################################
#List input files according to workspace type

def listInputFiles(inWorkspace):
	desc = arcpy.Describe(arcpy.env.workspace)
	if desc.workspaceType in ['LocalDatabase', 'RemoteDatabase']:
		fileList = arcpy.ListFeatureClasses(feature_type='point')
	elif desc.workspaceType in ['FileSystem']:
		fileList = set(arcpy.ListFiles())
	else: 
		arcpy.AddMessage("""There was a problem with the input workspace. 
			Valid workspaces include geodatabases, or a folder (directory) 
			containing  only the point shapefiles intended for analysis.""")
		fileList = None
	return fileList	

def addLayerToMap(layer):
	mxd = arcpy.mapping.MapDocument("current")
	df = arcpy.mapping.ListDataFrames(mxd)[0]
	addLayer = arcpy.mapping.Layer(layer)
	arcpy.mapping.AddLayer(df, addLayer)

def writeFileNameIntoTable():
	pass

##############################################################################
#Handle metadata table & verify with file names

#read csv file
def csvToDictList(metadataTable):
	readTable = []
	with open(metadataTable, 'rb') as csvfile:
		tableReader = csv.DictReader(csvfile)
		for row in tableReader:
			readTable.append(row)
	return readTable

#checks if required fields are filled out in metadata table, called in fxn below
def validateSingleRecord(r):
	for field in requiredFields:
		if r[field] in isNull:
			return False
	return True
def validateMetaData(readTable):	
	for row in readTable:		
		if validateSingleRecord(row) == False: 
			arcpy.AddMessage("Invalid Table Input - " + row["Name"] + " contains NULL values in required field")
			return False
	return True

#verify matching of input file names and metadata table
def testMatchingInputs(fileList, readTable):
	metadataFiles = {row["Name"] for row in readTable}
	if metadataFiles.issubset(fileList) == True:
		arcpy.AddMessage("Inputs are valid.")
		return True
	elif fileList == None:
		return False
	elif metadataFiles.issubset(fileList) == False:
		setMissing = metadataFiles.difference(fileList)
		missingFiles = ", ".join(setMissing)
		arcpy.AddMessage("""Error - Metadata Table contains filenames that do not match files in the workspace. Unmatched files include: """ + missingFiles + """. Check for spelling errors in the metadata table or for missing files in the workspace.""")
		return False

#######################################################################
#Parse & Assemble Analysis Groups

#makes list of grouping fields per each file (as per metadata)
def groupingFieldsFromMetaData(metaDataRow):
	groupFields = [metaDataRow["StudyAreaFieldName"]]
	if metaDataRow["SubStudyAreaFieldName"] not in isNull:
		groupFields.append(metaDataRow["SubStudyAreaFieldName"])
	return groupFields

def groupingFieldsFromMetaDataForConvexHull(metaDataRow):
	groupFields = []
	if metaDataRow["SubStudyAreaFieldName"] not in isNull:
		groupFields.append(metaDataRow["SubStudyAreaFieldName"])
	groupFields.append(metaDataRow["StudyAreaFieldName"])
	return groupFields

#reads into file to assemble its unique groups as per grouping fields
def findDistinctGroups(metaDataRow):
	groupFields = groupingFieldsFromMetaData(metaDataRow)
	uniqueCombo = set(arcpy.da.SearchCursor(metaDataRow["Name"], groupFields))
	return uniqueCombo

#master dictionary of analysis groups
def createAnalysisGroups(readTable):
	analysisGroups = {}
	for metaDataRow in readTable: 
		groups = findDistinctGroups(metaDataRow)
		for group in groups: 
			if group in analysisGroups: 
				analysisGroups[group].append(metaDataRow)
			else: 
				analysisGroups[group] = [metaDataRow]
	return analysisGroups

def parseAnalysisGroups(analysisGroup, *fieldStrings):
	for groupDict in analysisGroup:
		simplifiedGroup = {k:groupDict[k] for k in fieldStrings}
	return simplifiedGroup


########################################################################
#Geoprocessing Toolset for analysis

def calculateConvexHull(inputPath, outputPath, groupFields):
	return arcpy.MinimumBoundingGeometry_management(
		in_features = inputPath, 
		out_feature_class = outputPath, 
		geometry_type = "CONVEX_HULL", 
		group_option = "LIST", 
		group_field = groupFields)

def bufferPolygons(inputPath, outputPath, bufferDistanceInMeters=30):
	return arcpy.Buffer_analysis(
		in_features = inputPath, 
		out_feature_class = outputPath, 
		buffer_distance_or_field = str(bufferDistanceInMeters) + " Meters")

def envelopeBuffer(readTable):
	for row in readTable:
		convexHull = calculateConvexHull(
			inputPath = makeFullPath(arcpy.env.workspace, row["Name"]),
			outputPath = makeFullPath(outGDB, row["Name"]+ "_Conv"),
			groupFields = groupingFieldsFromMetaDataForConvexHull(row))
		buff = bufferPolygons(
			inputPath = convexHull,
			outputPath = makeFullPath(outGDB, row["Name"]) + "_buff")		
		row["Buff"] = row["Name"] + "_buff"


##################################################################################
#Interpoloate & Extract

def interpolateSubRegion(metaDataRow, outputPath, tupleRegionSubRegion, readTable):
	outName = metaDataRow["Name"] + "_ebk"
	EBK = arcpy.EmpiricalBayesianKriging_ga(
		in_features = metaDataRow["Name"], 
		z_field = metaDataRow["ElevationField"], 
		out_ga_layer = '', 
		out_raster = makeFullPath(outputPath, outName))
	for row in readTable:
		if ["Name"] == metaDataRow["Name"]:
			row["EBK"] = outName
	return EBK

##########################################################################
#for unique group: 
	#interpolate
#for each file	
	#envelope (convex hull)
	#buffer envelope
	#write file name into buffer
	#intersect buffers by group (select base on group --> intersect)
	#merge intersects back together (maintain proper names)
	#create fishnet w/in polygons
		#assemble master table format
#loop over interpoliations, extract value by point
	#write into master table

### Does it make sense to use grouping field in convex hull?


############################################################################
#Run Program

SR = setSR(projection)

fileList = listInputFiles(inWorkspace)
for layer in fileList:
	addLayerToMap(layer)

readTable = csvToDictList(metadataTable)
validateMetaData(readTable)
testMatchingInputs(fileList, readTable)

analysisGroups = createAnalysisGroups(readTable)

envelopeBuffer(readTable)
bufferGroups = createAnalysisGroups(readTable)

for buff in bufferGroups[('Dennis, 1')]