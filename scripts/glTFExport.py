from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import json
import struct
import os
import sys
import base64
import math
import shutil
import time

import maya.cmds
import maya.OpenMaya as OpenMaya
try:
    from PySide.QtGui import QImage, QColor, qRed, qGreen, qBlue, QImageWriter
    from PySide.QtCore import QByteArray
except ImportError:
    from PySide2.QtGui import QImage, QColor, qRed, qGreen, qBlue, QImageWriter
    from PySide2.QtCore import QByteArray

# TODO don't export hidden nodes?

def timeit(method):

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print('%r (%r, %r) %2.2f sec' % \
              (method.__name__, args, kw, te-ts))
        return result

    return timed

class ResourceFormats(object):
    EMBEDDED = 'embedded'
    SOURCE = 'source'
    BIN = 'bin'

class AnimOptions(object):
    NONE = 'none'
    KEYED = 'keyed'
    BAKED = 'baked'

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
    anim = 'keyed'
    vflip=True
    out_file = ''
    _out_dir = ''
    _out_basename = ''
    
    @classmethod
    def set_defaults(cls):
        cls.file_format = 'glb'
        cls.resource_format = 'bin'
        cls.anim = 'keyed'
        cls.vflip=True
        cls.out_file = ''
    
    @classproperty
    def out_bin(cls):
        return cls.out_basename + '.bin'
    
    @classproperty    
    def out_basename(cls):
        base, ext = os.path.splitext(cls.out_file)
        cls._out_basename = os.path.basename(base)
        return cls._out_basename
        
    @classproperty
    def out_dir(cls):
        cls._out_dir = os.path.dirname(cls.out_file)
        return cls._out_dir
    
    
class GLTFExporter(object):
    # TODO: Add VFlip option
    def __init__(self, file_path, resource_format='bin', anim='keyed', vflip=True):
        self.output = {
            "asset": { 
                "version": "2.0", 
                "generator": "maya-glTFExport", 
            }
        }
        ExportSettings.set_defaults()
        Scene.set_defaults()
        Node.set_defaults()
        Mesh.set_defaults()
        Material.set_defaults()
        Camera.set_defaults()
        Animation.set_defaults()
        Image.set_defaults()
        Texture.set_defaults()
        Buffer.set_defaults()
        BufferView.set_defaults()
        Accessor.set_defaults()
        
        ExportSettings.out_file = file_path
        ExportSettings.resource_format = resource_format
        ExportSettings.anim = anim
        ExportSettings.vflip = vflip
        
    def run(self):
        if not ExportSettings.out_file:
            ExportSettings.out_file = maya.cmds.fileDialog2(caption="Specify a name for the file to export.",
                                                        fileMode=0)[0]
        basename, ext = os.path.splitext(ExportSettings.out_file)
        if not ext in ['.glb', '.gltf']:
            raise Exception("Output file must have gltf or glb extension.")
        ExportSettings.file_format = ext[1:]  
        
        if not os.path.exists(ExportSettings.out_dir):
            os.makedirs(ExportSettings.out_dir)
        
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
        if Animation.instances and Animation.instances[0].channels:
            self.output['animations'] = Animation.instances
        if Buffer.instances:
            self.output['buffers'] = Buffer.instances
        if BufferView.instances:
            self.output['bufferViews'] = BufferView.instances
        if Accessor.instances:
            self.output['accessors'] = Accessor.instances
        
        if not Scene.instances[0].nodes:
            raise RuntimeError('Scene is empty.  No file will be exported.')
        if ExportSettings.file_format == 'glb':
            
            json_str = json.dumps(self.output, sort_keys=True, separators=(',', ':'), cls=GLTFEncoder)
            json_bin = bytearray(json_str.encode(encoding='latin-1'))
            # 4-byte-aligned
            aligned_len = (len(json_bin) + 3) & ~3
            for i in range(aligned_len - len(json_bin)):
                json_bin.extend(b' ')

            bin_out = bytearray()
            file_length = 12 + 8 + len(json_bin)
            if Buffer.instances:
                buffer = Buffer.instances[0]
                file_length += 8 + len(buffer)
            # Magic number
            bin_out.extend(struct.pack('<I', 0x46546C67)) # glTF in binary
            bin_out.extend(struct.pack('<I', 2)) # version number
            bin_out.extend(struct.pack('<I', file_length))
            bin_out.extend(struct.pack('<I', len(json_bin)))
            bin_out.extend(struct.pack('<I', 0x4E4F534A)) # JSON in binary
            bin_out += json_bin
            
            if Buffer.instances:
                bin_out.extend(struct.pack('<I', len(buffer))) 
                bin_out.extend(struct.pack('<I', 0x004E4942)) # BIN in binary
                bin_out += buffer.byte_str
            
            with open(ExportSettings.out_file, 'wb') as outfile:
                outfile.write(bin_out)
        else:
            with open(ExportSettings.out_file, 'w') as outfile:
                json.dump(self.output, outfile, cls=GLTFEncoder)
            
            if (ExportSettings.resource_format == ResourceFormats.BIN
                    and Buffer.instances):
                buffer = Buffer.instances[0]
                with open(ExportSettings.out_dir + "/" + buffer.uri, 'wb') as outfile:
                    outfile.write(buffer.byte_str)
        
def export(file_path=None, resource_format='bin', anim='keyed', vflip=True, selection=False):
    GLTFExporter(file_path, resource_format, anim, vflip).run()
    
        
class GLTFEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ExportItem):
            return obj.to_json()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
   
class ExportItem(object):
    def __init__(self, name=None):
        self.name = name
    
    
class Scene(ExportItem):
    '''Needs to add itself to scenes'''
    instances = []
    maya_nodes = None
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, name="defaultScene", maya_nodes=None):
        super(Scene, self).__init__(name=name)
        self.index = len(Scene.instances)
        Scene.instances.append(self)
        anim = None
        if not ExportSettings.anim == AnimOptions.NONE:
            anim = Animation('defaultAnimation')
        self.nodes = []
        if maya_nodes:
            self.maya_nodes = maya_nodes
        else:
            self.maya_nodes = maya.cmds.ls(assemblies=True, long=True)
        for transform in self.maya_nodes:
            if transform not in Camera.default_cameras:
                self.nodes.append(Node(transform, anim))
        
    def to_json(self):
        scene_def = {"name":self.name, "nodes":[node.index for node in self.nodes]}
        return scene_def


class Node(ExportItem):
    '''Needs to add itself to nodes list, possibly node children, and possibly scene'''
    instances = []
    maya_node = None
    matrix = None
    translation = None
    rotation = None
    scale = None
    camera = None
    mesh = None
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, maya_node, anim=None):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Node, self).__init__(name=name)
        self.index = len(Node.instances)
        Node.instances.append(self)
        self.children = []
        self.translation = maya.cmds.getAttr(self.maya_node+'.translate')[0]
        self.rotation = self._get_rotation_quaternion()
        self.scale = maya.cmds.getAttr(self.maya_node+'.scale')[0]
        if anim:
            self._get_animation(anim)
        maya_children = maya.cmds.listRelatives(self.maya_node, children=True, fullPath=True)
        if maya_children:
            for child in maya_children:
                childType = maya.cmds.objectType(child)
                if childType == 'mesh' and not maya.cmds.getAttr(child + ".intermediateObject"):
                    mesh = Mesh(child)
                    self.mesh = mesh 
                elif childType == 'camera':
                    if maya.cmds.camera(child, query=True, orthographic=True):
                        cam = OrthographicCamera(child)
                    else:
                        cam = PerspectiveCamera(child)
                    self.camera = cam
                elif childType == 'transform':
                    node = Node(child, anim)
                    self.children.append(node)
    
    def _get_animation(self, anim):
        if maya.cmds.keyframe(self.maya_node, attribute='translate', query=True, keyframeCount=True):
            translation_channel = AnimationChannel(self, 'translation')
            anim.add_channel(translation_channel)
            anim.add_sampler(translation_channel.sampler)
        if maya.cmds.keyframe(self.maya_node, attribute='rotate', query=True, keyframeCount=True):
            rotation_channel = AnimationChannel(self, 'rotation')
            anim.add_channel(rotation_channel)
            anim.add_sampler(rotation_channel.sampler)
        if maya.cmds.keyframe(self.maya_node, attribute='scale', query=True, keyframeCount=True):
            scale_channel = AnimationChannel(self, 'scale')
            anim.add_channel(scale_channel)
            anim.add_sampler(scale_channel.sampler)
        
    def _get_rotation_quaternion(self):
        obj=OpenMaya.MObject()
        #make a object of type MSelectionList
        sel_list=OpenMaya.MSelectionList()
        #add something to it
        #you could retrieve this from function or the user selection
        sel_list.add(self.maya_node)
        #fill in the MObject
        sel_list.getDependNode(0,obj)
        #check if its a transform
        if (obj.hasFn(OpenMaya.MFn.kTransform)):
            quat = OpenMaya.MQuaternion()
            #then we can add it to transfrom Fn
            #Fn is basically the collection of functions for given objects
            xform=OpenMaya.MFnTransform(obj)
            xform.getRotation(quat)
            # glTF requires normalize quat
            quat.normalizeIt()
        
        py_quat = [quat[x] for x in range(4)]
        return py_quat       
    
    def to_json(self):
        node_def = {}
        if self.matrix:
            node_def['matrix'] = self.matrix
        if self.translation:
            node_def['translation'] = self.translation
        if self.rotation:
            node_def['rotation'] = self.rotation
        if self.scale:
            node_def['scale'] = self.scale
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
    maya_node = None
    material = None
    indices_accessor = None
    position_accessor = None
    normal_accessor = None
    texcoord0_accessor = None
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
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
        # We currently only support one materical per mesh, so we'll just grab the first one.
        # TODO: support facegroups as glTF primitivies to support one material per facegroup
        shader = maya.cmds.ls(maya.cmds.listConnections(shadingGrps),materials=True)[0]
        self.material = Material(shader)
    
    @timeit
    def _getMeshData(self):
        maya.cmds.select(self.maya_node)
        selList = OpenMaya.MSelectionList()
        OpenMaya.MGlobal.getActiveSelectionList(selList)
        meshPath = OpenMaya.MDagPath()
        selList.getDagPath(0, meshPath)
        meshIt = OpenMaya.MItMeshPolygon(meshPath)
        meshFn = OpenMaya.MFnMesh(meshPath)
        dagFn = OpenMaya.MFnDagNode(meshPath)
        boundingBox = dagFn.boundingBox()
        do_color = False
        if meshFn.numColorSets():
            do_color=True
        indices = []
        positions = [None]*meshFn.numVertices()
        normals = [None]*meshFn.numVertices()
        colors = [None]*meshFn.numVertices()
        uvs = [None]*meshFn.numVertices()
        ids = OpenMaya.MIntArray()
        points = OpenMaya.MPointArray()
        if do_color:
            vertexColorList = OpenMaya.MColorArray()
            meshFn.getFaceVertexColors(vertexColorList)
        normal = OpenMaya.MVector()
        face_verts = OpenMaya.MIntArray()
        polyNormals = OpenMaya.MFloatVectorArray()
        meshFn.getNormals(polyNormals)
        uv_util = OpenMaya.MScriptUtil()
        uv_util.createFromList([0,0], 2 )
        uv_ptr = uv_util.asFloat2Ptr()
        while not meshIt.isDone():
            meshIt.getTriangles(points, ids)  
            meshIt.getVertices(face_verts)
            face_vertices = list(face_verts)
            for point, vertex_index in zip(points, ids):
                indices.append(vertex_index)
                pos = (point.x, point.y, point.z)
                face_vert_id = face_vertices.index(vertex_index)
                norm_id = meshIt.normalIndex(face_vert_id)
                norm = polyNormals[norm_id]
                norm = (norm.x, norm.y, norm.z)
                meshIt.getUV(face_vert_id, uv_ptr, meshFn.currentUVSetName())
                u = uv_util.getFloat2ArrayItem( uv_ptr, 0, 0 )
                v = uv_util.getFloat2ArrayItem( uv_ptr, 0, 1 )
                # flip V for openGL
                # This fails if the the UV is exactly on the border (e.g. (0.5,1))
                # but we really don't know what udim it's in for that case.
                if ExportSettings.vflip:
                    v = int(v) + (1 - (v % 1))
                uv = (u, v)
                if not positions[vertex_index]:   
                    positions[vertex_index] = pos
                    normals[vertex_index] = norm
                    uvs[vertex_index] = uv
                elif not ( positions[vertex_index] == pos and
                            normals[vertex_index] == norm and
                            uvs[vertex_index] == uv):
                    positions.append(pos)
                    normals.append(norm)
                    uvs.append(uv)
                    indices[-1] = len(positions)-1
                        
                
                if do_color:
                    color = vertexColorList[vertex_index]
                    colors[vertex_index] = (color.r, color.g, color.b)   
            next(meshIt)

        if not len(Buffer.instances):
            primary_buffer = Buffer('primary_buffer')
        else:
            primary_buffer = Buffer.instances[0]
        
        if len(positions) >= 0xffff:
            idx_component_type = ComponentTypes.UINT
        else:
            idx_component_type = ComponentTypes.USHORT
        self.indices_accessor = Accessor(indices, "SCALAR", idx_component_type, 34963, primary_buffer, name=self.name + '_idx')
        self.indices_accessor.min_ = [0]
        self.indices_accessor.max_ = [len(positions) - 1]
        self.position_accessor = Accessor(positions, "VEC3", ComponentTypes.FLOAT, 34962, primary_buffer, name=self.name + '_pos')
        bbox_max = boundingBox.max()
        self.position_accessor.max_ = [bbox_max[0],bbox_max[1],bbox_max[2]]
        bbox_min = boundingBox.min()
        self.position_accessor.min_ =  [bbox_min[0],bbox_min[1],bbox_min[2]]
        self.normal_accessor = Accessor(normals, "VEC3", ComponentTypes.FLOAT, 34962, primary_buffer, name=self.name + '_norm')
        self.texcoord0_accessor = Accessor(uvs, "VEC2", ComponentTypes.FLOAT, 34962, primary_buffer, name=self.name + '_uv')

        

class Material(ExportItem):
    '''Needs to add itself to materials and meshes list'''
    instances = []
    maya_node = None
    base_color_factor = None
    base_color_texture = None
    metallic_factor = None
    roughness_factor = None
    metallic_roughness_texture = None
    normal_texture = None
    occlusion_texture = None
    emissive_factor = None
    emissive_texture = None
    transparency = None
    default_material_id = None
    supported_materials = ['lambert','phong','blinn','aiStandardSurface', 'StingrayPBS']
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
        cls.default_material_id = None
    
    def __new__(cls, maya_node, *args, **kwargs):
        if maya_node:
            name = maya.cmds.ls(maya_node, shortNames=True)[0]
            matches = [mat for mat in Material.instances if mat.name == name]
            if matches:
                return matches[0]
            
            maya_obj_type = maya.cmds.objectType(maya_node)
            if maya_obj_type not in cls.supported_materials:
                print("Shader {} is not a supported shader type: {}".format(maya_node, maya_obj_type))
                return cls._get_default_material()
        
        return super(Material, cls).__new__(cls, *args, **kwargs)
        
    def __init__(self, maya_node):
        if hasattr(self, 'index'):
            return
        
        if maya_node is None:
            self.base_color_factor = [0.5, 0.5, 0.5, 1]
            self.metallic_factor = 0
            self.roughness_factor = 1
            name = 'glTFDefaultMaterial'
            super(Material, self).__init__(name=name)
            self.index = len(Material.instances)
            self.__class__.default_material_id = self.index
            Material.instances.append(self)
            return
             
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Material, self).__init__(name=name)
        
        self.index = len(Material.instances)
        Material.instances.append(self)
        
        maya_obj_type = maya.cmds.objectType(maya_node)
        if maya_obj_type in ['phong', 'lambert', 'blinn']:
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
            
            if maya_obj_type == 'lambert':
                self.metallic_factor = 0
                self.roughness_factor = 1
            elif maya_obj_type == 'blinn':
                self.metallic_factor = maya.cmds.getAttr(self.maya_node+'.specularRollOff')
                self.roughness_factor = maya.cmds.getAttr(self.maya_node+'.eccentricity') 
            elif maya_obj_type == 'phong':
                self.metallic_factor = 1
                self.roughness_factor = 1 - min(1, maya.cmds.getAttr(self.maya_node+'.cosinePower') / 2000)
        elif maya_obj_type == 'aiStandardSurface':
            color_conn = maya.cmds.listConnections(self.maya_node+'.baseColor')
            if color_conn and maya.cmds.objectType(color_conn[0]) == 'file':
                file_node = color_conn[0]
                file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
                image = Image(file_path)
                self.base_color_texture = Texture(image)
            else:
                color = list(maya.cmds.getAttr(self.maya_node+'.baseColor')[0])
                self.base_color_factor = color
                opacity = list(maya.cmds.getAttr(self.maya_node+'.opacity')[0])
                opacity = sum(opacity) / float(len(opacity))
                self.base_color_factor.append(opacity)
            self.metallic_factor = maya.cmds.getAttr(self.maya_node+'.metalness')
            self.roughness_factor = maya.cmds.getAttr(self.maya_node+'.specularRoughness')
        elif maya_obj_type == 'StingrayPBS':
            color_conn = maya.cmds.listConnections(self.maya_node+'.TEX_color_map')
            if (color_conn and maya.cmds.objectType(color_conn[0]) == 'file'
                    and maya.cmds.getAttr(self.maya_node+'.use_color_map')):
                file_node = color_conn[0]
                file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
                image = Image(file_path)
                self.base_color_texture = Texture(image)
            else:
                color = list(maya.cmds.getAttr(self.maya_node+'.base_color')[0])
                self.base_color_factor = color
                self.base_color_factor.append(1) # opacity
            
            metallic_conn = maya.cmds.listConnections(self.maya_node+'.TEX_metallic_map')
            roughness_conn = maya.cmds.listConnections(self.maya_node+'.TEX_roughness_map')
            if (metallic_conn and maya.cmds.objectType(metallic_conn[0]) == 'file'
                    and maya.cmds.getAttr(self.maya_node+'.use_metallic_map')
                    and roughness_conn and maya.cmds.objectType(roughness_conn[0]) == 'file'
                    and maya.cmds.getAttr(self.maya_node+'.use_roughness_map')):
                metallic_file_node = metallic_conn[0]
                metallic_file_path = maya.cmds.getAttr(metallic_file_node+'.fileTextureName')
                roughness_file_node = roughness_conn[0]
                roughness_file_path = maya.cmds.getAttr(roughness_file_node+'.fileTextureName')
                metalrough_file_path, metalrough_qimage = self._create_metallic_roughness_map(metallic_file_path, roughness_file_path)
                image = Image(metalrough_file_path, metalrough_qimage)
                self.metallic_roughness_texture = Texture(image)
            else:
                self.metallic_factor = maya.cmds.getAttr(self.maya_node+'.metallic')
                self.roughness_factor = maya.cmds.getAttr(self.maya_node+'.roughness')
                
            normal_conn = maya.cmds.listConnections(self.maya_node+'.TEX_normal_map')
            if (normal_conn and maya.cmds.objectType(normal_conn[0]) == 'file'
                    and maya.cmds.getAttr(self.maya_node+'.use_normal_map')):
                file_node = normal_conn[0]
                file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
                image = Image(file_path)
                self.normal_texture = Texture(image)
            
            # Not all Stingray preset shaders have an AO map attribute
            if maya.cmds.attributeQuery("TEX_ao_map", node=self.maya_node, exists=True):    
                ao_conn = maya.cmds.listConnections(self.maya_node+'.TEX_ao_map')
                if (ao_conn and maya.cmds.objectType(ao_conn[0]) == 'file'
                        and maya.cmds.getAttr(self.maya_node+'.use_ao_map')):
                    file_node = ao_conn[0]
                    file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
                    image = Image(file_path)
                    self.occlusion_texture = Texture(image)
            
            emissive_conn = maya.cmds.listConnections(self.maya_node+'.TEX_emissive_map')
            if (emissive_conn and maya.cmds.objectType(emissive_conn[0]) == 'file'
                    and maya.cmds.getAttr(self.maya_node+'.use_emissive_map')):
                file_node = emissive_conn[0]
                file_path = maya.cmds.getAttr(file_node+'.fileTextureName')
                image = Image(file_path)
                self.emissive_texture = Texture(image)
                emissive_intensity = maya.cmds.getAttr(self.maya_node+'.emissive_intensity')
                self.emissive_factor = [emissive_intensity, emissive_intensity, emissive_intensity]
            else:
                emissive = list(maya.cmds.getAttr(self.maya_node+'.emissive')[0])
                self.emissive_factor = emissive
                
            
    
    def _create_metallic_roughness_map(self, metal_map, rough_map):

        metal = QImage(metal_map)
        rough = QImage(rough_map)
        metal_pixel = QColor()

        metal = metal.convertToFormat(QImage.Format_RGB32);
        rough = rough.convertToFormat(QImage.Format_RGB32);
        metal_uchar_ptr = metal.bits()
        rough_uchar_ptr = rough.bits()
        if (not metal.width() == rough.width()
                or not metal.height() == rough.height()):
            raise RuntimeError("Error processing material: {}. Metallic map and roughness map must have same dimensions.".format(self.maya_node))
        width = metal.width();
        height = metal.height();

        i = 0
        for y in range(height):
            for x in range(width):
                metal_color = struct.unpack('I', metal_uchar_ptr[i:i+4])[0]
                rough_color = struct.unpack('I', rough_uchar_ptr[i:i+4])[0]
                metal_pixel.setRgb(0, qGreen(rough_color), qBlue(metal_color))
                metal_uchar_ptr[i:i+4] = struct.pack('I', metal_pixel.rgb())
                i+=4
                
        output = ExportSettings.out_dir + "/"+self.name+"_metalRough.jpg"
        return output, metal
    
    @classmethod
    def _get_default_material(cls):
        if cls.default_material_id:
            return Material.instances[cls.default_material_id]
        else:
            return Material(None)
    
    def to_json(self):
        pbr = {}
        # TODO: Potentially add alphaMode=OPAQUE for textured materials that don't have
        # an alpha channel or have an opaque alpha
        # TODO: Support doubleSided property
        mat_def = {'pbrMetallicRoughness': pbr}
        mat_def['alphaMode'] = 'BLEND'
        if self.base_color_texture:
            pbr['baseColorTexture'] = {'index':self.base_color_texture.index}
            color = QImage(self.base_color_texture.image.src_file_path)
            if not color.hasAlphaChannel():
                mat_def['alphaMode'] = 'OPAQUE'
        else:
            pbr['baseColorFactor'] = self.base_color_factor
            if len(self.base_color_factor) == 4 \
                    and self.base_color_factor[3] < 1:
                mat_def['alphaMode'] = 'BLEND'
            else:
                mat_def['alphaMode'] = 'OPAQUE'
        
        if self.metallic_roughness_texture:
            pbr['metallicRoughnessTexture'] = {'index':self.metallic_roughness_texture.index}
        else:
            pbr['metallicFactor'] = self.metallic_factor
            pbr['roughnessFactor'] = self.roughness_factor
        if self.normal_texture:
            mat_def['normalTexture'] = {'index':self.normal_texture.index}
        if self.occlusion_texture:
            mat_def['occlusionTexture'] = {'index':self.occlusion_texture.index}
        if self.emissive_texture:
            mat_def['emissiveTexture'] = {'index':self.emissive_texture.index}
        if self.emissive_factor:
            mat_def['emissiveFactor'] = self.emissive_factor
        
        return mat_def


class Camera(ExportItem):
    '''Needs to add itself to node and cameras list'''
    instances = []
    default_cameras = ['|top', '|front', '|side', '|persp']
    maya_node = None
    type_ = None
    znear = 0.1
    zfar = 1000
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, maya_node):
        self.maya_node = maya_node
        name = maya.cmds.ls(maya_node, shortNames=True)[0]
        super(Camera, self).__init__(name=name)
        self.index = len(Camera.instances)
        self.znear = maya.cmds.camera(self.maya_node, query=True, nearClipPlane=True)
        self.zfar = maya.cmds.camera(self.maya_node, query=True, farClipPlane=True)
        
        
    def to_json(self):
        if not self.type_:
            # TODO: use custom error or ensure type is set
            raise RuntimeError("Type property was not defined")
        camera_def = {'type' : self.type_}
        camera_def[self.type_] = {'znear' : self.znear,
                                    'zfar' : self.zfar}
        return camera_def
 
    
class PerspectiveCamera(Camera):
    type_= 'perspective'
    
    def __init__(self, maya_node):
        super(PerspectiveCamera, self).__init__(maya_node)
        self.aspect_ratio = maya.cmds.camera(self.maya_node, query=True, aspectRatio=True)
        self.yfov = math.radians(maya.cmds.camera(self.maya_node, query=True, verticalFieldOfView=True))
        Camera.instances.append(self)
        
    def to_json(self):
        camera_def = super(PerspectiveCamera, self).to_json()
        camera_def[self.type_]['aspectRatio'] = self.aspect_ratio
        camera_def[self.type_]['yfov'] = self.yfov
        return camera_def
    
class OrthographicCamera(Camera):
    type_= 'orthographic'
    xmag = 1.0
    ymag = 1.0
    
    def __init__(self, maya_node):
        super(OrthographicCamera, self).__init__(maya_node)
        self.xmag = maya.cmds.camera(self.maya_node, query=True, orthographicWidth=True)
        self.ymag = self.xmag
        Camera.instances.append(self)
    
    def to_json(self):
        camera_def = super(OrthographicCamera, self).to_json()
        camera_def[self.type_]['xmag'] = self.xmag
        camera_def[self.type_]['ymag'] = self.ymag
        return camera_def
    
    
class Animation(ExportItem):
    instances = []
    channels = None
    samplers = None
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, name=''):
        super(Animation, self).__init__(name)
        self.instances.append(self)
        self.channels = []
        self.samplers = []
    
    def add_channel(self, channel):
        channel.index = len(self.channels)
        self.channels.append(channel)
    
    def add_sampler(self, sampler):
        sampler.index = len(self.samplers)
        self.samplers.append(sampler)
        
    def to_json(self):
        anim_def = {'channels': self.channels, 'samplers': self.samplers}
        return anim_def
        
    
class AnimationChannel(ExportItem):
    maya_node = None
    node = None
    path = None
    sampler = None
    
    def __init__(self, node, path):
        self.maya_node = node.maya_node
        self.node = node
        self.path = path
        name = maya.cmds.ls(self.maya_node, shortNames=True)[0]
        name = '{}_{}_channel'.format(name, path)
        super(AnimationChannel, self).__init__(name)
        self.sampler = AnimationSampler(self)
            
    
    def to_json(self):
        channel_def = {'target':{}, 'sampler': self.sampler.index}
        channel_def['target']['node'] = self.node.index
        channel_def['target']['path'] = self.path
        return channel_def
        

class AnimationSampler(ExportItem):
    input_accessor = None
    output_accessor = None
    interpolation = None
    attr_map = {'translation':'translate', 'rotation':'rotate', 'scale':'scale'}
    interp_map = {'spline':'CUBICSPLINE','linear':'LINEAR',
                    'auto':'LINEAR','fast':'CUBICSPLINE',
                    'slow':'CUBICSPLINE','step':'STEP',
                    'stepnext':'STEP','fixed':'CUBICSPLINE',
                    'clamped':'CUBICSPLINE', 'plateau':'CUBICSPLINE'}
    time_map = {'game':15.0,'film':24.0,'pal':25.0,'ntsc':30.0,'show':48.0,'palf':50.0,'ntscf':60.0}
    
    def __init__(self, anim_channel):
        node = anim_channel.node
        path = anim_channel.path
        name = '{}_{}_sampler'.format(node, path)
        super(AnimationSampler, self).__init__(name)
        
        keyframes = maya.cmds.keyframe(node.maya_node, attribute=self.attr_map[path], query=True, timeChange=True)
        keyframes = sorted(list(set(keyframes)))
        self.interpolation = self._get_interpolation(node.maya_node, path, keyframes[0])
        
        values = []
        if path in ['translation', 'scale']:
            for keyframe in keyframes:
                # Use get attr at a time because not every attr might have a keyframe
                values.append(maya.cmds.getAttr(node.maya_node+'.'+self.attr_map[path], time=keyframe)[0])
        else:
            for keyframe in keyframes:
                maya.cmds.currentTime(keyframe, edit=True)
                values.append(node._get_rotation_quaternion())
        if not len(Buffer.instances):
            primary_buffer = Buffer('primary_buffer')
        else:
            primary_buffer = Buffer.instances[0]
        time_unit = maya.cmds.currentUnit(query=True, time=True)
        fps = self.time_map[time_unit]
        keyframes = [key/fps for key in keyframes]
        self.input_accessor = Accessor(keyframes, "SCALAR", ComponentTypes.FLOAT, None, primary_buffer, name=self.name + '_tTime')
        self.input_accessor.min_ = [keyframes[0]]
        self.input_accessor.max_ = [keyframes[-1]]
        if path in ['translation', 'scale']:
            self.output_accessor = Accessor(values, "VEC3", ComponentTypes.FLOAT, None, primary_buffer, name=self.name + '_tVal')
        else:
            self.output_accessor = Accessor(values, "VEC4", ComponentTypes.FLOAT, None, primary_buffer, name=self.name + '_tVal')
        
    def _get_interpolation(self, node, path, first_key):
        for axis in ['X','Y','Z']:   
            out_tangent = maya.cmds.keyTangent(node, attribute=self.attr_map[path]+axis, time=(first_key,first_key), query=True, outTangentType=True)
            if out_tangent:
                return self.interp_map[out_tangent[0]]
            
    def to_json(self):
        sampler_def = {'input':self.input_accessor.index, 
                        'output':self.output_accessor.index,
                        'interpolation':self.interpolation}
        return sampler_def
        
    
# TODO: check to see if the image has been used
class Image(ExportItem):
    '''Needs to be added to images list and it's texture'''
    instances = []
    name = None
    uri = None
    buffer_view = None
    mime_type = None
    src_file_path = ""
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, file_path, qimage=None):
        file_name = os.path.basename(file_path)
        self.src_file_path = file_path
        super(Image, self).__init__(name=file_name)
        self.index = len(Image.instances)
        Image.instances.append(self)
        base, ext = os.path.splitext(file_path)
        mime_suffix = ext.lower()[1:]
        if mime_suffix == 'jpg':
            mime_suffix = 'jpeg'
        self.mime_type = 'image/{}'.format(mime_suffix)
        
        # Need to write this out temporarily or permanently
        # depending on resource_format
        if qimage:
                writer = QImageWriter(file_path, QByteArray(bytes(str(mime_suffix).encode("latin-1"))));
                writer.write(qimage);
                # delete the write to close file handle
                del writer
                
        if ExportSettings.resource_format == ResourceFormats.SOURCE:
            if not qimage:
                shutil.copy(file_path, ExportSettings.out_dir)
            self.uri = file_name
        else:
            with open(file_path, 'rb') as f:
                img_bytes = f.read()
            
            # Remove the temp qimage because resource_format isn't source
            if qimage:
                os.remove(file_path)
            
            if (ExportSettings.resource_format == ResourceFormats.BIN
                    or ExportSettings.file_format == 'glb'):
                single_buffer = Buffer.instances[0]
                buffer_end = len(single_buffer)
                single_buffer.byte_str += img_bytes
                self.buffer_view = BufferView(single_buffer, buffer_end)
                
                # 4-byte-aligned
                aligned_len = (len(img_bytes) + 3) & ~3
                for i in range(aligned_len - len(img_bytes)):
                    single_buffer.byte_str += b'0'
                    
        if (ExportSettings.file_format == 'gltf' and
                ExportSettings.resource_format == ResourceFormats.EMBEDDED):
            self.uri = "data:application/octet-stream;base64," + base64.b64encode(img_bytes).decode("latin-1")
    
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
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
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
    byte_str = b""
    uri = ''
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, name=None):
        super(Buffer, self).__init__(name=name)
        self.index = len(Buffer.instances)
        Buffer.instances.append(self)
        if (ExportSettings.file_format == 'gltf'
                and ExportSettings.resource_format == ResourceFormats.BIN):
            self.uri = ExportSettings.out_bin
    
    def __len__(self):
        return len(self.byte_str)
    
    def append_data(self, data, type_):
        pack_type = '<' + type_
        packed_data = []
        for item in data:
            if isinstance(item, (list, tuple)):
                packed_data.append(struct.pack(pack_type, *item))
            else:
                packed_data.append(struct.pack(pack_type, item))
        self.byte_str += b''.join(packed_data)
        # 4-byte-aligned
        aligned_len = (len(self.byte_str) + 3) & ~3
        for i in range(aligned_len - len(self.byte_str)):
            self.byte_str += b'0'
    
    def to_json(self):
        buffer_def = {"byteLength" : len(self)}
        if self.uri and ExportSettings.resource_format == ResourceFormats.BIN:
            buffer_def['uri'] = self.uri
        elif ExportSettings.resource_format in [ResourceFormats.EMBEDDED, ResourceFormats.SOURCE]:
            buffer_def['uri'] = "data:application/octet-stream;base64," + base64.b64encode(self.byte_str).decode("latin-1")
        # no uri for GLB
        return buffer_def

class BufferView(ExportItem):
    instances = []
    buffer = None
    byte_offset = None
    byte_length = None
    target = None
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
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


class ComponentTypes(object):
    USHORT = 5123
    UINT = 5125
    FLOAT = 5126


class Accessor(ExportItem):
    instances = []
    buffer_view = None
    byte_offset = 0
    component_type = None
    count = None
    type_ = None
    src_data = None
    max_  = None
    min_ = None
    type_codes = {
        "SCALAR":1,
        "VEC2":2,
        "VEC3":3,
        "VEC4":4
    }
    component_type_codes = {
        ComponentTypes.USHORT:"H", # unsigned short
        ComponentTypes.UINT:"I", # unsigned int
        ComponentTypes.FLOAT:"f"  # float
    }
    
    @classmethod
    def set_defaults(cls):
        cls.instances = []
    
    def __init__(self, data, type_, component_type, target, buffer, name=None):
        super(Accessor, self).__init__(name=name)
        self.index = len(Accessor.instances)
        Accessor.instances.append(self)
        self.src_data = data
        self.component_type = component_type
        self.type_= type_
        byte_code = self.component_type_codes[component_type]*self.type_codes[type_]
        
        buffer_end = len(buffer)
        buffer.append_data(self.src_data, byte_code)
        self.buffer_view = BufferView(buffer, buffer_end, target)
        
    def to_json(self):
        accessor_def = {
          "bufferView" : self.buffer_view.index,
          "byteOffset" : self.byte_offset,
          "componentType" : self.component_type,
          "count" : len(self.src_data),
          "type" : self.type_
        }
        if self.max_:
            accessor_def['max'] = self.max_
        if self.min_:
            accessor_def['min'] = self.min_
        return accessor_def
