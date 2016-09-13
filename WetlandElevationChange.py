#-------------------------------------------------------------
# Authored by Priscole
# 5/1/16
# Software: ArcMap 10.3 with GeoStatistical Analyst extension
# Description: Tool takes many elevation point files
# and exports a single csv file to compare elevation 
# changes over time. Interpolation method default is EBK, 
# with optional Spline with barriers if provided.
#-------------------------------------------------------------

import arcpy, csv

# metadataTable = arcpy.GetParameterAsText(0) #type file
# inWorkspace = arcpy.GetParameterAsText(1) #type folder
# outFolder = arcpy.GetParameterAsText(2) #type folder
# outCSV = arcpy.GetParameterAsText(3) #type string
# outGDB = arcpy.GetParameterAsText(4) #type data element - optional or in_memory?
# projection = arcpy.GetParameterAsText(5) #type int (optional) - default Delaware SP (m)


metadataTable = r'C:\Users\Priscole\Documents\code\GISPython\WetlandElevationChangeTable_demo.csv'
outGDB = r'C:\Users\Priscole\Documents\ArcGIS\Wetlands\WetlandsAppTestTemp.gdb'
inWorkspace = r'C:\Users\Priscole\Documents\ArcGIS\Wetlands\WetlandsAppTest.gdb'


arcpy.env.workspace = inWorkspace
mxd = arcpy.mapping.MapDocument("current")
df = arcpy.mapping.ListDataFrames(mxd)[0]

isNull = ["null", "NULL", "NA", "na", "N/A", "n/a", "", " "]
requiredFields = ["Name", "Date", "ElevationField", "SAFieldName"]
optionalField = "SubSAFieldName"

def makeFullPath(Path, Name):
	return Path + "\\" + Name

#############################################################################
#Handle Projections

def setSR(projection):
	if projection == "":
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)
	else: 
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(projection)

def testProjection(pointFile):
	pass

def reprojectFile(pointFile):
	pass

def setMapProjection():
	pass
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
	addLayer = arcpy.mapping.Layer(layer)
	arcpy.mapping.AddLayer(df, addLayer)

def removeLayerFromMap(layer):
	removeLayer = arcpy.mapping.Layer(layer)
	arcpy.mapping.RemoveLayer(df, removeLayer)

def clearSelectedFeatures(layerName):
	arcpy.SelectLayerByAttribute_management(layerName, "CLEAR_SELECTION")

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
			outputPath = makeFullPath(outGDB, row["Name"]+ "_Conv"),
			groupFields = groupingFieldsFromMetaDataForConvexHull(row))
		buff = bufferPolygons(
			inputPath = convexHull,
			outputPath = makeFullPath(outGDB, row["Name"]) + "_buff")		
		row["Buff"] = row["Name"] + "_buff"
		convexHulls.append(convexHull)
	return convexHulls

#feed ONE groupKey ("Dennis", 1) from organizedBuffs
#should SubSAField be a string or int???? -Makes HUGE diff in SQL
#Handle case len(groupKey) = 1, like ('Maurice',)
def intersectBufferGroups(groupKey):
	groupInfo = []
	for metadataDicts in analysisGroups[groupKey]:
		groupInfo.append(
			(metadataDicts["Buff"], 
				metadataDicts["SAFieldName"], 
				metadataDicts["SubSAFieldName"]))
	Buffers = []
	for f in groupInfo:
		arcpy.SelectLayerByAttribute_management(
			in_layer_or_view = f[0], 
			selection_type = "NEW_SELECTION",  
			where_clause = "{0} = '{1}' AND {2} = {3}".format(f[1], groupKey[0], f[2], groupKey[1]))
		Buffers.append(f[0])
	arcpy.Intersect_analysis(
		in_features = Buffers, 
		out_feature_class = makeFullPath(outGDB, groupKey[0] + str(groupKey[1]) + "_inter"), 
		join_attributes = "ALL")
	return groupKey[0] + str(groupKey[1]) + "_inter"

def makeStudyAreas(intersects):
	arcpy.Merge_management(
		inputs = intersects, 
		output = makeFullPath(outGDB, "StudyAreas"))

##################################################################################
#Make Analysis Points

def createFishNet():
	desc = arcpy.Describe("StudyAreas")
	arcpy.CreateFishnet_management(
		out_feature_class = makeFullPath(outGDB, "Fishnet"), 
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
	return makeFullPath(outGDB, "Fishnet_label")

def makeAnalysisPoints(fishnet):
	APoints = arcpy.SpatialJoin_analysis(
		target_features = fishnet, 
		join_features = "StudyAreas", 
		out_feature_class = makeFullPath(outGDB, "AnalysisPoints"), 
		join_operation = "JOIN_ONE_TO_MANY", 
		join_type = "KEEP_COMMON")
	return APoints

##################################################################################
#Interpoloate & Extract

class DataSet(object):
	def __init__(self, metaDataDict):
		self.metaDataDict = metaDataDict
		self.name = metaDataDict["Name"]
		self.date = metaDataDict["Date"]
		self.elevationField = metaDataDict["ElevationField"]
		self.saFieldName = metaDataDict["SAFieldName"]
		self.subSAFieldName = metaDataDict["SubSAFieldName"]

	def nameForGroup(self, groupKey):
		return groupKey[0] + str(groupKey[1]) + self.name

	def nameOfEBKOut(self, groupKey):
		return self.nameForGroup(groupKey) + "_GA"

	def nameOfLayerOut(self, groupKey):
		return self.nameForGroup(groupKey)

class InterpolationTask(object):
	def __init__(self, groupKey, dataset):
		self.groupKey = groupKey
		self.dataset = dataset
		self.saFieldValue = groupKey[0]
		self.subSAFieldValue = groupKey[1]

	def selectionWhereClause(self):
		return "{0} = '{1}' AND {2} = {3}".format(
			self.dataset.saFieldName, 
			self.saFieldValue, 
			self.dataset.subSAFieldName, 
			self.subSAFieldValue)

	def createGroupLayer(self):
		arcpy.MakeFeatureLayer_management(
			in_features = self.dataset.name, 
			out_layer = self.dataset.nameOfLayerOut(self.groupKey),  
			where_clause = self.selectionWhereClause())

	def runInterpolationOnGroupLayer(self):
		EBK = arcpy.EmpiricalBayesianKriging_ga(
			in_features = self.dataset.nameOfLayerOut(self.groupKey), 
			z_field = self.dataset.elevationField, 
			out_ga_layer = "", 
			out_raster = makeFullPath(outGDB, self.dataset.nameOfEBKOut(self.groupKey)),
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

	def run(self):
		self.createGroupLayer()
		self.runInterpolationOnGroupLayer()

def interpolateByGroup(groupKey):
	GAs = []
	for f in analysisGroups[groupKey]:
		arcpy.SelectLayerByAttribute_management(
			in_layer_or_view = f["Name"], 
			selection_type = "NEW_SELECTION",  
			where_clause = "{0} = '{1}' AND {2} = {3}".format(f["SAFieldName"], 
				groupKey[0], f["SubSAFieldName"], groupKey[1]))
			
		EBK = arcpy.EmpiricalBayesianKriging_ga(
			in_features = f["Name"], 
			z_field = f["ElevationField"], 
			out_ga_layer = '', 
			out_raster = makeFullPath(outGDB, f["Name"] + str(groupKey[1]) + "_GA"))
		GAs.append(f["Name"] + str(groupKey[1]) + "_GA")
	return GAs

def extractValues():
	pass 

############################################################################
#Execute Functions


#SR = setSR(projection)

fileList = listInputFiles(inWorkspace)
for layer in fileList:
	addLayerToMap(layer)

readTable = csvToDictList(metadataTable)
validateMetaData(readTable)
testMatchingInputs(fileList, readTable)

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

studyAreas = makeStudyAreas(intersects)[]
analysisPoints = makeAnalysisPoints(createFishNet())


interpolationGroups = {group:subsetAnalysisGroups(analysisGroups[group], 
	"Name", "SAFieldName", "SubSAFieldName") for group in analysisGroups}
interpolations = []
for groupKey in interpolationGroups: 
	interps = InterpolationTask(groupKey, DataSet(analysisGroups[gk][0]))
	intersects.append(interps)

gk = ('Dennis', 1)
it = 
it.run()
