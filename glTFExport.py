import json
import struct
import sys
import base64
import math
import maya.cmds
import maya.OpenMaya as OpenMaya
import shutil
import os


class GLTFExporter(object):
    
    output_file = 'C:/tmp_data/data.gltf'
    def __init__(self):
        self.output = {
            "asset": { 
                "version": "2.0", 
                "generator": "maya-glTFExport", 
                "copyright": "2018 (c) Matias Codesal" 
            },
            "scenes": [], # not required
            "nodes": [],
            "cameras": [],
            "meshes": [],
            "materials":[],
            "textures":[],
            "images":[],
            "buffers": [],
            "bufferViews": [],
            "accessors": []
        }
    def export_scene(self, file_path=None, type='gltf'):
        self.output_file = file_path
        if not self.output_file:
            self.output_file = maya.cmds.fileDialog2(caption="Specify a name for the file to export.",
                                                fileMode=0)[0]
        self.output_dir = os.path.dirname(self.output_file)                                     
        # TODO: validate file_path and type
        index = len(self.output['scenes'])
        scene = Scene(index, export_ctx=self)
        self.output['scenes'].append(scene)
        # we only support exporting single scenes, 
        # so the first scene is the active scene
        self.output['scene'] = 0
        print self.output
        #TODO: makedirs
        with open(self.output_file, 'w') as outfile:
            json.dump(self.output, outfile, cls=GLTFEncoder)

    def export_selected(self, file_path, type='gltf'):
        if not file_path:
            file_path = maya.cmds.fileDialog2(caption="Specify a name for the file to export.",
                                                fileMode=0)
        # TODO: validate file_path and type
        scene = Scene(nodes=maya.cmds.ls(selection=True), export_ctx=self)
    
    def _create_node(self, maya_node):
        next_index = len(self.output['nodes'])
        print next_index, maya_node
        # Need to temporarily add it to list because
        # of the recursive nature of the algorithm
        self.output['nodes'].append(None)
        node = Node(next_index, self, maya_node)
        self.output['nodes'][next_index] = node
        return node
        
    def _create_camera(self, maya_node):
        next_index = len(self.output['cameras'])
        if maya.cmds.camera(maya_node, query=True, orthographic=True):
            cam = OrthographicCamera(next_index, self, maya_node)
        else:
            cam = PerspectiveCamera(next_index, self, maya_node)
        self.output['cameras'].append(cam)
        return cam
    
    def _create_mesh(self, maya_node):
        next_index = len(self.output['meshes'])
        mesh = Mesh(next_index, self, maya_node)
        self.output['meshes'].append(mesh)
        return mesh
    
    def _create_material(self, maya_node):
        next_index = len(self.output['materials'])
        mat = Material(next_index, self, maya_node)
        self.output['materials'].append(mat)
        return mat
    
    def _create_image(self, file_path):
        next_index = len(self.output['images'])
        img = Image(next_index, self, file_path)
        self.output['images'].append(img)
        return img
    
    def _create_texture(self, image):
        next_index = len(self.output['textures'])
        texture = Texture(next_index, self, image)
        self.output['textures'].append(texture)
        return texture
        
    def _create_buffer(self, name):
        next_index = len(self.output['buffers'])
        buffer = Buffer(next_index, self, name)
        self.output['buffers'].append(buffer)
        return buffer
    
    def _create_buffer_view(self, buffer, byte_offset, target):
        next_index = len(self.output['bufferViews'])
        bv = BufferView(next_index, self, buffer, byte_offset, target)
        self.output['bufferViews'].append(bv)
        return bv
    
    def _create_accessor(self, name, data, type, component_type, target, buffer):
        next_index = len(self.output['accessors'])
        accessor = Accessor(next_index, self, data, type, component_type, target, buffer, name=name)
        self.output['accessors'].append(accessor)
        return accessor

        
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
    
    def __init__(self, index, export_ctx, name=None):
        self.index = index
        self.name = name
        self.context = export_ctx
    
    
class Scene(ExportItem):
    '''Needs to add itself to scenes'''
    maya_nodes = None
    nodes = []
    def __init__(self, index, export_ctx, name="defaultScene", maya_nodes=maya.cmds.ls(assemblies=True, long=True)):
        super(Scene, self).__init__(index, export_ctx, name=name)
        self.maya_nodes = maya_nodes
        for transform in self.maya_nodes:
            if transform not in Camera.default_cameras:
                self.nodes.append(self.context._create_node(transform))
        
    def to_json(self):
        scene_def = {"name":self.name, "nodes":[node.index for node in self.nodes]}
        return scene_def

class Node(ExportItem):
    '''Needs to add itself to nodes list, possibly node children, and possibly scene'''
    maya_node = None
    matrix = None
    camera = None
    mesh = None

    def __init__(self, index, export_ctx, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Node, self).__init__(index, export_ctx, name=name)
        self.children = []
        
        self.matrix = maya.cmds.xform(self.maya_node, query=True, matrix=True)
        maya_children = maya.cmds.listRelatives(self.maya_node, children=True, fullPath=True)
        if maya_children:
            for child in maya_children:
                childType = maya.cmds.objectType(child)
                if childType == 'mesh':
                    mesh = self.context._create_mesh(child)
                    self.mesh = mesh 
                elif childType == 'camera':
                    cam = self.context._create_camera(child)
                    self.camera = cam
                elif childType == 'transform':
                    node = self.context._create_node(child)
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
    maya_node = None
    material = None
    indices_accessor = None
    position_accessor = None
    normal_accessor = None
    texcoord0_accessor = None
    def __init__(self, index, export_ctx, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Mesh, self).__init__(index, export_ctx, name=name)
        
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
        self.material = self.context._create_material(shader)
        
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

        buffer_name = self.name + '_geom'
        geom_buffer = self.context._create_buffer(buffer_name)
        self.indices_accessor = self.context._create_accessor(self.name + '_idx', indices, "SCALAR", 5123, 34963, geom_buffer)
        self.indices_accessor.min = [0]
        self.indices_accessor.max = [len(positions) - 1]
        self.position_accessor = self.context._create_accessor(self.name + '_pos', positions, "VEC3", 5126, 34962, geom_buffer)
        self.position_accessor.max = [ bbox.xmax, bbox.ymax, bbox.zmax ]
        self.position_accessor.min =  [ bbox.xmin, bbox.ymin, bbox.zmin ]
        self.normal_accessor = self.context._create_accessor(self.name + '_norm', normals, "VEC3", 5126, 34962, geom_buffer)
        self.texcoord0_accessor = self.context._create_accessor(self.name + '_uv', uvs, "VEC2", 5126, 34962, geom_buffer)
        

class Material(ExportItem):
    '''Needs to add itself to materials and meshes list'''
    maya_node = None
    base_color_factor = None
    base_color_texture = None
    metallic_factor = None
    roughness_factor = None
    transparency = None
    
    def __init__(self, index, export_ctx, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Material, self).__init__(index, export_ctx, name=name)
        
        color_conn = maya.cmds.listConnections(self.maya_node+'.color')
        trans = list(maya.cmds.getAttr(self.maya_node+'.transparency')[0])
        self.transparency = sum(trans) / float(len(trans))
        if color_conn and maya.cmds.objectType(color_conn[0]) == 'file':
            file_node = color_conn[0]
            file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
            image = self.context._create_image(file_path)
            self.base_color_texture = self.context._create_texture(image)
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
    default_cameras = ['|top', '|front', '|side', '|persp']
    maya_node = None
    type = None
    znear = 0.1
    zfar = 1000
    def __init__(self, index, export_ctx, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Camera, self).__init__(index, export_ctx, name=name)
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
    
    def __init__(self, index, export_ctx, maya_node):
        super(PerspectiveCamera, self).__init__(index, export_ctx, maya_node)
        self.aspect_ratio = maya.cmds.camera(self.maya_node, query=True, aspectRatio=True)
        self.yfov = math.radians(maya.cmds.camera(self.maya_node, query=True, verticalFieldOfView=True))
        
    def to_json(self):
        camera_def = super(PerspectiveCamera, self).to_json()
        camera_def[self.type]['aspectRatio'] = self.aspect_ratio
        camera_def[self.type]['yfov'] = self.yfov
        return camera_def
    
class OrthographicCamera(Camera):
    type = 'orthographic'
    xmag = 1.0
    ymag = 1.0
    
    def __init__(self, index, export_ctx, maya_node):
        super(OrthographicCamera, self).__init__(index, export_ctx, maya_node)
        self.xmag = maya.cmds.camera(self.maya_node, query=True, orthographicWidth=True)
        self.ymag = self.xmag
    
    def to_json(self):
        camera_def = super(OrthographicCamera, self).to_json()
        camera_def[self.type]['xmag'] = self.xmag
        camera_def[self.type]['ymag'] = self.ymag
        return camera_def
    

class Image(ExportItem):
    '''Needs to be added to images list and it's texture'''
    name = None
    uri = None
    def __init__(self, index, export_ctx, file_path):
        file_name = os.path.basename(file_path)
        super(Image, self).__init__(index, export_ctx, name=file_name)
        
        shutil.copy(file_path, self.context.output_dir)
        self.uri = file_name
    
    def to_json(self):
        return {'uri':self.uri}
    
class Texture(ExportItem):
    '''Needs to be added to textures list and it's material'''
    image = None
    def __init__(self, index, export_ctx, image):
        self.image = image
        super(Texture, self).__init__(index, export_ctx, name=image.name)
    
    def to_json(self):
        return {'source':self.image.index}

class Sampler(ExportItem):
    def __init__(index, export_ctx, name=None):
        super(Sampler, self).__init__(index, export_ctx, name=name)
        
    
class Buffer(ExportItem):
    byte_str = ""

    def __init__(self, index, export_ctx, name=None):
        super(Buffer, self).__init__(index, export_ctx, name=name)
    
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
        buffer_def = {
          "uri" : "data:application/octet-stream;base64," + base64.b64encode(self.byte_str),
          "byteLength" : len(self)
        }
        return buffer_def

class BufferView(ExportItem):
    buffer = None
    byte_offset = None
    byte_length = None
    target = 34962
    
    def __init__(self, index, export_ctx, buffer, byte_offset, target, name=None):
        super(BufferView, self).__init__(index, export_ctx, name=name)
        self.buffer = buffer
        self.byte_offset = byte_offset
        self.byte_length = len(buffer) - byte_offset
        self.target = target
        
    def to_json(self):
        buffer_view_def = {
          "buffer" : self.buffer.index,
          "byteOffset" : self.byte_offset,
          "byteLength" : self.byte_length,
          "target" : self.target
        }
        return buffer_view_def
    
class Accessor(ExportItem):
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
    
    def __init__(self, index, export_ctx, data, type, component_type, target, buffer, name=None):
        super(Accessor, self).__init__(index, export_ctx, name=name)
        self.src_data = data
        self.component_type = component_type
        self.type = type
        byte_code = self.component_type_codes[component_type]*self.type_codes[type]
        
        buffer_end = len(buffer)
        buffer.append_data(self.src_data, byte_code)
        self.buffer_view = self.context._create_buffer_view(buffer, buffer_end, target)
        
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
    
def createScene():
    output["scenes"] = [{"name":"defaultScene", "nodes":[]}]
    output["scene"] = 0

def addNode(node):
    print node
    node_def = {'matrix' : maya.cmds.xform(node, query=True, matrix=True)}
    children = maya.cmds.listRelatives(node, children=True, fullPath=True)
    if children:
        for child in children:
            childType = maya.cmds.objectType(child)
            if childType == 'mesh':
                print child
                addGeomData(child)
                indices_accessor_index = len(output["meshes"])*4
                output["meshes"].append({
                                  "primitives" : [ {
                                    "mode": 4,
                                    "attributes" : {
                                      "POSITION" : indices_accessor_index + 1,
                                      "NORMAL": indices_accessor_index + 2,
                                      "TEXCOORD_0": indices_accessor_index + 3
                                    },
                                    "indices" : indices_accessor_index,
                                    "material" : addMaterial(child)
                                  } ]
                                })
                node_def['mesh'] = len(output["meshes"]) - 1
            elif childType == 'camera':
                camera_index = addCamera(child)
                node_def['camera'] = camera_index
            elif childType == 'transform':
                child_node_index = addNode(child)
                if not 'children' in node_def.keys():
                    node_def['children'] = []
                node_def['children'].append(child_node_index)
        
    # add the node defintion
    output["nodes"].append(node_def)
    
    print node, len(output["nodes"]) - 1
    return len(output["nodes"]) - 1
    
def addCamera(camera):
    camera_def = {}
    if maya.cmds.camera(camera, query=True, orthographic=True):
        camera_def['type'] = 'orthographic'
        camera_def['orthographic'] = {}
        camera_def['orthographic']['xmag'] = maya.cmds.camera(camera, query=True, orthographicWidth=True)
        camera_def['orthographic']['ymag'] = maya.cmds.camera(camera, query=True, orthographicWidth=True)
        camera_def['orthographic']['znear'] = maya.cmds.camera(camera, query=True, nearClipPlane=True)
        camera_def['orthographic']['zfar'] = maya.cmds.camera(camera, query=True, farClipPlane=True)
    else:
        camera_def['type'] = 'perspective'
        camera_def['perspective'] = {}
        camera_def['perspective']['aspectRatio'] = maya.cmds.camera(camera, query=True, aspectRatio=True)
        camera_def['perspective']['yfov'] = maya.cmds.camera(camera, query=True, verticalFieldOfView=True)
        camera_def['perspective']['znear'] = maya.cmds.camera(camera, query=True, nearClipPlane=True)
        camera_def['perspective']['zfar'] = maya.cmds.camera(camera, query=True, farClipPlane=True)
    
    output['cameras'].append(camera_def)
    return len(output['cameras']) - 1

def addGeomData(mesh):
    data = []
    
    pack_type = '<' + "H" * 1 # H = GL_UNSIGNED_SHORT
    indices, positions, normals, colors, uvs, bbox =  getVertices(mesh)
    for index in indices:
        data.append(struct.pack(pack_type, index))
    indices_byte_length = len(b''.join(data))
    if indices_byte_length % 4 == 2:
        print "indices has remainder"
    index_byte_str = b''.join(data)
    index_byte_length = len(index_byte_str)
    
    pack_type = '<' + "f" * 3 # f = GL_FLOAT
    pos_data = []
    for pos in positions:
        pos_data.append(struct.pack(pack_type, pos[0], pos[1], pos[2]))
    pos_byte_str = b''.join(pos_data)
    positions_byte_length = len(pos_byte_str)
    print positions_byte_length
    
    normals_data = []
    for normal in normals:
        normals_data.append(struct.pack(pack_type, normal[0], normal[1], normal[2]))
    normals_byte_str = b''.join(normals_data)
    normals_byte_length = len(normals_byte_str)
    
    pack_type = '<' + "f" * 2 # f = GL_FLOAT
    uvs_data = []
    for uv in uvs:
        uvs_data.append(struct.pack(pack_type, uv[0], uv[1]))
    uvs_byte_str = b''.join(uvs_data)
    uvs_byte_length = len(uvs_byte_str)
    
    byte_str = index_byte_str + pos_byte_str + normals_byte_str +uvs_byte_str
    byte_str_length = len(byte_str)

    if positions_byte_length % 4 == 2:
        print "pos has remainder"
    if normals_byte_length % 4 == 2:
        print "normals has remainder"
    buffer = {
      "uri" : "data:application/octet-stream;base64," + base64.b64encode(byte_str),
      "byteLength" : byte_str_length
    }
    output['buffers'].append(buffer)
    index_buffer_view = {
      "buffer" : len(output['buffers']) - 1,
      "byteOffset" : 0,
      "byteLength" : indices_byte_length,
      "target" : 34963
    }
    output["bufferViews"].append(index_buffer_view) 
    index_accessor = {
      "bufferView" : len(output['bufferViews']) - 1,
      "byteOffset" : 0,
      "componentType" : 5123,
      "count" : len(indices),
      "type" : "SCALAR",
      "max" : [len(positions) - 1],
      "min" : [0]
    }
    output["accessors"].append(index_accessor)
    position_buffer_view  = {
      "buffer" : len(output['buffers']) - 1,
      "byteOffset" : indices_byte_length,
      "byteLength" : positions_byte_length,
      "target" : 34962
    }
    output["bufferViews"].append(position_buffer_view)
    position_accessor = {
      "bufferView" : len(output['bufferViews']) - 1,
      "byteOffset" : 0,
      "componentType" : 5126,
      "count" : len(positions),
      "type" : "VEC3",
      "max" : [ bbox.xmax, bbox.ymax, bbox.zmax ],
      "min" : [ bbox.xmin, bbox.ymin, bbox.zmin ]
    }
    output["accessors"].append(position_accessor)
    
    normals_buffer_view  = {
      "buffer" : len(output['buffers']) - 1,
      "byteOffset" : indices_byte_length + positions_byte_length,
      "byteLength" : normals_byte_length,
      "target" : 34962
    }
    output["bufferViews"].append(normals_buffer_view)
    normals_accessor = {
      "bufferView" : len(output['bufferViews']) - 1,
      "byteOffset" : 0,
      "componentType" : 5126,
      "count" : len(normals),
      "type" : "VEC3",
    }
    output["accessors"].append(normals_accessor)
    
    uvs_buffer_view  = {
      "buffer" : len(output['buffers']) - 1,
      "byteOffset" : indices_byte_length + positions_byte_length + normals_byte_length,
      "byteLength" : uvs_byte_length,
      "target" : 34962
    }
    output["bufferViews"].append(uvs_buffer_view)
    uvs_accessor = {
      "bufferView" : len(output['bufferViews']) - 1,
      "byteOffset" : 0,
      "componentType" : 5126,
      "count" : len(uvs),
      "type" : "VEC2",
    }
    output["accessors"].append(uvs_accessor)

#TODO: Only store one instance of each mat
def addMaterial(mesh):
    pbr = {}
    mat_def = {'pbrMetallicRoughness': pbr}
    
    shadingGrps = maya.cmds.listConnections(mesh,type='shadingEngine')
    # glTF only allows one materical per mesh, so we'll just grab the first one.
    shader = maya.cmds.ls(maya.cmds.listConnections(shadingGrps),materials=True)[0]
    color_conn = maya.cmds.listConnections(shader+'.color')
    trans = list(maya.cmds.getAttr(shader+'.transparency')[0])
    trans = sum(trans) / float(len(trans))
    if color_conn and maya.cmds.objectType(color_conn[0]) == 'file':
        file_node = color_conn[0]
        file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
        file_name = os.path.basename(file_path)
        shutil.copy(file_path, output_dir)
        output['images'].append({'uri':file_name})
        output['textures'].append({'source':len(output['images'])-1})
        color_tx_id = len(output['textures'])-1
        pbr['baseColorTexture'] = {'index':color_tx_id}
    else:
        color = list(maya.cmds.getAttr(shader+'.color')[0])
        color.append(1-trans)
        pbr['baseColorFactor'] = color
    
    
    pbr['metallicFactor'] = 0
    pbr['roughnessFactor'] = 0
    output['materials'].append(mat_def)
    return len(output['materials']) - 1
    
class BoundingBox(object):
    xmin = 0
    ymin = 0
    zmin = 0
    xmax = 0
    ymax = 0
    zmax = 0

def getVertices_test(mesh):
    maya.cmds.select(mesh)
    selList = OpenMaya.MSelectionList()
    OpenMaya.MGlobal.getActiveSelectionList(selList)
    meshPath = OpenMaya.MDagPath()
    selList.getDagPath(0, meshPath)
    meshIt = OpenMaya.MItMeshFaceVertex(meshPath)
    meshFn = OpenMaya.MFnMesh(meshPath)
    do_color = False
    if meshFn.numColorSets():
        do_color=True
        print "doing color"
    all_indices = []
    all_positions = [None]*meshFn.numVertices()
    all_normals = []#[None]*meshFn.numVertices()
    all_colors = []
    uvs = []#[None]*meshFn.numUVs()
    norm = OpenMaya.MVector()
    uv_util = OpenMaya.MScriptUtil()
    uv_util.createFromList([0,0], 2 )
    uv_ptr = uv_util.asFloat2Ptr()
    id_util = OpenMaya.MScriptUtil()
    id_util.createFromInt(0)
    uv_id_ptr = id_util.asIntPtr()
    bbox = BoundingBox()
    while not meshIt.isDone():
        vert_id = meshIt.vertId()
        all_indices.append(vert_id)
        pos = meshIt.position()
        all_positions[vert_id] = (pos.x, pos.y, pos.z)
        meshIt.getNormal(norm)
        all_normals.append((norm.x, norm.y, norm.z))
        meshIt.getUV(uv_ptr)
        u = uv_util.getFloat2ArrayItem( uv_ptr, 0, 0 )
        v = uv_util.getFloat2ArrayItem( uv_ptr, 0, 1 )
        meshIt.getUVIndex(uv_id_ptr)
        uv_id = id_util.getInt(uv_id_ptr)
        uvs.append((u, v))

        if pos.x > bbox.xmax:
            bbox.xmax = pos.x
        elif pos.y > bbox.ymax:
            bbox.ymax = pos.y
        elif pos.z > bbox.zmax:
            bbox.zmax = pos.z
        elif pos.x < bbox.xmin:
            bbox.xmin = pos.x
        elif pos.y < bbox.ymin:
            bbox.ymin = pos.y
        elif pos.z < bbox.zmin:
            bbox.zmin = pos.z   
        meshIt.next()
    print 'indices: ', len(all_indices) 
    print 'positions: ', len(all_positions) 
    print 'normals: ', len(all_normals) 
    print 'uvs: ', len(uvs) 
    print uvs
    return (all_indices, all_positions, all_normals, all_colors, uvs, bbox)
    
def getVertices_old(mesh):
    maya.cmds.select(mesh)
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
    all_indices = []
    all_positions = [None]*meshFn.numVertices()
    all_normals = [None]*meshFn.numVertices()
    all_colors = [None]*meshFn.numVertices()
    uvs = [None]*meshFn.numUVs()
    indices = OpenMaya.MIntArray()
    points = OpenMaya.MPointArray()
    if do_color:
        vertexColorList = OpenMaya.MColorArray()
        meshFn.getFaceVertexColors(vertexColorList)
    #meshIt.hasUVs()
    u_list = OpenMaya.MFloatArray()
    v_list = OpenMaya.MFloatArray()
    meshFn.getUVs(u_list, v_list, meshFn.currentUVSetName())
    for x in range(0, len(u_list)):
        uvs[x] = (u_list[x], v_list[x])
    normal = OpenMaya.MVector()
    bbox = BoundingBox()
    while not meshIt.isDone():
        meshIt.getTriangles(points, indices)
        #meshIt.getUVs(u_list, v_list)
        print u_list.length()
        print indices.length()
        print points.length()
        for x in range(0, indices.length()):
            all_indices.append(indices[x])
            all_positions[indices[x]] = (points[x].x, points[x].y, points[x].z)
            meshFn.getFaceVertexNormal(meshIt.index(),indices[x],normal)
            all_normals[indices[x]] = (normal.x, normal.y, normal.z)
            #uvs[indices[x]] = (u_list[x], v_list[x])
            if do_color:
                color = vertexColorList[indices[x]]
                all_colors[indices[x]] = (color.r, color.g, color.b)
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
    print "uvs: ", len(uvs)
    print uvs
    return (all_indices, all_positions+all_positions, all_normals+all_normals, all_colors, uvs, bbox)

def getVertices(mesh):
    maya.cmds.select(mesh)
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
            #TODO: flip UVs in V
            u = uv_util.getFloat2ArrayItem( uv_ptr, 0, 0 )
            v = uv_util.getFloat2ArrayItem( uv_ptr, 0, 1 )
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
    print 'indices: ', len(indices) 
    print 'positions: ', len(positions) 
    print 'normals: ', len(normals) 
    print "uvs: ", len(uvs)
    print uvs
    return (indices, positions, normals, all_colors, uvs, bbox)    

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

def validate():
    offset = output["bufferViews"][0]["byteOffset"]
    length = output["bufferViews"][0]["byteLength"]
    stream = output["buffers"][0]["uri"].split("data:application/octet-stream;base64,")[-1]
    byteStr = base64.b64decode(stream)
    byteStr = byteStr[offset:length]
    ints = []
    for i in range(0, len(byteStr), 2):
        ints.append(struct.unpack("<H", byteStr[i:i+2])[0])
        ints[len(ints)-1]
    print len(ints)
    print ints
    
    offset = output["bufferViews"][1]["byteOffset"]
    length = output["bufferViews"][1]["byteLength"]
    stream = output["buffers"][0]["uri"].split("data:application/octet-stream;base64,")[-1]
    byteStr = base64.b64decode(stream)
    byteStr = byteStr[offset:offset+length]
    points = []
    for i in range(0, len(byteStr), 12):
        points.append(struct.unpack("<fff", byteStr[i:i+12]))
        
    print len(points)
    print points
    