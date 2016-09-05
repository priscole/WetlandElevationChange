import os

def makeFullPath(Path, Name):
	return Path + "\\" + Name


dictReaderResult = [
	{
	"Name" : "DennisWCT",
	"Date" : "2011" ,
	"ElevationField" : 'something',
	"StudyAreaFieldName" : "Watershed",
	"SubStudyAreaFieldName" : ""
	}
]


requiredFields = ["Name", "Date", "ElevationField", "StudyAreaFieldName"]
optionalField = "SubStudyAreaFieldName"
isNull = ["null", "NULL", "NA", "na", "N/A", "n/a", "", " "]

def validateSingleRecord(r):
	for field in requiredFields:
		if r[field] in isNull:
			return False
	return True

def validateMetaData(readTable):	
	for row in readTable:		
		if vaildateSingleRecord(row) == False: 
			arcpy.AddMessage("Invalid Table Input - " + row["Name"] + " contains NULL values in required field")
			return False
	return True

def groupingFieldsFromMetaData(metaData):
	groupFields = [metaData["StudyAreaFieldName"]]
	if metaData["SubStudyAreaFieldName"] not in isNull:
		groupFields.append(metaData["SubStudyAreaFieldName"])
	return groupFields
	
#arcpy.env.workspace = params.inFolder

def listInputFiles(inFolder):
	arcpy.env.workspace = inFolder
	desc = arcpy.Describe(arcpy.env.workspace)
	if desc.workspaceType in ['LocalDatabase', 'RemoteDatabase']:
		fileSet = arcpy.ListFeatureClasses(feature_type='point')
	elif desc.workspaceType in ['FileSystem']:
		fileSet = set(arcpy.ListFiles())
	else: 
		arcpy.AddMessage("""There was a problem with the input workspace. 
			Valid workspaces include geodatabases, or a folder (directory) 
			containing  only the point shapefiles intended for analysis.""")
		fileSet = None
	return fileSet	

def testMatchingInputs(fileSet, metadataTable):
	metadataFiles = {row["Name"] for row in metadataTable}
	if metadataFiles.issubset(fileSet) == True:
		arcpy.AddMessage("Inputs are valid.")
		return True
	elif fileSet == None:
		return False
	elif metadataFiles.issubset(fileSet) == False:
		setMissing = metadataFiles.difference(fileSet)
		missingFiles = ", ".join(setMissing)
		arcpy.AddMessage("""Error - Metadata Table contains filenames that do not match files in the workspace. Unmatched files include: """ + missingFiles + """. Check for spelling errors in the metadata table or for missing files in the workspace.""")
		return False




def calculateConvexHull(inputPath, outputPath, groupFields):
	"""Calculate a tight envelope around points for each group

	Parameters
	----------
	inputPath : String
		full path to Point file (either shapeFile or featureClass)
	outputPath : String
		desired full path to the result as a featureClass
	groupFields : list of strings
		names of fields that define groups

	Returns
	-------
	arcpy.arcobjects.arcobjects.Result

	The tool creates a Polygon feature class in the desired outputPath
	location. This feature class 
	contains one record for every distinct group in the inputPath, and
	includes a column for every grouping field.
	"""
	return arcpy.MinimumBoundingGeometry_management(
		inputPath, outputPath, "CONVEX_HULL", "LIST", groupFields)


def bufferPolygons(inputPath, outputPath, bufferDistanceInMeters=30):
	"""Extends (dilates) polygons

	Parameters
	----------
	inputPath : String
		full path to a Polygon feature class
	outputPath : String
		desired full path to the result as a featureClass
	bufferDistanceInMeters : number
	    distance in meters to dilate the polygon

	Returns
	-------
	arcpy.arcobjects.arcobjects.Result

	The tool creates a Polygon feature class in the desired outputPath
	location, in which every polygon from the input has been buffered
	by the specified amount
	"""
	return arcpy.Buffer_analysis(
		in_features = inputPath, 
		out_feature_class = outputPath, 
		buffer_distance_or_field = str(bufferDistanceInMeters) + " Meters"
		)


#####################################################################
#handle outGDB ('in_memory'), should bufferList be full paths?
def envelopeAndBuffer(readTable):	
	bufferList = []	
	for row in readTable:
		convexHull = calculateConvexHull(
			inputPath = makeFullPath(arcpy.env.workspace, row["Name"]),
			outputPath = makeFullPath(outGDB, row["Name"]+"Convex"),
			groupFields = groupingFieldsFromMetaData(row)
			)
		buff = bufferPolygons(
			inputPath = convexHull,
			outputPath = makeFullPath(outGDB, row["Name"])
			)
		bufferList.append(os.path.basename(buff[0]))
	return bufferList

#Sql statements only work with GDB, write case for shapefiles
def constructQueryGroups(bufferList, readTable):
	queryDict = {} 
	for buff in bufferList:
		buffTest = set(arcpy.da.SearchCursor(buff, readTable["StudyAreaFieldName"], readTable["SubStudyAreaFieldName"]]))
		if len(buffTest) == 1:
			queryDict[buffTest[0]] = ""
		if len(buffTest) > 1:
			for b in buffTest:
				if b[0] in queryDict:
					queryDict[b[0]].append("""StudyAreaFieldName =""" + str(b[1]) + 
						"""AND SubStudyAreaFieldName =""" +str(b[2]))
				else:
					queryDict[b[0]] = ["""StudyAreaFieldName =""" + str(b[1]) + 
						"""AND SubStudyAreaFieldName =""" +str(b[2])]
	return queryDict

#consume queryDict for selecting subset of points for interpolation
#also use when intersecting buffers for common areas
	#to create analysis points

##################################################################################
# def assignGroup(dictReaderResult): 
# 	for x in dictReaderResult:
# 		if x[optionalField] in isNull:
# 			if x["StudyAreaFieldName"] in group:
# 				group[x["StudyAreaFieldName"]].append(x["Name"])
# 			else:
# 				group[x["StudyAreaFieldName"]] = x["Name"]
# 		else:
# 			if x["StudyAreaFieldName"] + x[optionalField] in group:
# 				group[x["StudyAreaFieldName"]] = x[optionalField].append(x["Name"])
# 			else:
# 				group[x["StudyAreaFieldName"]] = x[optionalField] = x["Name"]



"""
1. validate valid metadata 
2. assign files or pieces of files to groups


3. create feature layers for sub-groups
4. feature envelopes to polygon
5. run groups through intersect tool (polygon output)
6. buffer common polygon 30m
7. fishnet to create sample points  
8. interpolate each layer or feature layer

"""