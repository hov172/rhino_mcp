using System;
using System.IO;
using System.Reflection;
using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

public static class SlotAnnouncer
{
    private static string? _announcePath;

    public static void Announce(string host, int port)
    {
        try
        {
            var dir = SlotsDirectory();
            Directory.CreateDirectory(dir);
            var pid = Environment.ProcessId;
            _announcePath = Path.Combine(dir, $"{pid}.json");
            var version = PluginVersion();
            var payload = JsonSerializer.Serialize(new {
                pid,
                host = host == "0.0.0.0" ? "127.0.0.1" : host,
                port,
                version,
                rhino_version = RhinoApp.Version.ToString(),
                started_at = DateTime.UtcNow.ToString("o")
            });
            File.WriteAllText(_announcePath, payload);
        }
        catch (Exception ex)
        {
            RhinoApp.WriteLine($"[RhinoMCP] SlotAnnouncer failed to write slot file: {ex.Message}");
            _announcePath = null;
        }
    }

    public static void Withdraw()
    {
        if (_announcePath == null) return;
        try
        {
            if (File.Exists(_announcePath))
                File.Delete(_announcePath);
        }
        catch (Exception ex)
        {
            RhinoApp.WriteLine($"[RhinoMCP] SlotAnnouncer failed to delete slot file: {ex.Message}");
        }
        _announcePath = null;
    }

    private static string PluginVersion()
    {
        return typeof(SlotAnnouncer).Assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion
            ?? typeof(SlotAnnouncer).Assembly.GetName().Version?.ToString()
            ?? "unknown";
    }

    private static string SlotsDirectory()
    {
        var tmp = Path.GetTempPath();
        return Path.Combine(tmp, "rhino-mcp-slots");
    }
}
