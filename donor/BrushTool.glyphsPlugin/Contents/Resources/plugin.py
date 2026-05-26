# encoding: utf-8
###########################################################################################################
#
# Brush Tool Plugin — v1.0
#
###########################################################################################################

from __future__ import division, print_function, unicode_literals
import objc, os, math
from GlyphsApp import Glyphs, GSPath, GSNode, GSOFFCURVE, GSCURVE, GSLINE, UPDATEINTERFACE
from GlyphsApp.plugins import SelectTool, PalettePlugin
from AppKit import NSImage, NSColor, NSBezierPath, NSPoint

# ----------------------------------------------------------
# Constantes globales
# ----------------------------------------------------------
DEFAULT_SIMPLIFY_EPSILON = 2.0
DEFAULT_STROKE_WIDTH = 80.0
MIN_DISTANCE = 4.0

# ----------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------
def distance(p1, p2):
    return math.hypot(p2.x - p1.x, p2.y - p1.y)

def distance_point_segment(p, a, b):
    x, y = p.x, p.y
    x1, y1 = a.x, a.y
    x2, y2 = b.x, b.y
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    projx = x1 + t*dx
    projy = y1 + t*dy
    return math.hypot(x - projx, y - projy)

def rdp_simplify(points, epsilon):
    if len(points) < 3:
        return points[:]
    dmax = 0.0
    index = 0
    a = points[0]
    b = points[-1]
    for i in range(1, len(points)-1):
        d = distance_point_segment(points[i], a, b)
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        left = rdp_simplify(points[:index+1], epsilon)
        right = rdp_simplify(points[index:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]

def ns_add(a,b): return NSPoint(a.x+b.x, a.y+b.y)
def ns_sub(a,b): return NSPoint(a.x-b.x, a.y-b.y)
def ns_mul(a,s): return NSPoint(a.x*s, a.y*s)
def ns_div(a,s): return NSPoint(a.x/s, a.y/s)

# ----------------------------------------------------------
# B-spline -> Bézier
# ----------------------------------------------------------
def b_spline_to_bezier(points):
    n = len(points)
    if n < 2: return []
    if n == 2:
        p0,p1 = points
        c1 = NSPoint(p0.x + (p1.x-p0.x)/3, p0.y + (p1.y-p0.y)/3)
        c2 = NSPoint(p0.x + 2*(p1.x-p0.x)/3, p0.y + 2*(p1.y-p0.y)/3)
        return [(p0,c1,c2,p1)]
    padded = [points[0], points[0]] + points[:] + [points[-1], points[-1]]
    beziers = []
    for i in range(len(padded)-3):
        P0,P1,P2,P3 = padded[i],padded[i+1],padded[i+2],padded[i+3]
        Q0 = ns_div(ns_add(ns_add(P0, ns_mul(P1,4.0)), P2),6.0)
        Q1 = ns_div(ns_add(ns_mul(P1,4.0), ns_mul(P2,2.0)),6.0)
        Q2 = ns_div(ns_add(ns_mul(P1,2.0), ns_mul(P2,4.0)),6.0)
        Q3 = ns_div(ns_add(ns_add(P1, ns_mul(P2,4.0)), P3),6.0)
        beziers.append((Q0,Q1,Q2,Q3))
    return [seg for seg in beziers if abs(seg[0].x-seg[3].x)>1e-6 or abs(seg[0].y-seg[3].y)>1e-6]

# --- Arrondir ancrages ---
def round_anchor_points(points):
    """Arrondit uniquement les coordonnées des points d’ancrage."""
    return [NSPoint(round(p.x), round(p.y)) for p in points]

# --- Trim des extrémités (stabilisation) ---
def trim_ends(points, trim_length=5.0):
    """Recule légèrement les extrémités pour éviter artefacts sur virages serrés."""
    if len(points) < 2:
        return points
    # direction au début
    dir_start = ns_sub(points[1], points[0])
    len_start = math.hypot(dir_start.x, dir_start.y)
    if len_start > 0:
        dir_start = ns_div(dir_start, len_start)
    # direction à la fin
    dir_end = ns_sub(points[-2], points[-1])
    len_end = math.hypot(dir_end.x, dir_end.y)
    if len_end > 0:
        dir_end = ns_div(dir_end, len_end)
    new_start = ns_add(points[0], ns_mul(dir_start, trim_length))
    new_end = ns_add(points[-1], ns_mul(dir_end, trim_length))
    # si la liste est très courte, garder sécurité
    if len(points) == 2:
        return [new_start, new_end]
    return [new_start] + points[1:-1] + [new_end]

# --- Clamp tangentes de début/fin pour qu'elles ne dépassent pas la ligne directrice ---
def clamp_end_tangents(beziers, points):
    """
    # Empêche les tangentes de sortie d'un tracé d'aller dans une direction incohérente
    # (limite les artefacts aux extrémités du tracé).
    - beziers: list of (p0,c1,c2,p1)
    - points: simplified (and trimmed/rounded) anchor points
    """
    if not beziers or len(points) < 2:
        return beziers

    # Premier segment
    p0, c1, c2, p1 = beziers[0]
    # vecteur tangente relative
    vec = ns_sub(c1, p0)
    # vecteur maximal (direction vers point suivant)
    max_vec = ns_sub(points[1], p0)
    # si vec est nul, rien à faire
    if (abs(vec.x) > 1e-9 or abs(vec.y) > 1e-9) and (abs(max_vec.x) > 1e-9 or abs(max_vec.y) > 1e-9):
        # calcule un facteur qui réduit vec pour ne pas dépasser max_vec en composantes x/y
        scale = 1.0
        if abs(vec.x) > 1e-9 and abs(max_vec.x) < abs(vec.x):
            scale = min(scale, abs(max_vec.x/vec.x))
        if abs(vec.y) > 1e-9 and abs(max_vec.y) < abs(vec.y):
            scale = min(scale, abs(max_vec.y/vec.y))
        # applique scale (ne déplace pas le point d'ancrage p0)
        c1 = ns_add(p0, ns_mul(vec, scale))
        beziers[0] = (p0, c1, c2, p1)

    # Dernier segment
    p0, c1, c2, p1 = beziers[-1]
    vec = ns_sub(c2, p1)  # vecteur de la tangente sortant du dernier ancrage
    max_vec = ns_sub(points[-2], p1)  # direction vers l'avant-dernier point
    if (abs(vec.x) > 1e-9 or abs(vec.y) > 1e-9) and (abs(max_vec.x) > 1e-9 or abs(max_vec.y) > 1e-9):
        scale = 1.0
        if abs(vec.x) > 1e-9 and abs(max_vec.x) < abs(vec.x):
            scale = min(scale, abs(max_vec.x/vec.x))
        if abs(vec.y) > 1e-9 and abs(max_vec.y) < abs(vec.y):
            scale = min(scale, abs(max_vec.y/vec.y))
        c2 = ns_add(p1, ns_mul(vec, scale))
        beziers[-1] = (p0, c1, c2, p1)

    return beziers

# ----------------------------------------------------------
# Palette intégrée : BrushVariables
# ----------------------------------------------------------
class BrushToolVariables(PalettePlugin):
    dialog = objc.IBOutlet()
    thicknessSlider = objc.IBOutlet()
    smoothingSlider = objc.IBOutlet()
    thicknessLabel = objc.IBOutlet()
    smoothingLabel = objc.IBOutlet()

    thickness = 80.0
    smoothing = 8

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({
            'en': 'Brush settings',
            'fr': 'Paramètres de la brosse',
            'de': 'Pinsel-Einstellungen',
            'es': 'Ajustes del pincel',
            'zh': '画笔设置',
            'ja': 'ブラシの設定',
            'pt': 'Configurações do pincel',
            'it': 'Impostazioni del pennello',
            'nl': 'Kwastinstellingen',
            'ko': '브러시 설정',
            'ru': 'Настройки кисти',
        })
        self.loadNib('IBdialog', __file__)
        self.dialog.setController_(self)

    @objc.python_method
    def start(self):
        Glyphs.addCallback(self.update, UPDATEINTERFACE)

    @objc.python_method
    def __del__(self):
        Glyphs.removeCallback(self.update)

    def minHeight(self): return 120
    def maxHeight(self): return 120

    @objc.IBAction
    def thicknessChanged_(self, sender):
        self.thickness = round(sender.floatValue())
        if Brush.instance:
            Brush.instance.strokeWidth = self.thickness
        self.update(None)

    @objc.IBAction
    def smoothingChanged_(self, sender):
        self.smoothing = round(sender.floatValue())
        if Brush.instance:
            Brush.instance.simplifyEpsilon = DEFAULT_SIMPLIFY_EPSILON * (1.25 ** self.smoothing)
        self.update(None)

    @objc.python_method
    def update(self, sender):
        labels = Glyphs.localize({
            'en': {'thickness_label': 'Thickness:', 'smoothing_label': 'Smoothing:'},
            'fr': {'thickness_label': 'Épaisseur :', 'smoothing_label': 'Lissage :'},
            'de': {'thickness_label': 'Dicke:', 'smoothing_label': 'Glättung:'},
            'es': {'thickness_label': 'Grosor:', 'smoothing_label': 'Suavizado:'},
            'zh': {'thickness_label': '粗细:', 'smoothing_label': '平滑度:'},
            'ja': {'thickness_label': '太さ:', 'smoothing_label': 'スムージング:'},
            'pt': {'thickness_label': 'Espessura:', 'smoothing_label': 'Suavização:'},
            'it': {'thickness_label': 'Spessore:', 'smoothing_label': 'Levigatura:'},
            'nl': {'thickness_label': 'Dikte:', 'smoothing_label': 'Gladmaken:'},
            'ko': {'thickness_label': '두께:', 'smoothing_label': '매끄럽게:'},
            'ru': {'thickness_label': 'Толщина:', 'smoothing_label': 'Сглаживание:'}
        })

        if self.thicknessLabel:
            self.thicknessLabel.setStringValue_(f'{labels["thickness_label"]} {int(self.thickness)}')
        if self.smoothingLabel:
            self.smoothingLabel.setStringValue_(f'{labels["smoothing_label"]} {int(self.smoothing)}')

    @objc.python_method
    def __file__(self): return __file__

# ----------------------------------------------------------
# Brush Tool principal
# ----------------------------------------------------------
class Brush(SelectTool):
    """
    Outil de pinceau plat monolinéaire pour Glyphs.
    - Largeur fixe
    - Extrémités carrées (lineCap 0)
    - Lissage configurable via palette
    """
    instance = None

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({
            'en': 'Brush',
            'fr': 'Brosse',
            'de': 'Pinsel',
            'es': 'Pincel',
            'zh': '画笔',
            'ja': 'ブラシ',
            'pt': 'Pincel',
            'it': 'Pennello',
            'nl': 'Kwast',
            'ko': '브러시',
            'ru': 'Кисть',
        })

        icon_path = os.path.join(os.path.dirname(__file__), "BrushTool.pdf")
        highlight_path = os.path.join(os.path.dirname(__file__), "BrushToolHighlight.pdf")
        self.default_image = NSImage.alloc().initByReferencingFile_(icon_path)
        self.active_image = NSImage.alloc().initByReferencingFile_(highlight_path)
        self.tool_bar_image = self.default_image
        self.toolbarIconName = "BrushTool"

        self.keyboardShortcut = 'Z'
        self.toolbarPosition = 183

        self.strokeWidth = DEFAULT_STROKE_WIDTH
        self.simplifyEpsilon = DEFAULT_SIMPLIFY_EPSILON
        self.minDistance = MIN_DISTANCE
        self.roundCaps = False  # Extrémités non arrondies

        Brush.instance = self

    @objc.python_method
    def start(self):
        self.points = []
        self.lastPoint = None

    @objc.python_method
    def activate(self):
        self.tool_bar_image = self.active_image

    @objc.python_method
    def deactivate(self):
        self.tool_bar_image = self.default_image

    def mouseDown_(self, theEvent):
        view = self.editViewController().graphicView()
        loc = view.getActiveLocation_(theEvent)
        self.points = [loc]
        self.lastPoint = loc

        # --- Détection du type d'entrée ---
        self.usingStylus = False
        try:
            if hasattr(theEvent, "pressure"):
                pressure = theEvent.pressure()

                if 0.0 < pressure < 1.0:
                    self.usingStylus = True
            elif hasattr(theEvent, "tabletPointingDeviceType"):
                devType = theEvent.tabletPointingDeviceType()
                # 1 = Pen, 2 = Cursor, 3 = Eraser
                if devType in (1, 3):
                    self.usingStylus = True
        except Exception as e:
            print("Device detection failed:", e)

        # Ajustement des paramètres en fonction du périphérique
        if self.usingStylus:
            self.minDistance = 2.0
        else:
            self.minDistance = 4.0

        view.setNeedsDisplay_(True)

    def mouseDragged_(self, theEvent):
        if not self.lastPoint:
            return
        view = self.editViewController().graphicView()
        loc = view.getActiveLocation_(theEvent)

        if distance(self.lastPoint, loc) >= self.minDistance:
            self.points.append(loc)
            self.lastPoint = loc
            view.setNeedsDisplay_(True)

    def mouseUp_(self, theEvent):
        objc.super(Brush, self).mouseUp_(theEvent)
        view = self.editViewController().graphicView()
        if len(self.points) < 2:
            self.points = []
            self.lastPoint = None
            view.setNeedsDisplay_(True)
            return

        layer = view.activeLayer()
        path = GSPath()
        path.closed = False

        # --- Simplification ---
        simplified_points = rdp_simplify(self.points, self.simplifyEpsilon)
        if len(simplified_points) < 2:
            simplified_points = self.points[:]

        # --- Trim des extrémités ---
        simplified_points = trim_ends(simplified_points, trim_length=self.strokeWidth * 0.05)

        # --- Arrondir uniquement les points d’ancrage ---
        simplified_points = round_anchor_points(simplified_points)

        # --- B-spline -> Bézier ---
        beziers = b_spline_to_bezier(simplified_points)

        # --- Clamp tangentes début/fin ---
        beziers = clamp_end_tangents(beziers, simplified_points)

        # --- Si Béziers vides, tracer juste des lignes ---
        if not beziers:
            for pt in simplified_points:
                path.nodes.append(GSNode(pt, type=GSLINE))
            layer.paths.append(path)
            self.points = []
            self.lastPoint = None
            view.setNeedsDisplay_(True)
            return

        # --- Ajouter les nœuds au path ---
        first = True
        for p0, c1, c2, p1 in beziers:
            # arrondir encore les ancrages au cas où (sécurité)
            p0 = NSPoint(round(p0.x), round(p0.y))
            p1 = NSPoint(round(p1.x), round(p1.y))
            if first:
                path.nodes.append(GSNode(p0, type=GSLINE))
                path.nodes[-1].smooth = True
                first = False
            path.nodes.append(GSNode(c1, type=GSOFFCURVE))
            path.nodes.append(GSNode(c2, type=GSOFFCURVE))
            path.nodes.append(GSNode(p1, type=GSCURVE))
            path.nodes[-1].smooth = True

        # --- Attributs du path ---
        try:
            path.attributes["strokeWidth"] = self.strokeWidth
            path.attributes["lineCapStart"] = 0
            path.attributes["lineCapEnd"] = 0
        except:
            pass

        layer.paths.append(path)
        self.points = []
        self.lastPoint = None
        view.setNeedsDisplay_(True)

    @objc.python_method
    def background(self, layer):
        simplified_points = rdp_simplify(self.points, self.simplifyEpsilon)
        if len(simplified_points) < 2:
            return
        color = NSColor.blackColor().colorWithAlphaComponent_(0.5)
        color.set()
        bezier = NSBezierPath.bezierPath()
        bezier.setLineWidth_(self.strokeWidth)
        bezier.setLineCapStyle_(0)
        beziers = b_spline_to_bezier(simplified_points)
        if not beziers:
            return
        bezier.moveToPoint_(beziers[0][0])
        for p0, c1, c2, p1 in beziers:
            bezier.curveToPoint_controlPoint1_controlPoint2_(p1, c1, c2)
        bezier.stroke()

    @objc.python_method
    def __file__(self):
        return __file__
