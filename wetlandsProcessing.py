# Authored by Priscole
# 10/30/15
# Software: ArcMap 10.3 with GeoStatistical Analyst extension

# NOTE: If this script is run outside of Priscole's Computer,
# workspaces need to be reset to reflect the file strucutre
# and intended destinations

import csv
import arcpy
startWS = "C:\Users\Priscole\Documents\ArcGIS\Wetlands\Wetlands.gdb"
endWS = "C:\Users\Priscole\Documents\ArcGIS\Wetlands\ElevCap.gdb"
TempWS = "C:\Users\Priscole\Documents\ArcGIS\Wetlands\Temp.gdb"
# All files should be projected to Delaware State Plane (meters)
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)

def projectFC():
	for FC in listFC():
		arcpy.Project_management(makeFullFCPath(TempWS, FC), 
			makeFullFCPath(Temp2WS, FC), arcpy.SpatialReference(103017))

# Full path outputs are required for many arc tools
# This function aids in path construction
def makeFullFCPath(WS, FCName):
	return WS + "\\" + FCName

# Workspace assignments get tricky because there are lots of 
# intermediate outputs being pushed to a Temp GDB
def setWorkspace(WS):
	print "Setting workspace to " + WS
	arcpy.env.workspace = WS	

# def inWorkspace(WS, command, **args):
# 	currentWS = arcpy.env.workspace
# 	setWorkspace(WS)
# 	try:
# 		command(**args)
# 	finally:
# 		setWorkspace(currentWS)

# crete list of feature classes (FC) in GDB, when nested in datasets
def listFcInDs():
	result = list()
	for DS in arcpy.ListDatasets():
		for FC in arcpy.ListFeatureClasses("", "", DS):
			result.append(FC)
	return result

# create list of FCs in generic GDBs
def listFC(prefix="",suffix=""):
	result = list() 
	for FC in arcpy.ListFeatureClasses():
		if FC.startswith(prefix) and FC.endswith(suffix):
			result.append(FC)
	return result

# for each FC, check for a field called "SET_num" (WS = startWS)
# if detected, select by SETs and export to new GDB
# Otherwise, export FC as-is
def sepBySetNewGDB():
	for FC in listFcInDs():
		desCol = arcpy.Describe(FC).fields
		columnNames = [col.name for col in desCol]
		hasSetNum = "SET_num" in columnNames
		if hasSetNum:
			for column in desCol:
				if column.name == "SET_num":
					for num in [1,2,3]:
						out_name = FC[:2] + str(num) + FC[2:]
						arcpy.FeatureClassToFeatureClass_conversion(FC, endWS, 
							out_name, "SET_num = " + str(num))
						print("A new FC was created in ElevCap.gdb for" + FC + "SET " + str(num))

		else:
			arcpy.FeatureClassToFeatureClass_conversion(FC, endWS, FC)
			print("Copied FC: " + FC + "to ElevCap.gdb")

# creates standand elevation field for EBK application (WS = endWS)
# this works, but it unnessariy iterates over every column
def ElevationField():
	for FC in listFC(): 
		arcpy.AddField_management(FC, "EBK_Elev", "DOUBLE")
		desCol = arcpy.Describe(FC).fields
		for column in desCol:
			if "OrthoHeigh" in column.name:
				arcpy.CalculateField_management(FC, "EBK_Elev", "!OrthoHeigh!", "PYTHON_9.3")
			if "Ortho_Ht" in column.name:
				arcpy.CalculateField_management(FC, "EBK_Elev", "!Ortho_Ht!", "PYTHON_9.3")
			if "Elevation" in column.name:
				arcpy.CalculateField_management(FC, "EBK_Elev", "!Elevation!", "PYTHON_9.3")
			# convert feet to meters in DEM's
			if "Field3" in column.name:
				arcpy.CalculateField_management(FC, "EBK_Elev", "!Field3!/3.2808", "PYTHON_9.3")

# create 30m buffers for each FC, store in Temp.gdb (WS = endWS)
def Buff30m():
	for FC in listFC(): 
		out_FC = makeFullFCPath(TempWS, FC + "_30m")
		arcpy.Buffer_analysis(FC, out_FC, 30, '', '', "ALL")

# group buffers by study area (SA), in a dictionary (WS = TempWS)
def buffersByStudyArea():
	result = dict()
	for i in listFC(suffix="30m"):
		if i[:3] in result:
			result[i[:3]].append(i)
		else: 
			result[i[:3]] = list()
			result[i[:3]].append(i)
	return result

# use merge tool for buffers in each SA (WS = TempWS)
def mergeBuffsBySA(): 
	for (studyArea, buffers) in buffersByStudyArea().items():
		mgBuff = makeFullFCPath(TempWS, studyArea + "_mrg")
		arcpy.Merge_management(buffers, mgBuff)
		arcpy.AddField_management(mgBuff, "Dissolve", "SHORT")
		arcpy.CalculateField_management(mgBuff, "Dissolve", 1)
		dssBuff = makeFullFCPath(TempWS, studyArea + "_diss")
		arcpy.Dissolve_management(mgBuff, dssBuff, "Dissolve")
	for FC in listFC(suffix="mrg"):
		in_feat = makeFullFCPath(TempWS, FC)
		arcpy.Delete_management(in_feat)
		
# crete envelope for merged buffers in each SA (WS = TempWS)
def envSABuffs():	
	for mergedBuffers in listFC(suffix="30mdiss"):
		out_FC = makeFullFCPath(TempWS, mergedBuffers + "Env")
		arcpy.FeatureEnvelopeToPolygon_management(mergedBuffers, out_FC)
		arcpy.AddField_management(out_FC, "StudyArea", "TEXT")
		text = mergedBuffers[:3]
		arcpy.CalculateField_management(out_FC, "StudyArea", "'" + text + "'", "PYTHON")

# merge envelopes for complete study areas, area calculated in Hectares (WS = TempWS)
def mergeEnv():
	listOfEnvs = list()
	for envelope in listFC(suffix="Env"):
		listOfEnvs.append(envelope)
	output = makeFullFCPath(TempWS, "StudyAreas")
	arcpy.Merge_management(listOfEnvs, output)
	arcpy.AddField_management(output, "Area_Ha", "DOUBLE")
	arcpy.CalculateField_management(output, "Area_Ha", "!shape.area@acres!", "PYTHON_9.3")
	for FC in listFC(suffix="dissEnv"):
		in_feat = makeFullFCPath(TempWS, FC)
		arcpy.Delete_management(in_feat)

# Make 150 random analysis points for each study area (WS = TempWS)
# We decided to make uniform points instead of random, so fxn commented-out
# def analysisPoints():
# 	for envelope in listFC(suffix="Env"):
# 		out_name = envelope + "150pt"
# 		arcpy.CreateRandomPoints_management(TempWS, out_name, envelope, '', 150)
# 	sPoints = list()
# 	output = makeFullFCPath(endWS, "AnalysisPoints")
# 	for FC in listFC(suffix="150pt"): sPoints.append(FC)
# 	arcpy.Merge_management(sPoints, output)

# Make uniform 35m spaced analysis points for each study area (WS = TempWS)
def analysisPoints():
	arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)
	out_FC = makeFullFCPath(TempWS, "FishNet")
	desc = arcpy.Describe(makeFullFCPath(TempWS, "StudyAreas"))
	APoints = makeFullFCPath(TempWS, "AnalysisPts")
	arcpy.CreateFishnet_management(out_FC, str(desc.extent.lowerLeft), 
		str(desc.extent.XMin) + " " + str(desc.extent.YMax + 10),
		"35","35","0","0",str(desc.extent.upperRight),"LABELS","#","POLYLINE")
	arcpy.SpatialJoin_analysis(makeFullFCPath(TempWS, "FishNet_label"), 
		makeFullFCPath(TempWS, "StudyAreas"), APoints, "JOIN_ONE_TO_MANY", "KEEP_COMMON")
	arcpy.AddField_management(APoints, "Points", "TEXT")
	arcpy.CalculateField_management(APoints, "Points", "!StudyArea! + '_' + str(!OBJECTID!)", "PYTHON_9.3")
	arcpy.DeleteField_management(APoints, ["Join_Count", "TARGET_FID", "JOIN_FID", "Dissolve", "ORIG_FID", "Area_Ha"] )
	arcpy.Delete_management(makeFullFCPath(TempWS, "FishNet_label"))
	arcpy.Delete_management(makeFullFCPath(TempWS, "FishNet"))

# For each FC, run EBK and output rasters (WS = endWS)
# Note: if duplicate points occur in the input dataset, this fxn will break.
# The geo-stat wizard, it will prompt for options on conflict handling. Choose mean. 
def applyEBK():
	for FC in listFC(): 
		in_pts = makeFullFCPath(endWS, FC)
		out_raster = makeFullFCPath(endWS, FC + "_EBK")
		arcpy.EmpiricalBayesianKriging_ga(FC, "EBK_Elev", '', out_raster)

# Extract Values to Points - analysis points v. EBK rasters (WS = endWS)
def extractValues():
	in_pts = makeFullFCPath(TempWS, "AnalysisPts")
	for FC in arcpy.ListRasters():
		in_rast = makeFullFCPath(endWS, FC)
		out_pts = makeFullFCPath(TempWS, FC + "_v")
		arcpy.sa.ExtractValuesToPoints(in_pts, in_rast, out_pts)
	# Remove non-data a.k.a Values = -9999

#(WS = TempWS)
def removeDuds():	
	for FC in listFC(suffix="_v"):
		in_feat = makeFullFCPath(TempWS, FC)
		out_name = FC + "al"
		expression = "RASTERVALU <> -9999"
		arcpy.FeatureClassToFeatureClass_conversion(in_feat, TempWS, out_name, expression)
	for FC in listFC(suffix="_v"):
		in_feat = makeFullFCPath(TempWS, FC)
		arcpy.Delete_management(in_feat)

# Format the vals feature classes # (WS = TempWS)
def formatVals():
	for FC in listFC(suffix="val"):
		values = makeFullFCPath(TempWS, FC)
		desc = arcpy.Describe(values).name
		if "Ans" in desc:
			arcpy.AddField_management(values, "Yr_2014", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2014", "!RASTERVALU!", "PYTHON_9.3")
		elif "RTKTrans" in desc:
			arcpy.AddField_management(values, "Yr_2014", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2014", "!RASTERVALU!", "PYTHON_9.3")
		elif "DEM" in desc:
			arcpy.AddField_management(values, "Yr_2008", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2008", "!RASTERVALU!", "PYTHON_9.3")
		elif "Plat" in desc:
			arcpy.AddField_management(values, "Yr_2015", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2015", "!RASTERVALU!", "PYTHON_9.3")
		elif "LT11" in desc:
			arcpy.AddField_management(values, "Yr_2011", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2011", "!RASTERVALU!", "PYTHON_9.3")
		elif "LT12" in desc:
			arcpy.AddField_management(values, "Yr_2012", "DOUBLE")
			arcpy.CalculateField_management(values, "Yr_2012", "!RASTERVALU!", "PYTHON_9.3")
		arcpy.DeleteField_management(values, ["RASTERVALU", "StudyArea"])

def dbf2csv(dbfpath, csvpath):
    rows = arcpy.SearchCursor(dbfpath)
    csvFile = csv.writer(open(csvpath, 'wb')) 
    fieldnames = [f.name for f in arcpy.ListFields(dbfpath)]

    allRows = []
    for row in rows:
        rowlist = []
        for field in fieldnames:
            rowlist.append(row.getValue(field))
        allRows.append(rowlist)

    csvFile.writerow(fieldnames)
    for row in allRows:
        csvFile.writerow(row)
    row = None
    rows = None

# Execute previous functions
def WorkMagic():
	setWorkspace(startWS) #starting workspace
	sepBySetNewGDB()
	
	setWorkspace(endWS) #ending workspace
	ElevationField()
	Buff30m()

	setWorkspace(TempWS) #temp workspace
	buffersByStudyArea()
	mergeBuffsBySA()
	envSABuffs()
	mergeEnv()
	
	setWorkspace(endWS) #end workspace
	applyEBK()

	setWorkspace(TempWS) #temp workspace
	analysisPoints()
	
	setWorkspace(endWS) #end workspace
	extractValues()

	setWorkspace(TempWS) #temp workspace
	removeDuds()
	formatVals()

	for FC in listFC(suffix="val"):
	dbf2csv(makeFullFCPath(TempWS, FC), makeFullFCPath('C:\Users\Priscole\Documents\ArcGIS\Wetlands', FC + ".csv"))


"""The code below was an attempt to create a final table. It was decided that R is a much
better tool for handling this type of task. A separate R-script was written: 'mergeYears.R'."""

# def joinValAnalyPts():
# 	for FC in listFC(suffix="val"):
# 		in_table = makeFullFCPath(TempWS, FC)
# 		arcpy.JoinField_management(anaPts, "Points", FC, "Points")
# 		arcpy.RemoveJoin_management(anaPts)

# def MasterTable():
# 	in_table = makeFullFCPath(endWS, "MASTER")
# 	for FC in listFC(suffix="val"):
# 		arcpy.JoinField_management(in_table, "Points", FC, "Points")
# 	arcpy.FeatureClassToFeatureClass_conversion(in_table, endWS, "MASTER2")


