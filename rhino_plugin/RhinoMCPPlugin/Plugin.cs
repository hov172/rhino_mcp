using Rhino;
using Rhino.PlugIns;

namespace RhinoMCPPlugin;

public sealed class RhinoMcpPlugin : PlugIn
{
    public static RhinoMcpPlugin Instance { get; private set; } = null!;
    public RhinoMcpServer? Server { get; private set; }

    public RhinoMcpPlugin()
    {
        Instance = this;
    }

    public bool StartServer(int port = 1999, string? bindHost = null)
    {
        if (Server is null)
        {
            // bindHost argument takes priority; fall back to env var (handled inside constructor).
            Server = new RhinoMcpServer(port, bindHost);
        }
        if (Server.IsRunning)
            return true;
        Server.Start();
        RhinoApp.WriteLine($"Rhino MCP server started on {Server.BindAddress}:{Server.Port}");
        return true;
    }

    public void StopServer()
    {
        Server?.Stop();
        Server = null;
        RhinoApp.WriteLine("Rhino MCP server stopped.");
    }

    protected override LoadReturnCode OnLoad(ref string errorMessage)
    {
        RhinoApp.WriteLine("Rhino MCP plug-in loaded. Run MCPStart to start the socket server.");
        return LoadReturnCode.Success;
    }

    protected override void OnShutdown()
    {
        StopServer();
        base.OnShutdown();
    }
}
