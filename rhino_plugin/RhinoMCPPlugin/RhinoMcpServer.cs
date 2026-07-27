using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
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
    public IPAddress BindAddress { get; }
    public bool IsRunning => _listener is not null;

    /// <param name="port">TCP port to listen on.</param>
    /// <param name="bindHost">
    ///   Host/IP string to bind to.  Defaults to the value of the
    ///   <c>RHINO_MCP_BIND_HOST</c> environment variable, or <c>127.0.0.1</c>
    ///   (loopback-only) when the variable is absent.
    ///   Pass <c>"0.0.0.0"</c> to accept connections from any network interface
    ///   (required for remote AI clients on a different machine).
    /// </param>
    public RhinoMcpServer(int port, string? bindHost = null)
    {
        Port = port;
        var host = bindHost ?? Environment.GetEnvironmentVariable("RHINO_MCP_BIND_HOST");
        BindAddress = ParseAddress(host);
    }

    /// <summary>
    /// Parse a host string into an <see cref="IPAddress"/>.
    /// Falls back to loopback for any unrecognised value.
    /// </summary>
    private static IPAddress ParseAddress(string? host) => host?.Trim() switch
    {
        null or "" or "localhost" or "127.0.0.1" => IPAddress.Loopback,
        "0.0.0.0"                                => IPAddress.Any,
        "::"                                     => IPAddress.IPv6Any,
        var s when IPAddress.TryParse(s, out var addr) => addr,
        _                                        => IPAddress.Loopback,
    };

    public void Start()
    {
        if (_listener is not null)
            return;
        if (!IPAddress.IsLoopback(BindAddress) &&
            string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RHINO_MCP_PLUGIN_SECRET")))
        {
            throw new InvalidOperationException(
                $"Refusing to listen on non-loopback address {BindAddress} without " +
                "RHINO_MCP_PLUGIN_SECRET set — that would expose unauthenticated code " +
                "execution to the network. Set RHINO_MCP_PLUGIN_SECRET on both the Rhino " +
                "machine and the MCP server machine, or unset RHINO_MCP_BIND_HOST to " +
                "listen on loopback only.");
        }
        var cts = new CancellationTokenSource();
        var listener = new TcpListener(BindAddress, Port);
        try
        {
            listener.Start();
        }
        catch
        {
            // Leave _listener null so IsRunning stays false and a later
            // MCPStart can retry instead of claiming "already listening".
            cts.Dispose();
            throw;
        }
        _cts = cts;
        _listener = listener;
        SlotAnnouncer.Announce(BindAddress.ToString(), Port);
        _acceptTask = Task.Run(() => AcceptLoop(cts.Token));
    }

    public void Stop()
    {
        _cts?.Cancel();
        _listener?.Stop();
        _listener = null;
        _cts = null;
        SlotAnnouncer.Withdraw();
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
                var client = await listener.AcceptTcpClientAsync(token).ConfigureAwait(false);
                // Fire-and-forget: handle each connection independently so new
                // connections are accepted without waiting for the current one to close.
                _ = Task.Run(() => HandleClient(client, token), token);
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
        using (client)
        {
            using var stream = client.GetStream();
            var buffer = new byte[8192];
            const int maxBytes = 10 * 1024 * 1024;

            // Keep-alive: process multiple requests on the same connection until
            // the client closes it or the server is cancelled.
            while (!token.IsCancellationRequested)
            {
                // Accumulate raw bytes and decode the whole buffer each pass —
                // decoding per-chunk corrupts multi-byte UTF-8 characters that
                // straddle a read boundary.
                using var accumulated = new System.IO.MemoryStream();

                // Read one complete JSON object.
                while (true)
                {
                    int read;
                    try
                    {
                        read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), token).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) { return; }
                    catch (Exception) { return; } // connection reset / closed

                    if (read <= 0) return; // client closed connection cleanly

                    accumulated.Write(buffer, 0, read);
                    if (accumulated.Length > maxBytes)
                    {
                        RhinoApp.WriteLine("Rhino MCP: request exceeded 10 MB limit — closing connection.");
                        return;
                    }

                    var text = Encoding.UTF8.GetString(accumulated.GetBuffer(), 0, (int)accumulated.Length).Trim();
                    if (text.Length == 0) continue;
                    try
                    {
                        using var _ = JsonDocument.Parse(text);
                        break; // valid complete JSON object
                    }
                    catch (JsonException)
                    {
                        // incomplete, keep reading
                    }
                }

                McpResponse response;
                try
                {
                    var text = Encoding.UTF8.GetString(accumulated.GetBuffer(), 0, (int)accumulated.Length).Trim();
                    var request = JsonSerializer.Deserialize<McpRequest>(text, JsonHelpers.Options);
                    if (request is null || string.IsNullOrWhiteSpace(request.Type))
                    {
                        response = McpResponse.Error("Invalid MCP request.");
                    }
                    else
                    {
                        // PSK check — only enforced when RHINO_MCP_PLUGIN_SECRET is configured.
                        var configuredSecret = Environment.GetEnvironmentVariable("RHINO_MCP_PLUGIN_SECRET");
                        if (configuredSecret is not null)
                        {
                            var provided = request.Secret ?? "";
                            if (!SecretEquals(configuredSecret, provided))
                            {
                                response = McpResponse.Error("Unauthorized: invalid or missing plugin secret.");
                                var errJson = JsonSerializer.Serialize(response, JsonHelpers.Options);
                                var errBytes = Encoding.UTF8.GetBytes(errJson);
                                await stream.WriteAsync(errBytes.AsMemory(0, errBytes.Length), token).ConfigureAwait(false);
                                return; // close connection on auth failure
                            }
                        }
                        response = InvokeOnRhinoThread(() => CommandDispatcher.Dispatch(request));
                    }
                }
                catch (Exception ex)
                {
                    response = McpResponse.Error(ex.Message);
                }

                try
                {
                    var json = JsonSerializer.Serialize(response, JsonHelpers.Options);
                    var bytes = Encoding.UTF8.GetBytes(json);
                    await stream.WriteAsync(bytes.AsMemory(0, bytes.Length), token).ConfigureAwait(false);
                }
                catch (Exception) { return; } // client disconnected before response was written
            }
        }
    }

    /// <summary>
    /// Constant-time secret comparison — hashes both values first to normalise
    /// length, then uses FixedTimeEquals to prevent timing attacks.
    /// </summary>
    private static bool SecretEquals(string configured, string provided)
    {
        var a = SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(configured));
        var b = SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(provided));
        return CryptographicOperations.FixedTimeEquals(a, b);
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
