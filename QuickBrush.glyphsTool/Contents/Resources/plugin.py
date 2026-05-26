# encoding: utf-8

import math
from Foundation import NSPoint, NSRect, NSSize, objc
from AppKit import NSBezierPath, NSColor, NSImage
from GlyphsApp import GSNode, GSPath
from GlyphsApp.plugins import SelectTool
from vanilla import Group, Slider, TextBox


class ImageView(Group):
    def __init__(self, posSize, imagePath):
        Group.__init__(self, posSize)
        self._image = NSImage.alloc().initByReferencingFile_(imagePath)

    def draw(self):
        if self._image:
            size = self.getPosSize()
            self._image.drawInRect_(NSRect(NSPoint(0, 0), NSSize(size[2], size[3])))


class QuickBrushTool(SelectTool):
    def settings(self):
        self.name = "QuickBrush"
        self.toolbarPosition = 120
        self.generalContextMenus = []
        self.angle = 0.0
        self.thickness = 40.0
        self.smoothing = 0.55
        self._rawPoints = []
        self.icon = NSImage.alloc().initByReferencingFile_(
            self.bundle.pathForResource_ofType_("toolbarIcon", "svg")
        )

    @objc.python_method
    def _clamp(self, value, lower, upper):
        return max(lower, min(value, upper))

    @objc.python_method
    def _smooth_points(self, points, factor):
        if len(points) < 3:
            return points[:]
        smoothed = [points[0]]
        a = self._clamp(factor, 0.0, 0.95)
        for i in range(1, len(points) - 1):
            prev_pt, curr_pt, next_pt = points[i - 1], points[i], points[i + 1]
            avg_x = (prev_pt.x + curr_pt.x + next_pt.x) / 3.0
            avg_y = (prev_pt.y + curr_pt.y + next_pt.y) / 3.0
            x = curr_pt.x * (1.0 - a) + avg_x * a
            y = curr_pt.y * (1.0 - a) + avg_y * a
            smoothed.append(NSPoint(x, y))
        smoothed.append(points[-1])
        return smoothed

    @objc.python_method
    def _build_outline(self, points, thickness, angle_deg):
        if len(points) < 2:
            return []
        angle = math.radians(angle_deg)
        half_t = thickness * 0.5
        dx, dy = math.cos(angle) * half_t, math.sin(angle) * half_t
        left = [NSPoint(p.x - dx, p.y - dy) for p in points]
        right = [NSPoint(p.x + dx, p.y + dy) for p in reversed(points)]
        return left + right

    @objc.python_method
    def _apply_to_layer(self, layer):
        if not layer or len(self._rawPoints) < 2:
            return
        smooth = self._smooth_points(self._rawPoints, self.smoothing)
        polygon = self._build_outline(smooth, self.thickness, self.angle)
        if len(polygon) < 3:
            return
        path = GSPath()
        for p in polygon:
            path.nodes.append(GSNode(NSPoint(p.x, p.y), type="line"))
        path.closed = True
        layer.shapes.append(path)

    def mouseDown_(self, event):
        pos = self.getActiveLocation_(event)
        self._rawPoints = [NSPoint(pos.x, pos.y)]

    def mouseDragged_(self, event):
        pos = self.getActiveLocation_(event)
        self._rawPoints.append(NSPoint(pos.x, pos.y))
        self.redraw()

    def mouseUp_(self, event):
        layer = self.editViewController().graphicView().activeLayer()
        self._apply_to_layer(layer)
        self._rawPoints = []
        self.redraw()

    def drawForegroundForLayer_(self, layer):
        if len(self._rawPoints) < 2:
            return
        preview = self._build_outline(self._smooth_points(self._rawPoints, self.smoothing), self.thickness, self.angle)
        if len(preview) < 3:
            return
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(preview[0])
        for point in preview[1:]:
            path.lineToPoint_(point)
        path.closePath()
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.55, 0.95, 0.25).set()
        path.fill()
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.55, 0.95, 0.95).set()
        path.setLineWidth_(1.5)
        path.stroke()

    def createInspectorView(self):
        view = Group((0, 0, 240, 230))
        view.preview = ImageView((12, 10, -12, 78), self.bundle.pathForResource_ofType_("preview", "svg"))
        view.angleLabel = TextBox((12, 96, -12, 17), "Brush Angle")
        view.angleSlider = Slider((12, 114, -12, 24), minValue=-90, maxValue=90, value=self.angle, callback=self._angleChanged)
        view.widthLabel = TextBox((12, 142, -12, 17), "Brush Thickness")
        view.widthSlider = Slider((12, 160, -12, 24), minValue=4, maxValue=180, value=self.thickness, callback=self._thicknessChanged)
        view.smoothLabel = TextBox((12, 186, -12, 17), "Curve Smoothness")
        view.smoothSlider = Slider((12, 204, -12, 24), minValue=0.0, maxValue=0.95, value=self.smoothing, callback=self._smoothChanged)
        self.inspectorView = view
        return view.getNSView()

    def _angleChanged(self, sender):
        self.angle = float(sender.get())
        self.redraw()

    def _thicknessChanged(self, sender):
        self.thickness = float(sender.get())
        self.redraw()

    def _smoothChanged(self, sender):
        self.smoothing = float(sender.get())
        self.redraw()
