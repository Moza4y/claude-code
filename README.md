# Smart Route - SOLIDWORKS add-in (beta)

A "Smart Route" tab appears next to the Routing commands in assemblies:

| Button | What it does |
|---|---|
| **Smart Auto Route** | Select the 2 end points of a route (in Edit Route), click. The engine plans a path around the REAL geometry (min bend radius, clearance, optional wanted length), adds the points to the route's 3D sketch and calls Routing's `CreateRouteThroughSketchEntities`. If that call fails, the points stay in the sketch so the normal Auto Route can be run through them. |
| **Scan Routes** | Reads every route sub-assembly (features, 3D sketch segments) and writes `%APPDATA%\SmartRoute\scan.txt`. Run this first to check the reading works on your files. |
| **Review Routes** | Re-plans each existing single-chain route with the others as rigid obstacles; lists the ones that can be shorter (>2 % and no bend problem). "Draw selected" puts the suggestion in as a 3D sketch for comparison. Nothing is changed automatically. |
| **Accuracy** | Grid cell 20 / 10 / 5 / 2.5 / 1.5 mm or custom. Higher = slower, more exact. |
| **Auto Watch** | ON: after the assembly changes (and 5 s of quiet) only the changed components are re-read and a review runs; you get a small list only if something better exists. |

Geometry is read once (and cached in `<assembly>_geom.cache`). New wires reuse it; only changed components are re-read; changing the accuracy re-processes the stored geometry.

## Build (Visual Studio 2019/2022, workload ".NET desktop development")
1. Open `SmartRoute.csproj`. If SOLIDWORKS is not in `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`, edit `<SWDir>` in the csproj.
2. The project references these from `<SWDir>\api\redist\`: `SolidWorks.Interop.sldworks`, `swconst`, `swpublished`, `SWRoutingLib`.
3. Build **Release | x64**. Output: `bin\Release\net48\SmartRoute.dll` and `auto_cable_route.py` next to it.

## Register (once, as Administrator, SOLIDWORKS closed)
```
"%windir%\Microsoft.NET\Framework64\v4.0.30319\regasm.exe" /codebase "<path>\SmartRoute.dll"
```
Unregister with the same command plus `/u`.

## Engine (Python, 64-bit, in PATH)
```
pip install pywin32 numpy scipy
```
Different Python? Put its full path in `%APPDATA%\SmartRoute\settings.json` -> `"PythonExe"`.

## Start
SOLIDWORKS -> Tools -> Add-Ins -> tick **Smart Route** (Routing add-in must be on too). Logs: `%APPDATA%\SmartRoute\smartroute.log`.

## Several SOLIDWORKS versions
Build against the OLDEST version you use (its `api\redist`); the same DLL normally loads in newer ones. If a version complains, build once per version with `/p:SWDir="<that install>"`.

## Notes
* Engine calls SOLIDWORKS from a separate process while SOLIDWORKS is idle, so requests are asynchronous: SOLIDWORKS stays usable while it plans; results appear in a message box.
* Wire diameter/bend radius for Review and for existing routes use the last values you entered in the dialog (the route's own cable properties are read only when a route segment is selected).
* Not verified on a live SOLIDWORKS session. Likely places to adjust if something misbehaves: coordinate frame of route sketches (`RoutingReader.ToAsm`), the feature type names that mark a route (see scan.txt), and the Routing status code returned by `CreateRouteThroughSketchEntities`.
