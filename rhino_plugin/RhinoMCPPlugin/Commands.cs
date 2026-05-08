using Rhino;
using Rhino.Commands;

namespace RhinoMCPPlugin;

public sealed class MCPStartCommand : Command
{
    public override string EnglishName => "MCPStart";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        RhinoMcpPlugin.Instance.StartServer();
        return Result.Success;
    }
}

public sealed class MCPStopCommand : Command
{
    public override string EnglishName => "MCPStop";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        RhinoMcpPlugin.Instance.StopServer();
        return Result.Success;
    }
}

public sealed class MCPStatusCommand : Command
{
    public override string EnglishName => "MCPStatus";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var server = RhinoMcpPlugin.Instance.Server;
        if (server?.IsRunning == true)
            RhinoApp.WriteLine($"Rhino MCP server running on {server.BindAddress}:{server.Port}");
        else
            RhinoApp.WriteLine("Rhino MCP server is stopped.");
        return Result.Success;
    }
}
