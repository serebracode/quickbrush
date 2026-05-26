# QuickBrush Glyphs Tool

Custom Glyphs drawing tool with rectangular brush behavior.

## Main controls
- **Brush Angle**: rotates the rectangular touch footprint.
- **Brush Thickness**: controls the rectangle width.
- **Curve Smoothness**: applies moving-average smoothing to drag points before generating the contour.

## Assets
- `toolbarIcon.svg` for the Glyphs toolbar button.
- `preview.svg` for the inspector panel illustration (HO line glyphs with brush application preview).

## Bundle integrity checklist
If Glyphs says that the executable cannot be located, verify the bundle:

```bash
./scripts/verify_bundle.sh QuickBrush.glyphsTool
```

Expected files:
- `Contents/Info.plist`
- `Contents/MacOS/plugin` (must be executable, `chmod +x`)
- `Contents/Resources/plugin.py`
- `Contents/Resources/toolbarIcon.svg`
- `Contents/Resources/preview.svg`
