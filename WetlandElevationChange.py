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
		self.outGDB = arcpy.GetParameterAsText(4) #type data element - intermediate files to in_memory
			#reserved exclusively for final analysis points merged with final table
			#maybe final study area polygons too???
		self.projection = arcpy.GetParameterAsText(5) #type int (optional) - default Delaware SP (m)
		#self.barriers = arcpy.GetParameterAsText(6) #type file (optional)
			#reserve for future updates with alternative interpolation methods (spline w/ barriers)

params = ParametersArcPy()

def makeFullFCPath(Path, Name):
	return Path + "\\" + Name

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

metaDataTable = {}

metaDataTable = []
with open(myTable, 'rb') as csvfile:
	tableReader = csv.DictReader(csvfile)
	for row in tableReader:
		metaDataTable.append(row)

# myTable = "C:\Users\Priscole\Documents\code\GISPython\WetlandElevationChangeTable.csv"

isNull = ["null", "NULL", "NA", "na", "N/A", "n/a", "", " "]

def createGroups(metaDict):
	groups = {}
	for fc in metaDict:
		if fc['OtherGroup'] not in isNull and fc['OtherGroup'] not in groups:
			groups[fc['OtherGroup']] = [fc['FileName']]
		elif fc['OtherGroup'] not in isNull and fc['OtherGroup'] in groups:
			groups[fc['OtherGroup']].append(fc['FileName'])
		elif 
	return groups



