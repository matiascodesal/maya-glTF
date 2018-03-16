import json
import struct
import sys
import base64
import math
import maya.cmds
import maya.OpenMaya as OpenMaya
import shutil
import os

class ResourceFormats(object):
    EMBEDDED = 'embedded'
    SOURCE = 'source'
    BIN = 'bin'

class ClassPropertyDescriptor(object):

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        raise AttributeError("can't set attribute")

def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)
    return ClassPropertyDescriptor(func)
        
class ExportSettings(object):
    file_format = 'gltf'
    resource_format = 'bin'
    out_file = ''
    out_basename = ''
    _out_dir = ''
    _out_basename = ''
    
    @classproperty
    def out_bin(cls):
        return cls.out_basename + '.bin'
    
    @classproperty    
    def out_basename(cls):
        if cls._out_basename:
            return cls._out_basename
        base, ext = os.path.splitext(cls.out_file)
        cls._out_basename = os.path.basename(base)
        return cls._out_basename
        
    @classproperty
    def out_dir(cls):
        if cls._out_dir:
            return cls._out_dir
        cls._out_dir = os.path.dirname(cls.out_file)
        return cls._out_dir
    
    
class GLTFExporter(object):
    # TODO: Add VFlip option
    def __init__(self, file_path, resource_format='bin'):
        self.output = {
            "asset": { 
                "version": "2.0", 
                "generator": "maya-glTFExport", 
            }
        }
        ExportSettings.out_file = file_path
        ExportSettings.resource_format = resource_format
        
    def run(self):
        if not ExportSettings.out_file:
            ExportSettings.out_file = maya.cmds.fileDialog2(caption="Specify a name for the file to export.",
                                                        fileMode=0)[0]
        basename, ext = os.path.splitext(ExportSettings.out_file)
        if not ext in ['.glb', '.gltf']:
            raise Exception("Output file must have gltf or glb extension.")
        ExportSettings.file_format = ext[1:]  
    
        # TODO: validate file_path and type
        scene = Scene()
        # we only support exporting single scenes, 
        # so the first scene is the active scene
        self.output['scene'] = 0
        if Scene.instances:
            self.output['scenes'] = Scene.instances
        if Node.instances:
            self.output['nodes'] = Node.instances
        if Mesh.instances:
            self.output['meshes'] = Mesh.instances
        if Camera.instances:
            self.output['cameras'] = Camera.instances
        if Material.instances:
            self.output['materials'] = Material.instances
        if Image.instances:
            self.output['images'] = Image.instances
        if Texture.instances:
            self.output['textures'] = Texture.instances
        if Buffer.instances:
            self.output['buffers'] = Buffer.instances
        if BufferView.instances:
            self.output['bufferViews'] = BufferView.instances
        if Accessor.instances:
            self.output['accessors'] = Accessor.instances
            
        if ExportSettings.file_format == 'glb':
            
            json_str = json.dumps(self.output, sort_keys=True, separators=(',', ':'), cls=GLTFEncoder)
            json_bin = bytearray(json_str.encode(encoding='UTF-8'))
            # 4-byte-aligned
            aligned_len = (len(json_bin) + 3) & ~3
            for i in range(aligned_len - len(json_bin)):
                json_bin.extend(b' ')

            bin_out = bytearray()
            buffer = Buffer.instances[0]
            file_length = 12 + 8 + len(json_bin) + 8 + len(buffer)
            # Magic number
            bin_out.extend(struct.pack('<I', 0x46546C67)) # glTF in binary
            bin_out.extend(struct.pack('<I', 2)) # version number
            bin_out.extend(struct.pack('<I', file_length))
            bin_out.extend(struct.pack('<I', len(json_bin)))
            bin_out.extend(struct.pack('<I', 0x4E4F534A)) # JSON in binary
            bin_out += json_bin
            
            bin_out.extend(struct.pack('<I', len(buffer))) 
            bin_out.extend(struct.pack('<I', 0x004E4942)) # BIN in binary
            bin_out += buffer.byte_str
            
            with open(ExportSettings.out_file, 'wb') as outfile:
                outfile.write(bin_out)
        else:
            #TODO: makedirs
            with open(ExportSettings.out_file, 'w') as outfile:
                json.dump(self.output, outfile, cls=GLTFEncoder)
            
            if ExportSettings.resource_format == ResourceFormats.BIN:
                buffer = Buffer.instances[0]
                with open(ExportSettings.out_dir + "/" + buffer.uri, 'wb') as outfile:
                    outfile.write(buffer.byte_str)
        
def export(file_path=None, resource_format='bin', selection=False):
    GLTFExporter(file_path, resource_format).run()
    
        
class GLTFEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ExportItem):
            return obj.to_json()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
        '''
        for key in obj.keys():
            if key not in ignored_keys:
                obj[key] = [item.to_json() for item in obj[key]]
        
        return obj
        '''
   
class ExportItem(object):
    def __init__(self, name=None):
        self.name = name
    
    
class Scene(ExportItem):
    '''Needs to add itself to scenes'''
    instances = []
    maya_nodes = None
    def __init__(self, name="defaultScene", maya_nodes=maya.cmds.ls(assemblies=True, long=True)):
        super(Scene, self).__init__(name=name)
        self.index = len(Scene.instances)
        Scene.instances.append(self)
        self.nodes = []
        self.maya_nodes = maya_nodes
        for transform in self.maya_nodes:
            if transform not in Camera.default_cameras:
                self.nodes.append(Node(transform))
        
    def to_json(self):
        scene_def = {"name":self.name, "nodes":[node.index for node in self.nodes]}
        return scene_def

class Node(ExportItem):
    '''Needs to add itself to nodes list, possibly node children, and possibly scene'''
    instances = []
    maya_node = None
    matrix = None
    camera = None
    mesh = None

    def __init__(self, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Node, self).__init__(name=name)
        self.index = len(Node.instances)
        Node.instances.append(self)
        self.children = []
        
        self.matrix = maya.cmds.xform(self.maya_node, query=True, matrix=True)
        maya_children = maya.cmds.listRelatives(self.maya_node, children=True, fullPath=True)
        if maya_children:
            for child in maya_children:
                childType = maya.cmds.objectType(child)
                if childType == 'mesh':
                    mesh = Mesh(child)
                    self.mesh = mesh 
                elif childType == 'camera':
                    if maya.cmds.camera(child, query=True, orthographic=True):
                        cam = OrthographicCamera(child)
                    else:
                        cam = PerspectiveCamera(child)
                    self.camera = cam
                elif childType == 'transform':
                    node = Node(child)
                    self.children.append(node)
    
    def to_json(self):
        node_def = {'matrix' : self.matrix}
        if self.children:
            node_def['children'] = [child.index for child in self.children]
        if self.mesh:
            node_def['mesh'] = self.mesh.index
        if self.camera:
            node_def['camera'] = self.camera.index
        return node_def
                     
        
class Mesh(ExportItem):
    '''Needs to add itself to node and its accesors to meshes list'''
    instances = []
    format = None
    maya_node = None
    material = None
    indices_accessor = None
    position_accessor = None
    normal_accessor = None
    texcoord0_accessor = None
    def __init__(self, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Mesh, self).__init__(name=name)
        self.index = len(Mesh.instances)
        Mesh.instances.append(self)
        
        self._getMeshData()
        self._getMaterial()
        
    def to_json(self):
        mesh_def = {"primitives" : [ {
                        "mode": 4,
                        "attributes" : {
                          "POSITION" : self.position_accessor.index,
                          "NORMAL": self.normal_accessor.index ,
                          "TEXCOORD_0": self.texcoord0_accessor.index
                        },
                        "indices" : self.indices_accessor.index,
                        "material" : self.material.index
                      } ]
                    }
        return mesh_def
                    
    def _getMaterial(self):
        shadingGrps = maya.cmds.listConnections(self.maya_node,type='shadingEngine')
        # glTF only allows one materical per mesh, so we'll just grab the first one.
        shader = maya.cmds.ls(maya.cmds.listConnections(shadingGrps),materials=True)[0]
        self.material = Material(shader)
        
    def _getMeshData(self):
        maya.cmds.select(self.maya_node)
        selList = OpenMaya.MSelectionList()
        OpenMaya.MGlobal.getActiveSelectionList(selList)
        meshPath = OpenMaya.MDagPath()
        selList.getDagPath(0, meshPath)
        meshIt = OpenMaya.MItMeshPolygon(meshPath)
        meshFn = OpenMaya.MFnMesh(meshPath)
        do_color = False
        if meshFn.numColorSets():
            do_color=True
            print "doing color"
        indices = []
        positions = [None]*meshFn.numVertices()
        normals = [None]*meshFn.numVertices()
        all_colors = [None]*meshFn.numVertices()
        uvs = [None]*meshFn.numVertices()
        ids = OpenMaya.MIntArray()
        points = OpenMaya.MPointArray()
        if do_color:
            vertexColorList = OpenMaya.MColorArray()
            meshFn.getFaceVertexColors(vertexColorList)
        #meshIt.hasUVs()
        normal = OpenMaya.MVector()
        face_verts = OpenMaya.MIntArray()
        polyNormals = OpenMaya.MFloatVectorArray()
        meshFn.getNormals(polyNormals)
        uv_util = OpenMaya.MScriptUtil()
        uv_util.createFromList([0,0], 2 )
        uv_ptr = uv_util.asFloat2Ptr()
        bbox = BoundingBox()
        while not meshIt.isDone():
            meshIt.getTriangles(points, ids)
            #meshIt.getUVs(u_list, v_list)        
            meshIt.getVertices(face_verts)
            for x in range(0, ids.length()):
                indices.append(ids[x])
                pos = (points[x].x, points[x].y, points[x].z)
                
                local_vert_id = getFaceVertexIndex(face_verts, ids[x])
                #print "local vert:", local_vert_id
                norm_id = meshIt.normalIndex(local_vert_id)
                #meshIt.getNormal(local_vert_id, normal)
                normal = polyNormals[norm_id]
                norm = (normal.x, normal.y, normal.z)
                #print norm
                meshIt.getUV(local_vert_id, uv_ptr, meshFn.currentUVSetName())
                u = uv_util.getFloat2ArrayItem( uv_ptr, 0, 0 )
                v = uv_util.getFloat2ArrayItem( uv_ptr, 0, 1 )
                # flip V for openGL
                # This fails if the the UV is exactly on the border (e.g. (0.5,1))
                # but we really don't know what udim it's in for that case.
                v = int(v) + (1 - (v % 1))
                uv = (u, v)
                if not positions[ids[x]]:   
                    positions[ids[x]] = pos
                    normals[ids[x]] = norm
                    uvs[ids[x]] = uv              
                elif not ( positions[ids[x]] == pos and
                            normals[ids[x]] == norm and
                            uvs[ids[x]] == uv):
                    matched = False
                    for i in range(0, len(positions)):
                        if ( positions[i] == pos and
                            normals[i] == norm and
                            uvs[i] == uv):
                            matched = True
                            indices[-1] = i
                            break
                    if not matched:
                        positions.append(pos)
                        normals.append(norm)
                        uvs.append(uv)
                        indices[-1] = len(positions)-1
                        
                
                if do_color:
                    color = vertexColorList[ids[x]]
                    all_colors[ids[x]] = (color.r, color.g, color.b)
                if points[x].x > bbox.xmax:
                    bbox.xmax = points[x].x
                elif points[x].y > bbox.ymax:
                    bbox.ymax = points[x].y
                elif points[x].z > bbox.zmax:
                    bbox.zmax = points[x].z
                elif points[x].x < bbox.xmin:
                    bbox.xmin = points[x].x
                elif points[x].y < bbox.ymin:
                    bbox.ymin = points[x].y
                elif points[x].z < bbox.zmin:
                    bbox.zmin = points[x].z   
            meshIt.next()

        if not len(Buffer.instances):
            primary_buffer = Buffer('primary_buffer')
        else:
            primary_buffer = Buffer.instances[0]
        self.indices_accessor = Accessor(indices, "SCALAR", 5123, 34963, primary_buffer, name=self.name + '_idx')
        self.indices_accessor.min = [0]
        self.indices_accessor.max = [len(positions) - 1]
        self.position_accessor = Accessor(positions, "VEC3", 5126, 34962, primary_buffer, name=self.name + '_pos')
        self.position_accessor.max = [ bbox.xmax, bbox.ymax, bbox.zmax ]
        self.position_accessor.min =  [ bbox.xmin, bbox.ymin, bbox.zmin ]
        self.normal_accessor = Accessor(normals, "VEC3", 5126, 34962, primary_buffer, name=self.name + '_norm')
        self.texcoord0_accessor = Accessor(uvs, "VEC2", 5126, 34962, primary_buffer, name=self.name + '_uv')
        

class Material(ExportItem):
    '''Needs to add itself to materials and meshes list'''
    instances = []
    maya_node = None
    base_color_factor = None
    base_color_texture = None
    metallic_factor = None
    roughness_factor = None
    transparency = None
    
    def __new__(cls, maya_node):
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        matches = [mat for mat in Material.instances if mat.name == name]
        if matches:
            return matches[0]
        
        return super(Material, cls).__new__(cls, maya_node)
        
    def __init__(self, maya_node):
        if hasattr(self, 'index'):
            return
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Material, self).__init__(name=name)
        
        self.index = len(Material.instances)
        Material.instances.append(self)
       
        color_conn = maya.cmds.listConnections(self.maya_node+'.color')
        trans = list(maya.cmds.getAttr(self.maya_node+'.transparency')[0])
        self.transparency = sum(trans) / float(len(trans))
        if color_conn and maya.cmds.objectType(color_conn[0]) == 'file':
            file_node = color_conn[0]
            file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
            image = Image(file_path)
            self.base_color_texture = Texture(image)
        else:
            color = list(maya.cmds.getAttr(self.maya_node+'.color')[0])
            color.append(1-self.transparency)
            self.base_color_factor = color
        
        self.metallic_factor = 0
        self.roughness_factor = 0
        

    def to_json(self):
        pbr = {}
        mat_def = {'pbrMetallicRoughness': pbr}
        if self.base_color_texture:
            pbr['baseColorTexture'] = {'index':self.base_color_texture.index}
        else:
            pbr['baseColorFactor'] = self.base_color_factor

        pbr['metallicFactor'] = self.metallic_factor
        pbr['roughnessFactor'] = self.roughness_factor
        
        return mat_def


class Camera(ExportItem):
    '''Needs to add itself to node and cameras list'''
    instances = []
    default_cameras = ['|top', '|front', '|side', '|persp']
    maya_node = None
    type = None
    znear = 0.1
    zfar = 1000
    def __init__(self, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Camera, self).__init__(name=name)
        self.index = len(Camera.instances)
        self.znear = maya.cmds.camera(self.maya_node, query=True, nearClipPlane=True)
        self.zfar = maya.cmds.camera(self.maya_node, query=True, farClipPlane=True)
        
        
    def to_json(self):
        if not self.type:
            # TODO: use custom error or ensure type is set
            raise RuntimeError("Type property was not defined")
        camera_def = {'type' : self.type}
        camera_def[self.type] = {'znear' : self.znear,
                                    'zfar' : self.zfar}
        return camera_def
 
    
class PerspectiveCamera(Camera):
    type = 'perspective'
    
    def __init__(self, maya_node):
        super(PerspectiveCamera, self).__init__(maya_node)
        self.aspect_ratio = maya.cmds.camera(self.maya_node, query=True, aspectRatio=True)
        self.yfov = math.radians(maya.cmds.camera(self.maya_node, query=True, verticalFieldOfView=True))
        Camera.instances.append(self)
        
    def to_json(self):
        camera_def = super(PerspectiveCamera, self).to_json()
        camera_def[self.type]['aspectRatio'] = self.aspect_ratio
        camera_def[self.type]['yfov'] = self.yfov
        return camera_def
    
class OrthographicCamera(Camera):
    type = 'orthographic'
    xmag = 1.0
    ymag = 1.0
    
    def __init__(self, maya_node):
        super(OrthographicCamera, self).__init__(maya_node)
        self.xmag = maya.cmds.camera(self.maya_node, query=True, orthographicWidth=True)
        self.ymag = self.xmag
        Camera.instances.append(self)
    
    def to_json(self):
        camera_def = super(OrthographicCamera, self).to_json()
        camera_def[self.type]['xmag'] = self.xmag
        camera_def[self.type]['ymag'] = self.ymag
        return camera_def
    

class Image(ExportItem):
    '''Needs to be added to images list and it's texture'''
    instances = []
    name = None
    uri = None
    buffer_view = None
    mime_type = None
    
    def __init__(self, file_path):
        file_name = os.path.basename(file_path)
        super(Image, self).__init__(name=file_name)
        self.index = len(Image.instances)
        Image.instances.append(self)
        base, ext = os.path.splitext(file_path)
        self.mime_type = 'image/{}'.format(ext.lower()[1:])
            
        if ExportSettings.resource_format == ResourceFormats.SOURCE:
            shutil.copy(file_path, ExportSettings.out_dir)
            self.uri = file_name
        else:
            with open(file_path, 'rb') as f:
                img_bytes = f.read()
            
            if (ExportSettings.resource_format == ResourceFormats.BIN
                    or ExportSettings.file_format == 'glb'):
                single_buffer = Buffer.instances[0]
                buffer_end = len(single_buffer)
                single_buffer.byte_str += img_bytes
                self.buffer_view = BufferView(single_buffer, buffer_end)
                
                # 4-byte-aligned
                aligned_len = (len(img_bytes) + 3) & ~3
                for i in range(aligned_len - len(img_bytes)):
                    single_buffer.byte_str += b' '
        if (ExportSettings.file_format == 'gltf' and
                ExportSettings.resource_format == ResourceFormats.EMBEDDED):
            self.uri = "data:application/octet-stream;base64," + base64.b64encode(img_bytes)
    
    def to_json(self):
        img_def = {'mimeType' : self.mime_type}
        if self.uri:
            img_def['uri'] = self.uri
        else:
            img_def['bufferView'] = self.buffer_view.index
        return img_def
    
class Texture(ExportItem):
    '''Needs to be added to textures list and it's material'''
    instances = []
    image = None
    def __init__(self, image):
        self.image = image
        super(Texture, self).__init__(name=image.name)
        self.index = len(Texture.instances)
        Texture.instances.append(self)
    
    def to_json(self):
        return {'source':self.image.index}

class Sampler(ExportItem):
    def __init__(name=None):
        super(Sampler, self).__init__(name=name)
        
    
class Buffer(ExportItem):
    instances = []
    byte_str = ""
    uri = ''

    def __init__(self, name=None):
        super(Buffer, self).__init__(name=name)
        self.index = len(Buffer.instances)
        Buffer.instances.append(self)
        if (ExportSettings.file_format == 'gltf'
                and ExportSettings.resource_format == ResourceFormats.BIN):
            self.uri = ExportSettings.out_bin
    
    def __len__(self):
        return len(self.byte_str)
    
    def append_data(self, data, type):
        pack_type = '<' + type
        packed_data = []
        for item in data:
            if isinstance(item, (list, tuple)):
                packed_data.append(struct.pack(pack_type, *item))
            else:
                packed_data.append(struct.pack(pack_type, item))
        self.byte_str += b''.join(packed_data)
    
    def to_json(self):
        buffer_def = {"byteLength" : len(self)}
        if self.uri and ExportSettings.resource_format == ResourceFormats.BIN:
            buffer_def['uri'] = self.uri
        elif ExportSettings.resource_format in [ResourceFormats.EMBEDDED, ResourceFormats.SOURCE]:
            buffer_def['uri'] = "data:application/octet-stream;base64," + base64.b64encode(self.byte_str)
        # no uri for GLB
        return buffer_def

class BufferView(ExportItem):
    instances = []
    buffer = None
    byte_offset = None
    byte_length = None
    target = 34962
    
    def __init__(self, buffer, byte_offset, target=None, name=None):
        super(BufferView, self).__init__(name=name)
        self.index = len(BufferView.instances)
        BufferView.instances.append(self)
        self.buffer = buffer
        self.byte_offset = byte_offset
        self.byte_length = len(buffer) - byte_offset
        self.target = target
        
    def to_json(self):
        buffer_view_def = {
          "buffer" : self.buffer.index,
          "byteOffset" : self.byte_offset,
          "byteLength" : self.byte_length,
        }
        if self.target:
            buffer_view_def['target'] = self.target
            
        return buffer_view_def
    
class Accessor(ExportItem):
    instances = []
    buffer_view = None
    byte_offset = 0
    component_type = None
    count = None
    type = None
    src_data = None
    max  = None
    min = None
    type_codes = {"SCALAR":1,"VEC2":2,"VEC3":3}
    component_type_codes = {5123:"H",5126:"f"}
    
    def __init__(self, data, type, component_type, target, buffer, name=None):
        super(Accessor, self).__init__(name=name)
        self.index = len(Accessor.instances)
        Accessor.instances.append(self)
        self.src_data = data
        self.component_type = component_type
        self.type = type
        byte_code = self.component_type_codes[component_type]*self.type_codes[type]
        
        buffer_end = len(buffer)
        buffer.append_data(self.src_data, byte_code)
        self.buffer_view = BufferView(buffer, buffer_end, target)
        
    def to_json(self):
        accessor_def = {
          "bufferView" : self.buffer_view.index,
          "byteOffset" : self.byte_offset,
          "componentType" : self.component_type,
          "count" : len(self.src_data),
          "type" : self.type
        }
        if self.max:
            accessor_def['max'] = self.max
        if self.min:
            accessor_def['min'] = self.min
        return accessor_def
    

class BoundingBox(object):
    xmin = 0
    ymin = 0
    zmin = 0
    xmax = 0
    ymax = 0
    zmax = 0  

def getFaceVertexIndex(face_verts, obj_vert):
    for x in range(0, face_verts.length()):
        if face_verts[x] == obj_vert:
            return x

def getBoundingBox():
    transform = 'pCube1'

    mSel = om.MSelectionList()
    dagPath = om.MDagPath()
    mSel.add( transform )
    mSel.getDagPath(0, dagPath)

    dagFn = om.MFnDagNode(dagPath)

    # Returns the bounding box for the dag node in object space.
    boundingBox = dagFn.boundingBox()

    # There's a few useful methods available, including min and max
    # which will return the min/max values represented in the attribute editor.

    min = boundingBox.min()
    max = boundingBox.max()

    