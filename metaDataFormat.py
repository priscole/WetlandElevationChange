def makeFullFCPath(Path, Name):
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

arcpy.env.workspace = params.inFolder

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


BufferList = []

for row in Table: 
	if row["subRegionField"] in isNULL:
		regionOnly = arcpy.MinimumBoundingGeometry_management(
			makeFullPath(arcpy.env.workspace, row["Name"]), 
			makeFullPath(outGDB, outName), 
			"CONVEX_HULL", "LIST", 
			["Name", "regionField", "subRegionField"])
		buff = arcpy.Buffer_analysis(
			makeFullPath(arcpy.env.workspace, row["Name"]),  
			makeFullPath(outGDB, outName), 
			30 meters, 
			"FULL")
		BufferList.append(buff)
	else:
		regionAndSub = arcpy.MinimumBoundingGeometry_management(
			makeFullPath(arcpy.env.workspace, row["Name"]),  
			makeFullPath(outGDB, outName), 
			"CONVEX_HULL", 
			"LIST", ["Name", "regionField", "subRegionField"])
		buff = arcpy.Buffer_analysis(
			makeFullPath(arcpy.env.workspace, row["Name"]), 
			makeFullPath(outGDB, outName), 
			30 meters, 
			"FULL")
		BufferList.append(buff)

#Sql statements only work with GDB, write case for shapefiles
queryDict = {} 
for buff in BufferList:
	buffTest = set(arcpy.da.SearchCursor(buff, ["Name", "StudyAreaFieldName", "SubStudyAreaFieldName"]))
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

#consume queryDict for selecting subset of points for interpolation
#also use when intersecting buffers for common areas
	#to create analysis points