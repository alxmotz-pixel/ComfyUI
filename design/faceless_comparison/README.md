# Design-Set „Vergleiche“ (Faceless TikTok)

Konsistentes Asset-Set als Grundlage für Image-to-Video. Alle Dateien werden von `generate.py` erzeugt
(SVG = verlustfrei skalierbar, PNG = sofort nutzbar). Gesamtübersicht: `uebersicht.png`.

```
python generate.py --chrome /pfad/zu/headless_shell   # SVG + PNG neu erzeugen
```

## Style-Bible

| Regel | Wert |
|---|---|
| Stil | Stylisierter Soft-3D-Cartoon, runde Formen, klare Silhouetten |
| Licht | Ein Key-Light von oben links, weicher Bodenschatten unten (bei jedem Asset gleich) |
| Kontur | `#2B2F36`, 8 px bei 1024/1080 px Breite, abgerundete Ecken |
| Seite A | Blau `#2F7BFF` · hell `#8DB8FF` · dunkel `#1A4FBF` · tief `#173E8C` |
| Seite B | Rot `#EE3340` · hell `#FF8F96` · dunkel `#B41E2A` · tief `#7C121B` |
| Neutral | `#FFFFFF` `#F2F3F5` `#E6E8EC` `#D9DCE1` `#9AA1AB` `#4A505A` |
| Text | Keiner, außer „VS“ |

## Figuren (feste Merkmale, nie ändern)

- **Pip, Erzähler** (`1_maskottchen`): eiförmiger, weiß-grauer Körper; große runde schwarze Brille (Markenzeichen);
  eine dunkelgraue Haarlocke oben; Fliege links blau / rechts rot; kurze graue Arme, graue Füße, rosa Wangen.
  Frontal und seitlich.
- **Figur A, blau** (`2_figuren/figur_a_*`): groß und schlank, kapselförmiger Körper; dunkelblaue Tolle nach rechts;
  weißer Kragen und dunkelblaue Krawatte; lange dünne Arme und Beine; graue Schuhe. Typ: Angeber.
- **Figur B, rot** (`2_figuren/figur_b_*`): klein und kugelrund; dunkelrote Kappe mit Schirm nach rechts und weißem Knopf;
  große, weit auseinanderstehende Augen; kurze kräftige Arme und Beine; graue Schuhe. Typ: Laut und direkt.
- Emotionen je Figur: `neutral`, `stolz` (Hände in den Hüften), `ueberrascht` (Arme hoch), `genervt` (Arme steif).
- Jede Datei gibt es mit neutralem Hintergrund `#E6E8EC` und als `_freigestellt` (transparent).
  Die Arme sind frei, das Gesicht ist immer sichtbar.

## Dateien

| Ordner | Inhalt | Größe (PNG) |
|---|---|---|
| `1_maskottchen` | Pip frontal und seitlich | 2048×3072 |
| `2_figuren` | A und B, je 4 Emotionen | 2048×3072 |
| `3_hintergruende` | geteilte Bühne, Studio mit Podest, Skyline am Tag, Wohnzimmer, weißes Raster; ohne Personen, Mitte frei | 1080×1920 (9:16) |
| `4_requisiten` | Geldbündel, Waage, Pokal, Weltkugel, Stoppuhr, Haus, Auto, Lupe; je `_blau` und `_rot`, freigestellt | 2048×2048 |
| `5_elemente` | VS, Pfeile hoch/runter, Haken, Kreuz (je blau/rot), leere Balkendiagramme (A vs. B, Ranking 5) | 2048×2048 |

## Prompts für den echten 3D-Look

Die PNGs sind die verbindliche Referenz für Form und Farbe. Für den Pixar-ähnlichen Render das jeweilige PNG als
Referenzbild nutzen (img2img mit Denoise 0.45–0.6, IP-Adapter oder ControlNet Canny/Lineart) und Folgendes voranstellen:

**Basis (immer):**
`stylized 3D cartoon render, soft rounded shapes, clean silhouette, smooth matte plastic and soft clay materials, single soft key light from top left, soft contact shadow, subtle rim light, high detail, sharp, palette of cobalt blue #2F7BFF, bright red #EE3340, neutral greys and white`

**Negativ (immer):**
`text, letters, numbers, watermark, logo, signature, extra limbs, extra fingers, realistic human skin, photo, noise, blurry, cropped body, hands covering face`

| Asset | Zusatz-Prompt |
|---|---|
| Pip | `cute egg-shaped white-grey mascot, oversized round black glasses, big friendly eyes, single dark grey hair curl on top, small bow tie half blue half red, short grey arms, full body, neutral standing pose, plain light grey background` |
| Figur A | `tall slim capsule-shaped blue character, dark blue swoosh quiff to the right, white collar, dark blue tie, long thin arms and legs, grey shoes, full body, {emotion}, plain light grey background` |
| Figur B | `short round ball-shaped red character, dark red cap with brim to the right and white button, wide-set big eyes, short chunky arms and legs, grey shoes, full body, {emotion}, plain light grey background` |
| Emotionen | stolz: `smug proud smile, half-closed eyes, hands on hips` · überrascht: `wide eyes, open O mouth, arms raised` · genervt: `annoyed half-lidded eyes, angled brows, flat mouth, stiff arms` |
| Hintergründe | `empty scene, no people, clear empty center for characters, vertical 9:16` + Szene aus der Datei |
| Requisiten | `single isolated {objekt}, {blue/red} variant, centered, transparent or plain background` |

Für Image-to-Video: freigestellte Figur auf einen Hintergrund setzen, dann animieren.
Bewegungs-Prompts kurz halten (`character waves, slight bounce, blinks`) und die Kamera ruhig lassen,
damit Proportionen und Farben stabil bleiben.

## Themen-Video (10 s)

```
python demo_clip.py themen/arm_vs_reich.json   # -> demo/arm_vs_reich.mp4
```

Pro Thema eine JSON-Datei in `themen/`: `a` (blaue Seite), `b` (rote Seite), `fokus` (`a` oder `b`, die Seite, um die es geht),
`kostuem_a`/`kostuem_b` (optional, Overlays aus `6_kostueme`, z. B. `reich_figur_a`, `arm_figur_b`),
`plus` und `minus` (je 3 Punkte `{"text", "bilder": [Requisiten/Elemente], "emotion"}`), `frage` (Schlussfrage).
Ablauf: Intro mit VS und Zoom auf die Fokus-Seite (1,8 s), 3× besser im Vollbild (3,6 s), 3× schlechter (3,6 s), Frage (1 s).
Am Ende pfeift Pip als Schiedsrichter (`6_kostueme/pip_schiedsrichter*`, Pfiff als Ton im Video) und stellt die `frage`.
Bei Marken nur die Namen als Text und eigene Anspielungen statt Logos verwenden (Flügel für Nike, Bergspitze für Adidas
in `sport_figur_*`), keine Nachbauten von Swoosh oder drei Streifen.
