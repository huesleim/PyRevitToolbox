# PyRevitToolbox
A collection of Revit automation tools written in Python using the Autodesk Revit API, organized as a pyRevit extension for easy deployment and execution within Revit.
This toolbox was tailored for the Architecture office I currently work on, taking into consideration its specific needs and constraints.

## Tools
### Geometry
#### Area sketch
Needs to be run in an Area Plan View. Select a floor and create Area Separation Lines on top of the floor's sketch.

##### Future features/updates
- Tool was specifically built for using with floors, but that's an unecesary constraint. Will be updated to allow for other objects that reveal slketches, such as roofs.
  
##### Bugs
- Currently does not take into consideration floors with holes, so that it creates 2 overlapping floors. Needs to manually place holes inside floors.


#### Separate floors
Select a floor and separate every polygon into its own floor, then delete the original.
 
##### Bugs
- Currently does not take into consideration floors with holes, so that it creates 2 overlapping floors. Needs to manually place holes inside floors.

  
### Parameters
#### Ifc share clear
Needs to be run in a Scheduule. Sets all elements visible in the table's IFC Share parameters to None.


#### Ifc share set
Needs to be run in a Scheduule. Sets all elements visible in the table's IFC Share parameters to specific values, tailored to the office's specifics.


### Annotation
WIP.
