library(reshape2)
library(stringr)
library(plyr)

setwd("C:/Users/Priscole/Documents/ArcGIS/Wetlands")


files <- as.list(dir(pattern="_val\\.csv"))
names(files) <- str_replace(unlist(files), ".csv$", "")

readFile <- function(fileName) {
	nameNoExt <- str_replace(fileName, ".csv$", "")
	x <- read.csv(fileName)
	cbind(melt(x[,c(3,4)], id.vars="Points"), origin = nameNoExt)
}

allRead <- lapply(files, readFile)

stacked <- do.call(rbind, allRead)

# shows you that there are duplicate points
offending <- subset(
	ddply(stacked, c("Points", "variable"), summarize, numrows = length(Points)), 
	numrows != 1)
print(merge(stacked, offending)) # bad points are DV1_RTKTrans14

duplicatedPoints <- offending$Points

deduped <- subset(stacked, !((Points %in% duplicatedPoints) & (origin == "DV1_RTKTrans14_EBK_val")))


unstacked <- dcast(deduped, 'Points ~ variable', value.var="value")

write.csv(unstacked, file="_val_merged.csv")