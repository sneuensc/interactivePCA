interactivePCA --help

interactivePCA \
	--eigenvec data/aadr2.eigenvec \
	--server-port 8051

interactivePCA \
	--eigenvec data/aadr2.eigenvec \
	--server-port 8051  \
	--annotation data/aadr2.anno \
	--longitude Long. \
	--latitude Lat.
	
interactivePCA \
	--eigenvec data/aadr2.eigenvec \
	--server-port 8051  \
	--annotation data/aadr2.anno \
	--longitude Long. \
	--latitude Lat. \
	--time 'zDate mean in BP in years before 1950 CE [OxCal mu for a direct radiocarbon date, and average of range for a contextual date]'
	
	
	
interactivePCA \
	--eigenvec data-lucas/coord.tsv \
	--server-port 8051  \
	--annotation data-lucas/annot.tsv \
	--longitude long \
	--latitude lat \
	--time date
	
