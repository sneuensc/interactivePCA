# interactivePCA: simultaneous exploration of ancient DNA across genetic, geographic, temporal, and phenotypic dimensions

**Samuel Neuenschwander¹,²\*, Anna-Sapfo Malaspinas¹,³**

¹ Department of Computational Biology, University of Lausanne, Lausanne, Switzerland  
² Vital-IT, SIB Swiss Institute of Bioinformatics, Lausanne, Switzerland  
³ SIB Swiss Institute of Bioinformatics, Lausanne, Switzerland  
\* Corresponding author: samuel.neuenschwander@unil.ch

---

## Abstract

Principal component analysis (PCA) is the central exploratory tool in ancient DNA (aDNA) research, yet standard implementations constrain analysts to a single two-dimensional view at a time.
We present **interactivePCA**, a browser-based application that links up to five analytical dimensions in a single coordinated interface: two genetic principal components, geographic provenance, chronological age, and a user-defined grouping variable.
Lasso selections, hover information, and aesthetic styling propagate instantly across all panels, enabling cohesive visual interrogation of population structure, migration, and admixture.
interactivePCA is implemented in Python/Dash, requires no server infrastructure, and accepts the PLINK eigenvector format directly.

**Availability:** <https://github.com/sneuensc/interactive-pca>  
**Contact:** samuel.neuenschwander@unil.ch

---

## 1. Introduction

Ancient DNA studies have transformed our understanding of human prehistory by revealing large-scale migrations, admixture events, and population replacements that left no unambiguous trace in the archaeological record (Haak *et al.*, 2015; Mathieson *et al.*, 2015; Reich, 2018).
PCA remains the workhorse for presenting genetic variation: it is computationally tractable on cohorts of thousands of individuals and produces intuitive scatter plots that mirror population structure (Patterson *et al.*, 2006).

However, aDNA data are inherently multi-dimensional.
A single ancient individual carries simultaneously a genomic signature (its position in PC space), a geographic provenance (site latitude/longitude), a chronological age (radiocarbon date or archaeological period), and one or more categorical descriptors (culture, haplogroup, sex).
Standard PCA software — EIGENSOFT (Price *et al.*, 2006), PLINK (Purcell *et al.*, 2007) — writes static eigenvector tables; visualisation is then delegated to general-purpose plotting packages such as R/ggplot2 or Python/matplotlib.
Static images, however, force analysts to cross-reference separate figures mentally, a process that is slow, error-prone, and becomes impractical when cohort sizes reach hundreds of samples.

Interactive web-based tools such as HGDP Explorer and GenomePlot provide some dynamic functionality, but none natively links a PC scatter plot with a geographic map and a time axis in a fully coordinated, lasso-selectable interface suitable for local, offline use with private data.
interactivePCA fills this gap, allowing researchers to select a subset of individuals in any one panel and immediately see exactly where those individuals lived, when they lived, and how they cluster in PC space — simultaneously and without writing a single line of code.

---

## 2. Implementation

interactivePCA is a Python package built on the **Dash** reactive web framework (Plotly Inc.) with **Plotly.js** for rendering.
All computation is performed at startup; once the application is running, every interaction — selections, hover events, axis changes — is handled client-side through compiled JavaScript callbacks, giving sub-100 ms response times even on datasets of several thousand samples.

**Input.** The tool accepts two files: (i) a PLINK-format eigenvector file (`--eigenvec`) containing any number of principal components, and (ii) an optional tab-separated annotation file (`--annotation`) whose column roles — identifier, latitude, longitude, chronological date, grouping variables — are specified via command-line flags or auto-detected by column name.
Pre-computed MDS coordinates are equally accepted.

**Architecture.** The Dash application is launched via a single CLI command (`interactive-pca --eigenvec ... --annotation ...`) and served on localhost, ensuring that confidential genomic data never leave the analyst's machine.
The layout consists of two resizable panes: the left pane holds the PCA/MDS scatter plot and the time scatter plot (vertically stacked, with a draggable divider); the right pane holds the geographic map and a tabbed panel containing the annotation table, a hover-detail view, and the pandas query filter.
A clientside JavaScript callback propagates hover and selection events across all three plots in real time without server round-trips.

**Customisation.** Point colours, symbols, sizes, and opacities are configurable per group value through a modal aesthetics editor and can be persisted to a JSON file for reproducibility.
Continuous variables (e.g. radiocarbon dates, allele frequencies) are rendered with user-selectable colour scales; categorical grouping variables receive a default qualitative palette that the user can override.

---

## 3. Usage and key features

### 3.1 Five simultaneous analytical dimensions

A typical aDNA session opens with a two-dimensional PC scatter plot (dimensions 1 and 2), a Mapbox-backed geographic scatter plot showing sample provenance, and a chronological scatter plot (jittered along the y-axis to separate overlapping dates).
Taken together, these three panels expose **five analytical dimensions at once**: PC1 (x), PC2 (y), longitude, latitude, and time.
A sixth, discrete dimension is encoded through the **Group by** selector, which re-colours all three panels simultaneously according to any categorical or continuous annotation column — culture, haplogroup, admixture proportion, or quality metric.

### 3.2 Coordinated cross-panel selection

Lasso or box selection in any panel instantly highlights the matched individuals in the other two panels and updates the annotation table.
Conversely, toggling checkboxes in the annotation table, or applying a pandas query filter (e.g. `Date < -3000 & Culture == "Yamnaya"`), propagates the selection back to all three plots.
This bidirectionality enables rapid hypothesis testing: an analyst can, for example, isolate genomically outlying individuals from a PC cluster and immediately inspect whether they share a geographic or chronological signal.

### 3.3 Hover information and detail panel

Hovering over any point in any plot simultaneously displays the matching point in the other two plots, showing at minimum the sample identifier and group label.
A **Hover detailed** toggle enriches the tooltip with all annotation columns currently selected in the annotation table.
When the side-panel **Details** tab is active, the hover card is expanded into a scrollable key–value table, and the in-plot tooltips revert to minimal labels to avoid visual clutter.

### 3.4 Three-dimensional PCA and axis switching

PC axes are freely switchable via dropdowns (X, Y, and, in 3D mode, Z), allowing users to traverse the full PC space without regenerating figures.
Three-dimensional mode renders an interactive Scatter3d widget in which the lasso tool is replaced by 3D camera rotation; selections made in 3D are propagated to the 2D geographic and time panels.

---

## 4. Conclusion

interactivePCA provides an integrated, five-dimensional visual workspace for aDNA research that substantially reduces the cognitive overhead of multi-panel analysis.
By linking genetic, geographic, and chronological dimensions within a single coordinated interface, it enables analysts to detect patterns — such as the co-occurrence of PC outliers with chronologically early or geographically peripheral samples — that would be invisible in separate static plots.
The tool is designed to integrate directly into existing PLINK/EIGENSOFT workflows, requires no bioinformatics infrastructure beyond a standard Python environment, and scales to the cohort sizes typical of current aDNA studies (hundreds to a few thousand samples).

---

## Availability and requirements

- **Project name:** interactivePCA
- **Project home page:** <https://github.com/sneuensc/interactive-pca>
- **Operating system:** Platform-independent (tested on macOS and Linux)
- **Programming language:** Python ≥ 3.8
- **Other requirements:** Dash ≥ 2.0, Plotly ≥ 5.0, pandas ≥ 1.3, dash-ag-grid ≥ 2.0
- **License:** MIT

---

## Acknowledgements

The authors thank members of the Malaspinas lab for testing and feedback.

*Funding:* [funding sources]

---

## References

Haak, W. *et al.* (2015) Massive migration from the steppe was a source for Indo-European languages in Europe. *Nature*, **522**, 207–211.

Mathieson, I. *et al.* (2015) Genome-wide patterns of selection in 230 ancient Eurasians. *Nature*, **528**, 499–503.

Patterson, N. *et al.* (2006) Population structure and eigenanalysis. *PLOS Genetics*, **2**, e190.

Price, A.L. *et al.* (2006) Principal components analysis corrects for stratification in genome-wide association studies. *Nature Genetics*, **38**, 904–909.

Purcell, S. *et al.* (2007) PLINK: a tool set for whole-genome association and population-based linkage analyses. *American Journal of Human Genetics*, **81**, 559–575.

Reich, D. (2018) *Who We Are and How We Got Here: Ancient DNA and the New Science of the Human Past*. Oxford University Press, Oxford.
