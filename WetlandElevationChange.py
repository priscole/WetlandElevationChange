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

class ParametersArcPy(object):
	def __init__(self):
		self.metaDataTable = arcpy.GetParameterAsText(0) #type file
		self.inFolder = arcpy.GetParameterAsText(1) #type folder
		self.outFolder = arcpy.GetParameterAsText(2) #type folder
		self.outCSV = arcpy.GetParameterAsText(3) #type string
		self.outGDB = arcpy.GetParameterAsText(4) #type GDB (optional) - default to in_memory
		self.projection = arcpy.GetParameterAsText(5) #type int (optional)
		self.barriers = arcpy.GetParameterAsText(6) #type file (optional)
		
params = ParametersArcPy()

def makeFullFCPath(Path, Name):
	return Path + "\\" + Name

def setWorkspace(WS):
	print "Setting workspace to " + WS
	arcpy.env.workspace = WS

def listFC(prefix="",suffix=""):
	result = list() 
	for FC in arcpy.ListFeatureClasses():
		if FC.startswith(prefix) and FC.endswith(suffix):
			result.append(FC)
	return result

def setSR(params.projection):
	if params.projection == "":
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(103017)
	else: 
		arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(params.projection)

SR = setSR(params.projection)

# class HardCodedParameters(object):
# 	def __init__(self):
# 		self.metaDataTable = "WetlandsMetaData.csv"
# 		self.inFolder =  "C:\\Users\\Priscole\\Documents\\ArcGIS\\Wetlands"
# 		self.outFolder = "C:\\Users\\Priscole\\Documents\\code\\GISPython"
# 		self.outCSV =  "WetlandElevationChange_DEMO.csv"
# 		self.projection = arcpy.SpatialReference(103017)
# 		self.barriers =  "Rivers.shp"