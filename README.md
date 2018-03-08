# maya-glTF
glTF exporter for Autodesk Maya

There's a lot in the glTF spec to implement, but enough functionality to play around with.  It's just a python script for now, but I plan on wrapping it up in a plugin.

**Current Features**
- Export whole scene from Maya
- Exports transform nodes and mesh with hierarchy
- Exports single shader per mesh (glTF spec).
   - Picks the first shader.
   - Exports shader color attribute.  Textures are WIP and may conflict.
   - Metallic and Roughness hard-coded
- glTF format only currently.
   
**TODO**
- Major refactoring required
- Flip UVs in V
- Add filebrowser
- Continue implementing the rest of glTF spec
