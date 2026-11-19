# Changelog

## [0.3.0]
- Free-angle path pulling: routes are shorter (about 10 % in the test scene) than the old right-angle grid paths.
- Up to 3 alternatives per wire (*Shortest (free angles)*, *Neat (right angles)*, *Extra clearance*) with a rotatable 3D preview; nothing is created until you confirm.
- Independent verification (fine KD-tree over the real mesh): bend radius, clearance, collisions, other wires; runs on every alternative before creation and on the created route afterwards, plus SOLIDWORKS interference detection.
- Smooth (flexible) or orthogonal Routing mode depending on the chosen alternative.
- Minimum straight piece at both connectors (>= bend radius).
- GUI installer (Inno Setup, bundled engine: no Python needed), in-app update check from GitHub Releases, build/release scripts, CI, tests.

## [0.2.0]
- SOLIDWORKS add-in (Scan Routes, Smart Auto Route, Review Routes, Accuracy, Auto Watch) on top of the planning engine.
- Geometry cache with incremental updates, accuracy levels, coarse-to-fine search, wanted length, rigid earlier wires, better-order search.
