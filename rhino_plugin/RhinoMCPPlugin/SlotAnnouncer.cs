using System;
using System.IO;
using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

public static class SlotAnnouncer
{
    private static string? _announcePath;

    public static void Announce(string host, int port, string version)
    {
        var dir = SlotsDirectory();
        Directory.CreateDirectory(dir);
        var pid = Environment.ProcessId;
        _announcePath = Path.Combine(dir, $"{pid}.json");
        var payload = JsonSerializer.Serialize(new {
            pid,
            host,
            port,
            version,
            rhino_version = RhinoApp.Version.ToString(),
            started_at = DateTime.UtcNow.ToString("o")
        });
        File.WriteAllText(_announcePath, payload);
    }

    public static void Withdraw()
    {
        if (_announcePath != null && File.Exists(_announcePath))
            File.Delete(_announcePath);
        _announcePath = null;
    }

    private static string SlotsDirectory()
    {
        var tmp = Path.GetTempPath();
        return Path.Combine(tmp, "rhino-mcp-slots");
    }
}
