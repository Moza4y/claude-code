# Smart Route for SOLIDWORKS

A SOLIDWORKS add-in that plans cable routes around the **real geometry** of your assembly (not bounding boxes),
respects the cable's minimum bend radius, shows you **alternatives in a 3D preview**, builds the one you pick as a
real **SOLIDWORKS Routing** route, and **verifies** it afterwards. It installs like any program (GUI installer),
stays in SOLIDWORKS, and updates itself from GitHub Releases.

> **Status: beta.** The planning engine and the add-in logic are covered by automated tests, but the add-in has not
> been verified against a live SOLIDWORKS session yet. Start with **Scan Routes** and report what you get (see
> [Reporting problems](#reporting-problems)).

## Features (v0.3)

| Button (tab "Smart Route") | What it does |
|---|---|
| **Smart Auto Route** | Select the two end points of a route (in *Edit Route*), click. Plans around the real surfaces with clearance and min bend radius, optional *wanted length*. Opens a **preview** with up to 3 alternatives: *Shortest (free angles)*, *Neat (right angles)*, *Extra clearance* — each already checked for collisions, bend radius and clearance. Nothing is created until you press **Create route**. |
| after creating | The route is built through Routing's `CreateRouteThroughSketchEntities` (smooth/flexible or orthogonal), then **verified**: min bend radius, clearance to the real geometry, collisions, plus SOLIDWORKS' own interference detection. `Ctrl+Z` undoes the route. |
| **Scan Routes** | Reads every route in the assembly and writes `%APPDATA%\SmartRoute\scan.txt` (diagnostics). |
| **Review Routes** | Re-plans existing routes (others as rigid obstacles) and lists the ones that could be shorter. Nothing is changed automatically; "Draw selected" drops the suggestion in as a 3D sketch. |
| **Accuracy** | Grid cell 20 / 10 / 5 / 2.5 / 1.5 mm or custom. Higher = slower, more exact. |
| **Auto Watch** | After the assembly changes, re-reads only what changed and re-reviews. |
| **Updates** | Checks GitHub for a newer version; installs it when you close SOLIDWORKS. |

Geometry is read once and cached (`<assembly>_geom.cache`). New wires reuse it, only changed components are re-read,
changing the accuracy re-processes the stored data.

## Install (users)

1. Download **`SmartRoute-Setup-x.y.z.exe`** from the [Releases](../../releases) page.
2. Run it (needs admin rights), next → next → finish. Close SOLIDWORKS if Setup asks.
3. Start SOLIDWORKS → *Tools ▸ Add-Ins* → tick **Smart Route** (and **SOLIDWORKS Routing**). Open an assembly.

Nothing else to install (the planning engine is bundled). Updates: *Smart Route ▸ Updates*, or automatically
once a day; the new Setup runs when SOLIDWORKS is closed.

## Publish it on GitHub (maintainer, one time)

```powershell
# in this folder; needs git, GitHub CLI (gh auth login), Python 64-bit, Inno Setup 6.3+, .NET SDK / Visual Studio
.\tools\init-github.ps1 -Name smart-route     # creates a PUBLIC repo, pushes all commits and tags
.\tools\release.ps1 -Version 0.3.0            # builds the installer and publishes the GitHub Release
```

The repository must be **public**: installed copies look at `api.github.com/repos/<owner>/<repo>/releases/latest`
anonymously. `tools/build.ps1` fills in `<owner>/<repo>` from your `origin` remote.

### Every new version

Edit code → add a section to `CHANGELOG.md` → `.\tools\release.ps1 -Version 0.4.0`.
It stamps the version, builds, commits, tags `v0.4.0`, pushes and attaches `SmartRoute-Setup-0.4.0.exe`.
Everyone who has Smart Route installed is offered the update.

## Build from source

* `tools\build.ps1` — add-in DLL (against *your* SOLIDWORKS interop DLLs in `<SWDir>\api\redist`) + engine exe + installer.
  Build against the **oldest** SOLIDWORKS version you need; the same DLL normally loads in newer ones.
* Tests: `pip install -r requirements-dev.txt numpy scipy && pytest tests`.
* CI (GitHub Actions) runs the engine tests, compiles the add-in against stubs (syntax check only — the SOLIDWORKS
  DLLs can't be on GitHub), and packages the engine exe.

## Layout

```
src/SmartRoute/   C# add-in (command tab, routing reader, preview, verification, updater)
src/engine/       Python planning engine (grid + distance field + A*, coarse-to-fine, verification, JSON server)
installer/        Inno Setup script (GUI installer)
tools/            build.ps1, release.ps1, init-github.ps1, CI stubs
tests/            pytest suite for the engine
```

## How it works (short)

The add-in talks to a local engine process (`SmartRouteEngine.exe --server`, JSON lines). The engine reads component
meshes from SOLIDWORKS once, voxelises them for the chosen accuracy, searches a 3-D path (A*, coarse-to-fine for large
regions), pulls it straight where free space allows, rounds corners with the min bend radius, and re-checks the result
against a fine KD-tree of the real surfaces. Requests are asynchronous so SOLIDWORKS stays usable.

## Limits

* Resolution is the grid cell; features smaller than a cell can be missed — the verification step and SOLIDWORKS'
  interference detection are the safety net.
* Branched routes (harnesses) are not reviewed yet; wire diameter for Review/old routes is the last value you typed.
* Not a replacement for engineering judgement: always check the result.

## Reporting problems

Attach `%APPDATA%\SmartRoute\smartroute.log` and `scan.txt` and describe what you clicked.

License: MIT.
