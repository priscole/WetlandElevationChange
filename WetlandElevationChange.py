#-------------------------------------------------------------
# Authored by Priscole
# Software: ArcMap 10.3 with GeoStatistical Analyst extension
# Description: Tool takes elevation point files
# and exports a single csv file to compare elevation 
# changes over time. Interpolation method default is EBK, 
# with optional Spline with barriers if provided.
#-------------------------------------------------------------

import arcpy, csv, os 
arcpy.env.overwriteOutput = True

# metadataTable = arcpy.GetParameterAsText(0) #type file
# inWorkspace = arcpy.GetParameterAsText(1) #type folder
# projection = arcpy.GetParameterAsText(2) #type int (optional) - default Delaware SP (m)

metadataTable = r'C:\Users\Priscole\Documents\code\GISPython\WetlandElevationChangeTable_demo.csv'
tempGDB = r'C:\Users\Priscole\Documents\ArcGIS\Wetlands\TempWetland.gdb'
inWorkspace = r'C:\Users\Priscole\Documents\ArcGIS\Wetlands\WetlandsAppTest.gdb'
endGDB = r'C:\Users\Priscole\Documents\ArcGIS\Wetlands\WetlandElevation.gdb'
projection = ""


mxd = arcpy.mapping.MapDocument("current")
df = arcpy.mapping.ListDataFrames(mxd)[0]

isNull = ["null", "NULL", "NA", "na", "N/A", "n/a", "", " "]
requiredFields = ["Name", "Date", "ElevationField", "SAFieldName"]
optionalField = "SubSAFieldName"


#############################################################################
# Handle workspaces & files

class WorkSpace(object):
	def __init__(self, path):
		self.path = path

	def setWorkSpace(self):
		arcpy.env.workspace = self.path
		return arcpy.env.workspace

	def listFiles(self):
		if arcpy.Describe(arcpy.env.workspace).workspaceType in ['LocalDatabase', 'RemoteDatabase']:
			return arcpy.ListFeatureClasses(feature_type="point")
		return arcpy.ListFiles()

	def directoryName(self):
		return os.path.dirname(self.path)

def makeFullPath(Path, Name):
	return Path + "\\" + Name

def addLayerToMap(layer):
	addLayer = arcpy.mapping.Layer(layer)
	arcpy.mapping.AddLayer(df, addLayer)

def removeLayerFromMap(layer):
	removeLayer = arcpy.mapping.Layer(layer)
	arcpy.mapping.RemoveLayer(df, removeLayer)

def clearSelectedFeatures(layerName):
	arcpy.SelectLayerByAttribute_management(layerName, "CLEAR_SELECTION")

#############################################################################
#Handle Projections

class SpatialReference(object):
	def __init__(self, projection):
		self.projection = projection

	def setEnvSpatialReference(self):
		if self.projection == "":
			arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)
		else: 
			arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(self.projection)

	def setMapProjection(self):
		df.spatialReference = arcpy.env.outputCoordinateSystem.PCSCode
	
	def testProjection(self, fc):
		if arcpy.Describe(fc).spatialReference.PCSCode == df.spatialReference.PCSCode:
			return True
		return False

def createCommonProjections(workspace):
	for fc in workspace.listFiles():
		if SR.testProjection(fc) == True:
			arcpy.FeatureClassToFeatureClass_conversion(fc, str(endGDB), fc)
		else:
			arcpy.Project_management(fc, 
				makeFullPath(str(endGDB), fc), 
				df.spatialReference)

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
	groupFields = [metaDataRow["SAFieldName"]]
	if metaDataRow["SubSAFieldName"] not in isNull:
		groupFields.append(metaDataRow["SubSAFieldName"])
	return groupFields

def groupingFieldsFromMetaDataForConvexHull(metaDataRow):
	groupFields = []
	if metaDataRow["SubSAFieldName"] not in isNull:
		groupFields.append(metaDataRow["SubSAFieldName"])
	groupFields.append(metaDataRow["SAFieldName"])
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

def subsetAnalysisGroups(analysisGroupList, *fieldStrings):
	simplifiedGroup = []
	for groupDict in analysisGroupList:
		simplifiedGroup.append({k:groupDict[k] for k in fieldStrings})
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
	convexHulls = []
	for row in readTable:
		convexHull = calculateConvexHull(
			inputPath = makeFullPath(arcpy.env.workspace, row["Name"]),
			outputPath = makeFullPath(tempGDB, row["Name"]+ "_Conv"),
			groupFields = groupingFieldsFromMetaDataForConvexHull(row))
		buff = bufferPolygons(
			inputPath = convexHull,
			outputPath = makeFullPath(tempGDB, row["Name"]) + "_buff")		
		row["Buff"] = row["Name"] + "_buff"
		convexHulls.append(row["Name"] + "_Conv")
	return convexHulls

#feed ONE groupKey ("Dennis", 1) from organizedBuffs
#should SubSAField be a string or int???? -Makes HUGE diff in SQL
#Handle case len(groupKey) = 1, like ('Maurice',)
def nameIntersect(groupKey): 
	if len(groupKey) > 1:
		return groupKey[0] + str(groupKey[1]) + "_inter"
	return groupKey[0] + "_inter"

def intersectBufferGroups(groupKey):
	buffers = []
	for f in analysisGroups[groupKey]:
		fGroup = GroupLayer(f)
		buffers.append(fGroup.buffName)
		arcpy.SelectLayerByAttribute_management(
			in_layer_or_view = fGroup.buffName,
			selection_type = "NEW_SELECTION",
			where_clause = fGroup.selectionWhereClause(groupKey))
	arcpy.Intersect_analysis(
		in_features = buffers, 
		out_feature_class = makeFullPath(tempGDB, nameIntersect(groupKey)), 
		join_attributes = "ALL")
	return nameIntersect(groupKey)

def makeStudyAreas(intersects):
	arcpy.Merge_management(
		inputs = intersects, 
		output = makeFullPath(tempGDB, "StudyAreas"))

##################################################################################
#Make Analysis Points

def createFishNet():
	desc = arcpy.Describe("StudyAreas")
	arcpy.CreateFishnet_management(
		out_feature_class = makeFullPath(tempGDB, "Fishnet"), 
		origin_coord = str(desc.extent.lowerLeft), 
		y_axis_coord = str(desc.extent.XMin) + " " + str(desc.extent.YMax + 10),
		cell_width = "35",
		cell_height = "35",
		number_rows = "0",
		number_columns = "0",
		corner_coord = str(desc.extent.upperRight),
		labels = "LABELS",
		template = "#",
		geometry_type = "POLYLINE")
	return makeFullPath(tempGDB, "Fishnet_label")

def makeAnalysisPoints(fishnet):
	APoints = arcpy.SpatialJoin_analysis(
		target_features = fishnet, 
		join_features = "StudyAreas", 
		out_feature_class = makeFullPath(tempGDB, "AnalysisPoints"), 
		join_operation = "JOIN_ONE_TO_MANY", 
		join_type = "KEEP_COMMON")
	removeLayerFromMap('Fishnet_label')
	removeLayerFromMap('Fishnet')
	return APoints

def addYearsToAnalysisPoints():
	dates = set()
	newFields = []
	for groupKey in analysisGroups:
		for f in analysisGroups[groupKey]:
			dates.add(GroupLayer(f).date)
	for date in dates:
		arcpy.AddField_management(
			in_table = "AnalysisPoints",
			field_name = "YR_" + date,
			field_type = "TEXT")
		newFields.append("YR_" + date)
	return newFields
	


##################################################################################
#Interpoloate & Extract

class GroupLayer(object):
	def __init__(self, metaDataDict):
		self.metaDataDict = metaDataDict
		self.name = metaDataDict["Name"]
		self.saFieldName = metaDataDict["SAFieldName"]
		self.subSAFieldName = metaDataDict["SubSAFieldName"]
		if "Date" in metaDataDict:
			self.date = metaDataDict["Date"]
		if "ElevationField" in metaDataDict:
			self.elevationField = metaDataDict["ElevationField"]
		if "Buff" in metaDataDict:
			self.buffName = metaDataDict["Buff"]

	def nameForGroup(self, groupKey):
		if len(groupKey) > 1:
			return groupKey[0] + str(groupKey[1]) + self.name
		return groupKey[0] + self.name

	def nameOfLayerOut(self, groupKey):
		return self.nameForGroup(groupKey)

	def nameOfEBKOut(self, groupKey):
		return self.nameForGroup(groupKey) + "_GA"

	def nameOFExtractValues(self, groupKey):
		return self.nameForGroup(groupKey) + "_val"

	def selectionWhereClause(self, groupKey):
		if self.subSAFieldName == '':
			return "{0} = '{1}'".format(
			self.saFieldName, 
			groupKey[0])		
		return "{0} = '{1}' AND {2} = {3}".format(
			self.saFieldName, 
			groupKey[0], 
			self.subSAFieldName, 
			groupKey[1])

	def createGroupLayer(self, groupKey):
		arcpy.MakeFeatureLayer_management(
			in_features = self.name, 
			out_layer = self.nameOfLayerOut(groupKey),  
			where_clause = self.selectionWhereClause(groupKey))

	def runInterpolationOnGroupLayer(self, groupKey):
		try:
			EBK = arcpy.EmpiricalBayesianKriging_ga(
				in_features = self.nameOfLayerOut(groupKey), 
				z_field = self.elevationField, 
				out_ga_layer = "", 
				out_raster = makeFullPath(tempGDB, self.nameOfEBKOut(groupKey)),
				cell_size="", 
				transformation_type="NONE", 
				max_local_points="100", 
				overlap_factor="1", 
				number_semivariograms="100", 
				search_neighborhood="", 
				output_type="PREDICTION", 
				quantile_value="0.5", 
				threshold_type="EXCEED", 
				probability_threshold="", 
				semivariogram_model_type="POWER")
		except Exception:
			pass

	def extractValuesFromInterpolations(self, analysisPoints, groupKey):
		try:
			extracted = arcpy.sa.ExtractValuesToPoints(
				in_point_features = analysisPoints,
				in_raster = self.nameOfEBKOut(groupKey),
				out_point_features = self.nameOFExtractValues(groupKey))
			return extracted
		except Exception:
			pass

############################################################################
#Execute Functions

inWS = WorkSpace(inWorkspace)
inWS.setWorkSpace()
tempGDB = str(arcpy.CreateFileGDB_management(inWS.directoryName(), "TempWetland"))
tempWS = WorkSpace(tempGDB)
endGDB = str(arcpy.CreateFileGDB_management(inWS.directoryName(), "WetlandElevation"))
endWS = WorkSpace(endGDB)

SR = SpatialReference(projection)
SR.setEnvSpatialReference()
SR.setMapProjection()
createCommonProjections(inWS) #copy or reproject points into endGDB
endWS.setWorkSpace() #change workspace to where reprojected points are

readTable = csvToDictList(metadataTable)
validateMetaData(readTable)
testMatchingInputs(endWS.listFiles(), readTable)

analysisGroups = createAnalysisGroups(readTable)

listConvexHulls = envelopeBuffer(readTable)
for convexHull in listConvexHulls:
	removeLayerFromMap(convexHull)

buffGroups = {group:subsetAnalysisGroups(analysisGroups[group],
	"Buff", "SAFieldName", "SubSAFieldName") for group in analysisGroups}

intersects = []
for group in buffGroups: 
	inter = intersectBufferGroups(group)
	intersects.append(inter)

# use field mappings in merge tool making study areas
studyAreas = makeStudyAreas(intersects)
analysisPoints = makeAnalysisPoints(createFishNet())
analysisYears = addYearsToAnalysisPoints()

#clean up map
for i in intersects:
	removeLayerFromMap(i)
# figure out how to remove buffers from map

tempWS.setWorkSpace()

for groupKey in analysisGroups:
	for fileDict in analysisGroups[groupKey]:
		f = GroupLayer(fileDict)
		f.createGroupLayer(groupKey)
		f.runInterpolationOnGroupLayer(groupKey)
		extracted = f.extractValuesFromInterpolations("AnalysisPoints", groupKey)
		extractedVals = list(arcpy.da.SearchCursor(extracted, ['OBJECTID','RASTERVALU'], "RASTERVALU <> -9999" ))
		with arcpy.da.UpdateCursor("AnalysisPoints", analysisYears) as cur:
			for row in cur:
				for val in extractedVals:
					if val[0] in row[analysisYears.index("YR_" + f.date)]:
						row[analysisYears.index("YR_" + f.date)] = val[1]
						cur.updateRow(row)


