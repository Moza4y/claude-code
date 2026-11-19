using System;
namespace SolidWorks.Interop.swpublished { public interface ISwAddin { bool ConnectToSW(object ThisSW, int Cookie); bool DisconnectFromSW(); } }
namespace SolidWorks.Interop.swconst {
  [Flags] public enum swCommandItemType_e { swMenuItem = 1, swToolbarItem = 2 }
  public enum swDocumentTypes_e { swDocASSEMBLY = 2 }
  public enum swCommandTabButtonTextDisplay_e { swCommandTabButton_TextBelow = 1 }
}
namespace SolidWorks.Interop.SWRoutingLib {
  public enum swAutoRouteConversionMode_e { swOrthogonalAutoRouteMode = 2 }
  public enum swAutoRouteAutoTangencyMode_e { swAutoTangencyMode_OFF = 0, swAutoTangencyMode_ON = 1 }
  public enum swAutoRouteSketchEntitiesTypes_e { swAutoRouteSketchEntitiesType_Point = 0 }
}
namespace SolidWorks.Interop.sldworks {
  public interface ISldWorks { bool SetAddinCallbackInfo2(int InModule, object Client, int AddinID); ICommandManager GetCommandManager(int Cookie); }
  public interface ICommandGroup { object IconList { get; set; } object MainIconList { get; set; } bool HasToolbar { get; set; } bool HasMenu { get; set; }
    int AddCommandItem2(string Name, int Position, string HintString, string ToolTip, int ImageListIndex, string CallbackFunction, string UpdateCallbackFunction, int UserID, int MenuTBOption);
    bool Activate(); int get_CommandID(int Index); }
  public class CommandTabBox { public bool AddCommands(object CommandIDs, object TextTypes) { return true; } }
  public class CommandTab { public CommandTabBox AddCommandTabBox() { return new CommandTabBox(); } }
  public interface ICommandManager {
    ICommandGroup CreateCommandGroup2(int UserID, string Title, string ToolTip, string Hint, int Position, bool IgnorePreviousVersion, ref int Errors);
    CommandTab GetCommandTab(int DocType, string Title); CommandTab AddCommandTab(int DocType, string Title);
    bool RemoveCommandTab(CommandTab t); bool RemoveCommandGroup2(int UserID, bool RuntimeOnly); }
}
