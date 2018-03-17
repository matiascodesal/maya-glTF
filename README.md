# maya-glTF
glTF exporter for Autodesk Maya

There's a lot in the glTF spec to implement, but enough functionality to play around with.  It's just a python script for now, but I plan on wrapping it up in a plugin.

### Installation
Download the glTFExport.py file and put it in your Maya scripts directory: https://www.youtube.com/watch?v=rVDfCNtth0Y

### Usage
Opens a file dialog to specify the output file and runs.
```python
import glTFExport   
glTFExport.export()
```
Runs with no file dialog and ouputs the the string path specified.
```python
import glTFExport   
glTFExport.export(r"C:\Temp\test.glb")
```

For glTF with external images:
```python
import glTFExport   
glTFExport.export(r"C:\Temp\test.gltf", type='gltf', bin_format='flattened')
```

### Current Features
- Export whole scene from Maya
- Exports transform nodes and meshes with hierarchy
- Exports single material shader per mesh (glTF spec).
   - Picks the first shader.
- Lambert, Blinn, Phong use a PBR conversion approximation
   - Base color comes from color attribute as texture or value.
   - Metallic and roughness are derived from the other attribute values and do not support textures.
- Recommend aiStandardSurface shader for best material conversion.
   - Textures not supported for metallicRoughness
- glTF and glb supported
- Options for embedded binary data, single external bin, or preserved external images.
   
### TODO
- Continue implementing the rest of glTF spec
- Add export_selected
- Convert arnold metalness maps and roughness maps to metallicRoughness maps.
- Support aiStandardSurface normal maps
- Support aiStandardSurface emission
- Simplify export options
- Write tests