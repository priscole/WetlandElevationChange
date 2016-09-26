#--------------------------------------------------------------------
# Authored by Priscole
# Software: ArcMap 10.3 with GeoStatistical Analyst, Python 2.7x
# Description: Tool takes elevation point files
# and exports a single csv file to compare elevation 
# changes over time. Interpolation method: Empirical Bayesian Kriging
#--------------------------------------------------------------------

import arcpy, csv, os 
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = True

metadataTable = arcpy.GetParameterAsText(0) #type file
inWorkspace = arcpy.GetParameterAsText(1) #type folder
projection = arcpy.GetParameterAsText(2) #type int (optional) - default Delaware SP (m)
endGDB = arcpy.GetParameterAsText(3) #type data element (optional)
tempGDB = arcpy.GetParameterAsText(4) #type data element (optional)

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
		arcpy.AddMessage("Setting workspace to: " + arcpy.env.workspace)
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

def removeLayerLike(partialString):
	for layer in arcpy.mapping.ListLayers(mxd):
		if partialString in layer.name:
			arcpy.mapping.RemoveLayer(df, layer)

def deleteFieldLike(partialString, layerName):
	for fld in arcpy.ListFields(layerName):
		if partialString in fld.name:
			arcpy.DeleteField_management(layerName, fld.name)

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
		arcpy.AddMessage("Setting spatial reference to: " + str(df.spatialReference.PCSCode) + "-" + df.spatialReference.PCSName)
	
	def testProjection(self, fc):
		if arcpy.Describe(fc).spatialReference.PCSCode == df.spatialReference.PCSCode:
			return True
		return False

def createCommonProjections(workspace):
	arcpy.AddMessage("Projecting input data to common spatial reference...")
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
	arcpy.AddMessage("Reading csv file...")
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

def envelopePoints(readTable):
	arcpy.AddMessage("Running convex hull...")
	for row in readTable:
		arcpy.MinimumBoundingGeometry_management(
			in_features = makeFullPath(arcpy.env.workspace, row["Name"]),
			out_feature_class = makeFullPath(tempGDB, row["Name"]+ "_Conv"),
			geometry_type = "CONVEX_HULL", 
			group_option = "LIST", 
			group_field = groupingFieldsFromMetaDataForConvexHull(row))
		row["Envelope"] = row["Name"] + "_Conv"

def nameIntersect(groupKey): 
	if len(groupKey) > 1:
		return groupKey[0] + str(groupKey[1]) + "_inter"
	return groupKey[0] + "_inter"

def intersectBufferGroups(groupKey):
	envelopes = []
	for f in analysisGroups[groupKey]:
		fGroup = GroupLayer(f)
		envelopes.append(fGroup.buffName)
		arcpy.SelectLayerByAttribute_management(
			in_layer_or_view = fGroup.buffName,
			selection_type = "NEW_SELECTION",
			where_clause = fGroup.selectionWhereClause(groupKey))
	arcpy.Intersect_analysis(
		in_features = envelopes, 
		out_feature_class = makeFullPath(tempGDB, nameIntersect(groupKey)), 
		join_attributes = "ALL")
	return nameIntersect(groupKey)

def makeStudyAreas(intersects):
	arcpy.AddMessage("Creating study areas...")
	arcpy.Merge_management(
		inputs = intersects, 
		output = makeFullPath(endGDB, "StudyAreas"))
	deleteFieldLike("FID", "StudyAreas")
	deleteFieldLike("_1", "StudyAreas")

##################################################################################
#Make Analysis Points

def createFishNet():
	arcpy.AddMessage("Creating fishnet in study areas...")
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
	arcpy.AddMessage("Making final analysis points...")
	APoints = arcpy.SpatialJoin_analysis(
		target_features = fishnet, 
		join_features = "StudyAreas", 
		out_feature_class = makeFullPath(endGDB, "AnalysisPoints"), 
		join_operation = "JOIN_ONE_TO_MANY", 
		join_type = "KEEP_COMMON")
	removeLayerFromMap('Fishnet_label')
	removeLayerFromMap('Fishnet')
	deleteFieldLike("_FID", "AnalysisPoints")
	deleteFieldLike("Join", "AnalysisPoints")
	return APoints

def addYearsToAnalysisPoints():
	arcpy.AddMessage("Inserting years into analysis points...")
	dates = set()
	newFields = []
	for groupKey in analysisGroups:
		for f in analysisGroups[groupKey]:
			dates.add(GroupLayer(f).date)
	for date in dates:
		arcpy.AddField_management(
			in_table = "AnalysisPoints",
			field_name = "YR_" + date,
			field_type = "DOUBLE")
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
		if "Envelope" in metaDataDict:
			self.buffName = metaDataDict["Envelope"]

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
		elif type(groupKey[1]) == int: 
			return "{0} = '{1}' AND {2} = {3}".format(
				self.saFieldName, 
				groupKey[0], 
				self.subSAFieldName, 
				groupKey[1])
		else:
			return "{0} = '{1}' AND {2} = '{3}'".format(
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
			return None

############################################################################
#Execute Functions

inWS = WorkSpace(inWorkspace)
inWS.setWorkSpace()
if arcpy.Exists(makeFullPath(inWS.directoryName(), "TempWetland.gdb")):
	tempGDB = makeFullPath(inWS.directoryName(), "TempWetland")
elif tempGDB == '':
	tempGDB = str(arcpy.CreateFileGDB_management(inWS.directoryName(), "TempWetland"))

if arcpy.Exists(makeFullPath(inWS.directoryName(), "WetlandElevation.gdb")):
	endGDB = makeFullPath(inWS.directoryName(), "WetlandElevation")
elif endGDB == '':
	endGDB = str(arcpy.CreateFileGDB_management(inWS.directoryName(), "WetlandElevation"))
tempWS = WorkSpace(tempGDB)
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

envelopePoints(readTable)
envelopeGroups = {group:subsetAnalysisGroups(analysisGroups[group],
	"Envelope", "SAFieldName", "SubSAFieldName") for group in analysisGroups}
arcpy.AddMessage("Intersecting envelopes...")
intersects = []
for group in envelopeGroups: 
	inter = intersectBufferGroups(group)
	intersects.append(inter)

studyAreas = makeStudyAreas(intersects)
analysisPoints = makeAnalysisPoints(createFishNet())
analysisYears = addYearsToAnalysisPoints()

tempWS.setWorkSpace()

arcpy.AddMessage("Running interpolations and extracting values into analysis points...")
for groupKey in analysisGroups:
	for fileDict in analysisGroups[groupKey]:
		f = GroupLayer(fileDict)
		f.createGroupLayer(groupKey)
		f.runInterpolationOnGroupLayer(groupKey)
		extracted = f.extractValuesFromInterpolations("AnalysisPoints", groupKey)
		if extracted != None:
			extractedVals = list(arcpy.da.SearchCursor(extracted, ['OBJECTID','RASTERVALU'], "RASTERVALU <> -9999" ))
			with arcpy.da.UpdateCursor("AnalysisPoints", ['OBJECTID', "YR_" + f.date]) as cur:
				for row in cur:
					for val in extractedVals:
						if val[0] == row[0]:
							row[1] = val[1]
							cur.updateRow(row)

finalOutputs = ['AnalysisPoints', 'StudyAreas']
for layer in arcpy.mapping.ListLayers(mxd):
	if layer.name not in finalOutputs:
		arcpy.mapping.RemoveLayer(df, layer)

arcpy.AddMessage("Final data stored in: " + endGDB + ". Temporary data stored in: " + tempGDB)