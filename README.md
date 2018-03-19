# maya-glTF
glTF exporter plugin for Autodesk Maya

This plugin is compatible with every version of Maya.  Tested with 2015+.  Most of the glTF spec has been implemented, but this is still a work in progress.  There are a couple of features still missing and some material translations that need to be tuned.  Report any issues [here](https://github.com/matiascodesal/maya-glTF/issues)!

![Pig Export](https://github.com/matiascodesal/maya-glTF/blob/master/doc/images/pig-export.png)
Model credit: https://sketchfab.com/KulerRuler

## Installation
1. Download the ZIP file using the green button at the top of this page.  
1. Extract the ZIP and copy the files to their appropriate folders:  
- `glTFExport.py` and `glTFTranslatorOpts.mel` from the `scripts` folder need to be copied to the scripts folder here:   

| OS | Path |
|---------|----------|
|(Windows)|  `C:/Users/<username>/Documents/maya/<version>/scripts`|  
|(Mac OS X) |`Library/Preferences/Autodesk/maya/<version>/scripts`|  
|(Linux)  |  `$MAYA_APP_DIR/maya/<version>/scripts`|  

- `glTFTranslator.py` from the `plug-ins` folder needs to be copied to the plug-ins folder here (create a plug-ins folder if you don't have one):  

| OS | Path |
|----|-----|
(Windows) | `C:/Users/<username>/Documents/maya/<version>/plug-ins`  
(Mac OS X) |`Library/Preferences/Autodesk/maya/<version>/plug-ins`  
(Linux)   | `$MAYA_APP_DIR/maya/<version>/plug-ins`  

## Usage

### Exporting through the File menu
1. Launch Maya.
1. Open the Plug-in Manager
   - ![Plug-in Manager 1](https://github.com/matiascodesal/maya-glTF/blob/master/doc/images/find-plug-man.PNG)
1. Check on "Loaded" for "glTFTranslator.py" plug-in.
   - ![Plug-in Manager 2](https://github.com/matiascodesal/maya-glTF/blob/master/doc/images/plug-in-man.PNG)
1. Export your scene: File->Export All...
   - File->Export Selection... not currently supported.
1. Choose "glTF Export" for the "Files of Type" option.
1. Optionally, set any file type specific options as well.
   - ![File options](https://github.com/matiascodesal/maya-glTF/blob/master/doc/images/file-type-opts.PNG)


### Exporting as a part of a script
```python
import glTFExport   
glTFExport.export(r"C:\Temp\test.glb", resource_format='bin', anim='keyed', vflip=True)
```
#### Export parameters

| Parameter | Description |   
| --------- | ----------- |   
|file_path|Path to export the file to.  File extension should be .glb or .gltf|   
|resource_format| How to export binary data. Only applies to .gltf format.  Valid value: 'bin', 'source', 'embedded'. **bin** - A single .bin file next to the .gltf file. **source** - Images are copied next to the .gltf file. **embedded** - Everything is embedded within the .gltf.|   
|anim|How to deal with animation. Valid values: 'none', 'keyed'.  **none** - Don't export animation. **keyed** - Respect current keys|   
|vFlip|GL renderers want UVs flippedin V compared to Maya.  Set to False if you don't need to fix the flipping.|   

## Current Features
- Export whole scene from Maya
- Exports transform nodes and meshes with hierarchy
- Exports single material shader per mesh (glTF spec).
   - Picks the first shader.
- Lambert, Blinn, Phong use a PBR conversion approximation
   - Base color comes from color attribute as texture or value.
   - Metallic and roughness are derived from the other attribute values and do not support textures.
- Recommend aiStandardSurface shader for best material conversion.
   - Textures not supported for metallicRoughness
- Node animation supported for translation, rotation, scale.
- glTF and glb supported
- Options for embedded binary data, single external bin, or preserved external images.
   
## TODO
- Implement skinning
- Implement blendshapes
- Add Export Selection... function.
- Convert arnold metalness maps and roughness maps to metallicRoughness maps.
- Support aiStandardSurface normal maps
- Support aiStandardSurface emission
- Write tests
