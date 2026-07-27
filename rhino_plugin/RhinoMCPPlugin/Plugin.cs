using Rhino;
using Rhino.PlugIns;

namespace RhinoMCPPlugin;

public sealed class RhinoMcpPlugin : PlugIn
{
    public static RhinoMcpPlugin Instance { get; private set; } = null!;
    public RhinoMcpServer? Server { get; private set; }

    // Load at Rhino startup so OnLoad fires immediately and the TCP server is ready
    // before the user runs any commands. Without this, Rhino defaults to WhenNeeded
    // and the plugin only loads (and the socket only opens) on the first MCPStart call.
    public override PlugInLoadTime LoadTime => PlugInLoadTime.AtStartup;

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
        {
            RhinoApp.WriteLine($"Rhino MCP already listening on {Server.BindAddress}:{Server.Port}");
            return true;
        }
        try
        {
            Server.Start();
        }
        catch (InvalidOperationException ex)
        {
            // e.g. non-loopback bind refused without RHINO_MCP_PLUGIN_SECRET.
            RhinoApp.WriteLine($"⚠ Rhino MCP: {ex.Message}");
            return false;
        }
        RhinoApp.WriteLine($"Rhino MCP listening on {Server.BindAddress}:{Server.Port}");
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
        try
        {
            StartServer();
        }
        catch (Exception ex)
        {
            // Non-fatal: log and let Rhino finish loading. User can retry with MCPStart.
            RhinoApp.WriteLine($"Rhino MCP: auto-start failed ({ex.Message}). Run MCPStart manually.");
        }
        return LoadReturnCode.Success;
    }

    protected override void OnShutdown()
    {
        StopServer();
        base.OnShutdown();
    }
}
