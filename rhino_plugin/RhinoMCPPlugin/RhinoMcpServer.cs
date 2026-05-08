using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

public sealed class RhinoMcpServer
{
    private TcpListener? _listener;
    private CancellationTokenSource? _cts;
    private Task? _acceptTask;

    public int Port { get; }
    public bool IsRunning => _listener is not null;

    public RhinoMcpServer(int port)
    {
        Port = port;
    }

    public void Start()
    {
        if (_listener is not null)
            return;
        _cts = new CancellationTokenSource();
        _listener = new TcpListener(IPAddress.Loopback, Port);
        _listener.Start();
        _acceptTask = Task.Run(() => AcceptLoop(_cts.Token));
    }

    public void Stop()
    {
        _cts?.Cancel();
        _listener?.Stop();
        _listener = null;
        _cts = null;
    }

    private async Task AcceptLoop(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            try
            {
                var listener = _listener;
                if (listener is null)
                    return;
                using var client = await listener.AcceptTcpClientAsync(token).ConfigureAwait(false);
                await HandleClient(client, token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }
            catch (Exception ex)
            {
                RhinoApp.WriteLine($"Rhino MCP server error: {ex.Message}");
            }
        }
    }

    private static async Task HandleClient(TcpClient client, CancellationToken token)
    {
        client.ReceiveTimeout = 30_000;
        using var stream = client.GetStream();
        var accumulated = new StringBuilder();
        var buffer = new byte[8192];
        const int maxBytes = 10 * 1024 * 1024;

        while (true)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), token).ConfigureAwait(false);
            if (read <= 0) break;
            accumulated.Append(Encoding.UTF8.GetString(buffer, 0, read));
            if (accumulated.Length > maxBytes)
                throw new InvalidOperationException("MCP request exceeded 10 MB limit.");
            // Check if we have a complete JSON object
            var text = accumulated.ToString().Trim();
            if (text.Length == 0) continue;
            try
            {
                using var _ = JsonDocument.Parse(text);
                break; // valid JSON, done reading
            }
            catch (JsonException)
            {
                // incomplete, keep reading
            }
        }

        McpResponse response;
        try
        {
            var text = accumulated.ToString().Trim();
            var request = JsonSerializer.Deserialize<McpRequest>(text, JsonHelpers.Options);
            if (request is null || string.IsNullOrWhiteSpace(request.Type))
                response = McpResponse.Error("Invalid MCP request.");
            else
                response = InvokeOnRhinoThread(() => CommandDispatcher.Dispatch(request));
        }
        catch (Exception ex)
        {
            response = McpResponse.Error(ex.Message);
        }

        var json = JsonSerializer.Serialize(response, JsonHelpers.Options);
        var bytes = Encoding.UTF8.GetBytes(json);
        await stream.WriteAsync(bytes.AsMemory(0, bytes.Length), token).ConfigureAwait(false);
    }

    private static T InvokeOnRhinoThread<T>(Func<T> func)
    {
        var done = new ManualResetEventSlim(false);
        T? result = default;
        Exception? error = null;
        RhinoApp.InvokeOnUiThread((Action)(() =>
        {
            try
            {
                result = func();
            }
            catch (Exception ex)
            {
                error = ex;
            }
            finally
            {
                done.Set();
            }
        }));
        done.Wait();
        if (error is not null)
            throw error;
        return result!;
    }
}
