'''
MAP Client, a program to generate detailed musculoskeletal models for OpenSim.
    Copyright (C) 2012  University of Auckland
    
This file is part of MAP Client. (http://launchpad.net/mapclient)

    MAP Client is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    MAP Client is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with MAP Client.  If not, see <http://www.gnu.org/licenses/>..
'''
import os, re
from math import sqrt, acos, pi, sin, cos

from PySide import QtGui, QtCore

from segmentationstep.widgets.ui_segmentationwidget import Ui_SegmentationWidget
from segmentationstep.undoredo import CommandMovePlane

from opencmiss.zinc.context import Context
from opencmiss.zinc.field import Field
from opencmiss.zinc.glyph import Glyph
from opencmiss.zinc.material import Material
from opencmiss.zinc.sceneviewerinput import Sceneviewerinput
from zincwidget import button_map, ProjectionMode
# from opencmiss.zinc.scenecoordinatesystem import SCENECOORDINATESYSTEM_WINDOW_PIXEL_TOP_LEFT

DEFAULT_NORMAL_ARROW_SIZE = 25.0
DEFAULT_ROTATION_CENTRE_SIZE = 10.0

def tryint(s):
    try:
        return int(s)
    except:
        return s

def alphanum_key(s):
    """ Turn a string into a list of string and number chunks.
        "z23a" -> ["z", 23, "a"]
    """
    return [ tryint(c) for c in re.split('([0-9]+)', s) ]

def magnitude(v):
    return sqrt(sum(v[i] * v[i] for i in range(len(v))))

def add(u, v):
    return [ u[i] + v[i] for i in range(len(u)) ]

def sub(u, v):
    return [ u[i] - v[i] for i in range(len(u)) ]

def dot(u, v):
    return sum(u[i] * v[i] for i in range(len(u)))

def eldiv(u, v):
    return [u[i] / v[i] for i in range(len(u))]

def elmult(u, v):
    return [u[i] * v[i] for i in range(len(u))]

def normalize(v):
    vmag = magnitude(v)
    return [ v[i] / vmag  for i in range(len(v)) ]

def cross(u, v):
    c = [u[1] * v[2] - u[2] * v[1],
         u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]

    return c

def mult(u, c):
    return [u[i] * c for i in range(len(u))]

def div(u, c):
    return [u[i] / c for i in range(len(u))]

def rotmx(quaternion):
    '''
    This method takes a quaternion representing a rotation
    and turns it into a rotation matrix. 
    '''
    mag_q = magnitude(quaternion)
    norm_q = div(quaternion, mag_q)
    qw, qx, qy, qz = norm_q
    mx = [[qw * qw + qx * qx - qy * qy - qz * qz, 2 * qx * qy - 2 * qw * qz, 2 * qx * qz + 2 * qw * qy],
          [2 * qx * qy + 2 * qw * qz, qw * qw - qx * qx + qy * qy - qz * qz, 2 * qy * qz - 2 * qw * qx],
          [2 * qx * qz - 2 * qw * qy, 2 * qy * qz + 2 * qw * qx, qw * qw - qx * qx - qy * qy + qz * qz]]

    return mx

def mxmult(mx, u):
    return []

def matmult(a, b):
    return [dot(row_a, b) for row_a in a]

class FakeMouseEvent(object):

    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class PlaneMovementMode(object):

    NONE = 1
    NORMAL = 2
    ROTATION = 4



class PlaneMovement(object):

    def __init__(self, mode=PlaneMovementMode.NONE):
        self._mode = mode
        self._active = False

    def isActive(self):
        return self._active

    def mode(self):
        return self._mode

    def leave(self):
        pass

    def enter(self):
        pass


class PlaneMovementGlyph(PlaneMovement):

    def __init__(self, mode):
        super(PlaneMovementGlyph, self).__init__(mode)
        self._default_material = None
        self._active_material = None
        self._glyph = None

    def setDefaultMaterial(self, material):
        self._default_material = material

    def setActiveMaterial(self, material):
        self._active_material = material

    def setActive(self, active=True):
        self._active = active
        if self._glyph and active:
            self._glyph.setMaterial(self._active_material)
        elif self._glyph and not active:
            self._glyph.setMaterial(self._default_material)

    def setGlyph(self, glyph):
        self._glyph = glyph

    def enter(self):
        self.setActive(False)
        self._glyph.setVisibilityFlag(True)

    def leave(self):
        self.setActive(False)
        self._glyph.setVisibilityFlag(False)


class PlaneDescription(object):

    def __init__(self, point, normal, centre):
        self._point = point
        self._normal = normal
        self._centre = centre

    def getPoint(self):
        return self._point

    def getNormal(self):
        return self._normal

    def getCentre(self):
        return self._centre


class ViewState(object):

    def __init__(self):
        self._eye = None
        self._lookat = None
        self._up = None
        self._pop = None
        self._normal = None
        self._rotation_mode = None
        self._projection_mode = ProjectionMode.PERSPECTIVE
        self._normal_base_size = DEFAULT_NORMAL_ARROW_SIZE
        self._rotation_centre_base_size = DEFAULT_ROTATION_CENTRE_SIZE

    def setViewParameters(self, eye, lookat, up):
        self._eye = eye
        self._lookat = lookat
        self._up = up

    def getViewParameters(self):
        return self._eye, self._lookat, self._up

    def setPointOnPlane(self, pt):
        self._pop = pt

    def getPointOnPlane(self):
        return self._pop

    def setPlaneNormal(self, normal):
        self._normal = normal

    def getPlaneNormal(self):
        return self._normal

    def setPlaneRotationMode(self, mode):
        self._rotation_mode = mode

    def getPlaneRotationMode(self):
        return self._rotation_mode

    def setProjectionMode(self, mode):
        self._projection_mode = mode

    def getProjectionMode(self):
        return self._projection_mode

    def setPlaneNormalGlyphBaseSize(self, base_size):
        self._normal_base_size = base_size

    def getPlaneNormalGlyphBaseSize(self):
        return self._normal_base_size

    def setPlaneRotationCentreGlyphBaseSize(self, base_size):
        self._rotation_centre_base_size = base_size

    def getPlaneRotationCentreGlyphBaseSize(self):
        return self._rotation_centre_base_size

class SegmentationWidget(QtGui.QWidget):
    '''
    About dialog to display program about information.
    '''


    def __init__(self, parent=None):
        '''
        Constructor
        '''
        QtGui.QWidget.__init__(self, parent)
        self._ui = Ui_SegmentationWidget()
        self._ui.setupUi(self)
        self._setupUi()
#         self._ui.actionButton.setText('Add Point(s)')

        self._context = Context('Segmentation')
#         self._ui.zinc_widget.setParent(self)
        self._ui.zinc_widget.setContext(self._context)

        self._image_data_location = ''
        self._dimensions = []
        self._maxdim = 100

        self._debug_print = False

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.falsifyMouseEvents)
#         self._timer.start(1000)
        self._counter = 0

        self._viewstate = None

        # Set up the states of the plane movement modes
        self._modes = {PlaneMovementMode.NONE: PlaneMovement(PlaneMovementMode.NONE),
                       PlaneMovementMode.NORMAL: PlaneMovementGlyph(PlaneMovementMode.NORMAL),
                       PlaneMovementMode.ROTATION: PlaneMovementGlyph(PlaneMovementMode.ROTATION)}
        self._active_mode = self._modes[PlaneMovementMode.NONE]

        self._undoStack = QtGui.QUndoStack()
        self._ui.zinc_widget.setUndoStack(self._undoStack)

        self._makeConnections()

    def _makeConnections(self):
        self._ui.zinc_widget.graphicsInitialized.connect(self.sceneviewerReady)
        self._ui._pushButtonReset.clicked.connect(self._resetViewClicked)
        self._ui._pushButtonViewAll.clicked.connect(self._viewAllClicked)

        self._ui._radioButtonSegment.clicked.connect(self._zincWidgetModeChanged)
        self._ui._radioButtonMove.clicked.connect(self._zincWidgetModeChanged)
        self._ui._radioButtonRotate.clicked.connect(self._zincWidgetModeChanged)
        self._ui._radioButtonParallel.clicked.connect(self._projectionModeChanged)
        self._ui._radioButtonPerspective.clicked.connect(self._projectionModeChanged)

        self._ui._lineEditWidthScale.editingFinished.connect(self._scaleChanged)
        self._ui._lineEditHeightScale.editingFinished.connect(self._scaleChanged)
        self._ui._lineEditDepthScale.editingFinished.connect(self._scaleChanged)

        self._ui._doubleSpinBoxNormalArrow.valueChanged.connect(self._iconSizeChanged)
        self._ui._doubleSpinBoxRotationCentre.valueChanged.connect(self._iconSizeChanged)

    def _setupUi(self):
        dbl_validator = QtGui.QDoubleValidator()
        self._ui._lineEditWidthScale.setValidator(dbl_validator)
        self._ui._lineEditHeightScale.setValidator(dbl_validator)
        self._ui._lineEditDepthScale.setValidator(dbl_validator)

        self._ui._doubleSpinBoxNormalArrow.setValue(DEFAULT_NORMAL_ARROW_SIZE)
        self._ui._doubleSpinBoxRotationCentre.setValue(DEFAULT_ROTATION_CENTRE_SIZE)

    def _updateImageUI(self):
        self._ui._labelmageWidth.setText(str(self._dimensions[0]) + ' px')
        self._ui._labelmageHeight.setText(str(self._dimensions[1]) + ' px')
        self._ui._labelmageDepth.setText(str(self._dimensions[2]) + ' px')

    def _setPlaneEquation(self, normal, point):
        fieldmodule = self._plane_normal_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        scene = self._iso_graphic.getScene()
        scene.beginChange()
        self._plane_normal_field.assignReal(fieldcache, normal)
        self._point_on_plane_field.assignReal(fieldcache, point)
        self._setPlaneRotationCentreGlyphPosition(point)
        scene.endChange()

    def _getPlaneNormal(self):
        fieldmodule = self._plane_normal_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        _, normal = self._plane_normal_field.evaluateReal(fieldcache, 3)

        return normal

    def _setPlaneNormal(self, normal):
        fieldmodule = self._point_on_plane_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        scene = self._iso_graphic.getScene()
        scene.beginChange()
        self._plane_normal_field.assignReal(fieldcache, normal)
        scene.endChange()

    def _setPointOnPlane(self, point):
        fieldmodule = self._point_on_plane_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        scene = self._iso_graphic.getScene()
        scene.beginChange()
        self._point_on_plane_field.assignReal(fieldcache, point)
        self._setPlaneRotationCentreGlyphPosition(point)
        scene.endChange()

    def _getPointOnPlane(self):
        fieldmodule = self._point_on_plane_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        _, point = self._point_on_plane_field.evaluateReal(fieldcache, 3)

        return point

    def _resetViewClicked(self):
        self._loadViewState()
        self._undoStack.clear()

    def _saveViewState(self):
        eye, lookat, up = self._ui.zinc_widget.getViewParameters()

        self._viewstate = ViewState()
        self._viewstate.setViewParameters(eye, lookat, up)
        self._viewstate.setPointOnPlane(self._getPointOnPlane())
        self._viewstate.setPlaneNormal(self._getPlaneNormal())
        self._viewstate.setPlaneRotationMode(self._getMode())
        self._viewstate.setProjectionMode(self._ui.zinc_widget.getProjectionMode())
        self._viewstate.setPlaneNormalGlyphBaseSize(self._ui._doubleSpinBoxNormalArrow.value())
        self._viewstate.setPlaneRotationCentreGlyphBaseSize(self._ui._doubleSpinBoxRotationCentre.value())

    def _loadViewState(self):
        eye, lookat, up = self._viewstate.getViewParameters()
        self._ui.zinc_widget.setViewParameters(eye, lookat, up)
        self._setPlaneEquation(self._viewstate.getPlaneNormal(), self._viewstate.getPointOnPlane())
        self._setMode(self._viewstate.getPlaneRotationMode())
        self._setProjectionMode(self._viewstate.getProjectionMode())
        base_size = self._viewstate.getPlaneNormalGlyphBaseSize()
        self._ui._doubleSpinBoxNormalArrow.setValue(base_size)
        self._setPlaneNormalGlyphBaseSize(base_size)
        base_size = self._viewstate.getPlaneRotationCentreGlyphBaseSize()
        self._ui._doubleSpinBoxRotationCentre.setValue(base_size)
        self._setPlaneRotationCentreGlyphBaseSize(base_size)

    def _viewAllClicked(self):
        self._ui.zinc_widget.viewAll()

    def _projectionModeChanged(self):
        if self.sender() == self._ui._radioButtonParallel:
            self._ui.zinc_widget.setProjectionMode(ProjectionMode.PARALLEL)
        elif self.sender() == self._ui._radioButtonPerspective:
            self._ui.zinc_widget.setProjectionMode(ProjectionMode.PERSPECTIVE)

    def _setProjectionMode(self, mode):
        self._ui._radioButtonParallel.setChecked(mode == ProjectionMode.PARALLEL)
        self._ui._radioButtonPerspective.setChecked(mode == ProjectionMode.PERSPECTIVE)
        self._ui.zinc_widget.setProjectionMode(mode)

    def _zincWidgetModeChanged(self):
        if self.sender() == self._ui._radioButtonSegment:
            self._setMode(PlaneMovementMode.NONE)
        elif self.sender() == self._ui._radioButtonMove:
            self._setMode(PlaneMovementMode.NORMAL)
        elif self.sender() == self._ui._radioButtonRotate:
            self._setMode(PlaneMovementMode.ROTATION)

    def _iconSizeChanged(self):
        if self.sender() == self._ui._doubleSpinBoxNormalArrow:
            self._setPlaneNormalGlyphBaseSize(self._ui._doubleSpinBoxNormalArrow.value())
        elif self.sender() == self._ui._doubleSpinBoxRotationCentre:
            self._setPlaneRotationCentreGlyphBaseSize(self._ui._doubleSpinBoxRotationCentre.value())

    def _scaleChanged(self):
        current_scale = self._getImageScale()
        new_scale = current_scale[:]
        if self.sender() == self._ui._lineEditWidthScale:
            new_scale[0] = float(self._ui._lineEditWidthScale.text())
        elif self.sender() == self._ui._lineEditHeightScale:
            new_scale[1] = float(self._ui._lineEditHeightScale.text())
        elif self.sender() == self._ui._lineEditDepthScale:
            new_scale[2] = float(self._ui._lineEditDepthScale.text())

        if new_scale != current_scale:
            self._setImageScale(new_scale)

    def _getImageScale(self):
        fieldmodule = self._scale_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        _, scale = self._scale_field.evaluateReal(fieldcache, 3)

        return scale

    def _getDimensions(self):
        scale = self._getImageScale()
        scaled_dimensions = elmult(self._dimensions, scale)
        return scaled_dimensions

    def _setImageScale(self, scale):
        fieldmodule = self._scale_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        fieldmodule.beginChange()
        self._scale_field.assignReal(fieldcache, scale)
        image_field = self._material.getTextureField(1).castImage()
        scaled_dimensions = elmult(self._dimensions, scale)
        image_field.setTextureCoordinateSizes(scaled_dimensions)
        plane_centre = self._calculatePlaneCentre()
        self._setPlaneNormalGlyphPosition(plane_centre)
        self._setPointOnPlane(plane_centre)
        fieldmodule.endChange()

    def _createMaterialUsingImageField(self):
        ''' 
        Use an image field in a material to create an OpenGL texture.  Returns the
        size of the image field in pixels.
        '''
        # create a graphics material from the graphics module, assign it a name
        # and set flag to true
        materials_module = self._context.getMaterialmodule()
        self._material = materials_module.createMaterial()
        self._material.setName('texture_block')
        self._material.setManaged(True)

        # Get a handle to the root _surface_region
        root_region = self._context.getDefaultRegion()

        # The field module allows us to create a field image to
        # store the image data into.
        field_module = root_region.getFieldmodule()

        # Create an image field. A temporary xi source field is created for us.
        image_field = field_module.createFieldImage()
        image_field.setName('image_field')
        image_field.setFilterMode(image_field.FILTER_MODE_LINEAR)

        # Create a stream information object that we can use to read the
        # image file from disk
        stream_information = image_field.createStreaminformationImage()
        # specify depth of texture block i.e. number of images
#        stream_information.setAttributeInteger(stream_information.IMAGE_ATTRIBUTE_, self.number_of_images)

        # Load images onto an invidual texture blocks.
        directory = self._image_data_location
        files = os.listdir(directory)
        files.sort(key=alphanum_key)
        for filename in files:
            # We are reading in a file from the local disk so our resource is a file.
            stream_information.createStreamresourceFile(os.path.join(directory, filename))

        # Actually read in the image file into the image field.
        image_field.read(stream_information)
        self._material.setTextureField(1, image_field)
        self._dimensions = image_field.getSizeInPixels(3)[1]
        image_field.setTextureCoordinateSizes(self._dimensions)

        return self._material

    def _createFiniteElementField(self, region):
        field_module = region.getFieldmodule()
        field_module.beginChange()

        # Create a finite element field with 3 components to represent 3 dimensions
        finite_element_field = field_module.createFieldFiniteElement(3)

        # Set the name of the field
        finite_element_field.setName('coordinates')
        # Set the attribute is managed to 1 so the field module will manage the field for us

        finite_element_field.setManaged(True)
        finite_element_field.setTypeCoordinate(True)
        field_module.endChange()

        return finite_element_field

    def _createFiniteElement(self, region, finite_element_field, dim):
        '''
        Create finite element meshes for each of the images.  Returns the finite element field
        used as the coordinate field.
        '''
        field_module = region.getFieldmodule()
        field_module.beginChange()
        # Define the coordinates for each 3D element
        node_coordinate_set = [[0, 0, 0], [dim[0], 0, 0], [0, dim[1], 0], [dim[0], dim[1], 0], [0, 0, dim[2]], [dim[0], 0, dim[2]], [0, dim[1], dim[2]], [dim[0], dim[1], dim[2]]]
#         node_coordinate_set = [[-0.5, -0.5, -0.5], [dim[0] + 0.5, -0.5, -0.5], [-0.5, dim[1] + 0.5, -0.5], [dim[0] + 0.5, dim[1] + 0.5, -0.5],
#                                 [-0.5, -0.5, dim[2] + 0.5], [dim[0] + 0.5, -0.5, dim[2] + 0.5], [-0.5, dim[1] + 0.5, dim[2] + 0.5], [dim[0] + 0.5, dim[1] + 0.5, dim[2] + 0.5]]
        self._ui.zinc_widget.create3DFiniteElement(field_module, finite_element_field, node_coordinate_set)

        field_module.defineAllFaces()
        field_module.endChange()

        # Create the three scalar fields in the x, y, z directions
        # ## x component

    def _createPlaneNormalField(self, fieldmodule):
        plane_normal_field = fieldmodule.createFieldConstant([1, 0, 0])
        return plane_normal_field

    def _createPointOnPlaneField(self, fieldmodule):
        point_on_plane_field = fieldmodule.createFieldConstant([0, 0, 0])
        return point_on_plane_field

    def _createIsoScalarField(self, fieldmodule, finite_element_field, plane_normal_field, point_on_plane_field):
        d = fieldmodule.createFieldDotProduct(plane_normal_field, point_on_plane_field)
        iso_scalar_field = fieldmodule.createFieldDotProduct(finite_element_field, plane_normal_field) - d

        return iso_scalar_field

    def _createTextureSurface(self, region, finite_element_field, iso_scalar_field):
        '''
        To visualize the 3D finite element that we have created for each _surface_region, we use a 
        surface graphic then set a _material for that surface to use.
        '''
        scene = region.getScene()

        scene.beginChange()
        # Create a surface graphic and set it's coordinate field to the finite element coordinate field
        # named coordinates
        outline = scene.createGraphicsLines()
#         finite_element_field = field_module.findFieldByName('coordinates')
        outline.setCoordinateField(finite_element_field)

        self._iso_graphic = scene.createGraphicsContours()
        self._iso_graphic.setCoordinateField(finite_element_field)
        self._iso_graphic.setMaterial(self._material)
#         xi_field = region.getFieldmodule().findFieldByName('xi')
        self._iso_graphic.setTextureCoordinateField(finite_element_field)
        # set the yz scalar field to our isosurface
        self._iso_graphic.setIsoscalarField(iso_scalar_field)
        # define the initial position of the isosurface on the texture block
        self._iso_graphic.setListIsovalues(0.0)  # Range(1, self.initial_positions[0], self.initial_positions[0])

        scene.endChange()

    def _createNodeLabels(self, region, finite_element_field):
        scene = region.getScene()

        scene.beginChange()

        graphic = scene.createGraphicsPoints()
        graphic.setFieldDomainType(Field.DOMAIN_TYPE_NODES)
        graphic.setCoordinateField(finite_element_field)
        attributes = graphic.getGraphicspointattributes()
#         attributes.setGlyphShapeType(Glyph.SHAPE_TYPE_SPHERE)
#         attributes.setBaseSize(1)

#         fieldmodule = region.getFieldmodule()
#         field = fieldmodule.findFieldByName('cmiss_number')
        attributes.setLabelField(finite_element_field)

        scene.endChange()

    def _createTestPoints(self):
        region = self._context.getDefaultRegion()
        materialmodule = self._context.getMaterialmodule()
        green = materialmodule.findMaterialByName('green')
        red = materialmodule.findMaterialByName('red')
        scene = region.getScene()
        scene.beginChange()
        self._test_points = []
        i = 0
        while i < 2:
            tp = scene.createGraphicsPoints()
            tp.setFieldDomainType(Field.DOMAIN_TYPE_POINT)
            if i == 0:
                tp.setMaterial(green)
            else:
                tp.setMaterial(red)
            attr = tp.getGraphicspointattributes()
            attr.setGlyphShapeType(Glyph.SHAPE_TYPE_CUBE_SOLID)
            attr.setBaseSize(1)
            self._test_points.append(tp)
            i += 1
#         self._test_point_1 = scene.createGraphicsPoints()
#         self._test_point_2 = scene.createGraphicsPoints()
#         self._test_point_1.setFieldDomainType(Field.DOMAIN_TYPE_POINT)
#         self._test_point_2.setFieldDomainType(Field.DOMAIN_TYPE_POINT)
        scene.endChange()

    def _createPlaneManipulationSphere(self, region, finite_element_field):
        scene = region.getScene()

        scene.beginChange()

        # Create transparent purple sphere
        plane_rotation_sphere = scene.createGraphicsPoints()
        plane_rotation_sphere.setFieldDomainType(Field.DOMAIN_TYPE_POINT)
        plane_rotation_sphere.setVisibilityFlag(False)
        tessellation = plane_rotation_sphere.getTessellation()
        tessellation.setCircleDivisions(24)
        plane_rotation_sphere.setTessellation(tessellation)
        attributes = plane_rotation_sphere.getGraphicspointattributes()
        attributes.setGlyphShapeType(Glyph.SHAPE_TYPE_SPHERE)
        attributes.setBaseSize(DEFAULT_ROTATION_CENTRE_SIZE)

        scene.endChange()

        return plane_rotation_sphere

    def _createPlaneNormalIndicator(self, region, finite_element_field, plane_normal_field):
        scene = region.getScene()

        scene.beginChange()
        # Create transparent purple sphere
        plane_normal_indicator = scene.createGraphicsPoints()
        plane_normal_indicator.setFieldDomainType(Field.DOMAIN_TYPE_POINT)
        plane_normal_indicator.setVisibilityFlag(False)

        fm = region.getFieldmodule()
        zero_field = fm.createFieldConstant([0, 0, 0])
        plane_normal_indicator.setCoordinateField(zero_field)

        attributes = plane_normal_indicator.getGraphicspointattributes()
        attributes.setGlyphShapeType(Glyph.SHAPE_TYPE_ARROW_SOLID)
        attributes.setBaseSize([DEFAULT_NORMAL_ARROW_SIZE, DEFAULT_NORMAL_ARROW_SIZE / 4, DEFAULT_NORMAL_ARROW_SIZE / 4])
        attributes.setScaleFactors([0, 0, 0])
        attributes.setOrientationScaleField(plane_normal_field)
#         attributes.setLabelField(zero_field)

        scene.endChange()

        return plane_normal_indicator

    def _setGlyphsForGlyphModes(self, rotation_glyph, normal_glyph):
        normal_mode = self._modes[PlaneMovementMode.NORMAL]
        normal_mode.setGlyph(normal_glyph)
        rotation_mode = self._modes[PlaneMovementMode.ROTATION]
        rotation_mode.setGlyph(rotation_glyph)

    def _setMaterialsForGlyphModes(self):
        '''
        Set the materials for the modes that have glyphs.
        '''
        materialmodule = self._context.getMaterialmodule()
        yellow_material = materialmodule.findMaterialByName('yellow')
        orange_material = materialmodule.findMaterialByName('orange')

        purple_material = materialmodule.createMaterial()
        purple_material.setName('purple')
        purple_material.setAttributeReal3(Material.ATTRIBUTE_AMBIENT, [0.4, 0.0, 0.6])
        purple_material.setAttributeReal3(Material.ATTRIBUTE_DIFFUSE, [0.4, 0.0, 0.6])
        purple_material.setAttributeReal(Material.ATTRIBUTE_ALPHA, 0.4)

        red_material = materialmodule.findMaterialByName('red')
        red_material.setAttributeReal(Material.ATTRIBUTE_ALPHA, 0.4)

        normal_mode = self._modes[PlaneMovementMode.NORMAL]
        normal_mode.setDefaultMaterial(yellow_material)
        normal_mode.setActiveMaterial(orange_material)

        rotation_mode = self._modes[PlaneMovementMode.ROTATION]
        rotation_mode.setDefaultMaterial(purple_material)
        rotation_mode.setActiveMaterial(red_material)

    def setImageDirectory(self, imagedir):
        self._image_data_location = imagedir

    def showImages(self):
        self._ui.zinc_widget.defineStandardMaterials()
        self._ui.zinc_widget.defineStandardGlyphs()
        self._setMaterialsForGlyphModes()
        self._createMaterialUsingImageField()
        self._updateImageUI()
        region = self._context.getDefaultRegion().createChild('image')
        finite_element_field = self._createFiniteElementField(region)
        fieldmodule = region.getFieldmodule()
        self._scale_field = fieldmodule.createFieldConstant([1.0, 1.0, 1.0])
        scaled_finite_element_field = finite_element_field * self._scale_field

        self._createFiniteElement(region, finite_element_field, self._dimensions)

        self._plane_normal_field = self._createPlaneNormalField(fieldmodule)
        self._point_on_plane_field = self._createPointOnPlaneField(fieldmodule)
        iso_scalar_field = self._createIsoScalarField(fieldmodule, scaled_finite_element_field, self._plane_normal_field, self._point_on_plane_field)
        self._createTextureSurface(region, scaled_finite_element_field, iso_scalar_field)
        self._createNodeLabels(region, scaled_finite_element_field)
        self._plane_rotation_glyph = self._createPlaneManipulationSphere(region, scaled_finite_element_field)
        self._plane_normal_glyph = self._createPlaneNormalIndicator(region, scaled_finite_element_field, self._plane_normal_field)
        self._setGlyphsForGlyphModes(self._plane_rotation_glyph, self._plane_normal_glyph)
        plane_centre = self._calculatePlaneCentre()
        self._setPlaneNormalGlyphPosition(plane_centre)
        self._setPointOnPlane(plane_centre)

#         self._createTestPoints()

    def sceneviewerReady(self):
        self._saveViewState()

    def _calculatePlaneCentre(self):
        dim = self._getDimensions()  # self._dimensions
        plane_normal = self._getPlaneNormal()
        point_on_plane = self._getPointOnPlane()
        axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        coordinate_set = [[0, 0, 0], [dim[0], 0, 0], [0, dim[1], 0], [dim[0], dim[1], 0], [0, 0, dim[2]], [dim[0], 0, dim[2]], [0, dim[1], dim[2]], [dim[0], dim[1], dim[2]]]

        ipts = []
        for axis in axes:
            den = dot(axis, plane_normal)
            if abs(den) < 0.000000001:
                continue

            for corner in coordinate_set:
                num = dot(sub(point_on_plane, corner), plane_normal)
                d = num / den

                ipt = add(mult(axis, d), corner)
                if 0 <= ipt[0] <= dim[0] and 0 <= ipt[1] <= dim[1] and 0 <= ipt[2] <= dim[2]:
                    ipts.append(ipt)

        unique_ipts = []
        for p in ipts:
            insert = True
            for u in unique_ipts:
                vdiff = sub(p, u)
                if sqrt(dot(vdiff, vdiff)) < 0.00000001:
                    insert = False
            if insert:
                unique_ipts.append(p)

        if self._debug_print:
            print
            print(ipts)
            print(unique_ipts)

        ca = CentroidAlgorithm(unique_ipts)
#         wa = WeiszfeldsAlgorithm(unique_ipts)
        plane_centre = ca.compute()
#         sum_ipts = [0, 0, 0]
#         for v in unique_ipts:
#             sum_ipts = add(sum_ipts, v)
#
#
#
#         plane_centre = div(sum_ipts, len(unique_ipts))
        return plane_centre

    def _boundCoordinatesToElement(self, coords):
        dim = self._getDimensions()
        bounded_coords = [ max(min(coords[i], dim[i]), 0.0)  for i in range(len(coords)) ]
        return bounded_coords

    def _setPlaneRotationCentreGlyphBaseSize(self, base_size):
        scene = self._plane_rotation_glyph.getScene()
        scene.beginChange()
        attributes = self._plane_rotation_glyph.getGraphicspointattributes()
        _, cur_base_size = attributes.getBaseSize(1)
        _, position = attributes.getGlyphOffset(3)
        true_position = mult(position, cur_base_size)
        attributes.setBaseSize(base_size)
        attributes.setGlyphOffset(div(true_position, base_size))
        scene.endChange()

    def _setPlaneRotationCentreGlyphPosition(self, position):
        scene = self._plane_rotation_glyph.getScene()
        scene.beginChange()
        attributes = self._plane_rotation_glyph.getGraphicspointattributes()
        _, base_size = attributes.getBaseSize(1)
        attributes.setGlyphOffset(div(position, base_size))
        scene.endChange()

    def _getPlaneRotationCentreGlyphPosition(self):
        attributes = self._plane_rotation_glyph.getGraphicspointattributes()
        _, base_size = attributes.getBaseSize(1)
        _, position = attributes.getGlyphOffset(3)

        return mult(position, base_size)

    def _setPlaneNormalGlyphBaseSize(self, base_size):
#         scene = self._plane_normal_glyph.getScene()
#         scene.beginChange()
        attributes = self._plane_normal_glyph.getGraphicspointattributes()
        attributes.setBaseSize([base_size, base_size / 4, base_size / 4])

    def _setPlaneNormalGlyphPosition(self, position):
        '''
        This is synonymous with setting the plane centre.
        '''
        scene = self._plane_normal_glyph.getScene()
        scene.beginChange()
#         attributes = self._plane_normal_glyph.getGraphicspointattributes()
        position_field = self._plane_normal_glyph.getCoordinateField()
        fieldmodule = position_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        position_field.assignReal(fieldcache, position)

        scene.endChange()

    def _getPlaneNormalGlyphPosition(self):
        '''
        This is synonymous with getting the plane centre.
        '''
        position_field = self._plane_normal_glyph.getCoordinateField()
        fieldmodule = position_field.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        _, position = position_field.evaluateReal(fieldcache, 3)

        return position


#     def _showPlaneRotationCentreGlyph(self, plane_centre):
#         self._setPlaneRotationCentreGlyphPosition(plane_centre)
#         self._plane_rotation_glyph.setVisibilityFlag(True)
#
#     def _showPlaneNormalGlyph(self, plane_centre):
#         self._setPlaneNormalGlyphPosition(plane_centre)
#         self._plane_normal_glyph.setVisibilityFlag(True)
#
#     def _hidePlaneRotationCentreGlyph(self):
#         self._plane_rotation_glyph.setVisibilityFlag(False)
#
#     def _hidePlaneNormalGlyph(self):
#         self._plane_normal_glyph.setVisibilityFlag(False)

    def keyPressEvent(self, keyevent):
        if keyevent.key() == 68 and not self._debug_print:
            self._debug_print = True

    def falsifyMouseEvents(self):
        if self._counter == 0:
            # falsify plane rotation mode
            self._plane_centre_position = self._calculatePlaneCentre()
            self._showPlaneRotationCentreGlyph(self._plane_centre_position)
            self._plane_movement_type = True
            me = FakeMouseEvent(666, 180)
            self.mousePressEvent(me)

        if 0 < self._counter <= 10:
            me = FakeMouseEvent(666, 180 - self._counter * 10)
            self.mouseMoveEvent(me)

        if self._counter > 10:
            self._hidePlaneRotationCentreGlyph()
            self._plane_movement_type = False
            self._timer.stop()

        self._counter += 1

    def _getMode(self):
        return self._active_mode.mode()

    def _setMode(self, mode):
        if mode != self._getMode():
            self._active_mode.leave()
            self._active_mode = self._modes[mode]
            self._active_mode.enter()

            self._ui.zinc_widget.setIgnoreMouseEvents(mode != PlaneMovementMode.NONE)


    def keyReleaseEvent(self, keyevent):
        if keyevent.key() == 82 and keyevent.modifiers() & QtCore.Qt.CTRL and not keyevent.isAutoRepeat():
            # Put tool into plane rotation mode
            # show sphere centre glyph
            reverse = keyevent.modifiers() & QtCore.Qt.SHIFT
            cur_mode = self._getMode()
            if cur_mode == PlaneMovementMode.NONE:
                if reverse:
                    self._setMode(PlaneMovementMode.ROTATION)
                else:
                    self._setMode(PlaneMovementMode.NORMAL)
            elif cur_mode == PlaneMovementMode.NORMAL:
                if reverse:
                    self._setMode(PlaneMovementMode.NONE)
                else:
                    self._setMode(PlaneMovementMode.ROTATION)
            elif cur_mode == PlaneMovementMode.ROTATION:
                if reverse:
                    self._setMode(PlaneMovementMode.NORMAL)
                else:
                    self._setMode(PlaneMovementMode.NONE)

        if keyevent.key() == 68 and not keyevent.isAutoRepeat():
            self._debug_print = False

    def _startPlaneMovement(self, movement_type):
        pass

    def _performPlaneMovement(self, movement_type):
        pass

    def _endPlaneMovement(self, movement_type):
        pass

    def mousePressEvent(self, mouseevent):
        self._previous_mouse_position = None
        cur_mode = self._getMode()
        if cur_mode != PlaneMovementMode.NONE:
            self._plane_rotation_mode_graphic = self._ui.zinc_widget.getNearestGraphicsPoint(mouseevent.x(), mouseevent.y())
            if self._plane_rotation_mode_graphic:
                self._active_mode.setActive()

            self._previous_mouse_position = [mouseevent.x(), mouseevent.y()]

            if not self._active_mode.isActive() and cur_mode == PlaneMovementMode.NORMAL:
                self._ui.zinc_widget.processZincMousePressEvent(mouseevent)
            else:
                self._start_plane = PlaneDescription(self._getPointOnPlane(), self._getPlaneNormal(), self._getPlaneNormalGlyphPosition())

        elif mouseevent.modifiers() & QtCore.Qt.CTRL and button_map[mouseevent.button()] == Sceneviewerinput.BUTTON_TYPE_RIGHT:
            self._previous_mouse_position = [mouseevent.x(), mouseevent.y()]
#             print([mouseevent.x() - 118, -(mouseevent.y() - 33), 0.9], [mouseevent.x() - 118, -(mouseevent.y() - 33), -0.9])

    def mouseMoveEvent(self, mouseevent):
        cur_mode = self._getMode()
        is_active = self._active_mode.isActive()
        if is_active and cur_mode == PlaneMovementMode.ROTATION:
            point_on_plane = self._getPointOnPlane()  # self._plane_centre_position  # self._getPointOnPlane()
            plane_normal = self._getPlaneNormal()

            x, y = self._ui.zinc_widget.mapToWidget(mouseevent.x(), mouseevent.y())
            far_plane_centre = self._ui.zinc_widget.unproject(x, -y, -1.0)
            near_plane_centre = self._ui.zinc_widget.unproject(x, -y, 1.0)
            line_direction = sub(near_plane_centre, far_plane_centre)
            d = dot(sub(point_on_plane, far_plane_centre), plane_normal) / dot(line_direction, plane_normal)
            new_plane_centre = add(mult(line_direction, d), far_plane_centre)
            new_plane_centre = self._boundCoordinatesToElement(new_plane_centre)
            if abs(dot(sub(point_on_plane, new_plane_centre), plane_normal)) < 1e-08:
                self._setPlaneRotationCentreGlyphPosition(new_plane_centre)
                self._setPointOnPlane(new_plane_centre)
#                 self._plane_centre_position = new_plane_centre

        elif not is_active and cur_mode == PlaneMovementMode.ROTATION:
            width = self._ui.zinc_widget.width()
            height = self._ui.zinc_widget.height()
            radius = min([width, height]) / 2.0
            delta_x = float(mouseevent.x() - self._previous_mouse_position[0])
            delta_y = float(mouseevent.y() - self._previous_mouse_position[1])
            tangent_dist = sqrt((delta_x * delta_x + delta_y * delta_y))
            if tangent_dist > 0.0:
                dx = -delta_y / tangent_dist;
                dy = delta_x / tangent_dist;

                d = dx * (mouseevent.x() - 0.5 * (width - 1)) + dy * ((mouseevent.y() - 0.5 * (height - 1)))
                if d > radius: d = radius
                if d < -radius: d = -radius

                phi = acos(d / radius) - 0.5 * pi
                angle = 1.0 * tangent_dist / radius

                eye, lookat, up = self._ui.zinc_widget.getViewParameters()

                b = up[:]
                b = normalize(b)
                a = sub(lookat, eye)
                a = normalize(a)
                c = cross(b, a)
                c = normalize(c)
                e = [None, None, None]
                e[0] = dx * c[0] + dy * b[0]
                e[1] = dx * c[1] + dy * b[1]
                e[2] = dx * c[2] + dy * b[2]
                axis = [None, None, None]
                axis[0] = sin(phi) * a[0] + cos(phi) * e[0]
                axis[1] = sin(phi) * a[1] + cos(phi) * e[1]
                axis[2] = sin(phi) * a[2] + cos(phi) * e[2]

                plane_normal = self._getPlaneNormal()
                point_on_plane = self._getPlaneRotationCentreGlyphPosition()

                plane_normal_prime_1 = mult(plane_normal, cos(angle))
                plane_normal_prime_2 = mult(plane_normal, dot(plane_normal, axis) * (1 - cos(angle)))
                plane_normal_prime_3 = mult(cross(axis, plane_normal), sin(angle))
                plane_normal_prime = add(add(plane_normal_prime_1, plane_normal_prime_2), plane_normal_prime_3)

                self._setPlaneEquation(plane_normal_prime, point_on_plane)

                self._previous_mouse_position = [mouseevent.x(), mouseevent.y()]
        elif is_active and cur_mode == PlaneMovementMode.NORMAL:
            pos = self._getPlaneNormalGlyphPosition()  # self._plane_centre_position  # self._getPointOnPlane()
            screen_pos = self._ui.zinc_widget.project(pos[0], pos[1], pos[2])
            global_cur_pos = self._ui.zinc_widget.unproject(mouseevent.x(), -mouseevent.y(), screen_pos[2])
            global_old_pos = self._ui.zinc_widget.unproject(self._previous_mouse_position[0], -self._previous_mouse_position[1], screen_pos[2])
            global_pos_diff = sub(global_cur_pos, global_old_pos)

            n = self._getPlaneNormal()
            proj_n = mult(n, dot(global_pos_diff, n))
            new_pos = add(pos, proj_n)
            scene = self._iso_graphic.getScene()
            scene.beginChange()
            self._setPointOnPlane(new_pos)
            plane_centre = self._calculatePlaneCentre()
            if plane_centre is None:
                self._setPointOnPlane(pos)
            else:
                self._setPlaneNormalGlyphPosition(plane_centre)
                self._setPointOnPlane(plane_centre)

            scene.endChange()
            self._previous_mouse_position = [mouseevent.x(), mouseevent.y()]
        elif not is_active and cur_mode == PlaneMovementMode.NORMAL:
            self._ui.zinc_widget.processZincMouseMoveEvent(mouseevent)

    def mouseReleaseEvent(self, mouseevent):
        c = None
        end_plane = PlaneDescription(self._getPointOnPlane(), self._getPlaneNormal(), self._getPlaneNormalGlyphPosition())
        if self._active_mode.isActive():
            self._active_mode.setActive(False)

            c = CommandMovePlane(self._start_plane, end_plane)
        elif self._getMode() == PlaneMovementMode.NORMAL:
            self._ui.zinc_widget.processZincMouseReleaseEvent(mouseevent)
        else:
            c = CommandMovePlane(self._start_plane, end_plane)

        if not c is None:
            c.setMethodCallbacks(self._setPlaneNormalGlyphPosition, self._setPlaneEquation)
            self._undoStack.push(c)

    def undoRedoStack(self):
        return self._undoStack

    def getPointCloud(self):
        return self._ui.zinc_widget.getPointCloud()

import math

class CentroidAlgorithm(object):

    def __init__(self, xi):
        self._xi = xi

    def compute(self):
        if len(self._xi) == 0:
            return None

        ave = self._average()
        e1, e2, e3 = self._calculateBasis()
        trans_xi = self._convertXi(ave, e1, e2, e3)
        ordered_xi = self._orderByHeading(trans_xi)
        area = self._calculatePolygonArea(ordered_xi)
        cx, cy = self._calculateCxCy(ordered_xi, area)
        centroid_x = ave[0] + e1[0] * cx + e2[0] * cy
        centroid_y = ave[1] + e1[1] * cx + e2[1] * cy
        centroid_z = ave[2] + e1[2] * cx + e2[2] * cy
        centroid = [centroid_x, centroid_y, centroid_z]

        return centroid

    def _orderByHeading(self, trans_xi):
        headings = self._calculateHeading(trans_xi)
        heading_indexes = [i[0] for i in sorted(enumerate(headings), key=lambda x:x[1])]
        ordered_xi = [trans_xi[i] for i in heading_indexes]
        ordered_xi.append(ordered_xi[0])  # repeat the first vertex

        return ordered_xi

    def _calculateCxCy(self, vertices, area):
        cx = 0.0
        cy = 0.0
        for i in range(len(vertices) - 1):
            val = (vertices[i][0] * vertices[i + 1][1] - vertices[i + 1][0] * vertices[i][1])
            cx += ((vertices[i][0] + vertices[i + 1][0]) * val)
            cy += ((vertices[i][1] + vertices[i + 1][1]) * val)

        cx = cx / (6 * area)
        cy = cy / (6 * area)
        return cx, cy

    def _calculatePolygonArea(self, vertices):
        area = 0.0
        for i in range(len(vertices) - 1):
            area += (vertices[i][0] * vertices[i + 1][1] - vertices[i + 1][0] * vertices[i][1])
        return 0.5 * area

    def _calculateHeading(self, direction):
        '''
        Convert a vector based direction into a heading
        between 0 and 2*pi.
        '''
        headings = [math.atan2(pt[1], pt[0]) + pi for pt in direction]
        return headings

    def _calculateBasis(self):
        e1 = e2 = e3 = None
        if len(self._xi) > 2:
            pta = self._xi[0]
            ptb = self._xi[1]
            ptc = self._xi[2]
            e1 = sub(ptb, pta)
            e2 = sub(ptc, pta)
#             e2 = cross(e1, self._nor)
            e3 = cross(e1, e2)
            e2 = cross(e1, e3)
            e1 = normalize(e1)
            e2 = normalize(e2)
            e3 = normalize(e3)

        return e1, e2, e3

    def _convertXi(self, ori, e1, e2, e3):
        '''
        Use average point as the origin 
        for new basis.
        '''
        converted = []

        for v in self._xi:
            diff = sub(v, ori)
            bv = [dot(diff, e1), dot(diff, e2)]
            converted.append(bv)

        return converted

    def _average(self):
        sum_xi = None
        for v in self._xi:
            if not sum_xi:
                sum_xi = [0.0] * len(v)
            sum_xi = add(sum_xi, v)

        average = div(sum_xi, len(self._xi))
        return average

class WeiszfeldsAlgorithm(object):

    def __init__(self, xi):

        self._xi = xi
        self._eps = 1e-04

    def compute(self):
        init_yi = self._average()
        yi = init_yi
        converged = False
        it = 0
        while not converged:

            diffi = [sub(xj, yi) for xj in self._xi]
            normi = [sqrt(dot(di, di)) for di in diffi]
            weight = sum([1 / ni for ni in normi])
            val = [div(self._xi[i], normi[i]) for i in range(len(self._xi))]

            yip1 = self._weightedaverage(val, weight)
            diff = sub(yip1, yi)
            yi = yip1
            it += 1
#             print(it)
            if sqrt(dot(diff, diff)) < self._eps:
                converged = True

        return yi

    def _weightedaverage(self, values, weight):
        sum_values = None
        for v in values:
            if not sum_values:
                sum_values = [0.0] * len(v)
            sum_values = add(sum_values, v)

        weightedaverage = div(sum_values, weight)
        return weightedaverage

    def _average(self):
        sum_xi = None
        for v in self._xi:
            if not sum_xi:
                sum_xi = [0.0] * len(v)
            sum_xi = add(sum_xi, v)

        average = div(sum_xi, len(self._xi))
        return average