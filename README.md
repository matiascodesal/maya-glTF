# maya-glTF
glTF exporter for Autodesk Maya

There's a lot in the glTF spec to implement, but enough functionality to play around with.  It's just a python script for now, but I plan on wrapping it up in a plugin.

**Installation**
Download the glTFExport.py file and put it in your Maya scripts directory: https://www.youtube.com/watch?v=rVDfCNtth0Y

**Usage**
`
import glTFExport
glTFExport.GLTFExporter().export_scene(r"C:\Temp\test.gltf")
`
`import glTFExport
glTFExport.GLTFExporter().export_scene(r"C:\Temp\test.gltf")`

**Current Features**
- Export whole scene from Maya
- Exports transform nodes and mesh with hierarchy
- Exports single shader per mesh (glTF spec).
   - Picks the first shader.
   - Exports shader color attribute.  Textures are WIP and may conflict.
   - Metallic and Roughness hard-coded
- glTF format only currently.
   
**TODO**
- Continue implementing the rest of glTF spec
- Add glb option
- Add export_selected
