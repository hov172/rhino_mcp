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

    public bool StartServer(int port = 1999)
    {
        Server ??= new RhinoMcpServer(port);
        if (Server.IsRunning)
            return true;
        Server.Start();
        RhinoApp.WriteLine($"Rhino MCP server started on 127.0.0.1:{port}");
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
