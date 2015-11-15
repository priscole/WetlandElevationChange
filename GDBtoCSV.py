import os
import arcpy
import csv

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


