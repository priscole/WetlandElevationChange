##########################################################################
#for unique group: 
	#interpolate
#for each file	
	#envelope (convex hull)
	#buffer envelope
	#write file name into buffer
	#intersect buffers by group (select base on group --> intersect)
	#create fishnet w/in polygons
		#assemble master table format
#loop over interpoliations, extract value by point
	#write into master table


class ParametersArcPy(object):
	def __init__(self):
		self.metaDataTable = arcpy.GetParameterAsText(0) #type file
		self.inFolder = arcpy.GetParameterAsText(1) #type folder
		self.outFolder = arcpy.GetParameterAsText(2) #type folder
		self.outCSV = arcpy.GetParameterAsText(3) #type string
		self.outGDB = arcpy.GetParameterAsText(4) #type data element - intermediate files to in_memory
			#reserved exclusively for final analysis points merged with final table
			#maybe final study area polygons too???
		self.projection = arcpy.GetParameterAsText(5) #type int (optional) - default Delaware SP (m)
		#self.barriers = arcpy.GetParameterAsText(6) #type file (optional)
			#reserve for future updates with alternative interpolation methods (spline w/ barriers)

params = ParametersArcPy()

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



#figure out how to reverse append
def groupingFieldsFromMetaData(metaDataRow):
	groupFields = [metaDataRow["StudyAreaFieldName"]]
	if metaDataRow["SubStudyAreaFieldName"] not in isNull:
		groupFields.append(metaDataRow["SubStudyAreaFieldName"])
	return groupFields
	
def findDistinctGroups(metaDataRow):
	"""finds all combinations of values in the groupingFields for this data

	Parameters
	----------
	metaDataRow : MetaData

	Returns
	-------
	set of tuples of studyarea and substudyarea for each unique combination
	in the same order as they appear in groupFields
	"""
	groupFields = groupingFieldsFromMetaData(metaDataRow)
	uniqueCombo = set(arcpy.da.SearchCursor(metaDataRow["Name"], groupFields))
	return uniqueCombo


def interpolateSubRegion(metaDataRow, outputPath, tupleRegionSubRegion):
	"""Runs elevation interpolator for a specified subregion of a file

	Parameters
	----------
	metaDataRow : metaData
	outputPath : Workspace GDB 
	tupleRegionSubRegion : from findDistinctGroups in metadata 

	Returns
	-------
	arcpy.arcobjects.arcobjects.Result

	"""
	return arcpy.EmpiricalBayesianKriging_ga(
		in_features = metaDataRow["Name"], 
		z_fieldd = metaDataRow["ElevationField"], 
		out_ga_layer = '', 
		out_raster = makeFullPath(outputPath, metaDataRow["Name"] + "_ebk")
		)

#arcpy.env.workspace = params.inFolder



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
		in_features = inputPath, 
		out_feature_class = outputPath, 
		geometry_type = "CONVEX_HULL", 
		group_option = "LIST", 
		group_field = groupFields
		)


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
#handle outGDB ('in_memory')
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







#takes the readTalbe and makes a new dictionary associating:
# FileName : SubStudyAreaField : List of SubStudyAreas
def associateSubStudyAreas(readTable): 
	testDict = {}
	for row in readTable:
		testDict[row["Name"]] = (row["SubStudyAreaFieldName"],[])
	return testDict

#populates list of subStudyAreas in dictionary
def populateSubStudyArea(testDict, bufferList):
	for item in testDict:
		if testDict[item][0] not in isNull:
			curList = list(arcpy.da.SearchCursor(item, testDict[item][0]))
			for thing in curList:
				testDict[item][1].append(thing[0])

def associateStudyAreaWithFiles(readTable):
	studyAreas = {}
	for row in readTable:
		regionCur = list(arcpy.da.SearchCursor(row["Name"], row["StudyAreaFieldName"]))
		for item in regionCur:
			if item[0] in studyAreas:
				studyAreas[item[0]].append(row["Name"])
			else: 
				studyAreas[item[0]] = [row["Name"]] 
	return studyAreas




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


#Sql statements only work with GDB, write case for shapefiles
# def constructQueryGroups(bufferList, readTable):
# 	queryDict = {} 
# 	for buff in bufferList:
# 		buffTest = set(arcpy.da.SearchCursor(buff, readTable["StudyAreaFieldName"], readTable["SubStudyAreaFieldName"]]))
# 		if len(buffTest) == 1:
# 			queryDict[buffTest[0]] = ""
# 		if len(buffTest) > 1:
# 			for b in buffTest:
# 				if b[0] in queryDict:
# 					queryDict[b[0]].append("""StudyAreaFieldName =""" + str(b[1]) + 
# 						"""AND SubStudyAreaFieldName =""" +str(b[2]))
# 				else:
# 					queryDict[b[0]] = ["""StudyAreaFieldName =""" + str(b[1]) + 
# 						"""AND SubStudyAreaFieldName =""" +str(b[2])]
# 	return queryDict

#consume queryDict for selecting subset of points for interpolation
#also use when intersecting buffers for common areas
	#to create analysis points

# def associateSubStudyAreas(readTable): 
# 	testDict = {}
# 	for row in readTable:
# 		if row["StudyAreaFieldName"] in testDict:
# 			testDict["StudyAreaFieldName"][testDict[row["Name"]]] = (row["SubStudyAreaFieldName"],[])

# 		else:
# 			testDict["StudyAreaFieldName"] = {testDict[row["Name"]]:(row["SubStudyAreaFieldName"],[])}
# 	return testDict

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

