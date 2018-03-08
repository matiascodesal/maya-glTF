import json
import struct
import sys
import base64
import maya.cmds
import maya.OpenMaya as OpenMaya
import shutil
import os

output = {
            "asset": { 
                "version": "2.0", 
                "generator": "maya-glTFExporter", 
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
output_file = 'C:/tmp_data/data.gltf'
output_dir = os.path.dirname(output_file)
def main():
    createScene()
    for transform in maya.cmds.ls(assemblies=True):
        node_index = addNode(transform)
        # add the node index to list of top nodes for the scene
        output["scenes"][0]["nodes"].append(node_index)
    #validate()
    with open(output_file, 'w') as outfile:
        json.dump(output, outfile)
    
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
    