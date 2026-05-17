using System.Text.Json;
using System.Text.Json.Serialization;

namespace RhinoMCPPlugin;

public sealed class McpRequest
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("params")]
    public JsonElement Params { get; set; }

    [JsonPropertyName("secret")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Secret { get; set; }
}

public sealed class McpResponse
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = "ok";

    [JsonPropertyName("result")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public object? Result { get; set; }

    [JsonPropertyName("message")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Message { get; set; }

    public static McpResponse Ok(object? result = null) => new() { Status = "ok", Result = result };
    public static McpResponse Error(string message) => new() { Status = "error", Message = message };
}

public static class JsonHelpers
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
    };

    public static Dictionary<string, JsonElement> Dict(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Object)
            return new Dictionary<string, JsonElement>();
        return element.EnumerateObject().ToDictionary(p => p.Name, p => p.Value);
    }

    public static string? String(this Dictionary<string, JsonElement> data, string key, string? fallback = null)
        => data.TryGetValue(key, out var value) && value.ValueKind != JsonValueKind.Null ? value.GetString() : fallback;

    public static bool Bool(this Dictionary<string, JsonElement> data, string key, bool fallback = false)
        => data.TryGetValue(key, out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False ? value.GetBoolean() : fallback;

    public static int Int(this Dictionary<string, JsonElement> data, string key, int fallback = 0)
        => data.TryGetValue(key, out var value) && value.TryGetInt32(out var result) ? result : fallback;

    public static double Double(this Dictionary<string, JsonElement> data, string key, double fallback = 0)
        => data.TryGetValue(key, out var value) && value.TryGetDouble(out var result) ? result : fallback;

    public static List<string> StringList(this Dictionary<string, JsonElement> data, string key)
    {
        if (!data.TryGetValue(key, out var value) || value.ValueKind != JsonValueKind.Array)
            return new List<string>();
        return value.EnumerateArray().Select(v => v.GetString()).Where(v => !string.IsNullOrEmpty(v)).Cast<string>().ToList();
    }

    public static double[] DoubleArray(this Dictionary<string, JsonElement> data, string key, double[]? fallback = null)
    {
        if (!data.TryGetValue(key, out var value) || value.ValueKind != JsonValueKind.Array)
            return fallback ?? Array.Empty<double>();
        return value.EnumerateArray().Select(v => v.GetDouble()).ToArray();
    }
}
